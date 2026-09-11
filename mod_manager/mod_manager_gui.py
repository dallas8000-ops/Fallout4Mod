"""Tk desktop GUI. Same widget behavior as before; load/save now goes
through core/ instead of a third independent copy of the sync/save logic
(and a third, cwd-dependent MOD_DATA_PATH -- see main.py's docstring for
why that was a real bug, not just duplication).
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mod_manager.core import catalog, config, loadorder_io, mod_data_store  # noqa: E402


class ModManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fallout 4 Mod Manager")
        self.geometry("700x500")
        self.resizable(False, False)
        self.installed = mod_data_store.scan_installed_mods()
        self.mod_data = mod_data_store.load()
        self.sync_mod_data()
        self.create_widgets()
        self.refresh_mod_list()

    def sync_mod_data(self) -> None:
        self.mod_data, changed = mod_data_store.sync_with_installed(self.mod_data, self.installed)
        if changed:
            mod_data_store.save(self.mod_data)

    def create_widgets(self) -> None:
        self.tree = ttk.Treeview(self, columns=("Category", "Priority", "Enabled"), show="headings")
        self.tree.heading("Category", text="Category")
        self.tree.heading("Priority", text="Priority")
        self.tree.heading("Enabled", text="Enabled")
        self.tree.column("Category", width=200)
        self.tree.column("Priority", width=80)
        self.tree.column("Enabled", width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="Edit Selected", command=self.edit_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Enable/Disable", command=self.toggle_selected).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Refresh", command=self.refresh_mod_list).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Quit", command=self.destroy).pack(side=tk.RIGHT, padx=5)

    def refresh_mod_list(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.installed = mod_data_store.scan_installed_mods()
        self.sync_mod_data()
        sorted_mods = sorted(
            self.installed,
            key=lambda m: (
                self.mod_data[m].get("priority", catalog.order_index(m)),
                self.mod_data[m].get("category", config.DEFAULT_CATEGORY),
                m,
            ),
        )
        loadorder_io.write_modlist(sorted_mods, self.mod_data)
        for mod in sorted_mods:
            entry = self.mod_data[mod]
            self.tree.insert(
                "",
                tk.END,
                iid=mod,
                values=(
                    entry.get("category"),
                    entry.get("priority"),
                    "Yes" if entry.get("enabled", True) else "No",
                ),
            )

    def edit_selected(self) -> None:
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("No selection", "Please select a mod to edit.")
            return
        mod = selected
        entry = self.mod_data[mod]
        new_cat = simpledialog.askstring("Edit Category", f"Category for '{mod}':", initialvalue=entry["category"])
        if new_cat is not None:
            entry["category"] = new_cat
        new_prio = simpledialog.askinteger("Edit Priority", f"Priority for '{mod}':", initialvalue=entry["priority"])
        if new_prio is not None:
            entry["priority"] = new_prio
        mod_data_store.save(self.mod_data)
        self.refresh_mod_list()

    def toggle_selected(self) -> None:
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("No selection", "Please select a mod to enable/disable.")
            return
        entry = self.mod_data[selected]
        entry["enabled"] = not entry.get("enabled", True)
        mod_data_store.save(self.mod_data)
        self.refresh_mod_list()


if __name__ == "__main__":
    app = ModManagerApp()
    app.mainloop()
