# Nenolink AI Marker 0.5.0

Windows desktop software for adding visible Nenolink AI disclosure badges to images and videos. Development on `main` also includes optional own-logo branding for images while preserving the 0.5.0 metadata semantics.

The standard package contains exactly these editable external assets: `ai-assisted.png`, `ai-generated.png`, `ai-modified.png`, `human-reviewed.png`, `ai-image.png`, `ai-video.png`, `ai-audio.png`, `ai-software.png`, `ai-translation.png`, and `ai-localization.png`, plus `badges.json`.

The full guide is in `docs/USER_GUIDE_EN.md` and `docs/Nenolink-AI-Marker-User-Guide-EN.pdf`.

## Features

- Opens JPG, JPEG, PNG and WebP images
- Discovers PNG badges dynamically from `assets/badges/`
- Places a badge in any corner
- Adjusts badge size, pixel margin and opacity
- Optionally adds an independently positioned PNG, JPG/JPEG or WebP user logo to images and image batches
- Shows a preview before saving
- Processes selected images or complete folder trees
- Overlays badges permanently or at the beginning/end of video using the bundled FFmpeg component
- Scans folders before batch processing and reports counts and destination
- Switches the complete interface between 12 offline languages
- Uses Nenolink standard badges or a user-selected badge folder
- Saves as `originalname_ai.ext` and adds `_2`, `_3`, etc. if needed
- Remembers preferences in `%APPDATA%\Nenolink\AI Marker\settings.json`
- Reads Nenolink AI Marker metadata from JPEG, PNG, WebP, MP4 and MOV without modifying the file

The Windows package includes FFmpeg. End users do not install FFmpeg or configure `PATH`; image processing remains independent of FFmpeg.

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

The complete application is written to `dist\Nenolink-AI-Marker\`. Python is not required on the computer that runs it. Keep the folder structure intact:

```text
Nenolink-AI-Marker\
  Nenolink-AI-Marker.exe
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

**Nenolink standard badges** is the default source. Version 0.3 ships the ten documented standard PNGs and `badges.json`. The application scans the directory dynamically and ignores non-PNG files.

To use your own badges, select **Use custom badge folder** in Settings and click **Browse**. The selected folder is remembered between sessions. Files are read in place and are never copied, renamed or modified. You can switch back to standard badges at any time. If a saved custom folder disappears, the application reports the path and falls back gracefully to the standard badges.

Language, badge source, custom folder, selected badge, placement and batch choices are stored per Windows user in `%APPDATA%\Nenolink\AI Marker\settings.json`. Settings therefore survive application replacement and Windows restarts without requiring administrator rights. Older settings from the previous Local AppData location are read automatically and migrated on the next save.

## Languages

The interface includes English, Dansk, Deutsch, Français, Español, Italiano, Português, Nederlands, Svenska, Norsk, Polski and Čeština. The selected language is remembered locally. Everything works offline, missing keys fall back to English, and badge filenames are never translated.

Translation files live in `locales\` beside the source application or packaged EXE. To add a translation:

1. Copy `locales\en.json` to a new locale code, for example `fi.json`.
2. Translate values only; keep the stable JSON keys unchanged.
3. Add the language name and code to `LANGUAGES` in `nenolink_ai_marker\i18n.py`.
4. Run the tests and rebuild the Windows package.

## Architecture and video

Image processing lives in `nenolink_ai_marker/processor.py`; scanning and batch/video orchestration live in `nenolink_ai_marker/batch.py`. Shared placement and persistent batch settings live in `MarkerSettings`. One corrupt input is isolated so later files continue.

## AI disclosure

See [AI_NOTICE.md](AI_NOTICE.md) for the project's AI-assisted development notice.

Copyright © Henrik Nielsen — [nenolink.com](https://nenolink.com)
