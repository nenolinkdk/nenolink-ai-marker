"""Stateless document scope and physical navigation presentations."""
import customtkinter as ctk

class DocumentScopeControl:
    def __init__(self, parent, *, on_mode, on_text, on_update, values, placeholder=""):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.mode_var = ctk.StringVar(value=values[0] if values else "All")
        self.menu = ctk.CTkOptionMenu(self.frame, variable=self.mode_var, values=list(values), command=on_mode, width=190); self.menu.grid(row=0, column=0, sticky="w")
        self.input_var = ctk.StringVar(value=""); self.input = ctk.CTkEntry(self.frame, textvariable=self.input_var, placeholder_text=placeholder, width=190); self.input.grid(row=1, column=0, pady=2, sticky="w"); self.input.bind("<KeyRelease>", lambda _e: on_text(self.input_var.get()))
        self.update = ctk.CTkButton(self.frame, text="Update", command=on_update, width=90); self.update.grid(row=2, column=0, sticky="w")
        self.status = ctk.CTkLabel(self.frame, text="", anchor="w"); self.status.grid(row=3, column=0, sticky="w")
    def project(self, *, mode, draft, status=""):
        self.mode_var.set(mode); self.input_var.set(draft); self.status.configure(text=status)

class PhysicalNavigationControl:
    def __init__(self, parent, *, on_previous, on_next):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.previous = ctk.CTkButton(self.frame, text="‹", width=34, command=on_previous); self.previous.grid(row=0, column=0, padx=4)
        self.status = ctk.CTkLabel(self.frame, text="—", width=90); self.status.grid(row=0, column=1, padx=4)
        self.next = ctk.CTkButton(self.frame, text="›", width=34, command=on_next); self.next.grid(row=0, column=2, padx=4)
    def project(self, *, current, total):
        self.status.configure(text=f"{current} / {total}" if total else "—")
        self.previous.configure(state="normal" if current > 1 else "disabled")
        self.next.configure(state="normal" if current < total else "disabled")
