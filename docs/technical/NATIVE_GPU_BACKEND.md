# Native GPU Backend

ShapeYourPhoto 1.2.7 uses a bundled native GPU backend instead of asking ordinary users to install Python GPU packages.

## Architecture

- Native core: `native/gpu-core`
- Release binary: `shapeyourphoto_gpu_core.exe`
- Packaged location: `gpu/shapeyourphoto_gpu_core.exe`
- Runtime API: JSON command mode plus a persistent JSON-lines worker (`serve`)
- Current backend: Rust + `wgpu`, using the best available adapter exposed through wgpu (`Vulkan`, `D3D12`, or another primary backend depending on driver support)

The Python app finds the packaged executable first, then development builds under `native/gpu-core/target/release` or `target/debug`. Users do not need Rust, CUDA Toolkit, torch, CuPy, or OpenCV CUDA.

## Current Accelerated Path

Large-image analysis calls `accelerated_luma_stats()` in `src/gpu_accel.py`. The native worker computes:

- luma histogram
- mean brightness
- highlight and clipped highlight ratios
- shadow and crushed shadow ratios
- p50 / p95 / p99 / p999 percentiles
- dynamic range

`src/analysis/core.py` uses those values before the CPU percentile path. When acceleration succeeds, performance timings include `gpu_luma_accelerated=1.0`, `gpu_luma_stats`, `gpu_luma_native`, and `gpu_luma_compute`.

## Performance Policy

GPU is only used where benchmark data shows a real benefit. On the RTX 4060 Laptop GPU test machine, warm native GPU luma statistics for large `test/*.JPG` images measured roughly 230-260 ms total Python time versus roughly 390-440 ms for the equivalent CPU luma/percentile block. End-to-end analysis improved by roughly 250-460 ms per large image.

Small thumbnails, repair candidate metrics, and similar-image feature extraction are currently faster on CPU because they operate on small resized images and already benefit from CPU parallelism. Those paths must remain CPU-gated until a new native kernel proves faster after warmup.

## Fallback

If the native executable is missing, the adapter cannot initialize, the worker times out, or the image is below the acceleration threshold, the caller silently returns to CPU. Diagnostics record the reason through `export_gpu_diagnostics_json()` without exposing Python package names as the main user-facing fix.

## Packaging

- `build/shapeyourphoto.spec` includes the release native binary under `gpu/`.
- `.github/workflows/windows-release.yml` builds `native/gpu-core` before PyInstaller and verifies the packaged executable exists.
- `build/installer.iss` relies on the PyInstaller output so the installer carries the `gpu/` folder.

## Validation

Recommended local checks:

```powershell
cargo build --manifest-path native\gpu-core\Cargo.toml --release
native\gpu-core\target\release\shapeyourphoto_gpu_core.exe self-test
py -3 -m compileall src
```

On an RTX 4060 Laptop GPU, settings should show a native GPU backend such as `Native GPU backend / wgpu Vulkan`, and large-image analysis logs should include an accelerated GPU luma task.
