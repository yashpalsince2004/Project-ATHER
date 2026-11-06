# PROJECT AETHER — Implementation Plan

> **Objective:** Build a native AETHER Glass Engine extending Evolution X's `AxBlur` framework to deliver Apple-inspired "Liquid Glass" on OnePlus Nord 2 5G (`denniz`/`op6893`).
>
> **Strategy:** Path A — Framework-Level Native Engine in `SystemUIGoogle` (recommended by REA)
>
> **Base:** Evolution X 17.0 v12.3 | Android 17 (SDK 37) | SystemUIGoogle + Axion `AxBlur` + `skiaglthreaded` RenderEngine

---

## 1. Architectural Principles (Deep Module Design)

| Principle | Application to AETHER |
|-----------|----------------------|
| **Depth** | Single `AetherGlassEngine` interface hides multi-pass AGSL shaders, normal map generation, thermal LOD, and framebuffer fetch logic |
| **Seam Placement** | Hook at `AxBlurEngine` extension point + `QSTileViewImpl`/`BrightnessSliderView`/`VolumeDialogViewBinder` drawable substitution |
| **Leverage** | One engine drives QS tiles, sliders, volume dialog, lockscreen media, notifications — all reuse the same refractive material |
| **Locality** | All glass logic in `com.aether.glass.*`; callers only know `AetherGlassDrawable` interface |
| **Testability** | `AetherGlassShader` is a pure function (inputs → fragment color); `AetherGlassDrawable` accepts `ShaderProvider` for faking in tests |

---

## 2. Module Architecture

```
com.aether.glass
├── AetherGlassEngine          # Main entry point (Deep Module Interface)
│   ├── configure(context, config)
│   ├── createDrawable(type)   # Returns AetherGlassDrawable
│   ├── setThermalState(state) # Thermal LOD callback
│   └── release()
│
├── shader
│   ├── AetherGlassShader      # AGSL source + RuntimeShader builder (Pure Function)
│   ├── GlassShaderParams      # Data class: curvature, ior, dispersion, bevel, tint
│   └── NormalMapGenerator     # SDF → Normal map for lens shapes (circle, capsule, rect)
│
├── drawable
│   ├── AetherGlassDrawable    # Implements Drawable, binds RuntimeShader + framebuffer fetch
│   ├── TileGlassDrawable      # Circular convex lens for QS tiles
│   ├── SliderGlassDrawable    # Capsule with fluid meniscus for brightness/volume
│   └── CardGlassDrawable      # Rect with edge falloff for notifications/media
│
├── integration
│   ├── AxBlurExtension        # Extends BlurEngine: trackView() + custom draw phase
│   ├── QSTileHook             # Replaces createTileBackground() in QSTileViewImpl
│   ├── BrightnessSliderHook   # Replaces track drawable in BrightnessSliderView
│   └── VolumeDialogHook       # Binds in VolumeDialogViewBinder
│
├── performance
│   ├── ThermalMonitor         # Listens to PowerManager thermal callbacks
│   ├── FrameBudgetTracker     # Choreographer callback → dynamic LOD
│   └── CacheManager           # Preallocates quarter-res offscreen buffers
│
└── config
    ├── AetherConfig           # Builder: refractionSamples, chromaticSplit, specularPower, etc.
    └── DefaultConfigs         # Presets: PERFORMANCE, BALANCED, QUALITY, THERMAL_SAFE
```

---

## 3. Phase Breakdown

### Phase 0: Foundation (Week 1) — *Zero-Risk Setup*

| Task | Deliverable | Validation |
|------|-------------|------------|
| 0.1 Clone Evolution X source (`frameworks/base`, `SystemUIGoogle`, `vendor_extras_sdk_ax_blur`) | Local buildable tree | `m SystemUIGoogle` succeeds |
| 0.2 Add `com.aether.glass` module to `SystemUIGoogle` (Android.bp) | New module compiles | No Dagger errors |
| 0.3 Implement `AetherConfig` + `DefaultConfigs` | Type-safe config | Unit tests pass |
| 0.4 Implement `ThermalMonitor` + `FrameBudgetTracker` | LOD infrastructure | Logcat shows thermal callbacks |

**Integration Point:** `SystemUIGoogleApplication.onCreate()` → initialize `AetherGlassEngine` early.

---

### Phase 1: Core Shader Engine (Week 2) — *Pure AGSL, No UI Hooks*

| Task | Deliverable | Validation |
|------|-------------|------------|
| 1.1 Write `AetherGlassShader.agsl` — single-pass refractive glass with: | AGSL source file | `RuntimeShader` compiles on device |
| ‑ Framebuffer fetch (`layout(framebuffer_fetch) in vec4`) |  |  |
| ‑ Normal map sampling (curvature → refraction vector) |  |  |
| ‑ Snell's law: `refract(viewDir, normal, 1.0/ior)` |  |  |
| ‑ Chromatic aberration: split R/G/B IOR (1.52/1.50/1.48) |  |  |
| ‑ Specular bevel: `pow(max(0, dot(reflectDir, lightDir)), specularPower)` |  |  |
| ‑ Fresnel term: `schlick(cosTheta, f0)` for edge glow |  |  |
| 1.2 `NormalMapGenerator` — SDF → normal map for circle/capsule/rounded-rect | Kotlin + RenderScript/Compute | Generates 256×256 normal maps |
| 1.3 `GlassShaderParams` data class + uniform binding | Type-safe params | Shader compiles with all uniforms |
| 1.4 `CacheManager` — quarter-res (540×1200) offscreen FBO pool | Preallocated buffers | `dumpsys gpu` shows stable cache |

**Performance Gate:** Shader executes in < 1.8 ms on Mali-G77 @ 90 Hz (profile via `adb shell dumpsys gpu --profile`).

---

### Phase 2: Drawable Abstractions (Week 3) — *Shape-Specific Materials*

| Drawable | Shape | Key Visuals | Integration Target |
|----------|-------|-------------|-------------------|
| `TileGlassDrawable` | Circle (convex lens) | Center thickening, edge bevel highlight, chromatic ring | `QSTileViewImpl.createTileBackground()` |
| `SliderGlassDrawable` | Capsule (pill) | Fluid meniscus follows thumb, dynamic fill refraction | `BrightnessSliderView` / `VolumeDialogSlider` |
| `CardGlassDrawable` | Rounded rect | Edge falloff, inter-card light bleeding | `NotificationBackgroundView` / `MediaControlPanel` |

**Each Drawable Implements:**
- `setBounds(rect)` → updates shader uniforms (center, radius, curvature)
- `setProgress(float)` → slider fill level → meniscus displacement
- `setThermalLOD(level)` → reduces refraction samples (8→4→2→0)
- `draw(canvas)` → binds `RuntimeShader` + `setFramebufferFetchEnabled(true)`

---

### Phase 3: AxBlur Integration (Week 4) — *The Critical Seam*

**Extend `com.android.axion.blur.BlurEngine` without forking:**

```kotlin
// In AetherGlassEngine.configure()
BlurEngine.getInstance().apply {
    // 1. Register our custom draw phase AFTER Kawase blur completes
    addPostBlurPhase("AETHER_GLASS") { canvas, viewport, blurTexture ->
        AetherGlassEngine.drawGlassLayer(canvas, viewport, blurTexture)
    }

    // 2. Track views that need glass treatment
    trackView(qsTileView) { TileGlassDrawable() }
    trackView(brightnessSlider) { SliderGlassDrawable() }
    trackView(volumeSlider) { SliderGlassDrawable() }
}
```

**Files to Modify in Evolution X Source:**
| File | Change | Risk |
|------|--------|------|
| `BlurEngine.java` | Add `addPostBlurPhase(name, callback)` + `PostBlurPhase` interface | Low — additive only |
| `QSTileViewImpl.java` | In `createTileBackground()`: return `engine.createDrawable(TILE)` | Medium — core QS path |
| `BrightnessSliderView.java` | Replace track drawable in `onDraw()` | Medium — high visibility |
| `VolumeDialogViewBinder.kt` | Bind `SliderGlassDrawable` in `bind()` | Medium — new architecture |

---

### Phase 4: Lockscreen & Notifications (Week 5)

| Component | Hook | Glass Treatment |
|-----------|------|-----------------|
| `KeyguardStatusView` (clock) | Custom `ClockPlugin` render | 3D-lit glass typography via `TextPaint.setShader(AetherGlassShader)` |
| `UdfpsView` (fingerprint) | `onDraw()` overlay | Optical glass disc + touch ripple refraction |
| `MediaControlPanel` | Container background | `CardGlassDrawable` edge-to-edge with album art chromatic bleed |
| `ExpandableNotificationRow` | `NotificationBackgroundView` | Per-card `CardGlassDrawable` with stack occlusion sorting |

---

### Phase 5: Polish & Ship (Week 6)

| Task | Details |
|------|---------|
| 5.1 Thermal LOD tuning | Map thermal states → sample counts; test 30-min sustained load |
| 5.2 Battery saver integration | `PowerManager.isPowerSaveMode` → force `THERMAL_SAFE` preset |
| 5.3 Accessibility | `reduce_motion` → disable chromatic animation; high contrast → boost specular |
| 5.4 Build & sign | `m SystemUIGoogle` → replace `/system_ext/priv-app/SystemUIGoogle/SystemUIGoogle.apk` |
| 5.5 OTA survival | Document `AxBlurExtension` as Evolutin X upstream PR candidate |

---

## 4. Technical Deep Dives

### 4.1 AGSL Shader Signature (Single Pass)

```glsl
// AetherGlassShader.agsl
uniform shader background;           // Blurred backdrop (from Kawase)
uniform sampler2D normalMap;         // Precomputed SDF normals
uniform vec2 center;                 // View center in screen space
uniform float radius;                // Curvature radius
uniform float ior;                   // Index of refraction (1.52 base)
uniform vec3 chromaticSplit;         // R/G/B IOR offsets (0.02, 0.0, -0.02)
uniform float specularPower;         // Bevel sharpness (64.0)
uniform vec3 lightDir;               // Virtual light direction (normalized)
uniform float thermalLOD;            // 0=full, 1=half, 2=quarter samples

half4 main(float2 xy) {
    // 1. Fetch backdrop via framebuffer fetch (zero blit)
    half4 backdrop = background.eval(xy);

    // 2. Compute normal from normalMap (UV mapped to view bounds)
    half2 uv = (xy - center) / radius + 0.5;
    half3 normal = normalize(texture(normalMap, uv).rgb * 2.0 - 1.0);

    // 3. View vector (orthographic approximation for UI)
    half3 viewDir = normalize(half3(0.0, 0.0, 1.0));

    // 4. Chromatic refraction (3 samples at thermalLOD=0)
    half3 refractedColor = 0;
    int samples = max(1, 8 >> int(thermalLOD));
    for (int i = 0; i < samples; i++) {
        float iorR = ior + chromaticSplit.r * (float(i) / samples - 0.5);
        float iorG = ior + chromaticSplit.g * (float(i) / samples - 0.5);
        float iorB = ior + chromaticSplit.b * (float(i) / samples - 0.5);

        half3 refractDir = refract(viewDir, normal, 1.0 / half3(iorR, iorG, iorB));
        half2 offset = refractDir.xy * radius * 0.1; // Scale to screen
        refractedColor += texture(background, xy + offset).rgb;
    }
    refractedColor /= float(samples);

    // 5. Specular bevel (Fresnel + Blinn-Phong)
    half3 reflectDir = reflect(viewDir, normal);
    float specular = pow(max(0.0, dot(reflectDir, lightDir)), specularPower);
    float fresnel = pow(1.0 - max(0.0, dot(viewDir, normal)), 5.0);

    // 6. Composite: refracted backdrop + specular edge + Fresnel glow
    half3 result = refractedColor
                 + half3(specular) * 0.6
                 + half3(fresnel) * 0.3 * backdrop.rgb;

    // 7. Alpha from backdrop + glass opacity
    float alpha = backdrop.a * 0.85 + fresnel * 0.15;

    return half4(result, alpha);
}
```

### 4.2 Framebuffer Fetch Setup (Critical for Performance)

```kotlin
// In AetherGlassDrawable.draw()
val runtimeShader = RuntimeShader(shader).apply {
    // Enable zero-copy framebuffer fetch
    setInputShader("background", BlurEngine.getBlurTextureShader())
    setFloatUniform("center", bounds.centerX(), bounds.centerY())
    setFloatUniform("radius", curvatureRadius)
    // ...
}

// CRITICAL: Tell Skia this shader reads framebuffer
val paint = Paint().apply {
    shader = runtimeShader
    // This flag enables GL_EXT_shader_framebuffer_fetch on Mali
    setFlags(Paint.FILTER_BITMAP_FLAG or 0x10000000) // Custom flag for FB fetch
}

canvas.drawRect(bounds, paint)
```

---

## 5. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Shader compile failure on Mali-G77** | Medium | High | Test AGSL on device early (Phase 1); fallback to Skia `ImageFilter` if needed |
| **90 Hz budget exceeded** | High | High | Quarter-res rendering, thermal LOD, sample count scaling; profile every phase |
| **Bootloop from SystemUIGoogle modification** | Low | Critical | Keep changes additive; `AxBlurExtension` is opt-in; test on userdebug build first |
| **Evolution X upstream breaks `AxBlur` API** | Medium | Medium | Minimize touch surface; submit `addPostBlurPhase` PR to AxionOS upstream |
| **Thermal throttling makes glass janky** | High | Medium | Aggressive LOD: 8→4→2→0 samples; disable chromatic at thermal state ≥ 2 |
| **AGSL `framebuffer_fetch` not supported** | Low | High | Verify `GL_EXT_shader_framebuffer_fetch` in `dumpsys gpu` (confirmed ✅); fallback to blit |

---

## 6. Testing Strategy

| Layer | Approach | Tools |
|-------|----------|-------|
| **Shader Unit** | Pure function: given params + mock backdrop → expected color | JUnit + Robolectric (AGSL compiles on host) |
| **Drawable Contract** | `AetherGlassDrawable` implements `Drawable` correctly | `DrawableCompat` test suite |
| **Integration** | `AetherGlassEngine` + `AxBlurExtension` on device | `adb shell am instrument -w com.android.systemui.test` |
| **Performance** | Frame time, GPU memory, thermal state over 30 min | `dumpsys gpu --profile`, `adb shell perfetto` |
| **Visual Regression** | Screenshot comparison: before/after glass | `uiautomator` + pixel diff (threshold 2%) |

---

## 7. Immediate Next Actions (This Week)

1. **Clone Evolution X source tree** — `frameworks/base`, `SystemUIGoogle`, `vendor_extras_sdk_ax_blur`
2. **Verify AGSL compiles on device** — Push a test `RuntimeShader` via `adb` and measure frame time
3. **Prototype `NormalMapGenerator`** — Generate circle/capsule normal maps; validate in Skia
4. **Add `com.aether.glass` module to `SystemUIGoogle/Android.bp`** — Ensure Dagger sees it
5. **Draft `addPostBlurPhase` API** in `BlurEngine.java` — Minimal, reviewable PR to AxionOS

---

## 8. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Frame time (glass active)** | ≤ 10.5 ms / frame (90 Hz) | `dumpsys gfxinfo com.android.systemui` |
| **GPU memory overhead** | ≤ 15 MiB additional | `dumpsys gpu` Skia cache delta |
| **Thermal sustained (30 min)** | No frame drops > 16.67 ms | `perfetto` trace + thermal callbacks |
| **Visual fidelity** | Matches Liquid Glass reference video | Designer review + pixel diff < 2% |
| **OTA survival** | Engine loads after Evolution X update | Clean flash + dirty flash test |

---

*Generated from REA findings: DEVICE_PROFILE.md, IMPLEMENTATION_GAPS.md, REA_FINDINGS.md, RENDERING_CAPABILITIES.md, SYSTEMUI_ARCHITECTURE.md*
