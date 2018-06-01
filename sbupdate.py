#!/usr/bin/env python3

import subprocess
import configparser
import argparse

EFISTUB = "/usr/lib/systemd/boot/efi/linuxx64.efi.stub"

INITRAMFS = [
  '/boot/intel-ucode.img',
  '/boot/initramfs-linux-sd.img'
]
KERNEL = '/boot/vmlinuz-linux-sd'
CMDLINE = 'root=/dev/mapper/thinkmett rootflags=subvol=active,compress=lzo'

KEY = '/root/secureboot/DB.key'
CERT = '/root/secureboot/DB.crt'

OUTPUT = '/tmp/secureboot.efi'


def objcopy (efistub, kernel, initramfs, cmdline, output):
  script = '/home/ansemjo/script/sbupdate-py/efistub-combine.sh'
  cmd = [script, '-e', efistub, '-k', kernel, '-c', cmdline, '-o', output]
  for image in initramfs:
    cmd.extend(['-i', image])
  subprocess.run(cmd, check=True)

# create a signature on the efistub binary
def sbsign (key, cert, binary):
  cmd = ['sbsign', '--key', key, '--cert', cert, '--output', binary, binary]
  subprocess.run(cmd, check=True)

objcopy(EFISTUB, KERNEL, INITRAMFS, CMDLINE, OUTPUT)
sbsign(KEY, CERT, OUTPUT)