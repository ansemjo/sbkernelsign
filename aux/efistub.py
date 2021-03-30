#!/usr/bin/env python3
# minimum version: 3.5

import struct as __struct
import shutil as __shutil
import subprocess as __subprocess
import os as __os
import tempfile as __tempfile

# parse version from kernel directly, k: file-object of opened kernel
# https://github.com/file/file/blob/31a82018c2ed153b84ea5e115fa855de24eb46d1/magic/Magdir/linux#L109
def parse_kernelversion(k):

  # save seek to restore later
  s = k.tell()

  # check 'magic' bytes
  if not k.seek(514) or not k.read(4) == b"HdrS":
    raise ValueError("%s is not a Linux kernel" % k.name)

  # seek to version string
  k.seek(526)
  offset = __struct.unpack("<h", k.read(2))[0]
  k.seek(offset + 512)

  # read and split kernel version, restore seek
  v = k.read(256).split(b" ", 1)[0].decode()
  k.seek(s)
  return v

# parse os-release if it exists and return either PRETTY_NAME, NAME or 'Linux'
def get_distroname(osrel_file = "/etc/os-release"):
  osdict = {}
  try:
    with open(osrel_file, "rt") as osrel:
      for line in osrel:
        key, value = line.rstrip().split("=")
        osdict[key] = value.strip("\"'")
  finally:
    return osdict.get('PRETTY_NAME', osdict.get('NAME', 'Linux'))

# generate a new os-release dynamically for embedding with efistub
# https://github.com/systemd/systemd/blob/72830b187f5aa06b3e89ca121bbc35451764f1bc/docs/BOOT_LOADER_SPECIFICATION.md#type-2-efi-unified-kernel-images
def generate_osrel(kernel, log=False, name=None):
  t = __tempfile.SpooledTemporaryFile(mode='wt+')
  distro = get_distroname()
  print('PRETTY_NAME="%s"' % distro, file=t)
  if log: print("os name: %s" % distro)
  name = __os.path.basename(kernel.name) if name is None else name
  print('ID="%s"' % name, file=t)
  version = parse_kernelversion(kernel)
  print('VERSION_ID="%s"' % version, file=t)
  if log: print("kernel version: %s" % version)
  t.seek(0)
  return t

# concatenate multiple files to tempfile
def concat(files):
  t = __tempfile.SpooledTemporaryFile()
  for f in files:
    __shutil.copyfileobj(f, t)
    f.close()
  t.seek(0)
  return t

# write a string to tempfile
def stof(s):
  t = __tempfile.SpooledTemporaryFile(mode='wt+')
  t.write(str(s))
  t.seek(0)
  return t

# combine kernel and initramfs in a single efi executable with a stub
def efistub_combine(efistub, kernel, initrd, cmdline, output, verbose=False, name=None):

  # write cmdline to tempfile
  cmdline = stof(cmdline)

  # generate an os-release for embedding
  osrel = generate_osrel(kernel, verbose, name)

  # concatenate initramfs in memory
  initrd = concat(initrd)

  # dict with all the file descriptors
  fds = {
    'efistub': efistub.fileno(),
    'kernel': kernel.fileno(),
    'cmdline': cmdline.fileno(),
    'osrel': osrel.fileno(),
    'initrd': initrd.fileno(),
    'output': output.fileno(),
  }

  # combine with objcopy subprocess
  ret = __subprocess.call([
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

  # close tempfiles
  cmdline.close()
  osrel.close()
  initrd.close()

  return ret

# commandline operation
def main():
  import argparse

  DEFAULT_EFISTUB = "/usr/lib/systemd/boot/efi/linuxx64.efi.stub"

  parser = argparse.ArgumentParser()
  parser.add_argument("-e", dest="efistub", help="efi loader stub", type=argparse.FileType('rb'), default=DEFAULT_EFISTUB)
  parser.add_argument("-k", dest="kernel", help="linux kernel", type=argparse.FileType('rb'), required=True)
  parser.add_argument("-i", dest="initrd", help="initramfs image", type=argparse.FileType('rb'), action='append', required=True)
  parser.add_argument("-c", dest="cmdline", help="kernel commandline", default="")
  parser.add_argument("-o", dest="output", help="output file", type=argparse.FileType('wb'), required=True)
  args = parser.parse_args()

  r = efistub_combine(**vars(args))
  exit(r)

if __name__ == "__main__":
  main()
