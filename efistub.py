#!/usr/bin/env python3
# minimum version: 3.5

import subprocess
import threading
import argparse
import magic  # < req
import distro  # < req
import re
import os

# parse version from kernel directly, k: file-object of opened kernel
# https://github.com/file/file/blob/31a82018c2ed153b84ea5e115fa855de24eb46d1/magic/Magdir/linux#L109
def parse_kernel_version(k):
  import struct

  # check 'magic' bytes
  if not k.seek(514) or not k.read(4) == b"HdrS":
    raise ValueError("%s is not a Linux kernel" % k.name)

  # seek to version string
  k.seek(526)
  offset = struct.unpack('<h', k.read(2))[0]
  k.seek(offset + 512)

  # read and split kernel version
  return k.read(256).split(b' ', 1)[0].decode()

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

def efistub_combine(efistub, kernel, initramfs, cmdline, output):

  # concatenate initramfs in pipe
  initramfs_r, initramfs_w = os.pipe()
  initramfs_w = os.fdopen(initramfs_w)
  iniramfs_p = subprocess.Popen(["cat"] + initramfs, stdout=initramfs_w)

  # write cmdline through pipe
  cmdline_r, cmdline_w = os.pipe()
  def pipe_cmdline():
    os.write(cmdline_w, cmdline.encode())
    os.close(cmdline_w)
  cmdline_t = threading.Thread(target=pipe_cmdline)
  cmdline_t.start()

  # write dynamic osrelease info through pipe
  osrel_r, osrel_w = os.pipe()
  def pipe_osrelease():
    kernelver = re.sub(r".*version ([^ ,]+).*", r"\1", magic.from_file(kernel))
    os.write(osrel_w, f'NAME="{distro.name()}"\n'.encode())
    os.write(osrel_w, f'ID="{os.path.basename(kernel)}"\n'.encode())
    os.write(osrel_w, f'VERSION_ID="{kernelver}"\n'.encode())
    os.close(osrel_w)
  osrel_t = threading.Thread(target=pipe_osrelease)
  osrel_t.start()

  # combine with objcopy
  objcopy = subprocess.Popen([
    "objcopy", "--verbose",
    "--add-section", f".osrel=/dev/fd/{osrel_r}",
    "--change-section-vma", ".osrel=0x0020000",
    "--add-section", f".cmdline=/dev/fd/{cmdline_r}",
    "--change-section-vma", ".cmdline=0x0030000",
    "--add-section", f".linux={kernel}",
    "--change-section-vma", ".linux=0x2000000",
    "--add-section", f".initrd=/dev/fd/{initramfs_r}",
    "--change-section-vma", ".initrd=0x3000000",
    efistub, "/tmp/combined.efi"],
    pass_fds=[osrel_r, cmdline_r, initramfs_r],
  )

  # wait for processes and close pipes
  # TODO: add timeout to wait and try:except to detect if objcopy crashes
  cmdline_t.join()
  osrel_t.join()
  iniramfs_p.wait()
  initramfs_w.close()
  objcopy.wait()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("-e", dest="efistub", help="efi stub", default="/usr/lib/systemd/boot/efi/linuxx64.efi.stub")
  parser.add_argument("-k", dest="kernel", help="linux kernel", required=True)
  parser.add_argument("-i", dest="initramfs", action="append", help="initramfs image", default=[])
  parser.add_argument("-c", dest="cmdline", help="kernel commandline", default="")
  parser.add_argument("-o", dest="output", help="output file", required=True)
  args = parser.parse_args()
  efistub_combine(**vars(args))
