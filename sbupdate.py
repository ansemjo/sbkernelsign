#!/usr/bin/env python3

import subprocess
import configparser
import argparse
import sys
import os

config = configparser.ConfigParser(
  interpolation=configparser.ExtendedInterpolation())

# string constants for variable names
NAME, BOOT, EFISTUB = 'name', 'boot', 'efistub'
KEY, CERT, KERNEL = 'key', 'crt', 'kernel'
INITRAMFS, CMDLINE = 'initramfs', 'cmdline'
OUTPUT = 'output'

# todo: accept commandline parameter
with open('secureboot.ini') as ini:
  config.read_file(ini)

# check configuration
for s in config.sections():

  # set 'name' to section name by default
  if not config.has_option(s, NAME):
    config.set(s, NAME, s)

  # debugging output
  print(f'[{s}]')
  for i in config.items(s): print(i)
  print()

  # check if everything that is required is present
  for r in [EFISTUB, KEY, CERT, KERNEL, INITRAMFS, CMDLINE, OUTPUT]:
    if not config.has_option(s, r):
      raise ValueError(f'required option {r} is missing in section {s}')

# combine efistub, kernel and initramfs into a single binary
def objcopy (efistub, kernel, initramfs, cmdline, output):
  script = '/home/ansemjo/script/sbupdate-py/efistub-combine.sh'
  cmd = [script, '-e', efistub, '-k', kernel, '-c', cmdline, '-o', output]
  for image in initramfs:
    cmd.extend(['-i', image])
  return subprocess.run(cmd, check=True)

# create a signature on the efistub binary
def sbsign (key, cert, binary):
  cmd = ['sbsign', '--key', key, '--cert', cert, '--output', binary, binary]
  return subprocess.run(cmd, check=True)

# let's go
for section in config.sections():

  cfg = config[section]

  # parse initramfs list
  initramfs = cfg[INITRAMFS].strip().splitlines()

  # if a 'boot' config option exists, join paths
  if BOOT in cfg:
    boot = cfg[BOOT]
    cfg[KERNEL] = os.path.join(boot, cfg[KERNEL])
    initramfs = [os.path.join(boot, image) for image in initramfs]

  # print info about this binary
  print((cfg[EFISTUB], cfg[KERNEL], initramfs, cfg[CMDLINE], cfg[OUTPUT]))

  # assemble and sign binary
  objcopy(cfg[EFISTUB], cfg[KERNEL], initramfs, cfg[CMDLINE], cfg[OUTPUT])
  sbsign(cfg[KEY], cfg[CERT], cfg[OUTPUT])
