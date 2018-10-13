#!/usr/bin/env python3

import subprocess
import configparser
import argparse
import shutil
import glob
import sys
import os

import chalk

# .ini config parser with ${var} interpolation
config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())

# configuration variable names
NAME = "name"
BOOT = "boot"
EFISTUB = "efistub"
KEY = "key"
CERT = "crt"
KERNEL = "kernel"
INITRAMFS = "initramfs"
CMDLINE = "cmdline"
OUTPUT = "output"

# TODO: put into config
OBJCOPY_SCRIPT = "/home/ansemjo/git/script/sbupdate/efistub-combine.sh"

# TODO: commandline parser
with open("secureboot.ini") as ini:
    config.read_file(ini)

# add missing sections by globbing
kernelglob = config.get("global", "kernels", fallback="/boot/vmlinuz-*")
for kernel in (k[len(kernelglob) - 1 :] for k in glob.iglob(kernelglob)):
    if not config.has_section(kernel):
        config.add_section(kernel)

# check configuration
for s in [s for s in config.sections() if s != "global"]:

    # set 'name' to section name by default
    if not config.has_option(s, NAME):
        config.set(s, NAME, s)

    # debugging output
    if True:
        print(f"[{s}]")
        for i in config.items(s):
            print(i)
        print()

    # check if everything that is required is present
    for r in [EFISTUB, KEY, CERT, KERNEL, INITRAMFS, CMDLINE, OUTPUT]:
        if not config.has_option(s, r):
            raise ValueError(f"required option {r} is missing in section {s}")

# combine efistub, kernel and initramfs into a single binary
def objcopy(efistub, kernel, initramfs, cmdline, output):
    cmd = [OBJCOPY_SCRIPT, "-v", "-e", efistub, "-k", kernel, "-c", cmdline, "-o", output]
    for image in initramfs:
        cmd.extend(["-i", image])
    return subprocess.run(cmd, check=True)


# create a signature on the efistub binary
def sbsign(key, cert, binary):
    cmd = ["sbsign", "--key", key, "--cert", cert, "--output", binary, binary]
    return subprocess.run(cmd, check=True)


# let's go
for cfg in [config[s] for s in config.sections() if s != "global"]:

    # fetch values
    efistub, cmdline, output = cfg[EFISTUB], cfg[CMDLINE], cfg[OUTPUT]
    kernel, key, cert = cfg[KERNEL], cfg[KEY], cfg[CERT]
    name = cfg[NAME]
    # parse initramfs list
    initramfs = cfg[INITRAMFS].strip().splitlines()

    # print info about this binary
    print(chalk.bold(f">>> {name}"))
    print("kernel  :", chalk.magenta(kernel))
    print("initrd  :", chalk.green(initramfs))
    print("cmdline :", chalk.cyan(cmdline))

    # create backup copy
    if os.path.isfile(output):
        shutil.copy2(output, output + ".bak")

    # assemble and sign binary
    objcopy(efistub, kernel, initramfs, cmdline, output)
    sbsign(key, cert, output)
