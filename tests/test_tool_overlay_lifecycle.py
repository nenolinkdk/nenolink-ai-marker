from nenolink_ai_marker.shell_controller import ShellTransitionExecutor, shell_transition_spec


class ToolRuntime:
    def __init__(self):
        self.tool = None
        self.mounts = []
        self.unmounts = 0
        self.clears = 0
        self.content_clears = 0
        self.destination_lookup = "success"
        self.mount_result = "success"

    def preserve_source(self): pass
    def clear_source(self, _source): self.content_clears += 1
    def clear_all_workspaces(self): self.content_clears += 1
    def clean_destination(self, _destination): pass
    def unmount_source(self, _source): pass
    def mount_destination(self, _destination): pass
    def project_destination(self, _destination): pass
    def mount_tool(self, tool): self.tool = tool; self.mounts.append(tool)
    def unmount_tool(self): self.tool = None; self.unmounts += 1
    def clear_tool(self): self.clears += 1
    def begin_receipt(self, _spec): pass
    def record_receipt(self, _receipt): pass


def _run(runtime, source_tool, event):
    spec = shell_transition_spec("pdf", source_tool, event, False)
    ShellTransitionExecutor().execute(spec, runtime)
    return spec


def test_tool_replacement_mounts_requested_tool_and_preserves_content():
    runtime = ToolRuntime()
    _run(runtime, None, "badges")
    _run(runtime, "badges", "inspect")
    assert runtime.mounts == ["badges", "inspect"]
    assert runtime.tool == "inspect"
    assert runtime.content_clears == 0


def test_tool_roundtrip_and_same_tool_are_deterministic():
    runtime = ToolRuntime()
    _run(runtime, None, "inspect")
    _run(runtime, "inspect", "inspect")
    assert runtime.mounts == ["inspect", "inspect"]
    _run(runtime, "inspect", "back")
    assert runtime.tool is None
    assert runtime.unmounts == 1
    assert runtime.content_clears == 0


def test_tool_spec_matrix_is_overlay_only():
    for source_tool, event in ((None, "badges"), (None, "inspect"), ("badges", "inspect"), ("inspect", "badges")):
        spec = shell_transition_spec("pptx", source_tool, event, True)
        assert spec.destination_content.value == "pptx"
        assert spec.requires_confirmation is False
        assert "clear_source" not in [action.value for action in spec.actions]
