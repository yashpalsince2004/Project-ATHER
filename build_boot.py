#!/usr/bin/env python3
"""
build_boot.py
=============
Repacks a MediaTek Android boot.img (header v2) by:
  - Keeping the original ramdisk from the ROM (Evolution X initramfs)
  - Replacing the kernel with the KernelSU-Next Image.gz-dtb
  - Placing the full multi-DTB blob (from Image.gz-dtb) into the v2 dtb section
  - Preserving all other header fields (cmdline, addrs, page size, etc.)

Usage:
    python3 build_boot.py
Outputs:
    boot_ksu.img
"""

import struct
import math
import zipfile
import hashlib
import os
import sys

# ── Paths ──────────────────────────────────────────────────────────────────────
ROM_BOOT    = "boot.img"
KSU_ZIP     = "KSU-NEXT-AOSP-v4.zip"
OUT_BOOT    = "boot_ksu.img"
PAGE_SIZE   = 2048

def pad(data: bytes, page: int) -> bytes:
    """Pad data to next page boundary."""
    rem = len(data) % page
    if rem:
        return data + b'\x00' * (page - rem)
    return data

def roundup_pages(size: int, page: int) -> int:
    return math.ceil(size / page)

# ── Step 1: Parse original boot.img header ────────────────────────────────────
print("[1/5] Parsing original boot.img header …")

with open(ROM_BOOT, "rb") as f:
    raw_hdr = f.read(PAGE_SIZE)

(magic, kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
 second_size, second_addr, tags_addr, page_size,
 header_version, os_version) = struct.unpack_from('<8sIIIIIIIIII', raw_hdr, 0)

assert magic == b"ANDROID!", f"Not a valid Android boot image (magic={magic})"
assert header_version == 2, f"Unsupported header version {header_version}"

name       = raw_hdr[48:64]
cmdline    = raw_hdr[64:576]
img_id     = raw_hdr[576:608]     # will be recalculated
extra_cmd  = raw_hdr[608:1632]

recovery_dtbo_size, recovery_dtbo_offset, header_size = struct.unpack_from('<IQI', raw_hdr, 1632)
orig_dtb_size, dtb_addr = struct.unpack_from('<IQ', raw_hdr, 1648)

print(f"   Page size       : {page_size}")
print(f"   Kernel addr     : {hex(kernel_addr)}")
print(f"   Ramdisk addr    : {hex(ramdisk_addr)}")
print(f"   Tags addr       : {hex(tags_addr)}")
print(f"   DTB addr        : {hex(dtb_addr)}")
print(f"   Cmdline         : {cmdline.split(b'\\x00')[0].decode()}")
print(f"   Original kernel : {kernel_size} bytes")
print(f"   Ramdisk         : {ramdisk_size} bytes")
print(f"   Original DTB    : {orig_dtb_size} bytes")

# ── Step 2: Extract RAMDISK from original boot.img ────────────────────────────
print("[2/5] Extracting original ramdisk …")

k_pages   = roundup_pages(kernel_size,           PAGE_SIZE)
r_pages   = roundup_pages(ramdisk_size,          PAGE_SIZE)
s_pages   = roundup_pages(second_size,           PAGE_SIZE)
rec_pages = roundup_pages(recovery_dtbo_size,    PAGE_SIZE) if recovery_dtbo_size else 0
dtb_offset_orig = (1 + k_pages + r_pages + s_pages + rec_pages) * PAGE_SIZE

with open(ROM_BOOT, "rb") as f:
    f.seek((1 + k_pages) * PAGE_SIZE)
    ramdisk_data = f.read(ramdisk_size)
    f.seek(dtb_offset_orig)
    orig_dtb_data = f.read(orig_dtb_size)

assert ramdisk_data[:2] == b'\x1f\x8b', "Ramdisk does not look like gzip!"
assert orig_dtb_data[:4] == bytes.fromhex('d00dfeed'), "Original DTB magic mismatch!"
print(f"   Ramdisk OK ({ramdisk_size} bytes, gzip)")
print(f"   Original DTB OK ({orig_dtb_size} bytes)")

# ── Step 3: Load KernelSU-Next kernel + DTB from zip ─────────────────────────
print("[3/5] Loading KernelSU-Next Image.gz-dtb …")

with zipfile.ZipFile(KSU_ZIP) as z:
    image_gz_dtb = z.read("Image.gz-dtb")

total_ksu_size = len(image_gz_dtb)
print(f"   Image.gz-dtb total : {total_ksu_size} bytes")

# Split at first DTB magic
dtb_magic = bytes.fromhex('d00dfeed')
split_pos = image_gz_dtb.find(dtb_magic)
assert split_pos > 0, "Could not find DTB magic in Image.gz-dtb!"

new_kernel_data = image_gz_dtb[:split_pos]
new_dtb_data    = image_gz_dtb[split_pos:]

assert new_kernel_data[:2] == b'\x1f\x8b', "KSU kernel section is not gzip!"
assert new_dtb_data[:4] == dtb_magic, "KSU DTB section magic mismatch!"

print(f"   KSU kernel (gz)    : {len(new_kernel_data)} bytes")
print(f"   KSU DTB blob       : {len(new_dtb_data)} bytes (multi-DTB with 22 entries)")

new_kernel_size = len(new_kernel_data)
new_dtb_size    = len(new_dtb_data)

# ── Step 4: Build new header ──────────────────────────────────────────────────
print("[4/5] Building new boot.img header v2 …")

# Recalculate img_id: SHA-1 of the four key blobs (kernel, ramdisk, second, dtb)
sha1 = hashlib.sha1()
sha1.update(new_kernel_data)
sha1.update(struct.pack('<I', new_kernel_size))
sha1.update(ramdisk_data)
sha1.update(struct.pack('<I', ramdisk_size))
sha1.update(b'')                              # second (empty)
sha1.update(struct.pack('<I', 0))
sha1.update(new_dtb_data)
sha1.update(struct.pack('<I', new_dtb_size))
new_img_id = sha1.digest() + b'\x00' * 12    # 32 bytes total

# Build header (1660 bytes for v2, zero-padded to PAGE_SIZE)
hdr  = b"ANDROID!"                            # magic
hdr += struct.pack('<I', new_kernel_size)     # kernel_size
hdr += struct.pack('<I', kernel_addr)         # kernel_addr (preserved)
hdr += struct.pack('<I', ramdisk_size)        # ramdisk_size
hdr += struct.pack('<I', ramdisk_addr)        # ramdisk_addr (preserved)
hdr += struct.pack('<I', second_size)         # second_size
hdr += struct.pack('<I', second_addr)         # second_addr
hdr += struct.pack('<I', tags_addr)           # tags_addr (preserved)
hdr += struct.pack('<I', page_size)           # page_size
hdr += struct.pack('<I', header_version)      # header_version = 2
hdr += struct.pack('<I', os_version)          # os_version (preserved)
hdr += name                                   # board name (16 bytes)
hdr += cmdline                                # cmdline (512 bytes)
hdr += new_img_id                             # img_id (32 bytes)
hdr += extra_cmd                              # extra cmdline (1024 bytes)
# v2 fields
hdr += struct.pack('<I', recovery_dtbo_size)  # recovery_dtbo_size
hdr += struct.pack('<Q', recovery_dtbo_offset)# recovery_dtbo_offset
hdr += struct.pack('<I', 1660)                # header_size
hdr += struct.pack('<I', new_dtb_size)        # dtb_size
hdr += struct.pack('<Q', dtb_addr)            # dtb_addr (preserved)

assert len(hdr) == 1660, f"Header size wrong: {len(hdr)}"
hdr_page = hdr + b'\x00' * (PAGE_SIZE - len(hdr))   # pad to one page

# ── Step 5: Write new boot.img ────────────────────────────────────────────────
print("[5/5] Writing new boot.img …")

with open(OUT_BOOT, "wb") as f:
    f.write(hdr_page)                       # page 0: header
    f.write(pad(new_kernel_data, PAGE_SIZE)) # pages 1…n: kernel
    f.write(pad(ramdisk_data,    PAGE_SIZE)) # pages n+1…m: ramdisk
    # second is empty → skip
    # recovery_dtbo is empty → skip
    f.write(pad(new_dtb_data,    PAGE_SIZE)) # dtb section

out_size = os.path.getsize(OUT_BOOT)
print()
print("══════════════════════════════════════════")
print(f"  SUCCESS: {OUT_BOOT}")
print(f"  Size   : {out_size:,} bytes ({out_size/(1024*1024):.1f} MB)")
print(f"  Kernel : KernelSU-Next v3.4.1 ({new_kernel_size:,} bytes)")
print(f"  Ramdisk: Evolution X initramfs ({ramdisk_size:,} bytes)")
print(f"  DTB    : Multi-DTB blob ({new_dtb_size:,} bytes, 22 entries)")
print("══════════════════════════════════════════")
print()
print("Next steps:")
print("  1. Boot test : adb reboot bootloader && fastboot boot boot_ksu.img")
print("  2. Flash perm: fastboot flash boot boot_ksu.img && fastboot reboot")
