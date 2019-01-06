#!/usr/bin/env python3
# minimum version: 3.5

import subprocess
import threading
import argparse
import magic  # < req
import distro  # < req
import re
import os

parser = argparse.ArgumentParser()
parser.add_argument("-e", dest="efistub", help="efi stub", default="/usr/lib/systemd/boot/efi/linuxx64.efi.stub")
parser.add_argument("-k", dest="kernel", help="linux kernel", required=True)
parser.add_argument("-i", dest="initramfs", action="append", help="initramfs image", default=[])
parser.add_argument("-c", dest="cmdline", help="kernel commandline", default="")
parser.add_argument("-o", dest="output", help="output file", required=True)
args = parser.parse_args()
print(args)

# concatenate initramfs in pipe
initramfs_r, initramfs_w = os.pipe()
initramfs_w = os.fdopen(initramfs_w)
iniramfs_p = subprocess.Popen(["cat"] + args.initramfs, stdout=initramfs_w)

# write cmdline through pipe
cmdline_r, cmdline_w = os.pipe()
def pipe_cmdline():
  os.write(cmdline_w, args.cmdline.encode())
  os.close(cmdline_w)
cmdline_t = threading.Thread(target=pipe_cmdline)
cmdline_t.start()

# write dynamic osrelease info through pipe
osrel_r, osrel_w = os.pipe()
def pipe_osrelease():
  kernelver = re.sub(r".*version ([^ ,]+).*", r"\1", magic.from_file(args.kernel))
  os.write(osrel_w, f'NAME="{distro.name()}"\n'.encode())
  os.write(osrel_w, f'ID="{os.path.basename(args.kernel)}"\n'.encode())
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
  "--add-section", f".linux={args.kernel}",
  "--change-section-vma", ".linux=0x2000000",
  "--add-section", f".initrd=/dev/fd/{initramfs_r}",
  "--change-section-vma", ".initrd=0x3000000",
  args.efistub, "/tmp/combined.efi"],
  pass_fds=[osrel_r, cmdline_r, initramfs_r],
)

# wait for processes and close pipes
# TODO: add timeout to wait and try:except to detect if objcopy crashes
cmdline_t.join()
osrel_t.join()
iniramfs_p.wait()
initramfs_w.close()
objcopy.wait()
