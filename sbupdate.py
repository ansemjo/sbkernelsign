#!/usr/bin/env python3

import sys
import os
import subprocess
import logging

# initialize logging
logging.basicConfig(format="%(levelname).4s: [%(name)s] %(message)s", level=logging.DEBUG)
log = logging.getLogger("sbkernelsign")
logger = logging.getLogger

# configuration variable names
GLOBAL = "global"
NAME = "name"
IGNORE = "ignore"
EFISTUB = "efistub"
SCRIPT = "combine"
KEY = "key"
CERT = "crt"
KERNEL = "kernel"
INITRAMFS = "initramfs"
CMDLINE = "cmdline"
OUTPUT = "output"

# initialize config parser with ${var} interpolation and loose section headers
def get_config(inifile):
    from configparser import ConfigParser, ExtendedInterpolation
    import re

    cp = ConfigParser(interpolation=ExtendedInterpolation())
    cp.SECTCRE = re.compile(r"\[ *(?P<header>[^]]+?) *\]")
    cp.read_file(inifile)
    return cp


# check config sections for possible kernels
def get_kernels(config, kernelglob=None):
    import glob

    # add missing sections by globbing
    if kernelglob is not None:
        for kernel in (k[len(kernelglob) - 1 :] for k in glob.iglob(kernelglob)):
            if not config.has_section(kernel):
                config.add_section(kernel)
                logger(kernel).debug("added automatically")

    kernels = []
    for s in [s for s in config.sections() if s != GLOBAL]:
        section = config[s]
        log = logger(s)

        # skip when IGNORE is truthy
        if IGNORE in section and section.getboolean(IGNORE):
            log.debug("ignored")
            continue

        # add name from section name by default
        if not NAME in section:
            section[NAME] = s.strip()

        # check if everything that is required is present, otherwise ignore
        try:
            for r in [EFISTUB, KEY, CERT, KERNEL, INITRAMFS, CMDLINE, OUTPUT]:
                if not r in section:
                    log.warning(f"ignored due to missing option '{r}'")
                    raise ValueError()
        except ValueError:
            continue

        # all checks passed, append to list
        kernels.append(section)

    # error when no kernels are found / left
    if len(kernels) == 0:
        log.error("no kernels configured")
        exit(1)

    return kernels


# combine efistub, kernel and initramfs into a single binary
def objcopy(script, efistub, kernel, initramfs, cmdline, output):
    cmd = [script, "-v", "-e", efistub, "-k", kernel, "-c", cmdline, "-o", output]
    for image in initramfs:
        cmd.extend(["-i", image])
    return subprocess.run(cmd, check=True)


# create a signature on the efistub binary
def sbsign(key, cert, binary):
    cmd = ["sbsign", "--key", key, "--cert", cert, "--output", binary, binary]
    return subprocess.run(cmd, check=True)


def do_sign_kernel(name, combine, efistub, kernel, initramfs, cmdline, key, cert, output, backup=None):
    log = logger(name)

    # print info about this kernel
    log.info("processing kernel")
    for m in (
        f"efistub: {efistub}",
        f"kernel: {kernel}",
        f"initramfs: {initramfs}",
        f"cmdline: {cmdline}",
        f"output: {output}",
    ):
        log.debug(m)

    # create backup copy
    if backup is not None:
        import shutil

        if os.path.isfile(output):
            backup = output + backup
            shutil.copy2(output, backup)
            log.info(f"backed up old kernel to {backup}")

    # assemble and sign kernel binary
    objcopy(combine, efistub, kernel, initramfs, cmdline, output)
    sbsign(key, cert, output)




class SbKernelSign(object):
    def __init__(self):
        from argparse import ArgumentParser, FileType
        parser = ArgumentParser(description="bundle and sign kernels for secureboot systems")
        commands = parser.add_subparsers(required=True, dest='command')

        auto = commands.add_parser("auto")
        auto.add_argument(
            "-c", dest="config", help="configuration file", type=FileType("r"), default="secureboot.ini"
        )
        auto.set_defaults(func=self.auto)

        manual = commands.add_parser("manual")
        manual.add_argument('-s', dest='script', help='efistub-combine script', required=True)
        manual.add_argument('-e', dest='efistub', help='systemd-boot efistub', required=True)
        manual.add_argument('-k', dest='kernel', help='kernel binary', required=True)
        manual.add_argument('-i', dest='initramfs', help='initramfs list', nargs='+', metavar='IMG')
        manual.add_argument('-c', dest='cmdline', help='kernel cmdline', required=True)
        manual.add_argument('-o', dest='output', help='signed kernel output', required=True)
        manual.add_argument('--key', help='signing key', required=True)
        manual.add_argument('--cert', help='signing certificate', required=True)
        manual.add_argument('-b', dest='backup', help='backup suffix')        
        manual.set_defaults(func=self.manual)

        args = parser.parse_args()
        args.func(args)

    def auto(self, args):
        config = get_config(args.config)
        kg = config.get(GLOBAL, "kernels", fallback="/boot/vmlinuz-*")
        kernels = get_kernels(config, kg)
        for k in kernels:

            do_sign_kernel(
                k[NAME],
                config.get(GLOBAL, SCRIPT),
                k[EFISTUB],
                k[KERNEL],
                k[INITRAMFS].strip().splitlines(),
                k[CMDLINE],
                k[KEY],
                k[CERT],
                k[OUTPUT],
                backup=".bak",
            )

    def manual(self, args):
        do_sign_kernel(
            'manual',
            args.script,
            args.efistub,
            args.kernel,
            args.initramfs,
            args.cmdline,
            args.key,
            args.cert,
            args.output,
            backup=args.backup
        )


# ------- let's go -------
if __name__ == "__main__":

    SbKernelSign()

