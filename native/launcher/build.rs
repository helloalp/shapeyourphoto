use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=src/main.rs");
    println!("cargo:rerun-if-changed=app.rc");
    println!("cargo:rerun-if-changed=app.manifest");
    println!("cargo:rerun-if-changed=../../assets/app_icon.ico");

    let target = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    if target != "windows" {
        return;
    }

    let out_dir = match env::var("OUT_DIR") {
        Ok(value) => PathBuf::from(value),
        Err(_) => return,
    };
    let manifest_dir = match env::var("CARGO_MANIFEST_DIR") {
        Ok(value) => PathBuf::from(value),
        Err(_) => return,
    };
    let output = out_dir.join("launcher.res");

    let status = Command::new("rc.exe")
        .current_dir(&manifest_dir)
        .args(["/nologo", "/fo"])
        .arg(&output)
        .arg("app.rc")
        .status();

    match status {
        Ok(status) if status.success() => {
            println!("cargo:rustc-link-arg-bin=ShapeYourPhoto={}", output.display());
        }
        Ok(status) => {
            println!("cargo:warning=rc.exe exited with {status}; launcher resource metadata was not embedded");
        }
        Err(error) => {
            println!("cargo:warning=rc.exe was not available ({error}); launcher resource metadata was not embedded");
        }
    }
}
