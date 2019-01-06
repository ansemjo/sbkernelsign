#!/usr/bin/env python3
# minimum version: 3.5

import subprocess
import magic
import distro
import re
import os

OSREL = '/etc/os-release'
EFISTUB = '/usr/lib/systemd/boot/efi/linuxx64.efi.stub'
INITRAMFS = ['/boot/intel-ucode.img', '/boot/initramfs-linux.img']
KERNEL = '/boot/vmlinuz-linux'
CMDLINE = 'noop'

# concatenate initramfs in pipe
initramfs_r, initramfs_w = os.pipe()
initramfs_w = os.fdopen(initramfs_w)
iniramfs_cat = subprocess.Popen(['cat'] + INITRAMFS, stdout=initramfs_w)

# open cmdline and dynamic osrelease pipes
cmdline_r, cmdline_w = os.pipe()
osrel_r, osrel_w = os.pipe()

# combine with objcopy
objcopy = subprocess.Popen([
  'objcopy', '--verbose',
  '--add-section', f'.osrel=/dev/fd/{osrel_r}',
  '--change-section-vma', '.osrel=0x0020000',
  '--add-section', f'.cmdline=/dev/fd/{cmdline_r}',
  '--change-section-vma', '.cmdline=0x0030000',
  '--add-section', f'.linux={KERNEL}',
  '--change-section-vma', '.linux=0x2000000',
  '--add-section', f'.initrd=/dev/fd/{initramfs_r}',
  '--change-section-vma', '.initrd=0x3000000',
  EFISTUB, '/tmp/combined.efi',
  ], pass_fds=[osrel_r, cmdline_r, initramfs_r])

# write dynamic osrelease info
kernelver = re.sub(r'.*version ([^ ,]+).*', r'\1', magic.from_file(KERNEL))
os.write(osrel_w, f'NAME="{distro.name()}"\nID="{os.path.basename(KERNEL)}"\nVERSION_ID="{kernelver}"\n'.encode())
os.close(osrel_w)

# write to cmdline pipe
os.write(cmdline_w, CMDLINE.encode())
os.close(cmdline_w)

# wait for processes and close pipes
# TODO: add timeout to wait and try:except to detect if objcopy crashes
print('wait for initramfs-cat')
iniramfs_cat.wait()
initramfs_w.close()
print('wait for objcopy')
objcopy.wait()
