"""Keep tkinter discoverable for the relocatable Windows build runtime."""

# PyInstaller's stock pre-find hook probes Tcl in a subprocess. The selected
# relocatable build runtime is validated by build.ps1 and initialized by the
# packaging runner/runtime hook, so no subprocess path rewrite is required.


def pre_find_module_path(hook_api):
    """Retain Python's normal tkinter search directories."""
    return None
