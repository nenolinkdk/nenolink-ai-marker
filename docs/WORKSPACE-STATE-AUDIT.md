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
