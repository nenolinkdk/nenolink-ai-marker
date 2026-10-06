import nenolink_ai_marker.save_control as module
from nenolink_ai_marker.save_control import SaveControl

class _Button:
    def __init__(self, parent, **kwargs): self.parent, self.options = parent, kwargs
    def configure(self, **kwargs): self.options.update(kwargs)
class _Ctk: CTkButton = _Button

def test_save_control_forwards_callback_and_has_no_workspace_dependency(monkeypatch):
    monkeypatch.setattr(module, "ctk", _Ctk); calls = []
    control = SaveControl(object(), command=lambda: calls.append("save"), label="Output")
    control.button.options["command"](); control.set_enabled(False); control.set_label("Again")
    assert calls == ["save"]; assert control.button.options["state"] == "disabled"; assert control.button.options["text"] == "Again"

def test_save_control_instances_keep_independent_callbacks(monkeypatch):
    monkeypatch.setattr(module, "ctk", _Ctk); calls = []
    first = SaveControl("a", command=lambda: calls.append("image")); second = SaveControl("b", command=lambda: calls.append("pdf"))
    first.button.options["command"](); second.button.options["command"]()
    assert calls == ["image", "pdf"]; assert first.button is not second.button

def test_save_control_contains_no_format_policy():
    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("WorkspaceState", "ProcessingRequest", "processor", "MarkerApp", "TransitionTable"):
        assert forbidden not in source
