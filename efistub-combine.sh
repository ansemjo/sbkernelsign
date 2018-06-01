#!/usr/bin/bash

# Copyright (c) 2018 Anton Semjonov

# combine the efistub from systemd-boot with a kernel,
# (multiple) initramfs and a kernel commandline. this
# creates a single efi binary which can be signed and
# copied as a whole

# print usage message and exit
usage() {
  [[ -n $1 ]] && echo "ERR: $1" >&2
  echo "$ $0 -e \$efistub -k \$kernel -i \$initrd [-i \$initrd] -c \$cmdline -o \$output" >&2
  exit 1
}

# constants
OSREL=/etc/os-release

# parse commandline options
while getopts 'e:k:i:c:o:v?' opt; do
  case $opt in
    e) EFISTUB="$OPTARG" ;;
    k) KERNEL="$OPTARG" ;;
    i) INITRAMFS+=("$OPTARG") ;;
    c) CMDLINE="$OPTARG" ;;
    o) OUTPUT="$OPTARG" ;;
    v) VERBOSE=true ;;
    *) usage ;;
  esac
done

# print parsed values if verbose
if [[ $VERBOSE == true ]]; then
  printf 'EFISTUB   : %s\n' "$EFISTUB"
  printf 'KERNEL    : %s\n' "$KERNEL"
  printf 'INITRAMFS :\n'
  printf ' - %s\n' "${INITRAMFS[@]}"
  printf 'CMDLINE   : %s\n' "$CMDLINE"
  printf 'OUTPUT    : %s\n' "$OUTPUT"
fi

# check parsed values
[[ -z $EFISTUB || -z $KERNEL || -z $OUTPUT || -z ${CMDLINE+isset} || ${#INITRAMFS[@]} -eq 0 ]] && usage
for f in "$OSREL" "$EFISTUB" "$KERNEL" "${INITRAMFS[@]}"; do
  [[ ! -f $f ]] && usage "no such file '$f'"
done

# perform objcopy
objcopy ${VERBOSE+--verbose} \
  --add-section   .osrel="$OSREL"                   --change-section-vma   .osrel=0x0020000 \
  --add-section .cmdline=<(printf '%s' "$CMDLINE")  --change-section-vma .cmdline=0x0030000 \
  --add-section   .linux="$KERNEL"                  --change-section-vma   .linux=0x2000000 \
  --add-section  .initrd=<(cat "${INITRAMFS[@]}")   --change-section-vma  .initrd=0x3000000 \
  "$EFISTUB" "$OUTPUT"
