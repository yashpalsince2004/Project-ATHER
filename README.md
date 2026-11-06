# Project AETHER

Project AETHER explores a native, glass-style rendering engine for Evolution X on the OnePlus Nord 2 5G (`denniz` / `op6893`). The current work is a reverse-engineering and implementation plan for extending the existing AxBlur path in SystemUI.

## Repository contents

- `research/`: device and SystemUI architecture notes, findings, implementation gaps, and rendering research.
- `build_boot.py`, `inject_*.py`, `package_custom_rom.py`, `resize_bootanimation.py`: local ROM and boot-image tooling.
- `*.png`: project screenshots and visual references.

Large ROM builds, boot images, APKs, downloaded flashable modules, and raw device dumps are intentionally kept out of Git. The build scripts expect their input artifacts to be available locally. See each script's constants for the expected filenames.

## Current status

The AETHER implementation is at reconnaissance and planning stage. The proposed engine and integration sequence are documented in [`research/AETHER_IMPLEMENTATION_PLAN.md`](research/AETHER_IMPLEMENTATION_PLAN.md), with findings and known gaps in the adjacent research notes.

## Device target

OnePlus Nord 2 5G, codename `denniz`, platform `op6893` / `mt6893`.
