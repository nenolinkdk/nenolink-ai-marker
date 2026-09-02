# Nenolink AI Marker - User Guide

Application version: 0.4.0<br>
Document language: English<br>
Updated: 2 September 2026<br>
Publisher: Nenolink<br>
Denmark

## 1. What Nenolink AI Marker does

Nenolink AI Marker adds a visible disclosure badge to images and, when FFmpeg is installed, videos. It supports individual images and repeatable folder batches. Originals are never intentionally overwritten; output names end in `_ai`.

The Nenolink badge system is a practical transparency system. Choose wording that accurately describes how AI was involved in the specific content or workflow.

> **Legal notice:** Nenolink AI Marker is a practical transparency and labelling tool. Its badges and documentation are not legal advice, certification, regulatory approval, or a guarantee of compliance with the EU AI Act or any other requirement. Users remain responsible for choosing appropriate disclosures, reviewing output, and complying with applicable laws, contracts, platform rules, and professional requirements. See the full Legal Notice and Disclaimer near the end of this guide.

## 2. Installation and first start

Extract the complete Windows ZIP to a writable folder. Keep the EXE, `assets`, `locales`, and `docs` together. Start `Nenolink-AI-Marker.exe`. Windows may show a reputation warning for an unsigned download; verify that the file came from the official Nenolink release before continuing.

The app needs no administrator rights. Settings are stored under `%APPDATA%\Nenolink\AI Marker\settings.json`, so replacing the program folder does not normally remove preferences.

## 3. Language selection

Choose a language in the top bar. English, Danish, German, French, Spanish, Italian, Portuguese, Dutch, Swedish, Norwegian, Polish, and Czech are included. The choice is saved immediately. Missing translated text falls back to English. The product name and badge artwork do not change with the interface language.

## 4. Standard and custom badge folders

Open **Badge settings**. **Nenolink Standard Badges** uses the ten files bundled in `assets\badges`. To use your own transparent PNG, select **Custom Badge Folder**, choose a folder, and click **Refresh Badges** after adding files. The app reads custom files in place and does not copy or alter them. If a saved custom folder disappears, the app reports the exact path and temporarily uses standard badges while retaining the old path for correction.

## 5. Selecting a badge

Select a filename from the badge menu. The same selected badge is used for the single-image preview, saved images, and every selected item in a folder batch. Refreshing preserves the selection when the file still exists.

## 6. Badge preview

The Badge settings view shows the badge without stretching it. Standard badges also show a display name and short usage description. Transparency and aspect ratio are preserved.

## 7. Processing a single image

Choose **Single image**, then **Choose Images**. JPG, JPEG, PNG, and WebP are supported. Adjust placement and inspect the preview. Click **Start Processing**, choose an output folder, and review the completion message. Full-resolution originals are used for final output; the preview is only a scaled display.

## 8. Processing video

Video batch support accepts MP4, MOV, MKV, AVI, and WebM. It requires an independently installed `ffmpeg` executable available on the Windows `PATH`. Audio is copied where the chosen output container permits it. Encoding uses H.264. Container/codec combinations vary; test an output before publication. If FFmpeg is missing or rejects one file, that file is recorded as an error and the batch continues.

## 9. Folder batch processing

Choose **Folder batch**, select an input folder, configure output and file options, then click **Scan Folder**. Review image, video, unsupported, selected-total, and destination counts. Click **Start Batch Processing** only after the scan. Progress shows the current filename and success, skip, and error totals. **Cancel Batch** stops before the next file; it does not delete completed outputs. A corrupt file does not stop later files.

## 10. Input and output folders

The default output is an editable `AI-marked` subfolder inside the input folder. Alternatively, choose a separate output folder. **Include subfolders** scans recursively. **Preserve folder structure** recreates relative folders under the destination. Existing output files are skipped, never overwritten. Output naming is `originalname_ai.ext`.

## 11. Position, size, margin, and opacity

Position can be top-left, top-right, bottom-left, or bottom-right. Size is a percentage of image width. Margin is measured in source pixels from the chosen edges. Opacity ranges from fully transparent to fully opaque. The app limits extreme settings so the badge remains within the media frame.

## 12. Choosing the right standard badge

The first four badges describe broad disclosure status. The remaining six describe a media type or workflow. A badge is a concise signal, not a complete provenance record. Keep supporting information when context requires it.

### 13. AI Assisted

Recommended when AI contributed but a person remained substantially involved in planning, selection, editing, or authorship.

### 14. AI Generated

Recommended when an AI system primarily generated the content. Human prompting or selection does not by itself make the output non-generated.

### 15. AI Modified

Recommended when AI materially changed existing content, such as substantial inpainting, replacement, synthesis, or transformation.

### 16. Human Reviewed

Recommended as an additional disclosure when a person reviewed AI-related output before publication. Review does not guarantee correctness, safety, legality, or regulatory compliance.

### 17. AI Image

Recommended for image-specific AI generation or material modification.

### 18. AI Video

Recommended for video-specific AI generation or material modification.

### 19. AI Audio

Recommended for synthetic or materially AI-modified speech, music, sound, or other audio.

### 20. AI Software

Recommended when AI materially assisted production of software or source code. It is not a security or quality certification.

### 21. AI Translation

Recommended when AI translated content between languages. Consider human review for consequential or specialist material.

### 22. AI Localization

Recommended when AI helped adapt content to a locale, market, or culture beyond direct translation.

## 23. EU AI Act transparency background

Regulation (EU) 2024/1689, commonly called the EU AI Act, contains transparency obligations for providers and deployers of certain AI systems. Article 50 addresses, among other matters, informing people when they interact with certain AI systems, machine-readable marking of synthetic outputs by providers, and disclosure duties for certain deepfake and public-interest text uses. The exact duties, exceptions, timing, technical standards, and responsible party depend on the facts and applicable law.

Nenolink AI Marker adds a visible badge. A visible badge is not the same as every machine-readable marking or disclosure that Article 50 may require. Not every Nenolink badge is individually mandated by the EU AI Act, and using this application does not automatically ensure compliance. Consult the official regulation and qualified legal advice for your situation.

Official source: Regulation (EU) 2024/1689, Article 50, EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689

## 24. File compatibility and processing limits

As practical guidance, images up to 50 MB and videos up to 2 GB are recommended. These are recommendations, not guaranteed technical maximums; larger files may still work.

Not every image or video file can necessarily be processed. Compatibility and practical processing limits depend on the file format, codec, resolution, duration, file size, whether the file is damaged or corrupt, unusual encoding, available RAM, CPU performance, available disk space, and temporary processing space. Video processing also depends on the installed FFmpeg version and whether FFmpeg supports the file's container, codecs, and encoding.

No fixed maximum file size is defined. A file that works on one computer may fail or take substantially longer on another because practical limits depend partly on the user's computer and available resources. Keep original files and review every processed output before publication or distribution.

## 25. Limitations and user responsibility

You are responsible for selecting an accurate badge, obtaining rights to source media and badge artwork, reviewing outputs, retaining originals, and meeting applicable contractual, platform, accessibility, privacy, intellectual-property, consumer-protection, and AI rules. Visible overlays can be cropped or removed. The tool does not embed cryptographic provenance and does not verify whether content was made with AI.

## Legal Notice and Disclaimer

Nenolink AI Marker is a software tool designed to assist users in providing transparent information about the use of artificial intelligence in digital content and production processes.

The badges, descriptions, recommendations, and documentation provided with the software constitute a practical transparency and labelling system developed by Nenolink. They do not constitute legal advice, certification, regulatory approval, or a guarantee of compliance with Regulation (EU) 2024/1689 (the EU Artificial Intelligence Act) or any other applicable law or regulation.

Not every Nenolink AI badge corresponds to a specific legal labelling requirement. Some badges are provided voluntarily to support greater transparency about how AI has been used.

The appropriate disclosure or labelling requirements depend on the content, the AI system involved, the user's role, the context in which the content is published, and applicable legislation.

Users remain responsible for determining whether and how their content must be labelled and for complying with applicable laws, contractual obligations, platform rules, and professional requirements.

References to the EU AI Act and other regulatory material are provided for general informational purposes. Legislation, regulatory guidance, and interpretations may change over time. Users should consult current official sources and, where necessary, obtain appropriate professional or legal advice.

Nenolink does not warrant that applying a badge with Nenolink AI Marker will by itself satisfy any particular legal, regulatory, or contractual disclosure requirement.

Software output should be reviewed by the user before publication or distribution.

Nenolink AI Marker must not be presented as:

- an EU-certified compliance tool;
- an automated EU AI Act compliance system;
- legal advice; or
- a guarantee that content has been correctly classified.

## 26. Troubleshooting

- **No badges found:** Confirm that PNG files are directly inside the folder shown in the message, then click **Refresh Badges**.
- **Custom folder missing:** Reconnect the drive or choose a replacement folder. Standard badges remain available.
- **Image will not open:** Confirm it is a valid JPG, JPEG, PNG, or WebP, not merely renamed.
- **Large or complex file fails:** Close other demanding applications, confirm sufficient RAM and free disk space, and try a smaller-resolution copy while retaining the original.
- **Damaged or unusually encoded file:** Open and re-export a copy in a common format with a trusted editor, then process the copy. Never discard the original.
- **Video fails:** Run `ffmpeg -version` in Command Prompt, ensure FFmpeg is on `PATH`, and confirm that FFmpeg supports the container and codecs. Very long, high-resolution, or unusually encoded videos can require substantial CPU, RAM, disk, and temporary space.
- **Processing stops or the disk fills:** Free disk space, including space used for temporary processing, then retry. Review the resulting file completely before publication or distribution.
- **PDF guide does not open:** Confirm `docs\Nenolink-AI-Marker-User-Guide-EN.pdf` remains beside the application structure and that Windows has a default PDF viewer.
- **Unexpected output location:** Scan again after changing input or output settings and read the displayed destination.
- **Existing output skipped:** Rename or move the existing `_ai` file. The application does not overwrite it.
- **Settings seem damaged:** Close the app, back up and remove `%APPDATA%\Nenolink\AI Marker\settings.json`; defaults are recreated on next start.

## Support and attribution

Nenolink AI Marker - (c) Henrik Nielsen - https://nenolink.com
