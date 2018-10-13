#!/usr/bin/env python3

import sys
import os
from configparser import ConfigParser, ExtendedInterpolation, DuplicateSectionError
from re import compile
from glob import iglob
import subprocess
import logging

# get a named logger
logger = lambda s: logging.getLogger(s)

# return a config section as dict for **kwargs
sectdict = lambda s: dict(s.items())

# configuration element
class Configuration(object):
    # initialize config parser with ${var} interpolation and loose section headers
    def __init__(self, file):

        self.cfg = ConfigParser(interpolation=ExtendedInterpolation())
        self.cfg.SECTCRE = compile(r"\[ *(?P<header>[^]]+?) *\]")
        self.cfg.read_file(file)

        
        self.kernelg = self.cfg.get(self.GLOBAL, "kernelglob", fallback="/boot/vmlinuz-*")
        self.kernelr = compile(self.cfg.get(self.GLOBAL, "kernelrexp", fallback="/?boot/vmlinuz-([^/]+)$"))
        self.efistub = self.cfg.get(self.GLOBAL, "efistub", fallback="/usr/lib/systemd/boot/efi/linuxx64.efi.stub")
        self.key = self.cfg.get(self.GLOBAL, "key", fallback="/etc/efikeys/DB.key")
        self.cert = self.cfg.get(self.GLOBAL, "cert", fallback="/etc/efikeys/DB.crt")

    # return globals as dict
    GLOBAL = "global"
    def globals(self):
        return {'efistub': self.efistub, 'key': self.key, 'cert': self.cert}

    # add sections by globbing for kernels on filesystem
    def addglob(self):
        for name in (self.kernelr.sub(r"\1", k) for k in iglob(self.kernelg)):
            self.addsection(name)

    # ensures that a named section is present
    def addsection(self, name):
        try:
            self.cfg.add_section(name)
            logger(name).debug("kernel added")
        except DuplicateSectionError:
            pass
        return self.cfg[name]

    def kernels(self, targets=None):
        
        kernels = []
        sections = (s for s in (self.cfg.sections() if targets is None else targets) if s != self.GLOBAL)
        
        for name in sections:
            section = self.addsection(name)
            log = logger(name)

            if "ignore" in section and section.getboolean("ignore"):
                log.debug("ignored")
                continue

            if not "name" in section:
                section["name"] = name.strip()

            try:
                k = Kernel(**self.globals(), **sectdict(section))
                kernels.append(k)
            except TypeError as e:
                log.error(f"missing attribute: {e}")
                continue

        if len(kernels) == 0:
            logger("*").warning("empty kernels list")
            exit(0)

        return kernels


# things that call external binaries or scripts
class Run(object):

    # combine efistub, kernel and initramfs into a single binary
    @staticmethod
    def objcopy(efistub, kernel, initramfs, cmdline, output):
        script = "./efistub-combine.sh"
        cmd = [script, "-v", "-e", efistub, "-k", kernel, "-c", cmdline, "-o", output]
        for image in initramfs:
            cmd.extend(["-i", image])
        return subprocess.run(cmd, check=True)

    # create a signature on the efistub binary
    @staticmethod
    def sbsign(key, cert, binary):
        cmd = ["sbsign", "--key", key, "--cert", cert, "--output", binary, binary]
        return subprocess.run(cmd, check=True)


# a single kernel signing configuration with its processing steps
class Kernel(object):
    def __init__(self, name, efistub, kernel, initramfs, cmdline, key, cert, output, **rest):
        self.name = name
        self.log = logger(self.name)
        self.efistub = efistub
        self.kernel = kernel
        self.initramfs = initramfs if type(initramfs) == list else initramfs.strip().splitlines()
        self.cmdline = cmdline
        self.key = key
        self.cert = cert
        self.output = output

        # skip removed kernels
        if not os.path.isfile(self.kernel):
            raise TypeError('kernel removed')
        # all other files should exist
        for f in [self.efistub] + self.initramfs + [self.key, self.cert]:
            if not os.path.isfile(f):
                raise FileNotFoundError(self.name + ': ' + f)

    def print(self):
        # print info about this kernel
        self.log.info("processing kernel")
        for k in ("efistub", "kernel", "initramfs", "cmdline", "output"):
            self.log.debug(f"{k}: {getattr(self, k)}")
        return self

    def backup(self, suffix):
        import shutil
        import os

        if os.path.isfile(self.output):
            backup = self.output + suffix
            shutil.copy2(self.output, backup)
            self.log.debug("backed up old kernel to " + backup)
        return self

    def sign(self):
        Run.objcopy(self.efistub, self.kernel, self.initramfs, self.cmdline, self.output)
        Run.sbsign(self.key, self.cert, self.output)
        return self


class Commandline(object):
    def __init__(self):
        from argparse import ArgumentParser, FileType

        parser = ArgumentParser(description="Bundle and sign kernels for secureboot systems.")
        commands = parser.add_subparsers(required=True, metavar="command", help="mode of operation")
        defaults = {"config": "secureboot.ini", "logging": "INFO", "no_glob": False}

        # --- automatic mode ---
        auto = commands.add_parser("auto", help="automatic, from configuration file")
        auto.add_argument("-c", dest="config", help="configuration file", type=FileType("r"))
        auto.add_argument("--no-glob", help="do not automatically add kernels", action="store_true")
        auto.add_argument("--logging", help="set logging level", choices=["INFO", "DEBUG", "WARN"])
        auto.set_defaults(**defaults, func=self.auto)

        # --- hook mode ---
        hook = commands.add_parser("hook", help="hook mode for pacman")
        hook.add_argument("-c", dest="config", help="configuration file", type=FileType("r"))
        hook.add_argument("--logging", help="set logging level", choices=["INFO", "DEBUG", "WARN"])
        hook.set_defaults(**defaults, func=self.hook)

        # --- manual mode ---
        manual = commands.add_parser("manual", help="manual, all args provided")
        manual.add_argument("-s", dest="script", help="efistub-combine script", required=True)
        manual.add_argument("-e", dest="efistub", help="systemd-boot efistub", required=True)
        manual.add_argument("-k", dest="kernel", help="kernel binary", required=True)
        manual.add_argument("-i", dest="initramfs", help="initramfs list", nargs="+", metavar="IMG")
        manual.add_argument("-c", dest="cmdline", help="kernel cmdline", required=True)
        manual.add_argument("-o", dest="output", help="signed kernel output", required=True)
        manual.add_argument("--key", help="signing key", required=True)
        manual.add_argument("--cert", help="signing certificate", required=True)
        manual.add_argument("-b", dest="backup", help="backup suffix")
        manual.add_argument("--logging", help="set logging level", choices=["INFO", "DEBUG", "WARN"])
        manual.set_defaults(**defaults, func=self.manual)

        args = parser.parse_args()
        loglevel = getattr(logging, args.logging or "INFO")
        logging.basicConfig(
            format="\033[1m%(levelname)s \033[32m[%(name)s]\033[0m %(message)s", level=loglevel
        )
        args.func(args)

    def auto(self, args):

        conf = Configuration(args.config)
        if not args.no_glob:
            conf.addglob()

        for k in conf.kernels():
            k.print().backup(".bak").sign()

    def hook(self, args):

        conf = Configuration(args.config)

        targets, force = [], False
        for line in (line.strip() for _, line in enumerate(sys.stdin)):
            match = conf.kernelr.match(line)
            if match is None:
                force = True
                continue
            name = match.expand(r"\1")
            conf.addsection(name)
            targets.append(name)

        if force:
            logger('*').info('forced rebuild')
            conf.addglob()
            targets = None

        for k in conf.kernels(targets):
            k.print().backup(".bak").sign()

    def manual(self, args):
        # print(dict(k.items()))
        #     Kernel.all_in_one(combine, ".bak", **dict(k.items()))
        # do_sign_kernel(
        #     "manual",
        #     args.script,
        #     args.efistub,
        #     args.kernel,
        #     args.initramfs,
        #     args.cmdline,
        #     args.key,
        #     args.cert,
        #     args.output,
        #     backup=args.backup,
        # )
        pass


# ------- let's go -------
if __name__ == "__main__":
    Commandline()

