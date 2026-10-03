# PPTX workspace state

## Current Phase 1 contract

`PptxWorkspace` is the single production PPTX mount and the sole runtime
owner for the current phase. Its FILE + AI BADGE flow is:

`FILE_DIALOG_RESULT → metrics → CHOOSE_FILE_SUCCESS → file reducer → PptxWorkspaceState → project_file/project_badge → Tk adapter`

The file reducer owns `selected_file`, `display_filename`, `file_size_bytes`
and `slide_count`. `CHOOSE_FILE_CANCEL` is a no-op. `BADGE_SELECT` and other
badge events mutate only the corresponding badge fields. The initial badge is
`AI Assisted`, resolved through the common badge repository into display name
and asset; the Tk adapter retains the resulting `CTkImage`.

No callback writes labels directly and no Tk variable is authoritative. A
metrics exception emits `FILE_METRICS_FAILED` with a safe exception type/message,
preserves the prior valid file state and exposes a readable status. Successful
file events produce the ordered receipts `CHOOSE_FILE_SUCCESS`,
`FILE_REDUCER_APPLIED`, `FILE_STATE_UPDATED`, `FILE_PROJECTED` and
`FILE_WIDGETS_UPDATED`. TEST builds additionally persist observational JSONL
receipts at `%TEMP%\\Nenolink-AI-Marker-test-receipts.jsonl`.

Only the current FILE + AI BADGE projection is implemented. SLIDES, OWN LOGO,
PREVIEW, OUTPUT/SAVE and metadata remain intentionally disconnected until the
next phases. The common contract and the four-state shell remain authoritative;
this file must not be read as permission to revive legacy PPTX/document UI.

The ShellController owns the external content FSM (`IMAGE`, `VIDEO`, `PDF`,
`PPTX`) and tools. The PPTX workspace owns only its internal runtime,
represented by `PptxWorkspaceState`.

```text
ShellController: IMAGE <-> VIDEO <-> PDF <-> PPTX
                                  |
PPTX: EMPTY <-> LOADED
       LOADED: current_slide (physical 1..N)
               active_scope (All/First/Selected/Range)
               badge configuration
               logo configuration
               output status
```

Events validate input, update `PptxWorkspaceState`, then render the current
view. Physical Previous/Next changes only `current_slide`; scope changes never
restrict physical navigation. An overlay is projected when the current slide
belongs to `active_scope`, using the independent badge and logo configurations.
The same state is passed to preview and Save As processing. Typing an editable
scope changes only the draft input; Update is the transition that validates and
applies it. Invalid input preserves the last applied scope and preview.

Global Reset clears the PPTX state and returns the shell to clean IMAGE.
Content-switch Cancel leaves the complete source state unchanged; Continue
clears it before the ShellController mounts the destination. Tools are overlays
and do not own or retain a hidden PPTX workspace.
