# EXIF And Developer Mode

## EXIF Editing

Normal mode only exposes safe text fields:

- Title / description
- Artist / author
- Copyright
- Keywords / notes

Developer mode can expose additional EXIF fields such as camera make/model, lens fields, date fields, exposure values, ISO, focal length and GPS summaries. When `exiftool` is installed or bundled, developer mode can also write GPS latitude/longitude/altitude plus selected XMP/IPTC text fields. Without `exiftool`, those advanced external fields are shown disabled with a backend-missing reason.

## Protected Fields

ShapeYourPhoto integrity and provenance fields are never editable through UI:

- Any EXIF/XMP/IPTC field whose value contains `shapeyourphoto`, case-insensitive.
- Software tags added by ShapeYourPhoto, such as `Modified by ShapeYourPhoto vX.X.X`.
- Orientation, ICC profile, MakerNote and other fields that can break image display, vendor metadata or the repair chain.

Protected fields are either omitted from editable controls or shown disabled with the reason. Save logic repeats the marker check so advanced editing cannot bypass the UI state.

## Empty Field Behavior

Empty fields must be real empty strings. The editor must not add invisible placeholder spaces, padding characters or newlines to make a field selectable. All Entry controls should behave consistently when empty.

## Developer Mode

Developer mode is unlocked from Settings -> Developer Mode. Password verification uses PBKDF2-SHA256 with salt and high iteration count. The password hash comes from a local secret file or environment variable and is never hard-coded into public source.

Unlock state is held only in memory:

- Valid for the current process only.
- Lost after close, restart or crash.
- Not written into `app_settings.json`.

Developer mode only expands local UI capabilities. It is not DRM, not a remote administration mechanism and not a guarantee against a user modifying open-source code.
