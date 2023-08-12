# sbkernelsign

Well, I never got around to writing a proper README for this tool and now
I'm giving notice that it is **DEPRECATED**.

For some background check [ansemjo/mksignkernels](https://github.com/ansemjo/mksignkernels)
and [andreyv/sbupdate](https://github.com/andreyv/sbupdate).

This script does the same thing. It is another reimplementation because I
didn't understand my own Makefile voodoo in `mksignkernels` after not touching
it for a while -- which bit me when I needed to rescue my system recently.

## Why it's deprecated

I had a little scare today because my system suddenly wouldn't boot anymore
after a system update. Unfortunately, I failed to notice some warnings like
`objcopy: /dev/fd/6:.osrel: section below image base` in the output. This was
ultimately due to changes in the EFI stub, which meant that the `.osrel`,
`.cmdline`, `.linux` and `.initrd` sections were suddenly inserted *before*
the stub itself. That defeats the entire point of the stub, of course.

The **short-term** solution to this was simply hardcoding sufficiently high
section VMAs. You can find the minimum required offset with `objdump -h` per this
[Arch Wiki entry](https://wiki.archlinux.org/title/Unified_kernel_image#Manually):

```
objdump -h "/usr/lib/systemd/boot/efi/linuxx64.efi.stub" \
| awk 'NF==7 { sz=strtonum("0x"$3); of=strtonum("0x"$4) } END { printf "0x%x\n", sz+of }'
```

The proper solution would be to parse the EFI stub and adjust the offsets dynamically.
Again, see the snippet in the linked Arch Wiki entry above.

The much more comfortable and future-proof solution is to simply rely on your
distribution's tools. It turns out that [`mkinitcpio` has support for generating
unified kernle images (UKI)](https://wiki.archlinux.org/title/Unified_kernel_image#mkinitcpio),
which can then be signed with a simple `post` hook.

## Doing it with `mkinitcpio`

The `tl;dr` of my configuration, for reference:

* put the Kernel commandline in `/etc/kernel/cmdline`
* adjust the `/etc/mkinitcpio.d/linux.preset` preset:
  * add `ALL_microcode=("/boot/amd-ucode.img")`
  * add `default_uki="/boot/efi/EFI/Linux/linux.efi"`
  * optionally adjust the `fallback` preset to generate a rescue image with a different
    commandline by appending `--cmdline /etc/kernel/cmdline.rescue` to `fallback_options`
* add the `sbsign` post-hook in `/etc/initcpio/post/sbsign`:
```
#!/usr/bin/env bash
# sign unified kernel images after mkinicpio run
# https://wiki.archlinux.org/title/Unified_kernel_image#Signing_the_UKIs_for_Secure_Boot
set -eu

# signing keypair (crt, key)
sk=(/etc/efikeys/DatabaseKey.{crt,key})

# the third argument will be the uki
image=${3-}; if [[ -n ${image} ]]; then

  # check if the keypair is readable
  if ! [[ -r ${sk[0]} ]] || ! [[ -r ${sk[1]} ]]; then
    echo >&2 "ERR: signing keypair is not readable: ${sk[@]}"
    exit 1
  fi

  # don't re-sign if the image is already signed with this key
  if sbverify --cert "${sk[0]}" "${image}" &>/dev/null; then
    exit 0
  fi

  # add signature otherwise
  sbsign --cert "${sk[0]}" --key "${sk[1]}" --output "${image}"{,}

fi
```
