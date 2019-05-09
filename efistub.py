#!/usr/bin/env python3
# minimum version: 3.5

import subprocess
import threading
import argparse
import magic  # < req
import distro  # < req
import re
import os

import struct
import shutil
import tempfile

# parse version from kernel directly, k: file-object of opened kernel
# https://github.com/file/file/blob/31a82018c2ed153b84ea5e115fa855de24eb46d1/magic/Magdir/linux#L109
def parse_kernel_version(k):
  # save seek to restore later
  s = k.tell()

  # check 'magic' bytes
  if not k.seek(514) or not k.read(4) == b"HdrS":
    raise ValueError("%s is not a Linux kernel" % k.name)

  # seek to version string
  k.seek(526)
  offset = struct.unpack('<h', k.read(2))[0]
  k.seek(offset + 512)

  # read and split kernel version, restore seek
  v = k.read(256).split(b' ', 1)[0].decode()
  k.seek(s)
  return v

# parse /etc/os-release if it exists and return either PRETTY_NAME, NAME or 'Linux'
def get_distro_name():
  osdict = {}
  try:
    with open('/etc/os-release', 'rt') as osrel:
      for line in osrel:
        key, value = line.rstrip().split('=')
        osdict[key] = value.strip('"\'')
  finally:
    return osdict.get('PRETTY_NAME', osdict.get('NAME', 'Linux'))

# generate a new os-release dynamically for embedding with efistub
# https://github.com/systemd/systemd/blob/72830b187f5aa06b3e89ca121bbc35451764f1bc/docs/BOOT_LOADER_SPECIFICATION.md#type-2-efi-unified-kernel-images
def generate_osrel(kernel):
  t = tempfile.SpooledTemporaryFile(mode='wt+')
  print('NAME="%s"' % get_distro_name(), file=t)
  print('ID="%s"' % os.path.basename(kernel.name), file=t)
  print('VERSION_ID="%s"' % parse_kernel_version(kernel), file=t)
  t.seek(0)
  return t

# concatenate multiple files to tempfile
def combine_files(flist):
  t = tempfile.SpooledTemporaryFile()
  for f in flist:
    shutil.copyfileobj(f, t)
    f.close()
  t.seek(0)
  return t

# write a string to tempfile
def string_to_tempfile(s):
  t = tempfile.SpooledTemporaryFile(mode='wt+')
  print(s, file=t)
  t.seek(0)
  return t

def efistub_combine(efistub, kernel, initramfs, cmdline, output):

  # write cmdline to tempfile
  cmdline = string_to_tempfile(cmdline)

  # generate an os-release for embedding
  osrel = generate_osrel(kernel)

  # concatenate initramfs in memory
  initrd = combine_files(initramfs)

  # dict with all the file descriptors
  fds = {
    'efistub': efistub.fileno(),
    'kernel': kernel.fileno(),
    'cmdline': cmdline.fileno(),
    'osrel': osrel.fileno(),
    'initrd': initrd.fileno(),
    'output': output.fileno(),
  }

  # combine with objcopy
  ret = subprocess.call([
      "objcopy",
      "--add-section", ".osrel=/dev/fd/%(osrel)d" % fds,
      "--change-section-vma", ".osrel=0x0020000",
      "--add-section", ".cmdline=/dev/fd/%(cmdline)d" % fds,
      "--change-section-vma", ".cmdline=0x0030000",
      "--add-section", ".linux=/dev/fd/%(kernel)d" % fds,
      "--change-section-vma", ".linux=0x2000000",
      "--add-section", ".initrd=/dev/fd/%(initrd)d" % fds,
      "--change-section-vma", ".initrd=0x3000000",
      "/dev/fd/%(efistub)d" % fds,
      "/dev/fd/%(output)d" % fds,
    ], pass_fds=fds.values(),
  )

  return ret

if __name__ == "__main__":
  DEFAULT_EFISTUB = "/usr/lib/systemd/boot/efi/linuxx64.efi.stub"
  parser = argparse.ArgumentParser()
  parser.add_argument("-e", dest="efistub", help="efi loader stub", type=argparse.FileType('rb'), default=DEFAULT_EFISTUB)
  parser.add_argument("-k", dest="kernel", help="linux kernel", type=argparse.FileType('rb'), required=True)
  parser.add_argument("-i", dest="initramfs", help="initramfs image", type=argparse.FileType('rb'), nargs='*')
  parser.add_argument("-c", dest="cmdline", help="kernel commandline", default="")
  parser.add_argument("-o", dest="output", help="output file", type=argparse.FileType('wb'), required=True)
  args = parser.parse_args()
  efistub_combine(**vars(args))
