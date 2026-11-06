# PROJECT AETHER — Reverse Engineering Findings (REA)

> **Phase 0 Reconnaissance Deliverable**
> **Investigation Target:** OnePlus Nord 2 5G (`denniz` / `op6893`)
> **Device Serial:** `[redacted]` (Root shell verified)
> **Audit Date:** 2026-11-06

---

## 1. Verified Evidence Catalog

### 1.1 Live Device Properties (`getprop`)
Every finding below is extracted directly from the connected OnePlus Nord 2 via root ADB shell:

| Property Name | Extracted Value | Significance / Architectural Interpretation |
|---|---|---|
| `ro.product.model` | `DN2103` | European / Global hardware revision of OnePlus Nord 2 5G |
| `ro.product.device` | `denniz` | Official OnePlus device tree codename |
| `ro.evolution.device` | `op6893` | Evolution X common platform tree identifier |
| `ro.evolution.version` | `17.0` | Evolution X 17.x generation |
| `ro.evolution.display.version`| `v12.3-20261024` | Point release version string matching the base ROM zip |
| `ro.build.version.release` | `17` | Base OS release version |
| `ro.build.version.sdk` | `37` | API Level 37 (Android 16 / 17 Canary preview base) |
| `ro.build.display.id` | `CP2A.260605.016 release-keys` | Base AOSP system build identifier |
| `ro.build.fingerprint` | `google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys` | Fingerprint spoofed/inherited from Pixel 6a Canary |
| `ro.surface_flinger.supports_background_blur` | `1` | **Native SurfaceFlinger background blur is globally enabled in build** |
| `debug.renderengine.backend` | `skiaglthreaded` | Multi-threaded Skia OpenGL ES RenderEngine backend in use |
| `ro.opengles.version` | `196610` (`0x30002`) | OpenGL ES 3.2 supported natively |
| `ro.hardware.egl` | `meow` | MediaTek proprietary EGL loader wrapper |
| `ro.hardware.vulkan` | `mali` | ARM Mali Vulkan driver active |
| `ro.vendor.composer_version` | `2.3` | MediaTek HWComposer HAL 2.3 interface |
| `ro.board.platform` | `mt6893` | MediaTek Dimensity 1200 SoC platform |

---

## 2. SystemUI Binary Inspection

### 2.1 APK Identification & Integrity
- **Physical Device Path:** `/system_ext/priv-app/SystemUIGoogle/SystemUIGoogle.apk`
- **File Size:** `60,945,779 bytes` (~58.12 MiB)
- **SHA-256 Checksum:** `2874215b61dfebcff6f73ab4a14e49d6e3bacc2ff79d2b6371ee24471b1dbe2e`
- **Package Manager Record:**
  - `codePath=/system_ext/priv-app/SystemUIGoogle`
  - `versionCode=37 minSdk=37 targetSdk=37`
  - `versionName=17`
  - `splits=[base]`

### 2.2 DEX Archive Analysis
Inspection of the compiled Dalvik bytecode revealed three distinct class archives:
1. **`classes.dex` (11,847,592 bytes):**
   - **AxionOS `AxBlur` Framework:**
     - `Lcom/android/axion/blur/BlurEngine;`
     - `Lcom/android/axion/blur/AxBlurSupport;`
     - `Lcom/android/axion/blur/AxBlurSurfaceKt;`
     - `Lcom/android/axion/blur/AxBlurProperties;`
     - `Lcom/android/axion/blur/AxBlurFrameTrackingNode;`
   - **Jetpack Compose SystemUI Runtime:** Compose UI elements used for lockscreen widgets and quick-look cards.
2. **`classes2.dex` (10,559,472 bytes):**
   - **Quick Settings Implementation:**
     - `Lcom/android/systemui/qs/tileimpl/QSTileViewImpl;`
     - `Lcom/android/systemui/qs/tiles/base/ui/viewmodel/QSTileViewModelImpl;`
     - `Lcom/android/systemui/qs/tiles/BlurTile;` (Dedicated tile to toggle blur)
   - **Window & Scrim Blur Repositories:**
     - `Lcom/android/systemui/window/data/repository/WindowRootViewBlurRepositoryImpl;`
     - `Lcom/android/systemui/window/domain/interactor/WindowRootViewBlurInteractor;`
     - `Lcom/android/systemui/window/ui/DefaultBlurChoreographer;`
3. **`classes3.dex` (9,405,824 bytes):**
   - **Volume UI Architecture:**
     - `Lcom/android/systemui/volume/dialog/ui/binder/VolumeDialogViewBinder;`
     - `Lcom/android/systemui/volume/dialog/ui/viewmodel/VolumeDialogViewModel;`
     - `Lcom/android/systemui/volume/dialog/sliders/domain/interactor/VolumeDialogSliderInputEventsInteractor;`

---

## 3. Live Configuration Settings (`settings get`)

Queries executed against the live system settings provider yielded exact Evolution X runtime flags:

| Namespace | Setting Key | Live Value | Impact on UI Presentation |
|---|---|---|---|
| `global` | `disable_window_blurs` | `0` | Window blurs are explicitly active (not disabled) |
| `system` | `qs_show_volume_slider` | `3` | Dual slider mode active in QS (Brightness + Volume) |
| `system` | `qs_tile_icon_shape` | `circle` | QS tiles render as circular lens icons |
| `system` | `qs_tile_label_hide` | `1` | QS tile text labels hidden (icon-only circular grid) |
| `system` | `qs_tiles_columns` | `4` | 4 columns per row |
| `system` | `qs_tiles_rows` | `4` | 4 rows visible (16 tiles total on page 1) |
| `system` | `qs_panel_style` | `1` | Evolution X custom QS panel backdrop styling |
| `system` | `qs_widget_panel` | `1` | QS widget panel enabled |
| `system` | `qs_brightness_slider_shape` | `1` | Custom brightness slider rounded rectangle shape |
| `secure` | `theme_customization_overlay_packages` | Contains `RAINBOW`, `96CBFF`, `lockscreen_clock_font: ios` | Dynamic accent color `#96CBFF` with iOS lockscreen clock |

---

## 4. Active Runtime Resource Overlays (RROs)

From `adb shell cmd overlay list`, the active overlays targeting SystemUI are:
- `[x] com.google.android.systemui.overlay.glanceablehubconfig`
- `[x] com.android.systemui.auto_generated_rro_product__`
- `[x] com.android.systemui.wifibar_i` (iOS-style Wi-Fi icon overlay)
- `[x] com.android.systemui.signalbar_ar` (Custom cellular signal icon overlay)
- `[x] com.android.systemui:accent` / `com.android.systemui:dynamic` (Material You dynamic theme overlays)
- `[x] com.android.systemui.hide.smartspace` (Smartspace hidden on lockscreen)

---

## 5. Source Tree & Upstream Mapping

Cross-referencing ROM build properties with Evolution X GitHub manifests:
- **Upstream Organization:** `https://github.com/Evolution-X`
- **Device Tree:** `Evolution-X-Devices/device_oplus_op6893` (Branch: `cnb` / `bka`)
- **Manifest Revision:** `Evolution-X/manifest` branch `cnb` (Commit `2b9e7c7f`: *"manifest: Initialize for Evolution X 12.x+"*)
- **Framework Source:** `Evolution-X/frameworks_base` (Branch: `cnb`)
- **Blur Engine Source:** Forked from `AxionOS/vendor_extras_sdk_ax_blur` and embedded into `SystemUIGoogle`.
