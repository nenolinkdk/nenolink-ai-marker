# Codex work order — Nenolink AI Marker 1.0.3

## Start now, continue safely later

Implement version 1.0.3 incrementally on this branch. The available development budget is limited today, so prefer small, testable commits and leave the branch in a clean, resumable state after each step. Do not attempt to finish every document type in one run.

Read first:
- `docs/V1.0.3-PLAN.md`
- `docs/ROADMAP.md`
- existing tests and architecture before modifying code.

Related issues: #2 UI, #3 PPTX, #4 PDF, #5 DOCX, #6 shared processors/metadata/logo, #7 European localisation.

## Priority for the first work session

1. Audit the current codebase and tests. Do not regress the working image/video functionality.
2. Introduce/refactor the application shell to retain the current header and add compact tabs for Images, Video, PDF, PowerPoint/Slides and Word.
3. Keep controls format-specific so the normal workflow fits a typical laptop screen without routine vertical scrolling. Advanced/rare controls may be collapsible.
4. Establish shared models/interfaces for disclosure, logo, output, metadata, language and source-file protection, but avoid an unnecessary large rewrite.
5. Implement PowerPoint/PPTX first if the architecture is ready:
   - one slide;
   - individually selected non-contiguous slides if practical;
   - slide range;
   - entire presentation;
   - AI badge/disclosure;
   - own/company logo where safe;
   - metadata where robust;
   - save to a new .pptx, never overwrite source by default.
6. Then implement PDF page selection/marking if resources remain.
7. DOCX comes after PPTX/PDF and may remain a technical spike until formatting preservation is proven.

## European requirements

- Preserve existing European UI languages.
- Keep UI language separate from disclosure/output-label language.
- No hard-coded English in processors.
- Unicode-safe filenames, labels and metadata.
- Architecture must make additional European languages easy to add.
- Use careful wording: AI Marker supports transparency/documentation; do not claim guaranteed EU AI Act compliance.

## Logo

Support a user/company logo in every document/media format where placement is safe and predictable. Reuse common logo settings (enable, file, position, size, margin, opacity where appropriate). Do not force logo insertion where it risks damaging content.

## Guardrails

- Local Windows processing remains the default/product principle.
- Never overwrite source files by default.
- Preserve existing image/video behaviour.
- Do not turn the app into a general document/image/video editor.
- Add tests before or with each supported document operation.
- For PDFs, be cautious with signatures, forms, annotations and embedded structures.
- Initial Office scope is .pptx and .docx, not legacy .ppt/.doc.
- Do not silently claim unsupported metadata or selection capabilities.

## Stop/resume protocol

When today's resource/time budget is reached:
1. finish the smallest coherent unit in progress;
2. run relevant tests;
3. commit and push completed work to this branch;
4. leave no half-generated release artefacts;
5. update `docs/V1.0.3-STATUS.md` with:
   - completed;
   - tests run/results;
   - known problems;
   - next exact task;
   - files/modules touched;
   - any decisions still needed.

Do not merge to main and do not create a release unless explicitly requested.
