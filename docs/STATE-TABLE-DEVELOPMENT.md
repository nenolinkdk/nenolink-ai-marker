# State-table development standard

This is the permanent development and testing standard for Nenolink AI Marker.

## Architecture

The application has one global shell state machine and four independent peer
workspace state machines:

```text
GLOBAL SHELL FSM
├── IMAGE WORKSPACE FSM
├── VIDEO WORKSPACE FSM
├── PDF WORKSPACE FSM
└── PPTX WORKSPACE FSM
```

Shell owns global content navigation, tool overlays and Reset coordination.
Each workspace owns its own typed events, transition specification, reducer,
runtime state, projection, preview and output boundary. A workspace must not
implement shell policy, and the shell must not implement workspace policy.

## Normative pipeline

```text
UI event
→ typed event
→ machine-readable state table
→ reducer / executor
→ authoritative state
→ projection
→ UI / preview / output
```

For Shell, the equivalent route is:

```text
UI command → typed shell event → ShellTransitionSpec
→ ShellTransitionExecutor → lifecycle execution
→ TransitionReceipt → resulting shell state

## Evidence levels established by the migration

- Normative state-table tests prove transition rules and executor outcomes.
- Authority/projection tests prove compatibility mirrors cannot override
  authoritative state.
- Callback-path tests prove active UI controls reach the authoritative owner.
- Regression tests protect product behavior.
- Packaged Windows acceptance verifies real CustomTkinter mapping, dialogs,
  retained images, rendering and packaged dependencies that headless tests
  cannot fully prove.

A selected checkpoint suite is not a release gate. State-table coverage and
the full release regression suite are separate requirements. The canonical
release command is:

`.venv\\Scripts\\python.exe -m pytest -q tests`

Test counts vary with the checked-out commit. Record the actual count in the
build report; the release requirement is zero failures.
```

The table/specification is required behavior. Receipts, where present, only
observe execution; they never control it.

## Ownership rules

- Every live runtime value has exactly one authoritative owner.
- Tk variables and widgets are adapters/projections, never state owners.
- MarkerApp compatibility fields are one-way mirrors only.
- Mirrors flow `authoritative state → compatibility consumer`; they never write back.
- Persistent settings may seed workspace state but are not live runtime owners.
- Processors, renderers, FFmpeg and caches consume projections and own only
  transient resources or results, never workspace runtime state.
- UI callbacks dispatch typed events and do not contain independent transition policy.
- Geometry and deterministic rendering calculations do not need artificial FSM states.

## Workspace invariants

Image uses `ImageWorkspaceState` and `IMAGE_TRANSITION_TABLE`; preview and
output derive from that state. Video uses `VideoWorkspaceState` and
`VIDEO_TRANSITION_TABLE`; FFmpeg is a service boundary. PDF uses
`PdfWorkspaceState` and `PDF_TRANSITION_TABLE`. PDF processing scope is not
the physical preview page, and draft scope is not effective scope. Invalid
updates preserve the last valid scope; physical navigation does not change it;
output uses effective scope. PPTX follows the same invariants for slides with
`PptxWorkspaceState` and `PPTX_TRANSITION_TABLE`.

## Mandatory testing gates

Tests must be derived or parameterized from the normative table wherever
practical. For every deterministic transition:

```text
specified → executable → executed → verified → passed
```

Required gates are:

`UNTESTED DETERMINISTIC TRANSITIONS = 0` and
`FAILED DETERMINISTIC TRANSITIONS = 0`.

Tests must also verify unrelated-state preservation and, where practical, the
actual production widget binding through typed event, reducer and projection.
Headless tests cannot claim Windows geometry or packaged-runtime acceptance.

The gates remain distinct:

1. **STATE-TABLE PASS** — normative deterministic behavior is modeled and tested.
2. **SOURCE/REGRESSION PASS** — relevant workspace, shell, compilation and source checks pass.
3. **PACKAGED RUNTIME PASS** — a clean Windows executable is manually verified.

## Change discipline

```text
change
→ update/verify normative table
→ table-derived tests
→ preservation tests
→ real callback tests
→ relevant regression
→ compilation + git diff --check
→ clean commit
→ build
→ packaged Windows acceptance
```

Scope the tests to the changed workspace or shell layer. A purely visual
change does not require an artificial state transition, but still requires
appropriate UI/runtime verification. Packaged Windows acceptance remains a
separate final gate and must never be inferred from headless tests.

See [WORKSPACE-STATE-AUDIT.md](WORKSPACE-STATE-AUDIT.md) for the current
implementation status.

## 4D16 presentation boundary

The Shell FSM and four independent local workspace FSMs remain the semantic
authority. `WorkspaceControlPanel` is a stateless composition owner for the
left control column; Image is the canonical panel reference. SourceControl,
SaveControl, BadgeControl and LogoControl are shared stateless presentation
controls with zero semantic authority. PDF/PPTX scope controls remain local
to their document workspaces. Windows runtime acceptance is separate from
headless tests; PDF/PPTX preview-fit acceptance remains a separate gate.

## Current v1.0.3 workspace and processing contract

The four production formats have separate runtime owners and separate local
transition tables: `ImageWorkspaceState` / `IMAGE_TRANSITION_TABLE`,
`VideoWorkspaceState` / `VIDEO_TRANSITION_TABLE`, `PdfWorkspaceState` /
`PDF_TRANSITION_TABLE`, and `PptxWorkspaceState` / `PPTX_TRANSITION_TABLE`.
Events are reduced into the owning state and `project()` updates the currently
mounted presentation. Shared `WorkspaceControlPanel`, `SourceControl`,
`SaveControl`, `BadgeControl`, `LogoControl`, `ParameterRow`, and `PreviewShell`
are stateless presentation/composition pieces. PDF and PPTX additionally own
format-specific document-scope and physical-navigation controls. Shared UI
components never own workspace values or transition policy.

PDF and PPTX deliberately keep processing scope separate from the physical
preview page/slide. Scope text is a draft; Update validates it against the
loaded document. Invalid updates preserve the last valid active scope. Reset
confirmation clears all four workspace sessions and tool results and returns
to clean Images; Cancel preserves the current session. Content-to-content
navigation clears the source workspace according to the Shell transition
contract, while Badges and Inspect overlays preserve the underlying workspace.

Preview is state-derived, not a second state owner. Video uses a representative
frame at approximately one second; preview and output consume independent
badge/logo timing values from `VideoWorkspaceState`. Video output is submitted
as an immutable `VideoProcessingRequest` to the existing FFmpeg service.
`VideoWorkspace.save()` starts a worker thread and polls its result on the Tk
thread; only the UI thread updates widgets. A duplicate-save guard disables
Save while processing.

Each workspace Save callback builds its output request from authoritative
workspace state and invokes its existing processor/service. Save As dialogs
suggest a new `_ai` destination so source files are not overwritten by default.
PDF retains encrypted-file rejection, digital-signature warnings and document
hard limits. PDF/PPTX metadata records the selected AI label as a declaration;
it does not independently verify AI use or file provenance.

Inspect File is a read-only metadata service for JPG/JPEG, PNG, WebP, MP4,
MOV, MKV, AVI, WebM, PDF, PPTX and DOCX. `Found` means recognized Nenolink
metadata was read; `Not found` is not evidence that AI was not used. Invalid,
unsupported, protected and over-limit files produce localized categorized
errors. DOCX inspection support does not make DOCX a fifth production
workspace.

Tests cover transition tables/reducers, authoritative projection, constructed
callbacks, processing requests, Inspect File, Reset and packaging resources.
Run `.venv\\Scripts\\python.exe -m pytest -q tests`, then compileall and
`git diff --check`. The canonical Windows packaging path is `build.ps1` with
`.venv-release` and `Nenolink-AI-Marker.spec`; it includes `docs`, `locales`,
badge/UI assets and bundled FFmpeg. Packaged smoke gates check packaged and
standalone resource modes and require a visible window owned by the launched
process with title `Nenolink AI-marker`. Source/test PASS and smoke PASS are
distinct from manual Windows acceptance of dialogs, transitions, previews and
Save output.
