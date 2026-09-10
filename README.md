# Nenolink AI Marker 1.0.1

Nenolink AI Marker is Windows desktop software for adding visible AI disclosure badges to images and videos. Version 1.0.1 processes files locally and can also add optional user branding to images without changing the meaning of the AI disclosure metadata.

The standard package contains exactly these editable external assets: `ai-assisted.png`, `ai-generated.png`, `ai-modified.png`, `human-reviewed.png`, `ai-image.png`, `ai-video.png`, `ai-audio.png`, `ai-software.png`, `ai-translation.png`, and `ai-localization.png`, plus `badges.json`.

The full guide is in `docs/USER_GUIDE_EN.md` and `docs/Nenolink-AI-Marker-User-Guide-EN.pdf`.

## Features

- Visible AI labelling for JPG, JPEG, PNG and WebP images
- Visible AI labelling for MP4, MOV, MKV, AVI and WebM video
- Ten standard Nenolink AI badges and editable custom AI badge folders
- Optional **Own Logo** branding for single images and image batches
- Live image preview containing the selected AI badge and optional logo
- Independent badge/logo placement, size, margin and opacity
- Single-file Save As and repeatable folder batch processing with source-file protection
- Permanent, Beginning and End video badge modes using the bundled FFmpeg component
- Automatic Nenolink AI Marker metadata containing software, selected AI label and marker version
- Read-only **Inspect File** support for JPEG, PNG, WebP, MP4 and MOV metadata
- Twelve offline UI languages
- Local media processing without cloud upload, login, telemetry or analytics
- Optional asynchronous update checks against Nenolink's small HTTPS version manifest
- Preferences stored per user in `%APPDATA%\Nenolink\AI Marker\settings.json`

The Windows package includes FFmpeg. End users do not install FFmpeg or configure `PATH`; image processing remains independent of FFmpeg. No personal filesystem paths are written into Nenolink AI Marker metadata.

## Install and run on Windows

Python 3.11 or newer is recommended.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Standard badges are read from `assets\badges\`. Click **Refresh badges** after changing the folder.

## Use

1. Click **Choose Image or Video** and select a supported file.
2. Select an approved badge and its position.
3. Adjust size, margin and opacity while checking the preview.
4. For images, optionally enable **Own Logo**, choose a logo, and adjust its independent position, size, margin and opacity.
5. Click **Save Marked Image...** or **Save Marked Video...** and choose the editable Save As name, initially `originalname_ai.ext`.

Own Logo is branding, not an AI disclosure. It is applied only to images, never becomes the `AI Label` metadata value, and is not added to videos. Transparent PNG or WebP is recommended.

For a folder batch, choose an input and output mode, select recursive/media options, click **Scan Folder**, review the summary, and then click **Start Batch Processing**.

The source images are never overwritten. If one file in a batch fails, the application continues with the remaining files and reports the errors clearly.

The four main tabs are **Single File**, **Batch Processing**, **Badges**, and **Inspect File**. **Back** returns to Single File without clearing state. **Reset** restores defaults and the Welcome view while retaining the saved custom badge folder path.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Build a Windows executable

Use a 64-bit Windows Python installation that includes Tcl/Tk. Verify the exact interpreter before building:

```powershell
& "C:\path\to\python.exe" -c "import tkinter; print(tkinter.TkVersion)"
```

The command must complete successfully and print a Tk version (normally `8.6`). A minimal or embeddable Python distribution without a working Tcl/Tk runtime cannot produce this GUI build.

Then run the build script from the repository root, passing that same interpreter explicitly:

```powershell
.\build.ps1 -PythonPath "C:\path\to\python.exe"
```

The script repeats the tkinter check in its isolated build environment, installs the pinned build requirements, deletes the old `build\` and `dist\` directories, builds from `Nenolink-AI-Marker.spec`, and launches the resulting GUI. The build fails unless a real application window appears during the smoke test.

The complete application is written to `dist\Nenolink-AI-Marker-1.0.1\`. Python is not required on the computer that runs it. Keep the folder structure intact:

```text
Nenolink-AI-Marker-1.0.1\
  Nenolink-AI-Marker-1.0.1.exe
  assets\
    badges\
      *.png
      badges.json
    ui\
      welcome-europe.png
  locales\
    en.json
    da.json
    ...
  docs\
    USER_GUIDE_EN.md
    Nenolink-AI-Marker-User-Guide-EN.pdf
```

The badge folder remains external and editable. Add approved PNG badges beside the executable as shown above, then click **Refresh badges**. Badge paths are resolved from the application location, not the current working directory.

## Standard and custom badges

**Nenolink standard badges** is the default source. Version 1.0.1 ships the ten documented standard PNGs and `badges.json`. The application scans the directory dynamically and ignores non-PNG files.

To use your own badges, select **Use custom badge folder** in Settings and click **Browse**. The selected folder is remembered between sessions. Files are read in place and are never copied, renamed or modified. You can switch back to standard badges at any time. If a saved custom folder disappears, the application reports the path and falls back gracefully to the standard badges.

Language, badge source, custom folder, selected badge, placement and batch choices are stored per Windows user in `%APPDATA%\Nenolink\AI Marker\settings.json`. Settings therefore survive application replacement and Windows restarts without requiring administrator rights. Older settings from the previous Local AppData location are read automatically and migrated on the next save.

## Languages

The interface includes English, Dansk, Deutsch, Français, Español, Italiano, Português, Nederlands, Svenska, Norsk, Polski and Čeština. The selected language is remembered locally, missing keys fall back to English, and badge filenames are never translated.

## Update checks and privacy

Automatic update checking is enabled by default and may be disabled in the Badges area. At most once every 30 days, the application asynchronously requests `https://nenolink.com/downloads/ai-marker/latest.json`. A manual **Check for updates** action ignores that interval. The request contains only ordinary connection headers and the installed application version; it never uploads media, filenames, file paths, badge or logo choices, licence information, or a unique installation identifier. Failures do not interrupt normal offline use. A validated newer version appears as a red header link to the single approved Nenolink update page. The application never downloads or installs an EXE or ZIP automatically.

Translation files live in `locales\` beside the source application or packaged EXE. To add a translation:

1. Copy `locales\en.json` to a new locale code, for example `fi.json`.
2. Translate values only; keep the stable JSON keys unchanged.
3. Add the language name and code to `LANGUAGES` in `nenolink_ai_marker\i18n.py`.
4. Run the tests and rebuild the Windows package.

## Architecture and video

Image processing lives in `nenolink_ai_marker/processor.py`; scanning and batch/video orchestration live in `nenolink_ai_marker/batch.py`. Shared placement and persistent batch settings live in `MarkerSettings`. One corrupt input is isolated so later files continue.

## AI disclosure

See [AI_NOTICE.md](AI_NOTICE.md) for the project's AI-assisted development notice.

## Limitations and responsibility

- Own Logo applies to images, not video.
- Badge and logo may overlap; there is no automatic collision avoidance.
- Inspect File reads recognized Nenolink AI Marker metadata. It does not detect whether content was created or modified with AI.
- Metadata is not cryptographic proof, provenance, certification or a guarantee of authenticity.
- Nenolink AI Marker is not legal advice, certification or a guarantee of regulatory compliance. Users remain responsible for selecting appropriate disclosures and reviewing output.
- The bundled FFmpeg build is GPLv3. Commercial distributors must review and satisfy the corresponding source, notice and license obligations described in `THIRD_PARTY_NOTICES/FFMPEG.md` before distribution.

Copyright © Henrik Nielsen — [nenolink.com](https://nenolink.com)
