# Updates And Cloud Messages

ShapeYourPhoto 1.1.8 adds a signed cloud update and announcement path. Public docs describe the client contract and safety boundary only; server deployment details and private key handling live in ignored `private_docs/`.

## Client Modules

- `cloud_client.py`: fetches signed update manifests and message payloads.
- `cloud_security.py`: canonical JSON, sha256, Ed25519 signature verification, safe path helpers.
- `cloud_state.py`: local update deferral state with HMAC integrity.
- `integrity_guard.py`: required update/message module existence checks and optional signed core hash manifest verification.
- `ui/cloud_actions.py`: Tk-main-thread safe UI orchestration for startup checks, manual checks, message dialogs and updater launch.
- `ui/cloud_dialogs.py`: update, checking and cloud-message dialogs.
- `updater.py`: independent GUI updater with package verification, safe extraction, replacement, quarantine and rollback.

## Manifest Contract

The signed object should include:

```json
{
  "version": "1.1.8",
  "version_id": 2,
  "build_id": 2,
  "package_url": "https://helloalp.top/shapeyourphoto/updates/packages/shapeyourphoto-1.1.8.zip",
  "sha256": "...",
  "package_size": 123456,
  "release_notes": ["..."],
  "managed_files": ["app.py", "ui/cloud_actions.py"],
  "deleted_paths": [],
  "channel": "stable"
}
```

The wire response is an envelope:

```json
{
  "signed": { "...": "manifest or messages payload" },
  "signature": "base64-ed25519-signature"
}
```

`version_id` / `build_id` are monotonic and are compared against `APP_VERSION_ID` / `APP_BUILD_ID`.

The current production update base is `https://helloalp.top/shapeyourphoto/updates/`.
Server release steps, Apache/httpd paths, upload commands, signing keys and rollback notes are private operational docs and are not published with the public repository.

## Message Contract

Messages are returned in the same signed envelope:

```json
{
  "messages": [
    {
      "id": "notice-2026-05-10",
      "enabled": true,
      "min_version_id": 1,
      "max_version_id": 2,
      "title": "公告",
      "body": "可滚动正文",
      "countdown_enabled": true,
      "countdown_seconds": 5,
      "show_update_button": true
    }
  ]
}
```

Fetch failure is user-invisible during startup and only writes a short Console line.

## Updater Safety

- The main app writes the verified manifest to the user data directory, starts `updater.py`, then enters the normal closing splash flow.
- The updater downloads the package, validates size and sha256, rejects zip-slip paths, writes only under the app directory and only for managed paths.
- Deleted paths are quarantined under `data/update_quarantine/`.
- Protected local data directories are never deleted or replaced by delete-list logic.
- Cancel confirmation does not pause the running update before the user confirms; after confirmation, rollback is attempted at the next safe point.
