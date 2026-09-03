# Bundled runtime components

Nenolink AI Marker 0.5.0 is packaged with third-party runtime components. This notice records the versions selected by the Windows release build; the accompanying license files contain the authoritative terms.

| Component | Release-build version | License | Project/source |
| --- | --- | --- | --- |
| CPython | 3.12.9 | Python Software Foundation License Version 2 and historical notices | https://www.python.org/ |
| Tcl/Tk | 8.6 | Tcl/Tk license terms | https://www.tcl.tk/ |
| CustomTkinter | 5.2.2 | MIT (license file distributed by the installed package) | https://github.com/TomSchimansky/CustomTkinter |
| Pillow | 11.1.0 | MIT-CMU | https://python-pillow.org/ |
| darkdetect | 0.8.0 | BSD-3-Clause | https://github.com/albertosottile/darkdetect |
| packaging | 24.2 | Apache-2.0 or BSD-2-Clause | https://github.com/pypa/packaging |
| NumPy | 2.2.3 | BSD-3-Clause, with bundled third-party notices in its license file | https://numpy.org/ |
| PyInstaller bootloader | 6.22.2 | GPL-2.0-or-later with the PyInstaller bootloader exception | https://pyinstaller.org/ |

The executable also includes standard-library and operating-system runtime material pulled in by the build tool. Copyright remains with the respective authors. No ownership of these third-party components is claimed by Nenolink.

The release build copies the license files supplied with CPython, Tcl/Tk, CustomTkinter, Pillow, darkdetect, packaging, and NumPy into this directory. FFmpeg is documented separately in `FFMPEG.md`, with the GNU GPL version 3 text in `GPL-3.0.txt`.

The FFmpeg source/build-material obligations described in `FFMPEG.md` require review by the distributor before public or commercial distribution. This notice is factual release documentation and is not legal advice or a conclusion that a particular distribution model complies with a license.
