#!/usr/bin/env python3
"""
inject_apk.py
=============
Patches EvolutionX-17.0-KSU-Next-op6893-12.3-Unofficial.zip to:
  1. Add KernelSU_Next_v3.4.2_33355-release.apk as
       priv-app/KernelSUNext/KernelSUNext.apk
  2. Patch META-INF/com/google/android/updater-script to
     mount /system after backuptool restore and copy the APK in.

All other entries are raw-copied (no decompress/recompress).
Output overwrites the same zip file.
"""

import copy, io, os, struct, sys, time, zipfile

SRC_ZIP  = "EvolutionX-17.0-KSU-Next-op6893-12.3-Unofficial.zip"
APK_SRC  = "KernelSU_Next_v3.4.2_33355-release.apk"
APK_DEST = "priv-app/KernelSUNext/KernelSUNext.apk"   # path inside zip
TMP_ZIP  = SRC_ZIP + ".tmp"
CHUNK    = 64 * 1024 * 1024

def human(n):
    for u in ('B','KB','MB','GB'):
        if abs(n) < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def lh_size(fp_or_bytes, offset):
    """Size of local file header at `offset`."""
    if isinstance(fp_or_bytes, (bytes, bytearray)):
        fp_or_bytes = io.BytesIO(fp_or_bytes)
    fp_or_bytes.seek(offset + 26)
    fn, ex = struct.unpack('<HH', fp_or_bytes.read(4))
    return 30 + fn + ex

def raw_copy(raw_fp, old_off, c_size, dst_fp, info):
    """Copy local header + compressed data verbatim; update info.header_offset."""
    total = lh_size(raw_fp, old_off) + c_size
    info.header_offset = dst_fp.tell()
    raw_fp.seek(old_off)
    rem = total
    while rem:
        buf = raw_fp.read(min(CHUNK, rem))
        if not buf: raise EOFError
        dst_fp.write(buf); rem -= len(buf)
    if info.flag_bits & 0x08:
        sig = raw_fp.read(4)
        if sig == b'PK\x07\x08': dst_fp.write(sig + raw_fp.read(16))
        else: raw_fp.seek(-4, 1)

def write_entry_stored(dst_fp, arcname, data, dt):
    """Write a STORED (uncompressed) entry; return populated ZipInfo."""
    import zlib
    crc = zlib.crc32(data) & 0xFFFFFFFF
    fname_b = arcname.encode('utf-8')
    extra_b = b''
    need64  = len(data) > 0xFFFFFFFF
    if need64:
        extra_b = struct.pack('<HH QQ', 1, 16, len(data), len(data))

    # Local file header: sig(4s) ver(H) flag(H) method(H) time(H) date(H) crc(I) csize(I) usize(I) fnlen(H) exlen(H)
    lh = struct.pack('<4sHHHHHIIIHH',
        b'PK\x03\x04', 45 if need64 else 20, 0, 0,
        dt[3]*2048+dt[4]*32+(dt[5]//2),
        (dt[0]-1980)*512+dt[1]*32+dt[2],
        crc,
        0xFFFFFFFF if need64 else len(data),
        0xFFFFFFFF if need64 else len(data),
        len(fname_b), len(extra_b))

    offset = dst_fp.tell()
    dst_fp.write(lh + fname_b + extra_b)
    # stream data in chunks
    pos = 0
    while pos < len(data):
        dst_fp.write(data[pos:pos+CHUNK]); pos += CHUNK

    zi = zipfile.ZipInfo(arcname, dt)
    zi.compress_type   = zipfile.ZIP_STORED
    zi.CRC             = crc
    zi.file_size       = len(data)
    zi.compress_size   = len(data)
    zi.header_offset   = offset
    zi.flag_bits       = 0
    zi.external_attr   = 0o100644 << 16
    return zi

def write_entry_deflated(dst_fp, arcname, data, dt):
    """Write a DEFLATED entry; return populated ZipInfo."""
    import zlib
    crc          = zlib.crc32(data) & 0xFFFFFFFF
    compressed   = zlib.compress(data, 6)[2:-4]   # strip zlib header/trailer
    fname_b      = arcname.encode('utf-8')
    extra_b      = b''
    # Local file header: sig(4s) ver(H) flag(H) method(H) time(H) date(H) crc(I) csize(I) usize(I) fnlen(H) exlen(H)
    lh = struct.pack('<4sHHHHHIIIHH',
        b'PK\x03\x04', 20, 0, 8,
        dt[3]*2048+dt[4]*32+(dt[5]//2),
        (dt[0]-1980)*512+dt[1]*32+dt[2],
        crc, len(compressed), len(data),
        len(fname_b), len(extra_b))
    offset = dst_fp.tell()
    dst_fp.write(lh + fname_b + extra_b + compressed)
    zi = zipfile.ZipInfo(arcname, dt)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.CRC           = crc
    zi.file_size     = len(data)
    zi.compress_size = len(compressed)
    zi.header_offset = offset
    zi.flag_bits     = 0
    zi.external_attr = 0o100644 << 16
    return zi

def write_central_directory(dst_fp, infolist):
    cd_start = dst_fp.tell()
    for info in infolist:
        fname_b   = info.filename.encode('utf-8')
        dt        = info.date_time
        dostime   = dt[3]*2048 + dt[4]*32 + (dt[5]//2)
        dosdate   = (dt[0]-1980)*512 + dt[1]*32 + dt[2]
        need64    = (info.file_size > 0xFFFFFFFF or
                     info.compress_size > 0xFFFFFFFF or
                     info.header_offset > 0xFFFFFFFF)
        extra_b   = b''
        if need64:
            extra_b = struct.pack('<HH QQ Q', 1, 24,
                info.file_size, info.compress_size, info.header_offset)
        comment_b = b''
        cd = struct.pack('<4sHHHHHHIIIHHHHHII',
            b'PK\x01\x02',
            (3<<8)|63, 45 if need64 else 20,
            getattr(info,'flag_bits',0) & ~0x08,
            info.compress_type,
            dostime, dosdate,
            info.CRC & 0xFFFFFFFF,
            min(info.compress_size, 0xFFFFFFFF),
            min(info.file_size,     0xFFFFFFFF),
            len(fname_b), len(extra_b), len(comment_b),
            0, 0, info.external_attr,
            min(info.header_offset, 0xFFFFFFFF))
        dst_fp.write(cd + fname_b + extra_b + comment_b)

    cd_size = dst_fp.tell() - cd_start
    n       = len(infolist)

    # ZIP64 EOCD
    z64_off = dst_fp.tell()
    dst_fp.write(struct.pack('<4sQHHIIQQQQ',
        b'PK\x06\x06', 44, (3<<8)|63, 45, 0, 0,
        n, n, cd_size, cd_start))
    # ZIP64 locator
    dst_fp.write(struct.pack('<4sIQI', b'PK\x06\x07', 0, z64_off, 1))
    # EOCD
    dst_fp.write(struct.pack('<4sHHHHIIH',
        b'PK\x05\x06',
        0xFFFF, 0xFFFF,
        min(n, 0xFFFF), min(n, 0xFFFF),
        min(cd_size,   0xFFFFFFFF),
        min(cd_start,  0xFFFFFFFF),
        0))

# ─── KSU Manager APK install snippet (appended to updater-script) ────────────
KSU_EDIFY = r"""
# ── KernelSU Next Manager auto-install ──────────────────────────────────────
ui_print("--------------------------------------------------");
ui_print("  Installing KernelSU Next Manager v3.4.2...");
ui_print("--------------------------------------------------");
package_extract_file("priv-app/KernelSUNext/KernelSUNext.apk", "/tmp/KernelSUNext.apk");
run_program("/sbin/sh", "-c",
  "SYS=$(ls /dev/block/mapper/system 2>/dev/null || ls /dev/block/by-name/system 2>/dev/null); "
  "mkdir -p /tmp/ksu_mnt; "
  "mount -o rw $SYS /tmp/ksu_mnt 2>/dev/null || mount -o remount,rw /system 2>/dev/null; "
  "DEST=/tmp/ksu_mnt/priv-app/KernelSUNext; "
  "[ -d /system/priv-app ] && DEST=/system/priv-app/KernelSUNext; "
  "mkdir -p $DEST; "
  "cp /tmp/KernelSUNext.apk $DEST/KernelSUNext.apk; "
  "chmod 644 $DEST/KernelSUNext.apk; "
  "chown 0:0 $DEST/KernelSUNext.apk; "
  "umount /tmp/ksu_mnt 2>/dev/null; "
  "rm -rf /tmp/KernelSUNext.apk /tmp/ksu_mnt");
ui_print("  KernelSU Next Manager installed successfully.");
ui_print("--------------------------------------------------");
"""

# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    for p, label in [(SRC_ZIP,'ROM zip'), (APK_SRC,'KSU APK')]:
        if not os.path.exists(p): sys.exit(f"❌ {label} not found: {p}")
    if os.path.exists(TMP_ZIP): os.remove(TMP_ZIP)

    apk_data = open(APK_SRC, 'rb').read()
    print(f"APK          : {APK_SRC}  ({human(len(apk_data))})")
    print(f"ROM zip      : {SRC_ZIP}  ({human(os.path.getsize(SRC_ZIP))})")
    print(f"Temp output  : {TMP_ZIP}")
    print()

    t0 = time.time()

    with zipfile.ZipFile(SRC_ZIP, 'r') as zin:
        infolist = zin.infolist()
        total    = len(infolist)
        now      = (2026,11,2,15,0,0)

        with open(SRC_ZIP, 'rb') as raw_fp, open(TMP_ZIP, 'wb') as dst_fp:
            new_list = []

            for idx, info in enumerate(infolist):
                tag = f"[{idx+1:>2}/{total}]"

                if info.filename == 'META-INF/com/google/android/updater-script':
                    # Patch: append KSU install block before set_progress line
                    print(f"{tag} PATCHING   {info.filename}")
                    orig = zin.read(info.filename).decode('utf-8')
                    # Insert before the final set_progress line
                    insert_before = 'set_progress(1.000000);'
                    if insert_before in orig:
                        new_script = orig.replace(insert_before,
                            KSU_EDIFY + insert_before)
                    else:
                        new_script = orig + KSU_EDIFY
                    zi = write_entry_deflated(dst_fp,
                        'META-INF/com/google/android/updater-script',
                        new_script.encode('utf-8'), info.date_time)
                    new_list.append(zi)

                else:
                    sz = human(info.compress_size)
                    print(f"{tag} copying    {info.filename:<55} ({sz})")
                    new_info = copy.copy(info)
                    raw_copy(raw_fp, info.header_offset,
                             info.compress_size, dst_fp, new_info)
                    new_list.append(new_info)

            # ── Add KSU APK ──────────────────────────────────────────────────
            print(f"[{total+1:>2}/{total+1}] ADDING     {APK_DEST}  "
                  f"({human(len(apk_data))})")
            zi = write_entry_stored(dst_fp, APK_DEST, apk_data, now)
            new_list.append(zi)

            print()
            print("Writing central directory …")
            write_central_directory(dst_fp, new_list)

    # Replace original with patched version
    print("Replacing original zip …")
    os.replace(TMP_ZIP, SRC_ZIP)

    elapsed  = time.time() - t0
    out_size = os.path.getsize(SRC_ZIP)
    print()
    print("═" * 62)
    print(f"  ✅  DONE in {elapsed:.1f}s")
    print(f"  Output : {SRC_ZIP}")
    print(f"  Size   : {human(out_size)}")
    print("═" * 62)
    print()
    print("What's in this zip:")
    print("  • Evolution X 17.0 full ROM  (all partitions)")
    print("  • KernelSU-Next v3.4.1       (boot.img)")
    print("  • KernelSU Next Manager APK  (auto-installs to /system/priv-app/)")

if __name__ == '__main__':
    main()
