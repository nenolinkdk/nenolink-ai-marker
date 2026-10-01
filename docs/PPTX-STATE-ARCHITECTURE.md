# PPTX workspace state

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
