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
