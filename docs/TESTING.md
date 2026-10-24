# v1.0.3 testing and release validation

## Test levels

1. **Focused development tests** are small selections for fast feedback and
   are not sufficient for release.
2. **State-table and architecture tests** verify normative transition tables,
   executors, authoritative ownership, mirror independence, callback routing,
   projection authority and output authority.
3. **Full repository regression** is the automated release gate:

   `.venv\\Scripts\\python.exe -m pytest -q tests`

   Test counts vary with the checked-out commit. Record the actual count in the
   build report; the release requirement is `FAILED = 0`.
4. **Compilation/static sanity**:

   `.venv\\Scripts\\python.exe -m compileall -q nenolink_ai_marker`

   followed by `git diff --check`.
5. **Clean packaged build** requires a clean working tree, local HEAD equal to
   origin, a full regression pass, exact build provenance and artifact hashes.
6. **Manual packaged Windows acceptance** is required because headless tests
   cannot fully prove CustomTkinter mapping, visual highlighting, retained
   image resources, native dialogs, preview rendering, packaged FFmpeg/document
   dependencies or real Badges/Inspect switching. SOURCE/HEAD PASS is not
   PACKAGED RUNTIME PASS.

The Windows startup smoke harness validates packaged resources and detects a
visible top-level window owned by the launched executable process tree. It
requires the exact title `Nenolink AI-marker`, records the title, window
handle, PID and startup timing, and distinguishes process exit, probe failure
and timeout. On failure it retains the per-run boot log and diagnostic report;
on success it removes temporary artifacts. Both packaged and standalone
`-EmbeddedResources` smoke gates must pass before the build script creates its
ZIP. This smoke check is not a substitute for manual packaged Windows
acceptance.

## Manual v1.0.3 acceptance sequence

Run `Images → Video → PDF → PPTX → Badges → Inspect → Badges → return to
content`. Check active top navigation, filename/status, loaded preview, badge
and applicable own-logo rendering, content-to-content confirmation, clean
Continue destinations, exact Cancel preservation, PDF page/scope behavior,
PPTX slide/scope behavior, tool preservation and actual Badges↔Inspect
replacement. Returning to content must restore the underlying workspace.

Confirm Global Reset clears Image, Video, PDF, PPTX and tool state. Exercise
Save/Process for all four production formats.

Inspect File acceptance should cover marked and unmarked image/video/PDF/PPTX
files, DOCX metadata, invalid inputs, localized errors and the read-only
contract. `Found` confirms a recognized metadata declaration only; `Not found`
does not establish that AI was not used.

## Release lesson

Earlier checkpoints used selected test scopes. The release process explicitly
distinguishes those scopes from the full repository suite above, so a selected
checkpoint must not be described as “all tests”.

Presentation normalization checks also cover compact FILE actions, shared
Badge/Logo geometry, Video's first-five-seconds default, blank unloaded
document status, and bounded PDF/PPTX preview fitting. The earlier unbounded
viewport interpretation from 4D16B failed Windows visual acceptance and is no
longer the runtime sizing model.

Production formats are Images, Video, PDF and PowerPoint/Slides. DOCX is not a
v1.0.3 production workspace, although Inspect File reads DOCX metadata.

The production UI uses one Shell FSM plus four independent workspace FSMs.
`WorkspaceControlPanel` composes natural-height sections; SourceControl,
SaveControl, BadgeControl and LogoControl are stateless. Headless tests do
not prove Windows/Tk geometry or packaged runtime behavior. The four-workspace
panel hard cutover is complete; PDF/PPTX 80% preview-fit runtime acceptance
remains a separate checkpoint.

# Localization release gate

The supported production languages are English, Danish, German, French,
Spanish, Italian, Portuguese, Dutch, Swedish, Norwegian, Polish and Czech.
`nenolink_ai_marker.i18n.PRODUCTION_UI_KEYS` is the authoritative inventory
for normal visible UI templates. The parameterized 4D17B localization tests
require every supported locale to provide each key with a non-blank value;
English is only a defensive recovery fallback, not a normal production source.
Dynamic page, slide, selection, warning and status text must be emitted from
localized templates. Changing language is presentation-only and must not alter
any workspace state, scope, physical document position, or output settings.

# Documentation and user-guide packaging

The Danish and English user guides are maintained in
`docs/USER_GUIDE_DA.md` and `docs/USER_GUIDE_EN.md`; regenerate their existing
PDFs with `python scripts/build-user-guide.py`. Tests verify guide source,
generated PDF content/version, language-specific path selection and inclusion
of `docs` in both the PyInstaller spec and Windows distribution folder. The
application selects the Danish or English PDF from the current UI language;
other interface locales use the English guide. A source-level packaging test
does not prove the contents of an EXE that has not been rebuilt; guide opening
inside that packaged build remains a separate Windows acceptance check.
