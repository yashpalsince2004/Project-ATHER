#!/usr/bin/env python3
"""
package_custom_rom.py
======================
Builds the complete custom Evolution X flashable ZIP for OnePlus Nord 2 (MT6893) with:
  1. KernelSU-Next v3.4.1 + SuSFS v2.2.0 kernel embedded in boot.img
  2. KernelSU Next Manager v3.4.2 APK pre-packaged
  3. Google Camera (AGC 8.4 BigKaka) APK pre-packaged
  4. Windows 11 Custom Boot Animation (1080p 60fps) pre-packaged
  5. OnePlus Camera (OplusCamera.apk) preserved in system_ext
  6. All Google Apps (GApps) 100% preserved in product and system
  7. Automated installation script for recovery (TWRP/OrangeFox)
"""

import copy
import io
import os
import struct
import sys
import time
import zipfile
import zlib

SRC_ZIP       = "EvolutionX-17.0-20261024-op6893-12.3-Unofficial.zip"
NEW_BOOT      = "boot_ksu.img"
KSU_APK       = "KernelSU_Next_v3.4.2_33355-release.apk"
GCAM_APK      = "AGC8.4.300_V15.1.apk"
BOOTANIM_SRC  = "bootanimation.zip"
OUT_ZIP       = "EvolutionX-17.0-KSU-Next-op6893-12.3-Unofficial.zip"
TMP_ZIP       = OUT_ZIP + ".tmp"
CHUNK         = 64 * 1024 * 1024

def human(n):
    for u in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def local_header_size(raw_fp, offset):
    raw_fp.seek(offset + 26)
    fn, ex = struct.unpack('<HH', raw_fp.read(4))
    return 30 + fn + ex

def copy_raw_entry(raw_fp, old_off, c_size, dst_fp, info):
    lh_sz = local_header_size(raw_fp, old_off)
    total = lh_sz + c_size
    info.header_offset = dst_fp.tell()
    raw_fp.seek(old_off)
    rem = total
    while rem:
        buf = raw_fp.read(min(CHUNK, rem))
        if not buf:
            raise EOFError("Truncated zip entry")
        dst_fp.write(buf)
        rem -= len(buf)
    if info.flag_bits & 0x08:
        sig = raw_fp.read(4)
        if sig == b'PK\x07\x08':
            dst_fp.write(sig + raw_fp.read(16))
        else:
            raw_fp.seek(-4, 1)

def write_entry_stored(dst_fp, arcname, data, dt):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    fname_b = arcname.encode('utf-8')
    extra_b = b''
    need64 = len(data) > 0xFFFFFFFF
    if need64:
        extra_b = struct.pack('<HHQQ', 1, 16, len(data), len(data))

    lh = struct.pack('<4sHHHHHIIIHH',
        b'PK\x03\x04',
        45 if need64 else 20,
        0, 0,
        dt[3] * 2048 + dt[4] * 32 + (dt[5] // 2),
        (dt[0] - 1980) * 512 + dt[1] * 32 + dt[2],
        crc,
        0xFFFFFFFF if need64 else len(data),
        0xFFFFFFFF if need64 else len(data),
        len(fname_b),
        len(extra_b))

    offset = dst_fp.tell()
    dst_fp.write(lh + fname_b + extra_b)
    pos = 0
    while pos < len(data):
        dst_fp.write(data[pos:pos+CHUNK])
        pos += CHUNK

    zi = zipfile.ZipInfo(arcname, dt)
    zi.compress_type = zipfile.ZIP_STORED
    zi.CRC = crc
    zi.file_size = len(data)
    zi.compress_size = len(data)
    zi.header_offset = offset
    zi.flag_bits = 0
    zi.external_attr = 0o100644 << 16
    return zi

def write_entry_deflated(dst_fp, arcname, data, dt):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    compressed = zlib.compress(data, 6)[2:-4]
    fname_b = arcname.encode('utf-8')
    extra_b = b''
    lh = struct.pack('<4sHHHHHIIIHH',
        b'PK\x03\x04',
        20, 0, 8,
        dt[3] * 2048 + dt[4] * 32 + (dt[5] // 2),
        (dt[0] - 1980) * 512 + dt[1] * 32 + dt[2],
        crc,
        len(compressed),
        len(data),
        len(fname_b),
        len(extra_b))
    offset = dst_fp.tell()
    dst_fp.write(lh + fname_b + extra_b + compressed)

    zi = zipfile.ZipInfo(arcname, dt)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.CRC = crc
    zi.file_size = len(data)
    zi.compress_size = len(compressed)
    zi.header_offset = offset
    zi.flag_bits = 0
    zi.external_attr = 0o100644 << 16
    return zi

def write_central_directory(dst_fp, infolist):
    cd_start = dst_fp.tell()
    for info in infolist:
        fname_b = info.filename.encode('utf-8')
        dt = info.date_time
        dostime = dt[3] * 2048 + dt[4] * 32 + (dt[5] // 2)
        dosdate = (dt[0] - 1980) * 512 + dt[1] * 32 + dt[2]
        need64 = (info.file_size > 0xFFFFFFFF or
                  info.compress_size > 0xFFFFFFFF or
                  info.header_offset > 0xFFFFFFFF)
        extra_b = b''
        if need64:
            extra_b = struct.pack('<HHQQQ', 1, 24,
                info.file_size, info.compress_size, info.header_offset)
        comment_b = b''
        cd = struct.pack('<4sHHHHHHIIIHHHHHII',
            b'PK\x01\x02',
            (3 << 8) | 63,
            45 if need64 else 20,
            getattr(info, 'flag_bits', 0) & ~0x08,
            info.compress_type,
            dostime, dosdate,
            info.CRC & 0xFFFFFFFF,
            min(info.compress_size, 0xFFFFFFFF),
            min(info.file_size, 0xFFFFFFFF),
            len(fname_b), len(extra_b), len(comment_b),
            0, 0, info.external_attr,
            min(info.header_offset, 0xFFFFFFFF))
        dst_fp.write(cd + fname_b + extra_b + comment_b)

    cd_size = dst_fp.tell() - cd_start
    n = len(infolist)

    z64_off = dst_fp.tell()
    dst_fp.write(struct.pack('<4sQHHIIQQQQ',
        b'PK\x06\x06', 44, (3 << 8) | 63, 45, 0, 0,
        n, n, cd_size, cd_start))
    dst_fp.write(struct.pack('<4sIQI', b'PK\x06\x07', 0, z64_off, 1))
    dst_fp.write(struct.pack('<4sHHHHIIH',
        b'PK\x05\x06',
        0xFFFF, 0xFFFF,
        min(n, 0xFFFF), min(n, 0xFFFF),
        min(cd_size, 0xFFFFFFFF),
        min(cd_start, 0xFFFFFFFF),
        0))

CUSTOM_MODS_EDIFY = r"""
# ── Custom Mods Auto-Install (KernelSU Next + GCam + Windows 11 Bootanim) ───
ui_print("--------------------------------------------------");
ui_print("  Installing Custom Mods & Apps...");
ui_print("    [*] KernelSU Next Manager v3.4.2");
ui_print("    [*] Google Camera (AGC 8.4 BigKaka)");
ui_print("    [*] Windows 11 Custom Boot Animation");
ui_print("--------------------------------------------------");
package_extract_file("priv-app/KernelSUNext/KernelSUNext.apk", "/tmp/KernelSUNext.apk");
package_extract_file("priv-app/GoogleCamera/GoogleCamera.apk", "/tmp/GoogleCamera.apk");
package_extract_file("media/bootanimation.zip", "/tmp/bootanimation.zip");
run_program("/sbin/sh", "-c",
  "mount_part() { "
  "  local name=\"$1\"; local mnt=\"$2\"; mkdir -p \"$mnt\"; "
  "  for dev in /dev/block/mapper/$name* /dev/block/by-name/$name*; do "
  "    if [ -b \"$dev\" ]; then "
  "      mount -o rw \"$dev\" \"$mnt\" 2>/dev/null && return 0; "
  "    fi; "
  "  done; "
  "  return 1; "
  "}; "
  "SYS_MNT=''; "
  "for d in /system /system_root /mnt/system; do "
  "  if [ -d \"$d/priv-app\" ]; then "
  "    mount -o remount,rw \"$d\" 2>/dev/null; "
  "    SYS_MNT=\"$d\"; "
  "    break; "
  "  fi; "
  "done; "
  "if [ -z \"$SYS_MNT\" ]; then "
  "  if mount_part system /tmp/sys_mnt; then "
  "    if [ -d /tmp/sys_mnt/priv-app ]; then "
  "      SYS_MNT=/tmp/sys_mnt; "
  "    elif [ -d /tmp/sys_mnt/system/priv-app ]; then "
  "      SYS_MNT=/tmp/sys_mnt/system; "
  "    fi; "
  "  fi; "
  "fi; "
  "if [ -n \"$SYS_MNT\" ]; then "
  "  mkdir -p \"$SYS_MNT/priv-app/KernelSUNext\"; "
  "  cp -f /tmp/KernelSUNext.apk \"$SYS_MNT/priv-app/KernelSUNext/KernelSUNext.apk\"; "
  "  chmod 755 \"$SYS_MNT/priv-app/KernelSUNext\"; "
  "  chmod 644 \"$SYS_MNT/priv-app/KernelSUNext/KernelSUNext.apk\"; "
  "  chown -R 0:0 \"$SYS_MNT/priv-app/KernelSUNext\"; "
  "  mkdir -p \"$SYS_MNT/priv-app/GoogleCamera\"; "
  "  cp -f /tmp/GoogleCamera.apk \"$SYS_MNT/priv-app/GoogleCamera/GoogleCamera.apk\"; "
  "  chmod 755 \"$SYS_MNT/priv-app/GoogleCamera\"; "
  "  chmod 644 \"$SYS_MNT/priv-app/GoogleCamera/GoogleCamera.apk\"; "
  "  chown -R 0:0 \"$SYS_MNT/priv-app/GoogleCamera\"; "
  "  mkdir -p \"$SYS_MNT/media\"; "
  "  cp -f /tmp/bootanimation.zip \"$SYS_MNT/media/bootanimation.zip\"; "
  "  chmod 755 \"$SYS_MNT/media\"; "
  "  chmod 644 \"$SYS_MNT/media/bootanimation.zip\"; "
  "  chown -R 0:0 \"$SYS_MNT/media\"; "
  "fi; "
  "PROD_MNT=''; "
  "for d in /product /mnt/product; do "
  "  if [ -d \"$d/media\" ] || [ -d \"$d/etc\" ]; then "
  "    mount -o remount,rw \"$d\" 2>/dev/null; "
  "    PROD_MNT=\"$d\"; "
  "    break; "
  "  fi; "
  "done; "
  "if [ -z \"$PROD_MNT\" ]; then "
  "  if mount_part product /tmp/prod_mnt; then "
  "    PROD_MNT=/tmp/prod_mnt; "
  "  fi; "
  "fi; "
  "if [ -n \"$PROD_MNT\" ]; then "
  "  mkdir -p \"$PROD_MNT/media\"; "
  "  cp -f /tmp/bootanimation.zip \"$PROD_MNT/media/bootanimation.zip\"; "
  "  chmod 755 \"$PROD_MNT/media\"; "
  "  chmod 644 \"$PROD_MNT/media/bootanimation.zip\"; "
  "  chown -R 0:0 \"$PROD_MNT/media\"; "
  "  [ \"$PROD_MNT\" = '/tmp/prod_mnt' ] && umount /tmp/prod_mnt 2>/dev/null; "
  "fi; "
  "if mount_part system_ext /tmp/sext_mnt; then "
  "  mkdir -p /tmp/sext_mnt/media; "
  "  cp -f /tmp/bootanimation.zip /tmp/sext_mnt/media/bootanimation.zip; "
  "  chmod 755 /tmp/sext_mnt/media; "
  "  chmod 644 /tmp/sext_mnt/media/bootanimation.zip; "
  "  chown -R 0:0 /tmp/sext_mnt/media; "
  "  umount /tmp/sext_mnt 2>/dev/null; "
  "fi; "
  "[ \"$SYS_MNT\" = '/tmp/sys_mnt' ] && umount /tmp/sys_mnt 2>/dev/null; "
  "rm -rf /tmp/KernelSUNext.apk /tmp/GoogleCamera.apk /tmp/bootanimation.zip /tmp/sys_mnt /tmp/prod_mnt /tmp/sext_mnt");
ui_print("  Custom apps & boot animation installed successfully.");
ui_print("--------------------------------------------------");
"""

def main():
    for f in [SRC_ZIP, NEW_BOOT, KSU_APK, GCAM_APK, BOOTANIM_SRC]:
        if not os.path.exists(f):
            sys.exit(f"❌ Missing file: {f}")

    if os.path.exists(TMP_ZIP):
        os.remove(TMP_ZIP)

    print("══════════════════════════════════════════════════════════════════════")
    print("  Evolution X Custom ROM Builder (OnePlus Nord 2 / MT6893)")
    print("══════════════════════════════════════════════════════════════════════")
    print(f"Base ROM      : {SRC_ZIP} ({human(os.path.getsize(SRC_ZIP))})")
    print(f"Custom Boot   : {NEW_BOOT} ({human(os.path.getsize(NEW_BOOT))})")
    print(f"KSU APK       : {KSU_APK} ({human(os.path.getsize(KSU_APK))})")
    print(f"GCam APK      : {GCAM_APK} ({human(os.path.getsize(GCAM_APK))})")
    print(f"Boot Animation: {BOOTANIM_SRC} ({human(os.path.getsize(BOOTANIM_SRC))})")
    print(f"Target Output : {OUT_ZIP}")
    print()

    boot_data     = open(NEW_BOOT, 'rb').read()
    ksu_data      = open(KSU_APK, 'rb').read()
    gcam_data     = open(GCAM_APK, 'rb').read()
    bootanim_data = open(BOOTANIM_SRC, 'rb').read()

    now = (2026, 11, 2, 16, 0, 0)
    t0 = time.time()

    with zipfile.ZipFile(SRC_ZIP, 'r') as zin:
        infolist = zin.infolist()
        total = len(infolist)

        with open(SRC_ZIP, 'rb') as raw_fp, open(TMP_ZIP, 'wb') as dst_fp:
            new_list = []

            for idx, info in enumerate(infolist):
                tag = f"[{idx+1:>2}/{total}]"

                if info.filename == 'boot.img':
                    print(f"{tag} REPLACING  boot.img with KernelSU-Next ({human(len(boot_data))})")
                    zi = write_entry_stored(dst_fp, 'boot.img', boot_data, info.date_time)
                    new_list.append(zi)

                elif info.filename == 'META-INF/com/google/android/updater-script':
                    print(f"{tag} PATCHING   {info.filename} with Custom Mods hook")
                    orig = zin.read(info.filename).decode('utf-8')
                    insert_before = 'set_progress(1.000000);'
                    if insert_before in orig:
                        new_script = orig.replace(insert_before, CUSTOM_MODS_EDIFY + insert_before)
                    else:
                        new_script = orig + CUSTOM_MODS_EDIFY
                    zi = write_entry_deflated(dst_fp, info.filename, new_script.encode('utf-8'), info.date_time)
                    new_list.append(zi)

                else:
                    sz = human(info.compress_size)
                    print(f"{tag} copying    {info.filename:<52} ({sz})")
                    new_info = copy.copy(info)
                    copy_raw_entry(raw_fp, info.header_offset, info.compress_size, dst_fp, new_info)
                    new_list.append(new_info)

            # Add KernelSU Manager APK
            print(f"[{total+1:>2}/{total+3}] ADDING     priv-app/KernelSUNext/KernelSUNext.apk ({human(len(ksu_data))})")
            zi_ksu = write_entry_stored(dst_fp, 'priv-app/KernelSUNext/KernelSUNext.apk', ksu_data, now)
            new_list.append(zi_ksu)

            # Add Google Camera APK
            print(f"[{total+2:>2}/{total+3}] ADDING     priv-app/GoogleCamera/GoogleCamera.apk ({human(len(gcam_data))})")
            zi_gcam = write_entry_stored(dst_fp, 'priv-app/GoogleCamera/GoogleCamera.apk', gcam_data, now)
            new_list.append(zi_gcam)

            # Add Windows 11 Boot Animation
            print(f"[{total+3:>2}/{total+3}] ADDING     media/bootanimation.zip ({human(len(bootanim_data))})")
            zi_anim = write_entry_stored(dst_fp, 'media/bootanimation.zip', bootanim_data, now)
            new_list.append(zi_anim)

            print()
            print("Writing central directory …")
            write_central_directory(dst_fp, new_list)

    print(f"Moving {TMP_ZIP} → {OUT_ZIP} …")
    os.replace(TMP_ZIP, OUT_ZIP)

    elapsed = time.time() - t0
    final_size = os.path.getsize(OUT_ZIP)
    print()
    print("═" * 70)
    print(f"  ✅  CUSTOM ROM WITH BOOT ANIMATION BUILT in {elapsed:.1f}s")
    print(f"  Output : {OUT_ZIP}")
    print(f"  Size   : {human(final_size)}")
    print("═" * 70)

if __name__ == '__main__':
    main()
