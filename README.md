# Nenolink AI Marker

Nenolink AI Marker 0.1 is a Windows desktop application that applies approved Nenolink AI disclosure badges to images. It supports individual images and batches while always preserving the original files.

## Features

- Opens JPG, JPEG, PNG and WebP images
- Discovers PNG badges dynamically from `assets/badges/`
- Places a badge in any corner
- Adjusts badge size, pixel margin and opacity
- Shows a preview before saving
- Processes multiple selected images in one batch
- Saves as `originalname_ai.ext` and adds `_2`, `_3`, etc. if needed
- Remembers the last settings in `%LOCALAPPDATA%\NenolinkAI Marker\config.json`

Video is intentionally not supported in version 0.1.

## Install and run on Windows

Python 3.11 or newer is recommended.

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Copy approved, transparent PNG badge files into `assets\badges\`, then click **Refresh badges** in the application. Badge assets are not bundled in this repository.

## Use

1. Click **Open images** and select one or more supported images.
2. Select an approved badge and its position.
3. Adjust size, margin and opacity while checking the preview.
4. Click **Save marked images** and select an output folder.

The source images are never overwritten. If one file in a batch fails, the application continues with the remaining files and reports the errors clearly.

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
```

The badge folder remains external and editable. Add approved PNG badges beside the executable as shown above, then click **Refresh badges**. Badge paths are resolved from the application location, not the current working directory.

## Architecture and version 0.2

Image processing lives outside the GUI in `nenolink_ai_marker/processor.py`. `MediaProcessor` defines the small processing boundary. A future FFmpeg-backed video processor can implement that boundary and be selected by media type without mixing FFmpeg commands into the GUI. Shared placement settings live in `MarkerSettings`.

## AI disclosure

See [AI_NOTICE.md](AI_NOTICE.md) for the project's AI-assisted development notice.

Copyright © Henrik Nielsen — [nenolink.com](https://nenolink.com)
