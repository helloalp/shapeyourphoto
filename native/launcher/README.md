# ShapeYourPhoto Native Launcher

This is the first native startup host for ShapeYourPhoto.

The launcher is intentionally small and dependency-free. It does not replace
the Python/Tk application yet. Instead it owns the earliest startup steps and
delegates to `tools/launcher/start_helper.py`, preserving the existing ability
to check Python dependencies, install missing runtime packages, organize legacy
files, verify the bundled native GPU component, and launch the GUI.

Build:

```powershell
cargo build --manifest-path native\launcher\Cargo.toml --release
```

Run:

```powershell
native\launcher\target\release\ShapeYourPhoto.exe --native-version
native\launcher\target\release\ShapeYourPhoto.exe --check-only
native\launcher\target\release\ShapeYourPhoto.exe
```

The launcher uses the Windows GUI subsystem and native error dialogs for early
startup failures. `start.bat` is retained only as a source-tree compatibility entry at `tools/launcher/start.bat` when the native executable has not been built yet.

Signing:

- Authenticode signing is supported as a release step after `cargo build`.
- `tools/sign_windows.ps1` signs the launcher when `SHAPEYOURPHOTO_SIGN_CERT`
  points to a local or CI-provided certificate. Optional variables are
  `SHAPEYOURPHOTO_SIGN_PASSWORD`, `SHAPEYOURPHOTO_SIGNTOOL`, and
  `SHAPEYOURPHOTO_SIGN_TIMESTAMP`.
- Provide the certificate through local secure storage or CI secrets only.
- Do not commit certificates, private keys, PFX files, passwords, or timestamp
  credentials.
- If no certificate is configured, the signing step exits successfully and
  prints that the build is unsigned; release notes should mark unsigned builds
  clearly until a real certificate signs the binary.
