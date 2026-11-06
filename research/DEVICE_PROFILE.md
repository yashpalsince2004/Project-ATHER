# PROJECT AETHER — Device Profile

> [!NOTE]
> Generated: 2026-11-06 | Status: **100% VERIFIED LIVE REA (ADB ROOT ACCESS)**
> Device Serial: `[redacted]` | Target Product: `DN2103` (`denniz`) | Platform: `op6893` / `mt6893`

---

## 1. Device Identification

| Property | Value | Source / Evidence | Confidence |
|---|---|---|---|
| **Marketing Name** | OnePlus Nord 2 5G | Commercial specification / AnyKernel3 banner | ✅ 100% |
| **Model Number** | `DN2103` (European / Global variant) | `ro.product.model=DN2103`, `getprop ro.product.name` | ✅ 100% |
| **Device Codename** | `denniz` | `ro.product.device=denniz`, `ro.build.product=denniz` | ✅ 100% |
| **Platform Codename** | `op6893` | `ro.evolution.device=op6893`, `ro.lineage.device=op6893` | ✅ 100% |
| **Hardware Platform** | MediaTek MT6893 (Dimensity 1200 5G) | `ro.board.platform=mt6893`, `ro.hardware=mt6893` | ✅ 100% |
| **Hardware Brand** | MTK / OnePlus | `[Build.BRAND]: [MTK]`, `ro.product.brand=OnePlus` | ✅ 100% |
| **Unified Device Group** | `denniz`, `OP515BL1`, `cupida`, `RMX3031`, `RMX3033` | ROM `updater-script` assert rule | ✅ 100% |

---

## 2. Software Identification

| Property | Value | Source / Evidence | Confidence |
|---|---|---|---|
| **ROM Name** | Evolution X 17.0 (Unofficial) | `ro.evolution.version=17.0`, `ro.evolution.build.version` | ✅ 100% |
| **Evolution X Release** | Version 12.3 (Iteration 12.3-20261024) | `ro.evolution.display.version=v12.3-20261024`, `ro.modversion=12.3` | ✅ 100% |
| **Android Version** | 17 (CinnamonBun / Baklava-based preview base) | `ro.build.version.release=17`, `ro.build.version.release_or_codename=17` | ✅ 100% |
| **SDK / API Level** | **37** (`SDK 37.0`) | `ro.build.version.sdk=37`, `ro.build.version.sdk_full=37.0` | ✅ 100% |
| **Build Fingerprint** | `google/bluejay_beta/bluejay:CANARY/ZP11.260918.007/16484274:user/release-keys` | `ro.build.fingerprint` | ✅ 100% |
| **Build Display ID** | `CP2A.260605.016 release-keys` | `ro.build.display.id` | ✅ 100% |
| **Build Timestamp** | Sat Oct 24 09:44:21 UTC 2026 (`1792835061`) | `ro.build.date.utc=1792835061` | ✅ 100% |
| **Security Patch** | `2026-10-01` (Vendor: `2025-07-05`) | `ro.build.version.security_patch` | ✅ 100% |
| **Build Type / Tags** | `userdebug` / `release-keys` | `ro.build.type=userdebug`, `ro.build.flavor=op6893-userdebug` | ✅ 100% |
| **Build Host** | `r-ab1c977a60d69076-p6qm` by `android-build` | `ro.build.host`, `ro.build.user` | ✅ 100% |
| **Active Kernel** | Linux 4.19.325-cip127-st11-g0def37f3c72d | `cat /proc/version`, `uname -a` (SMP PREEMPT aarch64) | ✅ 100% |
| **Root Solution** | KernelSU Next v3.4.1 + SuSFS v2.2.0 | `anykernel.sh`, `com.rifsxd.ksunext` package installed | ✅ 100% |

---

## 3. Display & Metrics (Verified from WindowManager & SurfaceFlinger)

| Property | Value | Evidence Source | Confidence |
|---|---|---|---|
| **Physical Resolution** | **1080 × 2400** pixels | `adb shell wm size` -> `Physical size: 1080x2400` | ✅ 100% |
| **Aspect Ratio** | 20:9 | 2400 / 1080 | ✅ 100% |
| **Screen Density** | **480 dpi** (xxhdpi) | `adb shell wm density` -> `Physical density: 480` | ✅ 100% |
| **Panel Technology** | Fluid AMOLED (6.43" diagonal) | Hardware specs, optical UDFPS present | ✅ 100% |
| **Peak Refresh Rate** | **90.0 Hz** | `dumpsys display` -> `mDefaultPeakRefreshRate: 90.0` | ✅ 100% |
| **Supported Modes** | `[90.0, 60.0, 45.0, 30.0, 22.5, 20.0]` Hz | `dumpsys display` -> `mSupportedRefreshRates` | ✅ 100% |
| **Color Support** | Wide Color supported (Managed, Native Mode 0) | `dumpsys SurfaceFlinger` -> `Device supports wide color: 1` | ✅ 100% |
| **HDR Standards** | HDR10, HDR10+, HLG (Metadata v7) | `dumpsys SurfaceFlinger` -> `hdr10plus=true hdr10=true hlg=true` | ✅ 100% |
| **Biometrics** | Under-Display Fingerprint Sensor (Optical) | `dumpsys display` -> `UdfpsObserver`, lockscreen UI | ✅ 100% |

---

## 4. GPU & Rendering Hardware (Verified from Dumpsys GPU & Driver)

| Property | Value | Evidence Source | Confidence |
|---|---|---|---|
| **GPU Model** | ARM Mali-G77 MC9 (9 Shader Cores) | MT6893 BSP specification, `ro.hardware.vulkan=mali` | ✅ 100% |
| **GPU Architecture** | Valhall (1st Gen) | ARM Mali hardware architecture | ✅ 100% |
| **Graphics Driver** | `com.mediatek.mt6893.gamedriver` | `dumpsys gpu` -> `Stable Game Driver: com.mediatek.mt6893.gamedriver` | ✅ 100% |
| **OpenGL ES Version** | **3.2** (`196610` = `0x30002`) | `ro.opengles.version=196610`, `dumpsys gpu` | ✅ 100% |
| **Vulkan API Version** | **1.1.0** (`4198400` = `0x401000`) | `dumpsys gpu` -> `vulkanVersion = 4198400` | ✅ 100% |
| **EGL Hardware Impl** | `meow` | `ro.hardware.egl=meow` | ✅ 100% |
| **HWComposer Version** | **HWC 2.3** | `ro.vendor.composer_version=2.3` | ✅ 100% |
| **RenderEngine Backend** | **`skiaglthreaded`** | `debug.renderengine.backend=skiaglthreaded` | ✅ 100% |
| **SF Blur Algorithm** | **`KawaseDualFilterV2`** | `dumpsys SurfaceFlinger` -> `RenderEngine chosen blur algorithm: KawaseDualFilterV2` | ✅ 100% |
| **SF Blur Capability** | **ENABLED (`1`)** | `ro.surface_flinger.supports_background_blur=1` | ✅ 100% |
| **Window Blur Policy** | **Active (`0`)** | `settings get global disable_window_blurs=0` | ✅ 100% |
| **Current GPU Memory** | ~277.7 MB allocated globally across procs | `dumpsys gpu` -> `Global total: 277741568` | ✅ 100% |

---

## 5. Memory Configuration (Verified from `/proc/meminfo`)

| Metric | Raw Value (kB) | Formatted Size | Notes |
|---|---|---|---|
| **Total RAM** | `7,660,416 kB` | **~7.30 GiB (~8.0 GB Physical)** | 8 GB LPDDR4X variant |
| **Available RAM** | `2,446,624 kB` | **~2.33 GiB** | Ample headroom for SystemUI effects |
| **Cached Memory** | `1,762,748 kB` | **~1.68 GiB** | Page cache and buffer allocations |
| **Free RAM** | `263,640 kB` | **~257.5 MiB** | Direct unallocated free memory |
| **Skia GPU Cache Cap** | `36,290,560 B` | **34.61 MiB limit** | Context cache in SurfaceFlinger |
| **Current Skia Cache** | `21,299,232 B` | **20.31 MiB (17.79 MiB purgeable)** | Active texture/stencil cache |

---

## 6. Partition Scheme & Storage Map (Non-A/B Super Partition)

The device uses a **Dynamic Partitions (Super Partition)** layout on a single slot (`IS_SLOT_DEVICE=0` / `ro.build.ab_update=false`):

| Partition | Block Size (Bytes) | Size (GB) | Filesystem / Content |
|---|---|---|---|
| `system` | 1,095,008,256 | ~1.02 GB | Android OS Core Framework & Daemons |
| `system_ext` | 1,751,605,248 | ~1.63 GB | **Hosts `SystemUIGoogle.apk`** |
| `product` | 3,094,822,912 | ~2.88 GB | Google Apps & Product Overlays |
| `vendor` | 724,254,720 | ~690 MB | MediaTek HALs, Driver Blobs, HWC 2.3 |
| `odm` | 1,359,384,576 | ~1.27 GB | Device/OEM Customizations & Sensors |
| **Total Super (Group main)** | **10,196,353,024** | **~9.50 GB** | Super Partition Group Limit |
| `boot` | 33,554,432 | 32.0 MB | Linux 4.19 Kernel + KernelSU ramdisk |
