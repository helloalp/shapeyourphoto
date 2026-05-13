from __future__ import annotations

import shutil
import sys
import urllib.error
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import updater  # noqa: E402
from app_metadata import APP_VERSION_ID  # noqa: E402
from cloud_client import (  # noqa: E402
    USER_AGENT as CLOUD_USER_AGENT,
    compare_builds,
    current_build_id,
    friendly_cloud_error,
    select_applicable_update_manifest,
    update_manifest_applies_to_this_client,
)


def _make_zip(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _manifest(package: Path, **overrides) -> dict:
    data = {
        "package_url": package.as_uri(),
        "sha256": updater.sha256_file(package),
        "package_size": package.stat().st_size,
        "managed_files": ["app.txt"],
        "deleted_paths": [],
    }
    data.update(overrides)
    return data


def _ctx(app_dir: Path, manifest: dict) -> updater.UpdateContext:
    return updater.UpdateContext(manifest=manifest, app_dir=app_dir, restart_cmd=[sys.executable, "-c", "pass"])


def _case_version_and_ua(tmp: Path) -> None:
    assert compare_builds({"version_id": APP_VERSION_ID + 1}) == 1
    assert compare_builds({"version_id": APP_VERSION_ID}) == 0
    assert "Python-urllib" not in CLOUD_USER_AGENT
    assert "Python-urllib" not in updater.USER_AGENT
    assert CLOUD_USER_AGENT.startswith("ShapeYourPhotoUpdater/")
    assert updater.USER_AGENT.startswith("ShapeYourPhotoUpdater/")
    assert friendly_cloud_error("<urlopen error _ssl.c:1063: The handshake operation timed out>") == "暂时无法连接更新服务，请稍后再试。"


def _case_update_manifest_target_ranges(tmp: Path) -> None:
    local_id = current_build_id()
    assert update_manifest_applies_to_this_client({"target_min_version_id": local_id, "target_max_version_id": local_id})
    assert not update_manifest_applies_to_this_client({"target_min_version_id": local_id + 1})
    assert not update_manifest_applies_to_this_client({"target_max_version_id": local_id - 1})
    selected = select_applicable_update_manifest(
        {
            "updates": [
                {
                    "version_id": local_id + 1,
                    "build_id": local_id + 1,
                    "target_min_version_id": local_id - 2,
                    "target_max_version_id": local_id - 1,
                    "external_download_only": True,
                },
                {
                    "version_id": local_id + 2,
                    "build_id": local_id + 2,
                    "target_min_version_id": local_id,
                    "target_max_version_id": local_id,
                },
            ]
        }
    )
    assert selected["version_id"] == local_id + 2
    skipped = select_applicable_update_manifest(
        {"updates": [{"version_id": local_id + 1, "target_min_version_id": local_id + 1}]}
    )
    assert skipped.get("_no_applicable_update") is True


def _case_package_size_mismatch_sha_ok(tmp: Path) -> None:
    app_dir = tmp / "size_sha_ok_app"
    app_dir.mkdir()
    package = tmp / "size_sha_ok.zip"
    _make_zip(package, {"app.txt": "new"})
    manifest = _manifest(package, package_size=package.stat().st_size + 1)
    updater.run_update(_ctx(app_dir, manifest))
    assert (app_dir / "app.txt").read_text(encoding="utf-8") == "new"


def _case_package_size_and_sha_mismatch(tmp: Path) -> None:
    app_dir = tmp / "size_sha_bad_app"
    app_dir.mkdir()
    package = tmp / "size_sha_bad.zip"
    _make_zip(package, {"app.txt": "new"})
    manifest = _manifest(package, package_size=package.stat().st_size + 1, sha256="0" * 64)
    try:
        updater.run_update(_ctx(app_dir, manifest))
    except RuntimeError as exc:
        assert "大小校验失败" in str(exc)
    else:
        raise AssertionError("package size mismatch with bad sha should fail")


def _case_sha_mismatch(tmp: Path) -> None:
    app_dir = tmp / "sha_app"
    app_dir.mkdir()
    package = tmp / "sha.zip"
    _make_zip(package, {"app.txt": "new"})
    manifest = _manifest(package, sha256="0" * 64)
    try:
        updater.run_update(_ctx(app_dir, manifest))
    except RuntimeError as exc:
        assert "校验失败" in str(exc)
    else:
        raise AssertionError("sha mismatch should fail")


def _case_zip_slip(tmp: Path) -> None:
    app_dir = tmp / "zip_slip_app"
    app_dir.mkdir()
    package = tmp / "zip_slip.zip"
    _make_zip(package, {"../evil.txt": "bad"})
    manifest = _manifest(package, managed_files=[])
    try:
        updater.run_update(_ctx(app_dir, manifest))
    except RuntimeError as exc:
        assert "异常路径" in str(exc)
    else:
        raise AssertionError("zip-slip package should fail")


def _case_deleted_missing_and_success(tmp: Path) -> None:
    app_dir = tmp / "deleted_missing_app"
    app_dir.mkdir()
    package = tmp / "deleted_missing.zip"
    _make_zip(package, {"app.txt": "new"})
    manifest = _manifest(package, deleted_paths=["missing.txt"])
    updater.run_update(_ctx(app_dir, manifest))
    assert (app_dir / "app.txt").read_text(encoding="utf-8") == "new"


def _case_cancel_before_download(tmp: Path) -> None:
    app_dir = tmp / "cancel_app"
    app_dir.mkdir()
    package = tmp / "cancel.zip"
    _make_zip(package, {"app.txt": "new"})
    ctx = _ctx(app_dir, _manifest(package))
    ctx.cancel_requested.set()
    try:
        updater.run_update(ctx)
    except RuntimeError as exc:
        assert "用户已取消更新" in str(exc)
    else:
        raise AssertionError("pre-cancelled update should fail")


def _case_download_timeout(tmp: Path) -> None:
    app_dir = tmp / "timeout_app"
    app_dir.mkdir()
    manifest = {
        "package_url": "https://example.invalid/package.zip",
        "sha256": "0" * 64,
        "package_size": 1,
        "managed_files": ["app.txt"],
    }
    original_urlopen = updater.urllib.request.urlopen

    def _timeout(*_args, **_kwargs):
        raise urllib.error.URLError("_ssl.c:1063: The handshake operation timed out")

    updater.urllib.request.urlopen = _timeout
    try:
        try:
            updater.run_update(_ctx(app_dir, manifest))
        except RuntimeError as exc:
            assert "timed out" in str(exc)
        else:
            raise AssertionError("download timeout should fail")
    finally:
        updater.urllib.request.urlopen = original_urlopen


def _case_deferred_updater(tmp: Path) -> None:
    app_dir = tmp / "deferred_app"
    (app_dir / "src").mkdir(parents=True)
    (app_dir / "src" / "updater.py").write_text("old updater", encoding="utf-8")
    package = tmp / "deferred.zip"
    _make_zip(package, {"app.txt": "new app", "src/updater.py": "new updater"})
    manifest = _manifest(package, managed_files=["app.txt", "src/updater.py"])
    ctx = _ctx(app_dir, manifest)
    updater.run_update(ctx)
    assert (app_dir / "app.txt").read_text(encoding="utf-8") == "new app"
    assert (app_dir / "src" / "updater.py").read_text(encoding="utf-8") == "old updater"
    assert ctx.stager_path is not None and ctx.stager_path.exists()


def _case_external_download_manifest(tmp: Path) -> None:
    assert updater._manifest_external_download_only({"external_download_only": True})
    assert updater._manifest_external_download_only({"disable_in_app_update": True})
    assert updater._manifest_external_download_only({"manual_download_only": True})
    assert not updater._manifest_external_download_only({"external_download_only": False})


def _case_v2_deferred_delete_and_move(tmp: Path) -> None:
    app_dir = tmp / "v2_cleanup_app"
    app_dir.mkdir()
    (app_dir / "updater.py").write_text("legacy root updater", encoding="utf-8")
    (app_dir / "old_config.txt").write_text("settings", encoding="utf-8")
    package = tmp / "v2_cleanup.zip"
    _make_zip(package, {"app.txt": "new app"})
    manifest = _manifest(
        package,
        managed_files=["app.txt"],
        moved_paths=[{"from": "old_config.txt", "to": "src/old_config.txt"}],
        deleted_paths=["updater.py"],
    )
    ctx = _ctx(app_dir, manifest)
    updater.run_update(ctx)
    assert (app_dir / "app.txt").read_text(encoding="utf-8") == "new app"
    assert (app_dir / "src" / "old_config.txt").read_text(encoding="utf-8") == "settings"
    assert (app_dir / "updater.py").exists()
    assert ctx.stager_path is not None and ctx.stager_path.exists()
    stager_text = ctx.stager_path.read_text(encoding="utf-8")
    assert "updater.py" in stager_text


def _case_replace_failure_and_rollback(tmp: Path) -> None:
    app_dir = tmp / "rollback_app"
    app_dir.mkdir()
    (app_dir / "app.txt").write_text("old app", encoding="utf-8")
    (app_dir / "second.txt").write_text("old second", encoding="utf-8")
    package = tmp / "rollback.zip"
    _make_zip(package, {"app.txt": "new app", "second.txt": "new second"})
    manifest = _manifest(package, managed_files=["app.txt", "second.txt"])
    ctx = _ctx(app_dir, manifest)
    original_copy2 = updater.shutil.copy2

    def _failing_copy2(src, dst, *args, **kwargs):
        if Path(dst) == app_dir / "second.txt":
            raise PermissionError("simulated occupied file")
        return original_copy2(src, dst, *args, **kwargs)

    updater.shutil.copy2 = _failing_copy2
    try:
        try:
            updater.run_update(ctx)
        except PermissionError:
            pass
        else:
            raise AssertionError("simulated occupied file should fail")
    finally:
        updater.shutil.copy2 = original_copy2
    updater._restore_backups(ctx)
    assert (app_dir / "app.txt").read_text(encoding="utf-8") == "old app"
    assert (app_dir / "second.txt").read_text(encoding="utf-8") == "old second"


def _case_rollback_failure(tmp: Path) -> None:
    ctx = _ctx(tmp / "rollback_failure_app", {"package_url": "", "sha256": ""})
    ctx.backups.append((Path("missing.txt"), tmp / "does-not-exist"))
    try:
        updater._restore_backups(ctx)
    except Exception:
        return
    raise AssertionError("missing rollback backup should fail")


def main() -> None:
    cases = [
        _case_version_and_ua,
        _case_update_manifest_target_ranges,
        _case_package_size_mismatch_sha_ok,
        _case_package_size_and_sha_mismatch,
        _case_sha_mismatch,
        _case_zip_slip,
        _case_deleted_missing_and_success,
        _case_cancel_before_download,
        _case_download_timeout,
        _case_deferred_updater,
        _case_external_download_manifest,
        _case_v2_deferred_delete_and_move,
        _case_replace_failure_and_rollback,
        _case_rollback_failure,
    ]
    tmp_root = ROOT / "_updater_smoke_test"
    shutil.rmtree(tmp_root, ignore_errors=True)
    tmp_root.mkdir()
    try:
        for case in cases:
            case(tmp_root)
            print(f"PASS {case.__name__}")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
