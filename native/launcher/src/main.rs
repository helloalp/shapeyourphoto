#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]

use std::env;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};

const VERSION: &str = "1.2.7-native-launcher.1";
const EXIT_MISSING_HELPER: u8 = 11;
const EXIT_MISSING_PYTHON: u8 = 12;
const EXIT_START_FAILED: u8 = 13;

#[derive(Clone, Debug)]
struct PythonCommand {
    program: OsString,
    prefix_args: Vec<OsString>,
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

    let root = find_app_root()?;
    let maintenance_mode = args.iter().any(|arg| arg == "--check-only" || arg == "--install-only");
    let helper = root.join("tools").join("launcher").join("start_helper.py");
    if maintenance_mode && !helper.exists() {
        show_error("ShapeYourPhoto could not start", &format!("Startup helper was not found:\n{}", helper.display()));
        return Ok(EXIT_MISSING_HELPER);
    }

    let python = match find_python() {
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

    if !maintenance_mode {
        if !dependencies_ready(&python) {
            if !helper.exists() {
                show_error("ShapeYourPhoto could not start", &format!("Startup helper was not found:\n{}", helper.display()));
                return Ok(EXIT_MISSING_HELPER);
            }
            let install_code = run_helper(&root, &helper, &python, vec![OsString::from("--install-only")])?;
            if install_code != 0 || !dependencies_ready(&python) {
                show_error(
                    "ShapeYourPhoto could not start",
                    "Runtime dependencies are not ready. Please run tools/launcher/start.bat --check-only to see details.",
                );
                return Ok(EXIT_START_FAILED);
            }
        }
        return launch_gui_direct(&root, &python, args);
    }

    run_helper(&root, &helper, &python, args)
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
    command
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|status| status.success())
        .unwrap_or(false)
}

fn launch_gui_direct(root: &Path, python: &PythonCommand, args: Vec<OsString>) -> Result<u8, String> {
    let app_pyw = root.join("tools").join("entry").join("app.pyw");
    let app_py = root.join("tools").join("entry").join("app.py");
    let entry = if app_pyw.exists() { app_pyw } else { app_py };
    if !entry.exists() {
        show_error("ShapeYourPhoto could not start", &format!("Application entry was not found:\n{}", entry.display()));
        return Ok(EXIT_MISSING_HELPER);
    }

    let mut program = python.program.clone();
    let mut prefix_args = python.prefix_args.clone();
    if cfg!(target_os = "windows") {
        if let Some(pythonw) = find_pythonw(python) {
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
    match command.spawn() {
        Ok(_) => Ok(0),
        Err(err) => {
            show_error("ShapeYourPhoto could not start", &format!("Failed to start the application:\n{err}"));
            Ok(EXIT_START_FAILED)
        }
    }
}

#[cfg(target_os = "windows")]
fn find_pythonw(python: &PythonCommand) -> Option<OsString> {
    if let Some(value) = env::var_os("SHAPEYOURPHOTO_PYTHONW") {
        if Path::new(&value).exists() {
            return Some(value);
        }
    }
    let mut command = Command::new(&python.program);
    command.args(&python.prefix_args);
    command.arg("-c");
    command.arg("import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))");
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
fn find_pythonw(_python: &PythonCommand) -> Option<OsString> {
    None
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
        if candidate.join("tools").join("launcher").join("start_helper.py").exists() {
            return Some(candidate.to_path_buf());
        }
    }
    None
}

fn find_python() -> Option<PythonCommand> {
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
