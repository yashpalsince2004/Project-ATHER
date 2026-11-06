#!/usr/bin/env python3
"""
resize_bootanimation.py
=======================
Scales the Windows 11 boot animation by 2.0x to native 1080x2400 (OnePlus Nord 2):
  - Original content: 224x568 (tiny on 1080x2400)
  - 2.0x scaled content: 448x1136 (perfect proportion)
  - Output canvas: 1080x2400 (60 fps)
  - All frames compressed with ZIP_STORED (required by Android bootanimation)
"""

import io
import os
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

SRC_ANIM  = "bootanimation.zip"
OUT_ANIM  = "bootanimation_2x.zip"
TARGET_W  = 1080
TARGET_H  = 2400
SCALE     = 2.0

# Center of original animation in 1080x1920:
CENTER_X  = 552
CENTER_Y  = 1004

CROP_W    = int(TARGET_W / SCALE)   # 540
CROP_H    = int(TARGET_H / SCALE)   # 1200
LEFT      = int(CENTER_X - CROP_W / 2)  # 282
TOP       = int(CENTER_Y - CROP_H / 2)  # 404
CROP_BOX  = (LEFT, TOP, LEFT + CROP_W, TOP + CROP_H)

def process_frame(args):
    filename, raw_bytes = args
    img = Image.open(io.BytesIO(raw_bytes))
    cropped = img.crop(CROP_BOX)
    resized = cropped.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)

    out_buf = io.BytesIO()
    resized.save(out_buf, format='JPEG', quality=95)
    return filename, out_buf.getvalue()

def main():
    if not os.path.exists(SRC_ANIM):
        sys.exit(f"❌ Missing {SRC_ANIM}")

    print(f"Loading {SRC_ANIM} …")
    t0 = time.time()

    with zipfile.ZipFile(SRC_ANIM, 'r') as zin:
        names = zin.namelist()
        img_tasks = []
        for name in names:
            if name.endswith('.jpg'):
                img_tasks.append((name, zin.read(name)))

    print(f"Resizing {len(img_tasks)} frames by {SCALE}x to {TARGET_W}x{TARGET_H} …")
    with ProcessPoolExecutor() as pool:
        results = list(pool.map(process_frame, img_tasks, chunksize=16))

    print(f"Writing {OUT_ANIM} with ZIP_STORED …")
    if os.path.exists(OUT_ANIM):
        os.remove(OUT_ANIM)

    desc_content = f"{TARGET_W} {TARGET_H} 60\np 1 0 part0 000000\np 0 0 part1 000000\n"

    with zipfile.ZipFile(OUT_ANIM, 'w', compression=zipfile.ZIP_STORED) as zout:
        # Write desc.txt first
        zi_desc = zipfile.ZipInfo("desc.txt")
        zi_desc.compress_type = zipfile.ZIP_STORED
        zout.writestr(zi_desc, desc_content.encode('utf-8'))

        # Write part0/ and part1/ directories
        for d in ["part0/", "part1/"]:
            zi_dir = zipfile.ZipInfo(d)
            zi_dir.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi_dir, b"")

        # Write all frames
        for name, data in results:
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_STORED
            zout.writestr(zi, data)

    elapsed = time.time() - t0
    in_size  = os.path.getsize(SRC_ANIM)
    out_size = os.path.getsize(OUT_ANIM)
    print()
    print("═" * 60)
    print(f"  ✅  SCALED 2.0x IN {elapsed:.1f}s")
    print(f"  Canvas  : {TARGET_W}x{TARGET_H} @ 60fps")
    print(f"  Input   : {in_size / (1024*1024):.1f} MB")
    print(f"  Output  : {out_size / (1024*1024):.1f} MB ({OUT_ANIM})")
    print("═" * 60)

if __name__ == '__main__':
    main()
