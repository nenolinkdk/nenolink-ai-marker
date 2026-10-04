# Workspace state audit (v1.0.3)

> **Historical note:** material below the current architecture section that
> describes migration targets is retained for traceability and is
> **HISTORICAL / PRE-MIGRATION**. It must not be read as the current route.

> **Current architecture baseline (3I-DOC1).** The historical audit tables
> below describe the pre-migration state and are retained as history. The
> current production baseline is the peer-workspace model documented at the
> end of this file.

This audit deliberately precedes implementation. The outer `ShellController`
remains the only owner of `IMAGE`, `VIDEO`, `PDF` and `PPTX` navigation.

| Workspace | Current runtime ownership | Preview | Scope | Output |
|---|---|---|---|---|
| Image | `sources`, selected source and shared `MarkerSettings` variables in `MarkerApp` | `preview_image` / `preview_photo` | not applicable | image processor and Save As |
| Video | selected source, video mode/duration and shared `MarkerSettings` variables | text/status preview (no player) | not applicable | FFmpeg processor and Save As |
| PDF | `pdf_path`, `pdf_info`, `pdf_preview_state`, `document_scope_states["pdf"]`, PDF badge variables | PDF preview renderer/state | independent validated page scope | `PdfProcessor` and metadata |
| PPTX | `PptxWorkspaceState` plus projected Tk variables for compatibility | `pptx_preview_state` / renderer | independent validated slide scope | `PptxProcessor` and metadata |

## Findings (HISTORICAL / PRE-MIGRATION)

Image and Video still use the shared persisted `MarkerSettings` as their
authoritative visual model. This is correct for their common badge/logo
preferences, but their widgets currently also hold the live values. PDF has
format-specific runtime and scope state, while visual settings are projected
from shared controls. PPTX now has an explicit internal state model, but its
Tk variables remain a projection boundary and need to be removed from preview
and output paths incrementally.

The main duplicated ownership risk is `MarkerApp`: it currently coordinates
format runtime, widgets and persistence in one class. A mechanical rewrite of
all four workspaces would risk the frozen navigation and processing behaviour.
The safe sequence is to establish adapters/events around existing state first,
then migrate one workspace at a time.

## Common contract (HISTORICAL / PRE-MIGRATION)

Each workspace should expose `load/clear`, `has_active_work`, visual property
events, `render_preview` and `process_output`. Events validate and mutate the
workspace state; both preview and output consume that state. UI variables are
draft/display values only.

For PDF/PPTX, physical page/slide navigation is independent of validated
processing scope. Cancel preserves the complete source state, Continue clears
the source runtime before ShellController mounts the destination, Tools/Back
does not clear it, and Reset unconditionally returns to clean Image.

## Recommended implementation sequence (HISTORICAL / PRE-MIGRATION)

1. Add a small common state/event contract and parity tests without changing
   behaviour.
2. Migrate Image visual state and preview/output projection.
3. Migrate Video visual/output state.
4. Migrate PDF file, preview, scope and visual state.
5. Align PPTX fully onto `PptxWorkspaceState` and widen its controls.
6. Run cross-workspace parity and navigation regressions.

## Phase 1 common contract

`nenolink_ai_marker.workspace_state` defines the deliberately small common
contract: `WorkspaceRuntimeState`, independent `BadgeVisualState` and
`LogoVisualState`, `WorkspaceEvent`, `has_active_work()` and
`clear_runtime_state()`. Format-specific scope is not part of this contract.

Tk variables remain UI input/projection adapters. Persistent `MarkerSettings`
may seed runtime state, but are not renderer state. Preview and output adapters
receive the same `visual_projection(state)` values. Badge and logo transitions
are isolated and cannot change file, physical navigation or format scope.

## Phase 2 Image reference

Image now owns `ImageWorkspaceState` for its selected file, badge/logo values
and preview runtime. Tk variables project events into this state; preview and
Save As use the same visual projection. Video, PDF and PPTX remain separate
migration phases.

## Phase 3 Video reference

Video now owns `VideoWorkspaceState` for its file, independent badge values,
and video-specific mode/duration. Existing controls remain adapters and Save
As consumes the state values. Video has no document scope or physical page
state.
## Phase 3 UI correction

Image keeps a responsive readable control column (approximately 35–40% of the workspace) while the preview receives the remaining width. Video follows the Image grouping and owns badge selection and visual state through `VideoWorkspaceState`. A representative frame is extracted with the bundled FFmpeg and composited through the same authoritative badge projection used by video output; preview extraction is runtime cache only and never modifies the source.
## Video preview correction

## Current peer-workspace contract

Production flow is:

`UI event → workspace → authoritative workspace state → projection or immutable processing request → UI/preview/processor`.

The shell owns only global navigation, the workspace registry, tool overlays,
locale and Reset coordination. Each workspace owns its format-specific UI,
lifecycle, callbacks, runtime state, preview and output orchestration.

Every workspace implements the common lifecycle contract:

- `mount(host)`: attach/build the view and project state;
- `unmount()`: detach the view without destroying the session;
- `project()`: state → UI projection;
- `has_active_work()`: state-owned active-work predicate;
- `clear_runtime_state()`: explicit session/runtime destruction.

`unmount()` is never a substitute for `clear_runtime_state()`.

### Ownership vocabulary

**Authoritative state** is the single source of truth for runtime values.
**Compatibility mirrors** are temporary one-way projections from state to
legacy/shared consumers; they never write back. Tk variables/widgets are UI
adapters, not state owners. CTkImage objects, extracted frames and preview
caches are UI/rendering resources. Dialogs, localization, status, asset
lookup, FFmpeg lookup and processors are application services.

### Image and Video reference implementations

| Concern | Image | Video |
|---|---|---|
| Registry | `ImageWorkspace` | `VideoWorkspace` |
| State | `ImageWorkspaceState` | `VideoWorkspaceState` |
| UI/lifecycle | `ImageWorkspace` | `VideoWorkspace` |
| Preview | `ImageWorkspace.refresh_preview()` | `VideoWorkspace.refresh_preview()` |
| Output | `ImageWorkspace.save()` → `ImageProcessingRequest` | `VideoWorkspace.save()` → `VideoProcessingRequest` |
| Processor | `ImageProcessor` | `BatchProcessor.process_video()` |
| Active work/clear | workspace state/lifecycle | workspace state/lifecycle |

Image and Video are fully migrated peer-workspace reference implementations.
Their remaining `sources`, `media_sources`, Tk variables and old MarkerApp
methods are compatibility/service surfaces only and are not authoritative.

### State tables and receipts

The state/transition table defines required behavior. A transition or execution
receipt records observed stages of the real production route. Tests must enter
through production callbacks where possible; static source assertions alone do
not prove runtime behavior.

### PDF and PPTX next

PDF and PPTX retain independent state, scope, navigation, renderer and
processor implementations. They are not merged with Image or Video. Their
next migration must adopt the same ownership and lifecycle principles while
preserving PDF page/scope and PPTX slide/scope semantics.

## Current migration status (3I-DOC2) — HISTORICAL / PRE-MIGRATION

The pre-migration PDF tables above are historical and must not be read as the
current production architecture. Image, Video and PDF are now reference peer
workspaces. PPTX is the remaining migration target.

| Concern | Image | Video | PDF |
|---|---|---|---|
| Registry owner | `ImageWorkspace` | `VideoWorkspace` | `PdfWorkspace` |
| Workspace/lifecycle | `ImageWorkspace` | `VideoWorkspace` | `PdfWorkspace` |
| State | `ImageWorkspaceState` | `VideoWorkspaceState` | `PdfWorkspaceState` |
| File/session | workspace state | workspace state | workspace state |
| Visual state | workspace state | workspace state | workspace state |
| Preview | `ImageWorkspace.refresh_preview()` | `VideoWorkspace.refresh_preview()` | `PdfWorkspace.refresh_preview()` |
| Preview UI resource | workspace retained CTk image | workspace retained CTk image | `PdfWorkspace.preview_photo` |
| Save/output | `ImageWorkspace.save()` | `VideoWorkspace.save()` | `PdfWorkspace.save()` |
| Processing request | `ImageProcessingRequest` | `VideoProcessingRequest` | `PdfProcessingRequest` |
| Processor/service | `ImageProcessor` | video service/FFmpeg | `PdfProcessor` |
| Active work | workspace state | workspace state | `PdfWorkspace.has_active_work()` |
| Clear/reset | workspace lifecycle | workspace lifecycle | `PdfWorkspace.clear_runtime_state()` |

### Current PDF production contract

`Shell → registry["pdf"] → PdfWorkspace → PdfWorkspaceState → projection /
preview / immutable processing request → UI / PdfPreviewRenderer /
PdfProcessor`

PDF ownership is workspace-based: file/session, scope, physical page navigation,
badge/logo events, preview, retained preview resource, Save, active-work and
clear/reset are all behind `PdfWorkspace`. The migration preserved All, First,
Selected draft plus Update, Range draft plus Update, invalid-update rollback,
physical-page/scope independence, out-of-scope overlay behavior, badge/logo
semantics, Save As/source protection and existing processor behavior.

Remaining MarkerApp surfaces are compatibility-only and one-way:
`PdfWorkspaceState → compatibility mirror`. They include
`_mount_pdf_workspace`, `_sync_pdf_state`, `render_pdf_preview`,
`process_pdf_phase6`, `pdf_path`, `pdf_info`, `pdf_current_page`,
`pdf_preview_photo`, PDF scope mirrors and PDF Tk mirrors. None is an
authoritative PDF state owner.

PPTX is substantially closer to the target than pre-migration PDF. It already
has `PptxWorkspace`, `PptxWorkspaceState`, reducer/state direction, independent
scope and physical slide navigation, workspace preview and existing processors.
Remaining PPTX work is direct registry/lifecycle cutover, reclassification or
removal of MarkerApp mirrors, consolidation of preview/output compatibility
paths and production-route acceptance. This is not a reason to mechanically
repeat the Image/Video/PDF migration sequence.

The packaged Video workspace had retained the pre-migration filename-only placeholder because the active ShellController-owned `MarkerApp` mounted a separate video workspace; the earlier extraction was only wired to the legacy media renderer. The active workspace now resolves the bundled FFmpeg, extracts a representative PNG frame, composites the authoritative `VideoWorkspaceState` badge, and retains the CTkImage reference on the preview widget.
## Video structural UI contract

The active Video workspace is a projection of `VideoWorkspaceState`: FILE, AI BADGE, VIDEO OPTIONS, then OUTPUT. It has one representative-frame path (`find_ffmpeg` → `extract_video_frame` → Pillow composition → retained `CTkImage`). Widget class names are implementation details and are never valid translated labels; missing localization must use the translator's human-readable fallback.
## Video clean UI boundary

The active Video destination is mounted directly by `ShellController` and is intentionally separate from the legacy `_single_ui()` media builder. Its left column is a projection of `VideoWorkspaceState` (file, badge, mode/duration and output), with a responsive controls/preview split. The current step leaves the right preview as a human-readable placeholder; FFmpeg preview remains a subsequent step.
## Video hard-reset mount audit

`LegacyMarkerApp._single_ui()` remains only as disconnected historical code; `MarkerApp.render_shell_state()` calls exactly one active `_mount_video_workspace()` path. That path now exposes explicit `video_controls_host` and `video_preview_host` regions and clears the common host before mounting, preventing a stale placeholder or destination from surviving a Video transition.
## Media workspace contract

Video now follows the same hard mount boundary as Image: `_mount_video_workspace`
clears `content_host` and creates exactly `video_controls_host` and
`video_preview_host`. The active Step-1 UI is built directly in those hosts with
explicit FILE, AI BADGE, VIDEO OPTIONS and OUTPUT groups. Selecting a file only
updates `VideoWorkspaceState` and the existing information widgets; it never
remounts or delegates to the legacy media builder. FFmpeg preview remains a
later step; the preview host deliberately displays a human-readable placeholder.

Image is the structural reference for media workspaces. Video is mounted once by `MarkerApp._mount_video_workspace()` after the ShellController selects `VIDEO`; it creates exactly `video_controls_host` and `video_preview_host`. File selection mutates `VideoWorkspaceState` and labels only, never reconstructs either host.

The current projection replaces the placeholder after a valid selection by
reusing `find_ffmpeg()` and `extract_video_frame()`. It composites from the
authoritative `VideoWorkspaceState.badge` and updates the existing preview
widget in place; visual events rerender without rebuilding the workspace.

## PDF final control contract

PDF follows the common workspace contract with `PdfWorkspaceState` as its sole
runtime owner. Its controls are ordered `FILE → PDF PAGES → AI BADGE → OWN
LOGO → OUTPUT` in a controls-at-most-40% / preview-at-least-60% layout. Every
accepted UI event validates into state and projects to the existing preview or
output; physical page navigation remains independent of All/First/Selected/
Range processing scope. Selected input accepts mixed expressions such as
`2,4-6,9`, while invalid updates preserve the last valid scope. Save As uses
`<stem>_ai.pdf` by default, never overwrites the source by default, and uses
the same authoritative badge/logo projection as preview. Disabling a logo
preserves its selected path so enabling it again can rerender immediately. No
PDF control remounts the workspace.

The PDF badge selector and current-badge presentation use the common badge
repository: the authoritative selected id projects to the dropdown, graphic,
human-readable name and preview. PPTX now projects its common badge repository
and visual state through the active workspace route; remaining layout details
are tracked separately and it is not changed by
the PDF work.

## Common presentation contract

## Current implementation stage

The audit's executable baseline is now the frozen four-state shell and the
one-way workspace contract:

`UI event → typed workspace event → validation/transition → state owner/reducer → authoritative state → projection → consumer`

Widgets/Tk variables are adapters, processors are data services, and receipts
are observational. PPTX Phase 1 currently implements FILE + AI BADGE in the
authoritative `PptxWorkspace`; the file state fields are
`selected_file`, `display_filename`, `file_size_bytes` and `slide_count`, and
the badge projection resolves the common repository and retains its image
reference. `FILE_METRICS_FAILED` preserves the previous valid state and is
logged safely. The latest focused gate is 67 passing tests; packaged
reverification after the `Path` processor fix remains pending.

IMAGE, VIDEO, PDF and PPTX are peer workspaces with independent runtime state.
Reusable left-column presentation helpers/tokens may be shared, but never live
state:

`Common UI → workspace event → workspace state → projection → Common UI + preview`

The common badge/logo presentation includes enablement, repository selection or
path, current graphic/name, position, size, margin and opacity. Scope and page/
slide navigation remain format-specific. `nenolink_ai_marker.workspace_ui`
contains stateless badge/logo section builders and layout tokens; Tk variables
remain adapters. Initial badge projection is mandatory from each workspace
state. The old shared
Document Workspace/`document_surface`/`document_tab` runtime is not reachable;
any remaining historical references are non-authoritative legacy code.

PPTX now uses the common callback contract and the same authoritative visual
projection for preview and output. Its active file row, SLIDES scope, AI BADGE
and OWN LOGO sections are mounted in that order, with Save Marked PowerPoint in
the file action row.

The active shell route now calls `_mount_pptx_workspace()` directly. A stale
branch in `_render_authoritative_state()` had replaced the complete PPTX route
with the historical `PPTX TEST` placeholder, which made the packaged screen
appear truncated even though the builder created the controls. That competing
path is disconnected.

## Final four-workspace architecture (3I-DOC3)

This is the current production contract. Image, Video, PDF and PPTX are all
fully migrated peer workspaces; none is a remaining migration target.

```text
Shell → workspace registry → format workspace → authoritative workspace state
      → projection / preview / deterministic processing boundary
      → UI / renderer / processor
```

| Format | Direct registry owner | Sole runtime state owner |
|---|---|---|
| Image | `ImageWorkspace` | `ImageWorkspaceState` |
| Video | `VideoWorkspace` | `VideoWorkspaceState` |
| PDF | `PdfWorkspace` | `PdfWorkspaceState` |
| PPTX | `PptxWorkspace` | `PptxWorkspaceState` |

All four workspaces implement `mount(host)`, `unmount()`, `project()`,
`has_active_work()` and `clear_runtime_state()`. `unmount()` removes the
presentation while preserving the session; `clear_runtime_state()` is the
destructive runtime reset. They are not interchangeable.

Workspace state is authoritative. MarkerApp fields and Tk variables are
compatibility mirrors or UI adapters only, with one-way flow
`workspace/state → compatibility mirror/adapter`; they never write back as a
second runtime owner. Retained CTkImage objects, frame caches and preview
resources are projection resources, not business state.

Preview ownership is workspace-local: state → workspace preview method or
projection → renderer → workspace-owned UI resource. The PPTX route is
`PptxWorkspaceState → PptxWorkspace._render_preview() → PptxPreviewRenderer`.
`MarkerApp._update_pptx_preview` is compatibility-only and is not the
production preview owner.

Output follows the same boundary: authoritative state → deterministic value
boundary → processor/service → result. Image uses `ImageProcessingRequest`,
Video uses `VideoProcessingRequest`, and PDF uses `PdfProcessingRequest`.
PPTX legitimately uses the active application service
`PptxWorkspace._save_as() → process_pptx_from_workspace(state) →
PptxProcessor`; that service is not a second state owner.

PPTX preserves All, First, Selected draft plus Update, Range draft plus
Update, invalid-update preservation, physical-slide navigation independent of
processing scope, badge/logo state, visual changes preserving slide/scope,
new-file reset, preview and Save As behavior. This migration preserved the
existing PPTX contract; it was not a processing rewrite.

The accepted global shell FSM is: same-content transitions preserve session;
Content → Tool and Tool → the same underlying Content preserve the session;
active Content → different Content warns, with Cancel preserving the source
and Continue clearing it before mounting a clean destination. Reset confirms
when active, preserves on Cancel, and on Confirm clears runtime/tool state and
returns to clean Image. Reset without active work follows the same clean Image
destination contract.

The state table defines required behavior; transition/execution receipts
record observed production stages. Tests should enter through production
callbacks where practical, not only helpers or static source assertions.

Compatibility surfaces remain intentionally where required by identified
consumers. They are one-way, non-authoritative, narrow services or
production-unreachable legacy code. Final legacy cleanup is technical debt,
not an incomplete workspace migration.

Architecture acceptance is complete. Packaged Windows behavior and physical
geometry remain **RUNTIME VERIFICATION REQUIRED** and must not be inferred
from headless tests.

## Mandatory pre-build gate

Builds follow an impact-based chain:
`state/transition tests → projection tests → mounted UI tests → pre-build
navigation/callback smoke → Windows build → manual packaged verification`.
For PPTX-only changes, run `tests/test_prebuild_ui_gate.py` together with the
PPTX contract tests before packaging.

PPTX transition semantics are machine-readable in `pptx_state.py` via
`PPTX_TRANSITION_TABLE` and `PptxEvent`. Visual events are applied through
`apply_pptx_visual_event`; the table declares mutation, preservation, preview,
output and remount effects. Parameterized tests iterate this table and enforce
badge/logo isolation, scope/physical-slide independence and no-remount rules.
