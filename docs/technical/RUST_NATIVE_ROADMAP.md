# Rust Native Roadmap

ShapeYourPhoto can move Python performance hot paths and Python runtime
fragility into Rust when there is clear evidence that the native path improves
startup, throughput, safety, or packaging reliability. Rust migration is a
tool, not a rewrite mandate: the Python/Tk UI remains the current product
surface until a native UI is proven feature-complete.

## Current Native Components

- `native/gpu-core`: Rust + wgpu backend for large-image luma statistics. It is
  launched by Python through JSON command mode or a persistent JSON-lines
  worker.
- `native/launcher`: native startup host. Release packages should expose its
  built `ShapeYourPhoto.exe` as the main user entry. It finds Python 3.10+ for
  source builds, preserves existing `start_helper.py` behavior, and shows a
  readable native error dialog on Windows.

## Rust Migration Candidates

Good candidates:

- Directory walking, ignore-rule filtering, and image path discovery for very
  large trees.
- Fast metadata probes that currently require repeated Python `Path.stat()` or
  PIL open/close loops.
- Perceptual hashing, similarity feature extraction, and duplicate grouping
  when benchmarked against real `test/` images.
- Image analysis kernels with large numeric arrays, especially when data
  transfer overhead is amortized across large images or batches.
- Repair scoring loops that evaluate many candidate outputs.
- Update staging, file replacement, rollback, and process restart orchestration.
- Startup hosting: environment checks, dependency detection, diagnostics,
  Python process supervision, and packaged-component validation.
- Task execution backends where the work is CPU/IO heavy and can expose a
  simple command or JSON-lines protocol back to Python `TaskManager`.

Poor candidates until benchmarked:

- AppContext / service registry and Tk task-state orchestration, because they
  sit on the Python/Tk event-loop boundary and must directly coordinate Tk
  callbacks, localization, and UI state.
- `TaskManager` itself. It is the Python-side bridge for Tk callbacks,
  cancellation events, error reporting, and UI queue draining; Rust workers
  should plug into it instead of replacing it during the Python/Tk era.
- Tiny thumbnails and already downsampled previews.
- UI layout, Tk widget updates, dialogs, and localization.
- One-off glue code where subprocess or FFI overhead would dominate.
- Any path where Rust would duplicate business rules without shared tests.

## Migration Rules

- Preserve the Python/Tk feature surface while migrating internals.
- A Rust path must have a CPU/Python fallback unless it is only a launcher or
  packaging host.
- Add benchmark evidence before enabling a Rust path by default.
- Record timings in the existing `perf_timings` / benchmark schema; do not
  create an isolated native timing vocabulary.
- Keep protocols explicit and versioned. JSON lines are preferred for
  subprocess workers until a stronger FFI boundary is justified.
- Do not require ordinary users to install Rust, CUDA, torch, CuPy, or OpenCV
  CUDA. Native binaries must be bundled in release packages.
- Native components must report their own version and keep it aligned with the
  app release version.
- If a native worker fails, times out, or is missing, the app must log a clear
  reason and continue on a safe fallback where possible.
- Native workers must report progress and cancellation through the existing
  `TaskRecord` / `cancel_event` / UI callback contract. A Rust module should
  not invent an independent task lifecycle.

## Native Launcher Direction

The launcher should grow in layers:

1. Locate app root, locate Python, and delegate to `start_helper.py`.
2. Validate packaged native components and print concise diagnostics.
3. Supervise the Python GUI process and return meaningful exit codes.
4. Own update staging and restart orchestration, reducing Python self-replace
   edge cases.
5. Optionally host future Rust services for scan/hash/analysis workers.

The launcher must not run benchmark, directory scan, update download, image
analysis, repair, or cleanup work during normal startup. Those remain explicit
user actions.

## Verification

Minimum checks after native changes:

```powershell
cargo build --manifest-path native\launcher\Cargo.toml --release
native\launcher\target\release\ShapeYourPhoto.exe --native-version
native\launcher\target\release\ShapeYourPhoto.exe --check-only
cargo build --manifest-path native\gpu-core\Cargo.toml --release
native\gpu-core\target\release\shapeyourphoto_gpu_core.exe self-test
py -3 -m compileall -q tools/entry src tools
```
