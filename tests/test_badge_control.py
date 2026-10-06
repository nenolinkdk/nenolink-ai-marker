import nenolink_ai_marker.badge_control as module
from nenolink_ai_marker.badge_control import BadgeControl, BadgeProjection

class _Var:
    def __init__(self, value=None): self.value=value
    def get(self): return self.value
    def set(self, value): self.value=value
class _Widget:
    def __init__(self, *args, **kwargs): self.options=kwargs; self.variable=kwargs.get('variable')
    def grid(self, **kwargs): pass
    def configure(self, **kwargs): self.options.update(kwargs)
class _Ctk:
    BooleanVar=_Var; StringVar=_Var; CTkFrame=CTkLabel=CTkCheckBox=CTkOptionMenu=_Widget

def test_badge_control_projects_and_forwards_callbacks(monkeypatch):
    monkeypatch.setattr(module, 'ctk', _Ctk); seen=[]
    control=BadgeControl(object(), on_enabled_changed=lambda v: seen.append(('enabled',v)), on_badge_selected=lambda v: seen.append(('badge',v)))
    control.project(BadgeProjection(True,'AI',('AI','No AI'),asset_path=None))
    control._on_enabled_changed(True); control._on_badge_selected('No AI')
    assert control.enabled_var.get() is True and control.selector_var.get() == 'AI'
    assert seen == [('enabled',True),('badge','No AI')]

def test_badge_control_instances_are_independent(monkeypatch):
    monkeypatch.setattr(module, 'ctk', _Ctk); calls=[]
    a=BadgeControl('a', on_badge_selected=lambda v: calls.append('a'))
    b=BadgeControl('b', on_badge_selected=lambda v: calls.append('b'))
    a._on_badge_selected('x'); b._on_badge_selected('y')
    assert calls == ['a','b'] and a.frame is not b.frame

def test_badge_control_has_no_workspace_or_policy_dependencies():
    source=open(module.__file__,encoding='utf-8').read()
    for forbidden in ('WorkspaceState','TransitionTable','Processor','MarkerApp','PdfEvent','PptxEvent'):
        assert forbidden not in source
