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

Run the included PowerShell build script from the repository root:

```powershell
.\build.ps1
```

If Python is not in `PATH`, pass it explicitly: `.\build.ps1 -PythonPath C:\path\to\python.exe`.

The standalone application is written to `dist\Nenolink-AI-Marker.exe`. Python is not required on the computer that runs the resulting executable. Keep `dist\assets\badges\` beside the executable and add approved PNG badges there. The application discovers new badges dynamically when **Refresh badges** is clicked.

## Architecture and version 0.2

Image processing lives outside the GUI in `nenolink_ai_marker/processor.py`. `MediaProcessor` defines the small processing boundary. A future FFmpeg-backed video processor can implement that boundary and be selected by media type without mixing FFmpeg commands into the GUI. Shared placement settings live in `MarkerSettings`.

## AI disclosure

See [AI_NOTICE.md](AI_NOTICE.md) for the project's AI-assisted development notice.
