# v1.0.3 testing and release validation

## Test levels

1. **Focused development tests** are small selections for fast feedback and
   are not sufficient for release.
2. **State-table and architecture tests** verify normative transition tables,
   executors, authoritative ownership, mirror independence, callback routing,
   projection authority and output authority.
3. **Full repository regression** is the automated release gate:

   `.venv\\Scripts\\python.exe -m pytest -q tests`

   The recorded v1.0.3 baseline is 496 passed and one warning. This number may
   change as tests are added or removed; the release requirement is
   `FAILED = 0`.
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

## Manual v1.0.3 acceptance sequence

Run `Images → Video → PDF → PPTX → Badges → Inspect → Badges → return to
content`. Check active top navigation, filename/status, loaded preview, badge
and applicable own-logo rendering, content-to-content confirmation, clean
Continue destinations, exact Cancel preservation, PDF page/scope behavior,
PPTX slide/scope behavior, tool preservation and actual Badges↔Inspect
replacement. Returning to content must restore the underlying workspace.

Confirm Global Reset clears Image, Video, PDF, PPTX and tool state. Exercise
Save/Process for all four production formats.

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
v1.0.3 production format.

The production UI uses one Shell FSM plus four independent workspace FSMs.
`WorkspaceControlPanel` composes natural-height sections; SourceControl,
SaveControl, BadgeControl and LogoControl are stateless. Headless tests do
not prove Windows/Tk geometry or packaged runtime behavior. The four-workspace
panel hard cutover is complete; PDF/PPTX 80% preview-fit runtime acceptance
remains a separate checkpoint.
