import customtkinter as ctk

PP_MOUNT_TOKEN = "PP_MOUNT"


class PPWorkspace:
    def __init__(self, trace=None):
        self.trace = trace if trace is not None else []
        self.root = None
        self.mounted = False

    def has_active_work(self):
        return False

    def mount(self, content_host):
        self.trace.append(PP_MOUNT_TOKEN)
        for child in content_host.winfo_children():
            child.destroy()
        self.root = ctk.CTkFrame(content_host, fg_color="transparent")
        self.root.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.root, text="PP\nPowerPoint NEW", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, padx=24, pady=24, sticky="nw")
        self.mounted = True

    def clear_runtime_state(self):
        self.unmount()

    def unmount(self):
        if self.root is not None and self.root.winfo_exists():
            self.root.destroy()
        self.root = None
        self.mounted = False
