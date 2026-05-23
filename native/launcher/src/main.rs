#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::env;
use std::ffi::OsString;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};
use std::time::Instant;

const VERSION: &str = "1.2.7-native-launcher.1";
const EXIT_MISSING_HELPER: u8 = 11;
const EXIT_MISSING_PYTHON: u8 = 12;
const EXIT_START_FAILED: u8 = 13;

#[derive(Clone, Debug)]
struct PythonCommand {
    program: OsString,
    prefix_args: Vec<OsString>,
}

#[derive(Clone, Debug)]
struct LaunchManifest {
    app_version: String,
    gui_entry: PathBuf,
    fallback_entry: PathBuf,
    bundled_runtime: PathBuf,
    bundled_pythonw: PathBuf,
    requirements: PathBuf,
    dependency_cache: bool,
    diagnostic_log: bool,
}

#[derive(Debug)]
struct Diagnostics {
    enabled: bool,
    started: Instant,
    last: Instant,
    lines: Vec<String>,
}

impl Diagnostics {
    fn new(enabled: bool) -> Self {
        let now = Instant::now();
        Self {
            enabled,
            started: now,
            last: now,
            lines: Vec::new(),
        }
    }

    fn mark(&mut self, stage: &str) {
        if !self.enabled {
            return;
        }
        let now = Instant::now();
        let delta = now.duration_since(self.last).as_millis();
        let total = now.duration_since(self.started).as_millis();
        self.lines.push(format!("{stage}: +{delta} ms / {total} ms"));
        self.last = now;
    }

    fn flush(&self, root: &Path) {
        if !self.enabled {
            return;
        }
        let dir = root.join("data").join("diagnostics");
        let _ = fs::create_dir_all(&dir);
        let path = dir.join("launcher.log");
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "ShapeYourPhoto launcher {VERSION}");
            for line in &self.lines {
                let _ = writeln!(file, "{line}");
            }
            let _ = writeln!(file);
        }
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(message) => {
            show_error("ShapeYourPhoto could not start", &message);
            ExitCode::from(1)
        }
    }
}

fn run() -> Result<u8, String> {
    let args: Vec<OsString> = env::args_os().skip(1).collect();
    if args.iter().any(|arg| arg == "--native-version") {
        println!("{VERSION}");
        return Ok(0);
    }
    let diagnostic_arg = args.iter().any(|arg| arg == "--diagnostic");
    let passthrough_args: Vec<OsString> = args.iter().filter(|arg| *arg != "--diagnostic").cloned().collect();
    let mut diagnostics = Diagnostics::new(diagnostic_arg || env::var_os("SHAPEYOURPHOTO_LAUNCH_DIAGNOSTIC").is_some());
    diagnostics.mark("launcher initialized");

    let root = find_app_root()?;
    diagnostics.mark("app root located");
    let manifest = read_manifest(&root)?;
    if manifest.diagnostic_log {
        diagnostics.enabled = true;
    }
    diagnostics.mark("manifest read");
    let maintenance_mode = args.iter().any(|arg| arg == "--check-only" || arg == "--install-only");
    let helper = root.join("tools").join("launcher").join("start_helper.py");
    if maintenance_mode && !helper.exists() {
        show_error("ShapeYourPhoto could not start", &format!("Startup helper was not found:\n{}", helper.display()));
        return Ok(EXIT_MISSING_HELPER);
    }

    let python = match find_python(&root, &manifest) {
        Some(command) => command,
        None => {
            show_python_missing(&root);
            show_error(
                "Python was not found",
                "Python 3.10 or newer was not found. Install Python, then start ShapeYourPhoto again.",
            );
            return Ok(EXIT_MISSING_PYTHON);
        }
    };
    diagnostics.mark("python runtime resolved");

    if !maintenance_mode {
        if !dependencies_ready_cached(&root, &manifest, &python, &mut diagnostics) {
            if !helper.exists() {
                show_error("ShapeYourPhoto could not start", &format!("Startup helper was not found:\n{}", helper.display()));
                return Ok(EXIT_MISSING_HELPER);
            }
            let install_code = run_helper(&root, &helper, &python, vec![OsString::from("--install-only")])?;
            if install_code != 0 || !dependencies_ready_cached(&root, &manifest, &python, &mut diagnostics) {
                show_error(
                    "ShapeYourPhoto could not start",
                    "Runtime dependencies are not ready. Please run tools/launcher/start.bat --check-only to see details.",
                );
                return Ok(EXIT_START_FAILED);
            }
        }
        let result = launch_gui_direct(&root, &manifest, &python, passthrough_args);
        diagnostics.mark("gui process spawned");
        diagnostics.flush(&root);
        return result;
    }

    let result = run_helper(&root, &helper, &python, passthrough_args);
    diagnostics.mark("helper completed");
    diagnostics.flush(&root);
    result
}

fn run_helper(root: &Path, helper: &Path, python: &PythonCommand, args: Vec<OsString>) -> Result<u8, String> {
    let mut command = Command::new(&python.program);
    command.args(&python.prefix_args);
    command.arg(helper);
    command.args(args);
    command.current_dir(root);
    command.stdin(Stdio::inherit());
    command.stdout(Stdio::inherit());
    command.stderr(Stdio::inherit());
    suppress_console_window(&mut command);

    let status = match command.status() {
        Ok(status) => status,
        Err(err) => {
            show_error("ShapeYourPhoto could not start", &format!("Failed to start the application helper:\n{err}"));
            return Ok(EXIT_START_FAILED);
        }
    };
    Ok(status.code().unwrap_or(1).clamp(0, u8::MAX as i32) as u8)
}

fn dependencies_ready(python: &PythonCommand) -> bool {
    let mut command = Command::new(&python.program);
    command.args(&python.prefix_args);
    command.arg("-c");
    command.arg("import PIL, numpy, platformdirs, cryptography");
    suppress_console_window(&mut command);
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn launch_gui_direct(root: &Path, manifest: &LaunchManifest, python: &PythonCommand, args: Vec<OsString>) -> Result<u8, String> {
    let app_pyw = root.join(&manifest.gui_entry);
    let app_py = root.join(&manifest.fallback_entry);
    let entry = if app_pyw.exists() { app_pyw } else { app_py };
    if !entry.exists() {
        show_error("ShapeYourPhoto could not start", &format!("Application entry was not found:\n{}", entry.display()));
        return Ok(EXIT_MISSING_HELPER);
    }

    let mut program = python.program.clone();
    let mut prefix_args = python.prefix_args.clone();
    if cfg!(target_os = "windows") {
        if let Some(pythonw) = find_pythonw(root, manifest, python) {
            program = pythonw;
            prefix_args.clear();
        }
    }

    let mut command = Command::new(program);
    command.args(prefix_args);
    command.arg(entry);
    command.args(args);
    command.current_dir(root);
    command.env("PYTHONPATH", root.join("src"));
    command.stdin(Stdio::null());
    command.stdout(Stdio::null());
    command.stderr(Stdio::null());
    suppress_console_window(&mut command);
    match command.spawn() {
        Ok(_) => Ok(0),
        Err(err) => {
            show_error("ShapeYourPhoto could not start", &format!("Failed to start the application:\n{err}"));
            Ok(EXIT_START_FAILED)
        }
    }
}

#[cfg(target_os = "windows")]
fn find_pythonw(root: &Path, manifest: &LaunchManifest, python: &PythonCommand) -> Option<OsString> {
    if let Some(value) = env::var_os("SHAPEYOURPHOTO_PYTHONW") {
        if Path::new(&value).exists() {
            return Some(value);
        }
    }
    let bundled = root.join(&manifest.bundled_pythonw);
    if bundled.exists() {
        return Some(bundled.into_os_string());
    }
    let mut command = Command::new(&python.program);
    command.args(&python.prefix_args);
    command.arg("-c");
    command.arg("import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))");
    suppress_console_window(&mut command);
    let output = command.stdin(Stdio::null()).stderr(Stdio::null()).output().ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if text.is_empty() {
        return None;
    }
    let candidate = PathBuf::from(text);
    if candidate.exists() {
        Some(candidate.into_os_string())
    } else {
        None
    }
}

#[cfg(not(target_os = "windows"))]
fn find_pythonw(_root: &Path, _manifest: &LaunchManifest, _python: &PythonCommand) -> Option<OsString> {
    None
}

fn read_manifest(root: &Path) -> Result<LaunchManifest, String> {
    let path = {
        let config_path = root.join("config").join("launch_manifest.json");
        if config_path.exists() {
            config_path
        } else {
            root.join("launch_manifest.json")
        }
    };
    let text = if path.exists() {
        fs::read_to_string(&path).map_err(|err| format!("could not read {}: {err}", path.display()))?
    } else {
        String::new()
    };
    let schema = parse_json_number(&text, "schema_version").unwrap_or(1);
    if schema != 1 {
        return Err(format!("unsupported launch_manifest schema_version: {schema}"));
    }
    let manifest = LaunchManifest {
        app_version: parse_json_string(&text, "app_version").unwrap_or_else(|| "1.2.7".to_string()),
        gui_entry: safe_manifest_path(parse_json_string(&text, "gui_entry").unwrap_or_else(|| "tools/entry/app.pyw".to_string()))?,
        fallback_entry: safe_manifest_path(parse_json_string(&text, "fallback_entry").unwrap_or_else(|| "tools/entry/app.py".to_string()))?,
        bundled_runtime: safe_manifest_path(parse_json_string(&text, "bundled_runtime").unwrap_or_else(|| "runtime/python/python.exe".to_string()))?,
        bundled_pythonw: safe_manifest_path(parse_json_string(&text, "bundled_pythonw").unwrap_or_else(|| "runtime/python/pythonw.exe".to_string()))?,
        requirements: safe_manifest_path(parse_json_string(&text, "requirements").unwrap_or_else(|| "requirements/runtime.txt".to_string()))?,
        dependency_cache: parse_json_bool(&text, "dependency_cache").unwrap_or(true),
        diagnostic_log: parse_json_bool(&text, "diagnostic_log").unwrap_or(false),
    };
    for required in [&manifest.gui_entry, &manifest.fallback_entry] {
        if !root.join(required).exists() {
            return Err(format!("manifest entry does not exist inside app root: {}", required.display()));
        }
    }
    Ok(manifest)
}

fn safe_manifest_path(value: String) -> Result<PathBuf, String> {
    let path = PathBuf::from(value.replace('\\', "/"));
    if path.is_absolute() || path.components().any(|component| matches!(component, std::path::Component::ParentDir)) {
        return Err(format!("manifest path must stay inside the app root: {}", path.display()));
    }
    Ok(path)
}

fn parse_json_string(text: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\"");
    let start = text.find(&needle)?;
    let rest = &text[start + needle.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    let value = value.strip_prefix('"')?;
    let end = value.find('"')?;
    Some(value[..end].to_string())
}

fn parse_json_bool(text: &str, key: &str) -> Option<bool> {
    let needle = format!("\"{key}\"");
    let start = text.find(&needle)?;
    let rest = &text[start + needle.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    if value.starts_with("true") {
        Some(true)
    } else if value.starts_with("false") {
        Some(false)
    } else {
        None
    }
}

fn parse_json_number(text: &str, key: &str) -> Option<u32> {
    let needle = format!("\"{key}\"");
    let start = text.find(&needle)?;
    let rest = &text[start + needle.len()..];
    let colon = rest.find(':')?;
    let digits: String = rest[colon + 1..].trim_start().chars().take_while(|ch| ch.is_ascii_digit()).collect();
    digits.parse().ok()
}

fn dependencies_ready_cached(root: &Path, manifest: &LaunchManifest, python: &PythonCommand, diagnostics: &mut Diagnostics) -> bool {
    if !manifest.dependency_cache {
        let ok = dependencies_ready(python);
        diagnostics.mark("dependency imports checked");
        return ok;
    }
    let fingerprint = dependency_fingerprint(root, manifest, python);
    let state_path = root.join("data").join("launcher_state.json");
    if let Ok(text) = fs::read_to_string(&state_path) {
        if text.contains("\"ok\":true") && text.contains(&format!("\"fingerprint\":\"{fingerprint}\"")) {
            diagnostics.mark("dependency check cache hit");
            return true;
        }
    }
    let ok = dependencies_ready(python);
    diagnostics.mark("dependency imports checked");
    if ok {
        if let Some(parent) = state_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let _ = fs::write(
            state_path,
            format!(
                "{{\"ok\":true,\"fingerprint\":\"{}\",\"app_version\":\"{}\"}}\n",
                fingerprint, manifest.app_version
            ),
        );
    }
    ok
}

fn dependency_fingerprint(root: &Path, manifest: &LaunchManifest, python: &PythonCommand) -> String {
    let requirements_hash = file_hash(&root.join(&manifest.requirements));
    let python_key = PathBuf::from(&python.program)
        .to_string_lossy()
        .replace('\\', "/");
    let runtime_key = python_runtime_fingerprint(python);
    let startup_mode = if root.join(&manifest.bundled_runtime) == PathBuf::from(&python.program) {
        "portable"
    } else if python.program.to_string_lossy().eq_ignore_ascii_case("py") {
        "py-launcher"
    } else {
        "system"
    };
    let run_dir = root.to_string_lossy().replace('\\', "/");
    format!(
        "{}|{}|{}|{}|{}|{}|{}",
        VERSION, startup_mode, manifest.app_version, python_key, requirements_hash, run_dir, runtime_key
    )
}

fn python_runtime_fingerprint(python: &PythonCommand) -> String {
    let script = "import importlib.metadata as md, os, site, sys\npaths=[]\ntry: paths.extend(site.getsitepackages())\nexcept Exception: pass\ntry: paths.append(site.getusersitepackages())\nexcept Exception: pass\nprint('python=' + sys.version.split()[0])\nfor pkg in ('Pillow','numpy','platformdirs','cryptography'):\n    try: print(pkg + '=' + md.version(pkg))\n    except Exception: print(pkg + '=missing')\nfor p in paths:\n    try: print(p + '=' + str(int(os.path.getmtime(p))))\n    except Exception: print(p + '=missing')\n";
    let mut command = Command::new(&python.program);
    command.args(&python.prefix_args);
    command.arg("-c");
    command.arg(script);
    suppress_console_window(&mut command);
    let output = command.stdin(Stdio::null()).stderr(Stdio::null()).output();
    match output {
        Ok(output) if output.status.success() => String::from_utf8_lossy(&output.stdout).replace('\n', ";"),
        _ => "runtime-unknown".to_string(),
    }
}

fn file_hash(path: &Path) -> u64 {
    let mut hash = 1469598103934665603u64;
    let Ok(bytes) = fs::read(path) else {
        return 0;
    };
    for byte in bytes {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }
    hash
}

fn find_app_root() -> Result<PathBuf, String> {
    let mut seeds = Vec::new();
    if let Ok(current) = env::current_dir() {
        seeds.push(current);
    }
    if let Ok(exe) = env::current_exe() {
        if let Some(parent) = exe.parent() {
            seeds.push(parent.to_path_buf());
        }
    }

    for seed in seeds {
        if let Some(root) = find_root_from(&seed) {
            return Ok(root);
        }
    }
    Err("could not locate project root containing tools/launcher/start_helper.py".to_string())
}

#[cfg(target_os = "windows")]
fn show_error(title: &str, message: &str) {
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;

    type Hwnd = *mut core::ffi::c_void;
    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(hwnd: Hwnd, text: *const u16, caption: *const u16, typ: u32) -> i32;
    }

    const MB_ICONERROR: u32 = 0x00000010;
    const MB_OK: u32 = 0x00000000;
    let text: Vec<u16> = std::ffi::OsStr::new(message).encode_wide().chain(once(0)).collect();
    let caption: Vec<u16> = std::ffi::OsStr::new(title).encode_wide().chain(once(0)).collect();
    unsafe {
        MessageBoxW(core::ptr::null_mut(), text.as_ptr(), caption.as_ptr(), MB_OK | MB_ICONERROR);
    }
}

#[cfg(not(target_os = "windows"))]
fn show_error(title: &str, message: &str) {
    eprintln!("{title}: {message}");
}

fn find_root_from(seed: &Path) -> Option<PathBuf> {
    for candidate in seed.ancestors() {
        if candidate.join("config").join("launch_manifest.json").exists()
            || candidate.join("launch_manifest.json").exists()
            || candidate.join("tools").join("launcher").join("start_helper.py").exists()
        {
            return Some(candidate.to_path_buf());
        }
    }
    None
}

fn find_python(root: &Path, manifest: &LaunchManifest) -> Option<PythonCommand> {
    let bundled = root.join(&manifest.bundled_runtime);
    if bundled.exists() {
        let candidate = PythonCommand {
            program: bundled.into_os_string(),
            prefix_args: Vec::new(),
        };
        if python_version_ok(&candidate) {
            return Some(candidate);
        }
    }

    if let Some(value) = env::var_os("SHAPEYOURPHOTO_PYTHON") {
        let candidate = PythonCommand {
            program: value.clone(),
            prefix_args: Vec::new(),
        };
        if python_version_ok(&candidate) {
            return Some(candidate);
        }
    }

    let py_launcher = PythonCommand {
        program: OsString::from("py"),
        prefix_args: vec![OsString::from("-3")],
    };
    if python_version_ok(&py_launcher) {
        return Some(py_launcher);
    }

    let python = PythonCommand {
        program: OsString::from("python"),
        prefix_args: Vec::new(),
    };
    if python_version_ok(&python) {
        return Some(python);
    }

    None
}

fn python_version_ok(candidate: &PythonCommand) -> bool {
    let mut command = Command::new(&candidate.program);
    command.args(&candidate.prefix_args);
    command.arg("-c");
    command.arg("import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)");
    suppress_console_window(&mut command);
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn show_python_missing(root: &Path) {
    #[cfg(target_os = "windows")]
    {
        let script = root.join("tools").join("launcher").join("python_missing.ps1");
        if script.exists() {
            let _ = Command::new("powershell")
                .arg("-NoProfile")
                .arg("-ExecutionPolicy")
                .arg("Bypass")
                .arg("-File")
                .arg(script)
                .current_dir(root)
                .status();
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = root;
    }
}

#[cfg(target_os = "windows")]
fn suppress_console_window(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x08000000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(target_os = "windows"))]
fn suppress_console_window(_command: &mut Command) {}
