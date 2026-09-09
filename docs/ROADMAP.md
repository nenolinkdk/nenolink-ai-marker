# Nenolink AI Marker — Product Roadmap

This document is the central collection point for future product ideas and possible extensions after version 1.0.0.

Items listed here are ideas, not commitments. Inclusion does not imply a promised version, release date, implementation order, or entitlement beyond the licence terms. The verified 1.0.0 release remains the technical baseline.

## Guiding principle

Nenolink AI Marker should remain primarily a practical transparency and marking tool. New features should support one or more of these purposes:

- AI transparency and disclosure
- human/no-AI disclosure
- branding
- practical preparation of media for publication
- machine-readable marking and inspection

Avoid turning the application into a general-purpose image, document, or video editor.

## 1. More document and content formats

### PDF

Possible PDF marking support:

- open `.pdf` files;
- add an AI badge to selected pages or all pages;
- optionally add own logo;
- configurable position, size, margin and opacity where technically appropriate;
- save as a new PDF;
- preserve the source file;
- investigate suitable metadata support.

PDF support should be designed carefully because PDFs may contain forms, signatures, annotations, embedded fonts and other structures that should not be damaged.

### Microsoft Word

Possible `.docx` support:

- add AI disclosure to a document;
- badge/logo in suitable document areas;
- optional text disclosure, for example in footer or document information;
- selected sections or whole document where practical;
- save as a new `.docx`;
- preserve the source file;
- investigate document metadata.

Initial scope should be `.docx`, not legacy `.doc`.

### Microsoft PowerPoint

Possible `.pptx` support:

- AI badge;
- own logo;
- optional short disclosure/footer text;
- current slide, selected slides or all slides;
- possible presets such as first slide, all slides, all except first/last, or slide range;
- four-corner placement;
- size, margin and opacity controls;
- save as a new `.pptx`;
- preserve the source file.

Initial scope should be `.pptx`, not legacy `.ppt`.

### Web content

Investigate marking for web publishing. Possible forms include:

- visible AI disclosure badges for website assets;
- exportable badge assets/snippets;
- metadata suitable for web publishing;
- assistance preparing marked images for Joomla, WordPress or ordinary HTML sites.

Web support needs a clearly defined scope before implementation so that the desktop application does not become a CMS.

## 2. Human-created / No-AI badge

Add an optional badge for content declared by the user to be created without generative AI.

Initial visual concept:

- green badge;
- `AI` symbol/text;
- red diagonal strike through `AI`;
- clear meaning such as `No AI`, `Human Created` or another carefully selected label.

Before implementation:

- settle terminology;
- distinguish `No AI` from `Human Reviewed`;
- avoid implying independent verification by Nenolink AI Marker;
- make clear that the user is making the declaration;
- define corresponding machine-readable metadata.

The application should not claim to detect whether AI was actually used.

## 3. Social-media image preparation

Add a dedicated workflow for preparing images for publishing while optionally applying an AI badge and own logo.

Possible platform presets:

- Instagram
- Facebook
- LinkedIn
- Pinterest

The preset catalogue should be maintainable because platform recommendations can change.

Possible workflow:

1. Select image.
2. Select destination/platform and format.
3. Choose fit method.
4. Preview result.
5. Optionally add AI badge.
6. Optionally add own logo.
7. Export a new image at the requested dimensions.

Possible fit methods:

- resize while preserving aspect ratio;
- crop to target aspect ratio;
- fit inside target canvas;
- padding/background where required;
- no upscaling unless explicitly enabled.

The original image must remain unchanged.

## 4. Custom image dimensions

In addition to social-media presets, allow exact output dimensions.

Possible controls:

- width in pixels;
- height in pixels;
- lock/unlock aspect ratio;
- crop or fit;
- optional output quality/compression setting;
- optional AI badge;
- optional own logo;
- preview before export.

Examples:

- website hero images;
- Open Graph images;
- thumbnails;
- banners;
- client-specified image sizes;
- marketplace or CMS requirements.

Batch processing could later support converting multiple images to one selected target size while applying the same badge/logo settings.

## 5. Combined Publish Image workflow

The social-media and custom-size features may be best implemented as one coherent feature rather than separate tools.

Working concept: `Prepare Image` or `Publish Image`.

It could combine:

- platform preset OR custom dimensions;
- resize/crop/fit;
- AI badge;
- own logo;
- output format;
- output quality;
- Save As;
- batch processing later.

This keeps the product focused: preparing transparent, branded media for publication rather than providing general image editing.

## 6. Future fulfilment/security improvements

Commercial infrastructure ideas are tracked here as product-operation improvements:

- Stripe webhooks for durable order fulfilment;
- order/download database;
- expiring or one-time download tokens;
- configurable download limits;
- restricted Stripe API key with minimum required permissions;
- controlled audit logging and retention policy;
- easier release-file switching for future versions.

See `SALES-AND-DOWNLOAD-SETUP.md` for the current production implementation.

## 7. Candidate prioritisation

A preliminary order for evaluation, not a commitment:

**Near-term candidates**

1. No-AI / Human Created badge.
2. Custom image dimensions.
3. Social-media image presets.
4. Combined Prepare/Publish Image workflow.

**Document expansion candidates**

5. PowerPoint (`.pptx`).
6. PDF.
7. Word (`.docx`).
8. Web-publishing support after its scope is defined.

The order may change after customer feedback and technical investigation.

## Adding new ideas

New feature ideas should be added to this file first. Larger items can later be promoted to dedicated specification documents and GitHub issues when they are selected for implementation.

Before development begins for any roadmap item, define:

- user problem;
- minimum scope;
- supported formats;
- source-file protection behaviour;
- metadata behaviour;
- UI impact;
- batch behaviour if relevant;
- tests and acceptance criteria;
- version target.
