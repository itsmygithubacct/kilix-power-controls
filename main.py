"""Kilix Power Controls: power policy and the shared Pleb Screen Lock page."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from power_controls import Backend, FIELDS, Preferences, devices


def screenlock_module():
    command = shutil.which("pleb")
    candidates = ([Path(command).resolve().parents[1] / "lib"] if command else [])
    candidates.append(Path("/usr/local/lib/pleb"))
    for directory in candidates:
        if (directory / "screenlock_gui.py").is_file():
            sys.path.insert(0, str(directory))
            import screenlock_gui
            return screenlock_gui
    raise RuntimeError("The Pleb Screen Lock settings module is missing; update the Pleb session")


class PowerControls:
    def __init__(self, root, backend=None):
        self.root = root
        self.preferences = Preferences(backend or Backend())
        root.title("Kilix Power Controls")
        root.geometry("1000x720")
        root.minsize(850, 700)
        style = ttk.Style(root)
        style.theme_use("clam")
        bg, text, panel = "#101827", "#e6edf7", "#192438"
        root.configure(background=bg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=text, font=("DejaVu Sans", 11))
        style.configure("TCheckbutton", background=bg, foreground=text, padding=4)
        style.configure("TButton", background="#293b56", foreground=text, padding=(14, 9))
        style.map("TButton", background=[("active", "#395273")])
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel, foreground=text, padding=(13, 10))
        style.map("TNotebook.Tab", background=[("selected", "#395273")])
        style.configure("TCombobox", padding=6)
        ttk.Label(root, text="Power Controls", font=("DejaVu Sans", 23, "bold"), padding=(24, 16)).pack(anchor="w")
        ttk.Label(root, text="Choose how your computer handles power. Changes take effect when you apply them.", padding=(24, 0)).pack(anchor="w")
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=18)
        self.variables = {}
        for section in ("General", "Plugged In", "Battery", "Display", "Dimming"):
            frame = ttk.Frame(self.tabs, padding=20)
            frame.columnconfigure(1, weight=1)
            self.tabs.add(frame, text=section)
            fields = [field for field in FIELDS if field.section == section]
            for row, field in enumerate(fields):
                value = self.preferences.values[field.key]
                if field.kind == "bool":
                    variable = tk.BooleanVar(value=value)
                    ttk.Checkbutton(frame, text=field.label, variable=variable).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
                else:
                    if field.choices is not None:
                        label = field.choices.get(value, f"Existing value: {value}")
                        variable = tk.StringVar(value=label)
                        widget = ttk.Combobox(frame, textvariable=variable, values=list(field.choices.values()), state="readonly", width=25)
                    else:
                        variable = tk.StringVar(value=str(0 if field.dim_timeout and value == 9 else value))
                        widget = ttk.Spinbox(frame, textvariable=variable, from_=0 if field.dim_timeout else field.minimum, to=field.maximum, width=12)
                    ttk.Label(frame, text=field.label).grid(row=row, column=0, sticky="w", padx=(0, 20), pady=4)
                    widget.grid(row=row, column=1, sticky="e", pady=4)
                self.variables[field.key] = variable
            ttk.Label(frame, text="Available actions depend on the computer's hardware and sleep support.", wraplength=800).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(18, 0))
        # This is exactly the same page and preferences as Display Settings.
        self.tabs.add(screenlock_module().tk_page(self.tabs), text="Screen Lock")
        device_page = ttk.Frame(self.tabs, padding=20)
        self.tabs.add(device_page, text="Devices")
        self.device_text = tk.Text(device_page, bg=panel, fg=text, relief="flat", font=("DejaVu Sans Mono", 11), height=12)
        self.device_text.pack(fill="both", expand=True)
        ttk.Button(device_page, text="Refresh devices", command=self.refresh_devices).pack(anchor="w", pady=10)
        self.refresh_devices()
        self.status = tk.StringVar(value="Opening this window does not change any settings.")
        status_label = ttk.Label(root, textvariable=self.status, wraplength=800, padding=(24, 4))
        status_label.pack(side="bottom", fill="x", before=self.tabs)
        footer = ttk.Frame(root, padding=(24, 12))
        footer.pack(side="bottom", fill="x", before=status_label)
        ttk.Button(footer, text="Reload", command=self.reload).pack(side="left")
        self.apply_button = ttk.Button(footer, text="Apply power settings", command=self.apply)
        self.apply_button.pack(side="right")

    def draft(self):
        values = {}
        for field in FIELDS:
            raw = self.variables[field.key].get()
            if field.choices is not None:
                if raw == f"Existing value: {self.preferences.values[field.key]}":
                    # Preserve an unknown backend enum until explicitly edited.
                    continue
                raw = next(key for key, label in field.choices.items() if label == raw)
            elif field.kind == "uint":
                raw = int(raw)
                if field.dim_timeout and raw == 0:
                    raw = 9
            values[field.key] = raw
        return values

    def apply(self):
        try:
            count = self.preferences.apply(self.draft())
            self.status.set(f"Applied {count} power setting(s). Screen Lock has its own Save button and applies at the next login.")
        except Exception as error:
            self.status.set(str(error))

    def reload(self):
        try:
            preferences = Preferences(self.preferences.backend)
            for field in FIELDS:
                value = preferences.values[field.key]
                if field.choices is not None:
                    value = field.choices.get(value, f"Existing value: {value}")
                elif field.dim_timeout and value == 9:
                    value = 0
                self.variables[field.key].set(value)
            self.preferences = preferences
            self.status.set("Power settings reloaded. Screen Lock changes are saved separately.")
        except Exception as error:
            self.status.set(str(error))

    def refresh_devices(self):
        rows = []
        for name, values in devices():
            rows.append(name)
            rows.extend(f"  {key.replace('_', ' '):<16} {value}" for key, value in values.items())
            rows.append("")
        self.device_text.configure(state="normal")
        self.device_text.delete("1.0", "end")
        self.device_text.insert("1.0", "\n".join(rows) or "No battery or power-supply devices were reported.")
        self.device_text.configure(state="disabled")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kilix Power Controls")
    parser.add_argument("--native", action="store_true", help="open on the current X display")
    parser.add_argument("--show", action="store_true", help="print saved power preferences without opening a window")
    parser.add_argument("--version", action="version", version="kilix-power-controls 0.1.0")
    args = parser.parse_args(argv)
    try:
        if os.getuid() == 0:
            raise RuntimeError("Run as the desktop user, without sudo")
        if args.show:
            print(json.dumps(Preferences(Backend()).values, sort_keys=True))
            return 0
        root = tk.Tk()
        try:
            PowerControls(root)
        except Exception as error:
            messagebox.showerror("Power Controls", str(error), parent=root)
            root.destroy()
            return 1
        root.mainloop()
        return 0
    except Exception as error:
        print(f"kilix-power-controls: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
