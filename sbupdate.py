#!/usr/bin/env python3

import subprocess
import configparser
import argparse
import shutil
import glob
import sys
import os
import re

# .ini config parser with ${var} interpolation
config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())

# ignore whitespace around section header
config.SECTCRE = re.compile(r"\[ *(?P<header>[^]]+?) *\]")

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

# TODO: commandline parser
with open("secureboot.ini") as ini:
    config.read_file(ini)


def err(e, exit=True, prefix="ERR"):
    print(prefix + ":", e, file=sys.stderr)
    if exit:
        sys.exit(1)


# check config sections for possible kernels
def get_kernels(config, kernelglob=None):

    # add missing sections by globbing
    if kernelglob is not None:
        for kernel in (k[len(kg) - 1 :] for k in glob.iglob(kernelglob)):
            if not config.has_section(kernel):
                config.add_section(kernel)

    kernels = []
    for s in [s for s in config.sections() if s != GLOBAL]:
        section = config[s]

        # skip when IGNORE is truthy
        if IGNORE in section and section.getboolean(IGNORE):
            continue

        # add name from section name by default
        if not NAME in section:
            section[NAME] = s.strip()

        # exception for missing config items
        class MissingConf(Exception):
            pass

        # check if everything that is required is present, otherwise ignore
        try:
            for r in [EFISTUB, KEY, CERT, KERNEL, INITRAMFS, CMDLINE, OUTPUT]:
                if not r in section:
                    err(f"[{s}]: required option '{r}' missing", exit=False, prefix="WARN")
                    raise MissingConf()
        except MissingConf:
            continue

        # all checks passed, append to list
        kernels.append(section)

    # error when no kernels are found / left
    if len(kernels) == 0:
        err("no kernels configured")

    return kernels


kg = config.get(GLOBAL, "kernels", fallback="/boot/vmlinuz-*")
kernels = get_kernels(config, kg)

# combine efistub, kernel and initramfs into a single binary
def objcopy(efistub, kernel, initramfs, cmdline, output):
    cmd = [config.get(GLOBAL, SCRIPT), "-v", "-e", efistub, "-k", kernel, "-c", cmdline, "-o", output]
    for image in initramfs:
        cmd.extend(["-i", image])
    return subprocess.run(cmd, check=True)


# create a signature on the efistub binary
def sbsign(key, cert, binary):
    cmd = ["sbsign", "--key", key, "--cert", cert, "--output", binary, binary]
    return subprocess.run(cmd, check=True)


def do_sign_kernel(name, efistub, kernel, initramfs, cmdline, key, cert, output, verbose=True, backup=".bak"):

    # print info about this kernel
    if verbose:
        for i in ("", f"\033[1m[ {name} ]\033[0m", kernel, initramfs, output, ""):
            print(i)

    # create backup copy
    if backup is not None:
        if os.path.isfile(output):
            shutil.copy2(output, output + backup)

    # assemble and sign kernel binary
    objcopy(efistub, kernel, initramfs, cmdline, output)
    sbsign(key, cert, output)


# let's go
for k in kernels:

    do_sign_kernel(
        k[NAME],
        k[EFISTUB],
        k[KERNEL],
        k[INITRAMFS].strip().splitlines(),
        k[CMDLINE],
        k[KEY],
        k[CERT],
        k[OUTPUT],
        verbose=True,
        backup=".bak",
    )

