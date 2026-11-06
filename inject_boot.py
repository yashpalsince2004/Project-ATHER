#!/usr/bin/env python3
"""
inject_boot.py  (v2)
=====================
Replaces boot.img inside the Evolution X ROM zip with boot_ksu.img by doing a
RAW copy of every other zip entry's compressed bytes — no decompress/recompress.
The central directory is written by Python's own zipfile module so we don't
have to hand-roll the structs.

Usage:
    python3 inject_boot.py
Output:
    EvolutionX-17.0-KSU-Next-op6893-12.3-Unofficial.zip
"""

import copy
import io
import os
import struct
import sys
import time
import zipfile

SRC_ZIP  = "EvolutionX-17.0-20261024-op6893-12.3-Unofficial.zip"
NEW_BOOT = "boot_ksu.img"
OUT_ZIP  = "EvolutionX-17.0-KSU-Next-op6893-12.3-Unofficial.zip"
CHUNK    = 64 * 1024 * 1024  # 64 MB I/O buffer

# ── helpers ───────────────────────────────────────────────────────────────────

def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def local_header_size(raw_fp, offset):
    """Return byte-length of the local file header at `offset`."""
    raw_fp.seek(offset + 26)
    fn_len, extra_len = struct.unpack('<HH', raw_fp.read(4))
    return 30 + fn_len + extra_len

def copy_raw_entry(raw_fp, dst_fp, info):
    """
    Copy local-header + compressed-data verbatim from raw_fp → dst_fp.
    Updates info.header_offset to the new position in dst_fp.
    Returns number of bytes written.
    """
    lh_size  = local_header_size(raw_fp, info.header_offset)
    total    = lh_size + info.compress_size

    info.header_offset = dst_fp.tell()   # record NEW offset before writing
    raw_fp.seek(info.header_offset - info.header_offset + info.header_offset)
    # ^ need the OLD offset – recompute from a saved value below
    raise RuntimeError("Use copy_raw_entry2 instead")

def copy_raw_entry2(raw_fp, old_offset, compress_size, dst_fp, info):
    lh_size = local_header_size(raw_fp, old_offset)
    total   = lh_size + compress_size

    info.header_offset = dst_fp.tell()
    raw_fp.seek(old_offset)
    remaining = total
    while remaining > 0:
        chunk = raw_fp.read(min(CHUNK, remaining))
        if not chunk:
            raise EOFError("Truncated source zip")
        dst_fp.write(chunk)
        remaining -= len(chunk)

    # handle data-descriptor trailer (flag bit 3)
    if info.flag_bits & 0x08:
        sig = raw_fp.read(4)
        if sig == b'PK\x07\x08':
            dst_fp.write(sig + raw_fp.read(16))
        else:
            raw_fp.seek(-4, 1)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    for path, label in [(SRC_ZIP, 'Source ROM'), (NEW_BOOT, 'New boot')]:
        if not os.path.exists(path):
            sys.exit(f"❌  Not found: {path}")

    if os.path.exists(OUT_ZIP):
        os.remove(OUT_ZIP)

    src_size  = os.path.getsize(SRC_ZIP)
    boot_size = os.path.getsize(NEW_BOOT)

    print(f"Source ROM : {SRC_ZIP}  ({human(src_size)})")
    print(f"New boot   : {NEW_BOOT}  ({human(boot_size)})")
    print(f"Output     : {OUT_ZIP}")
    print()

    t0 = time.time()

    with zipfile.ZipFile(SRC_ZIP, 'r') as zin:
        infolist = zin.infolist()
        total    = len(infolist)

        with open(SRC_ZIP, 'rb') as raw_fp, \
             open(OUT_ZIP, 'w+b') as dst_fp:

            # We will collect ZipInfo objects with updated header_offsets, then
            # hand the list to a ZipFile opened on the same dst_fp for CD write.
            new_infolist = []

            for idx, info in enumerate(infolist):
                label = f"[{idx+1:>2}/{total}]"

                if info.filename == 'boot.img':
                    # ── Replace boot.img with boot_ksu.img (STORED) ──────────
                    print(f"{label} REPLACING  boot.img  "
                          f"({human(info.file_size)} → {human(boot_size)}) …")

                    # Build a tiny in-memory zip containing just our boot image
                    # so Python generates a correct local header for us.
                    tmp_buf = io.BytesIO()
                    with zipfile.ZipFile(tmp_buf, 'w',
                                         compression=zipfile.ZIP_STORED,
                                         allowZip64=True) as ztmp:
                        ztmp.write(NEW_BOOT, arcname='boot.img')
                    tmp_bytes = tmp_buf.getvalue()

                    # Parse the single ZipInfo from that temp zip
                    tmp_zi = zipfile.ZipFile(io.BytesIO(tmp_bytes)).infolist()[0]

                    # Grab the local header from the temp zip (starts at offset 0)
                    lh_size = local_header_size(io.BytesIO(tmp_bytes), 0)
                    local_hdr_bytes = tmp_bytes[:lh_size]

                    new_info = copy.copy(tmp_zi)
                    new_info.header_offset = dst_fp.tell()

                    # Write local header
                    dst_fp.write(local_hdr_bytes)

                    # Stream body from disk
                    with open(NEW_BOOT, 'rb') as bf:
                        while True:
                            chunk = bf.read(CHUNK)
                            if not chunk:
                                break
                            dst_fp.write(chunk)

                    new_infolist.append(new_info)

                else:
                    # ── Raw-copy every other entry ───────────────────────────
                    old_offset    = info.header_offset
                    compress_size = info.compress_size
                    new_info      = copy.copy(info)

                    print(f"{label} copying    {info.filename:<52} "
                          f"({human(compress_size)})")

                    copy_raw_entry2(raw_fp, old_offset, compress_size,
                                    dst_fp, new_info)
                    new_infolist.append(new_info)

            # ── Write central directory using zipfile internals ────────────────
            # Open a ZipFile on the same dst_fp and inject our infolist,
            # then let close() write the CD + EOCD.
            print()
            print("Writing central directory …")
            cd_offset = dst_fp.tell()

            # Write central directory entries manually (avoids needing to open
            # ZipFile on the file, which would seek back and clobber data).
            for info in new_infolist:
                fname_b = info.filename.encode('utf-8')
                extra_b = b''
                comment_b = (info.comment or b'') if isinstance(info.comment, bytes) \
                             else b''

                # Determine if we need ZIP64 extension
                need_zip64 = (info.file_size     > 0xFFFFFFFF or
                              info.compress_size > 0xFFFFFFFF or
                              info.header_offset > 0xFFFFFFFF)

                if need_zip64:
                    extra_b = struct.pack('<HH QQ Q',
                        1, 24,  # ZIP64 extra field tag + size
                        info.file_size,
                        info.compress_size,
                        info.header_offset,
                    )
                    file_size_cd     = 0xFFFFFFFF
                    compress_size_cd = 0xFFFFFFFF
                    offset_cd        = 0xFFFFFFFF
                else:
                    file_size_cd     = info.file_size
                    compress_size_cd = info.compress_size
                    offset_cd        = info.header_offset

                dt = info.date_time
                dostime = dt[3] * 2048 + dt[4] * 32 + (dt[5] // 2)
                dosdate = (dt[0] - 1980) * 512 + dt[1] * 32 + dt[2]

                # Central directory entry: 46 bytes fixed + variable
                # struct format: sig(4s) ver_by(H) ver_need(H) flags(H)
                #   compress(H) mod_time(H) mod_date(H) crc(I)
                #   compress_size(I) file_size(I) fname_len(H) extra_len(H)
                #   comment_len(H) disk_start(H) int_attr(H) ext_attr(I) offset(I)
                cd_entry = struct.pack(
                    '<4sHHHHHHIIIHHHHHII',
                    b'PK\x01\x02',            # central dir sig
                    (3 << 8) | 63,             # version made by (UNIX / 6.3)
                    45 if need_zip64 else 20,  # version needed
                    info.flag_bits & ~0x08,    # strip data-descriptor flag
                    info.compress_type,
                    dostime,                   # mod time (H)
                    dosdate,                   # mod date (H)
                    info.CRC & 0xFFFFFFFF,
                    compress_size_cd,
                    file_size_cd,
                    len(fname_b),
                    len(extra_b),
                    len(comment_b),
                    0,                         # disk start
                    0,                         # internal attrs
                    info.external_attr,
                    offset_cd,
                )
                dst_fp.write(cd_entry)
                dst_fp.write(fname_b)
                dst_fp.write(extra_b)
                dst_fp.write(comment_b)

            cd_size   = dst_fp.tell() - cd_offset
            n_entries = len(new_infolist)

            # ZIP64 end of central directory record (needed since file > 4 GB)
            zip64_eocd_offset = dst_fp.tell()
            dst_fp.write(struct.pack(
                '<4s Q H H I I Q Q Q Q',
                b'PK\x06\x06',
                44,            # size of remaining record
                (3 << 8) | 63,
                45,
                0, 0,          # disk numbers
                n_entries,
                n_entries,
                cd_size,
                cd_offset,
            ))

            # ZIP64 end of central directory locator
            dst_fp.write(struct.pack(
                '<4s I Q I',
                b'PK\x06\x07',
                0,
                zip64_eocd_offset,
                1,
            ))

            # End of central directory (EOCD)
            dst_fp.write(struct.pack(
                '<4s H H H H I I H',
                b'PK\x05\x06',
                0xFFFF, 0xFFFF,          # disk numbers (ZIP64 sentinel)
                min(n_entries, 0xFFFF),
                min(n_entries, 0xFFFF),
                min(cd_size,   0xFFFFFFFF),
                min(cd_offset, 0xFFFFFFFF),
                0,                        # comment length
            ))

    elapsed  = time.time() - t0
    out_size = os.path.getsize(OUT_ZIP)

    print()
    print("═" * 62)
    print(f"  ✅  DONE in {elapsed:.1f}s")
    print(f"  Output : {OUT_ZIP}")
    print(f"  Size   : {human(out_size)}")
    print("═" * 62)
    print()
    print("Flash via custom recovery (TWRP / OrangeFox):")
    print("  • ADB sideload:")
    print(f"      adb sideload \"{OUT_ZIP}\"")
    print("  • Or copy to phone & flash from recovery file manager")

if __name__ == '__main__':
    main()
