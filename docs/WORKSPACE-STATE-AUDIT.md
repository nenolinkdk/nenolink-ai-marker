# Workspace state audit (v1.0.3)

This audit deliberately precedes implementation. The outer `ShellController`
remains the only owner of `IMAGE`, `VIDEO`, `PDF` and `PPTX` navigation.

| Workspace | Current runtime ownership | Preview | Scope | Output |
|---|---|---|---|---|
| Image | `sources`, selected source and shared `MarkerSettings` variables in `MarkerApp` | `preview_image` / `preview_photo` | not applicable | image processor and Save As |
| Video | selected source, video mode/duration and shared `MarkerSettings` variables | text/status preview (no player) | not applicable | FFmpeg processor and Save As |
| PDF | `pdf_path`, `pdf_info`, `pdf_preview_state`, `document_scope_states["pdf"]`, PDF badge variables | PDF preview renderer/state | independent validated page scope | `PdfProcessor` and metadata |
| PPTX | `PptxWorkspaceState` plus projected Tk variables for compatibility | `pptx_preview_state` / renderer | independent validated slide scope | `PptxProcessor` and metadata |

## Findings

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

## Common contract

Each workspace should expose `load/clear`, `has_active_work`, visual property
events, `render_preview` and `process_output`. Events validate and mutate the
workspace state; both preview and output consume that state. UI variables are
draft/display values only.

For PDF/PPTX, physical page/slide navigation is independent of validated
processing scope. Cancel preserves the complete source state, Continue clears
the source runtime before ShellController mounts the destination, Tools/Back
does not clear it, and Reset unconditionally returns to clean Image.

## Recommended implementation sequence

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
