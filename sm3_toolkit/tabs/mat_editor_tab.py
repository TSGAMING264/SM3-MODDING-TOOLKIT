from __future__ import annotations

from pathlib import Path
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path
from sm3_toolkit.services.mat_editor_service import (
    MATDocument,
    MATEditorError,
    build_parameters,
    bytes_changed,
    hex_context,
    load_mat,
    overwrite_with_backup,
    reset_all,
    reset_float,
    save_copy,
    write_float,
)


GROUP_COLORS = {
    "A / 0x40-0x4C": "#61A7FF",
    "B / 0x50-0x5C": "#FF6E98",
    "C / 0x60-0x6C": "#72D572",
    "D / 0x70-0x7C": "#FFD65A",
    "Shader constants": "#C98BFF",
}


class MATEditorTab(ttk.Frame):
    """Spider-Man 3 native MAT editor.

    The tab intentionally exposes confirmed/candidate shader constant offsets
    rather than borrowing Web of Shadows parameter names that are not yet proven
    to match SM3's serialization.
    """

    def __init__(self, parent, app_state):
        super().__init__(parent, padding=10)
        self.app_state = app_state
        self.doc: MATDocument | None = None
        self.selected_offset: int | None = None
        self._visible_params = {}

        self.path_var = tk.StringVar()
        self.search_var = tk.StringVar()
        self.show_zeros_var = tk.BooleanVar(value=True)
        self.show_raw_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Open an extracted Spider-Man 3 .mat file to begin.")
        self.value_var = tk.StringVar()
        self.slider_var = tk.DoubleVar(value=0.0)

        self.info_name_var = tk.StringVar(value="-")
        self.info_hash_var = tk.StringVar(value="-")
        self.info_shader_var = tk.StringVar(value="-")
        self.info_profile_var = tk.StringVar(value="-")
        self.info_size_var = tk.StringVar(value="-")
        self.info_dirty_var = tk.StringVar(value="No")
        self.sel_name_var = tk.StringVar(value="-")
        self.sel_offset_var = tk.StringVar(value="-")
        self.sel_type_var = tk.StringVar(value="-")
        self.sel_original_var = tk.StringVar(value="-")
        self.sel_note_var = tk.StringVar(value="Select a shader-float row to edit it.")

        self._build_ui()
        self.search_var.trace_add("write", lambda *_: self._refresh_table())
        self.show_zeros_var.trace_add("write", lambda *_: self._refresh_table())
        self.show_raw_var.trace_add("write", lambda *_: self._refresh_table())

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        title = ttk.Frame(self)
        title.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        title.columnconfigure(0, weight=1)
        ttk.Label(title, text="MAT Editor", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            title,
            text="Spider-Man 3 native material editor. Edit shader float slots without resizing the MAT or touching reference fields.",
            wraplength=1100,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Keep the file controls usable at narrower resolutions by putting the
        # path on the first row and the action buttons on a second row.
        top = ttk.LabelFrame(self, text="Material File", padding=8)
        top.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Button(top, text="OPEN MAT", command=self._open_mat).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(top, textvariable=self.path_var, state="readonly").grid(row=0, column=1, columnspan=4, sticky="ew", padx=4)
        ttk.Button(top, text="OPEN FOLDER", command=self._open_folder).grid(row=1, column=0, padx=(0, 6), pady=(7, 0), sticky="w")
        ttk.Button(top, text="SAVE MODIFIED MAT", command=self._save_copy).grid(row=1, column=1, padx=4, pady=(7, 0), sticky="w")
        ttk.Button(top, text="SAVE CHANGES", command=self._save_changes).grid(row=1, column=2, padx=4, pady=(7, 0), sticky="w")

        # Filters wrap to two rows instead of forcing the tab wider than the
        # screen. This was the main source of clipped controls on 1366x768.
        filters = ttk.Frame(self)
        filters.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Search:").grid(row=0, column=0, padx=(0, 5), sticky="w")
        ttk.Entry(filters, textvariable=self.search_var).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 10))
        ttk.Button(filters, text="RESET ALL", command=self._reset_all).grid(row=0, column=4, padx=(10, 0), sticky="e")
        ttk.Checkbutton(filters, text="Show Zeros", variable=self.show_zeros_var).grid(row=1, column=1, sticky="w", pady=(5, 0))
        ttk.Checkbutton(filters, text="Show Raw Fields (read-only)", variable=self.show_raw_var).grid(row=1, column=2, columnspan=2, sticky="w", padx=(10, 0), pady=(5, 0))

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=3, column=0, sticky="nsew")

        left = ttk.Frame(body, padding=(0, 0, 6, 0))
        right_host = ttk.Frame(body, padding=(6, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right_host, weight=2)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        right_host.rowconfigure(0, weight=1)
        right_host.columnconfigure(0, weight=1)

        self.count_label = ttk.Label(left, text="No MAT loaded")
        self.count_label.grid(row=0, column=0, sticky="w", pady=(0, 4))

        columns = ("offset", "parameter", "type", "group", "value")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("offset", text="Offset")
        self.tree.heading("parameter", text="Parameter")
        self.tree.heading("type", text="Type")
        self.tree.heading("group", text="Group")
        self.tree.heading("value", text="Value")
        self.tree.column("offset", width=90, anchor="center", stretch=False)
        self.tree.column("parameter", width=220, anchor="w")
        self.tree.column("type", width=145, anchor="w")
        self.tree.column("group", width=145, anchor="w")
        self.tree.column("value", width=180, anchor="w")
        for group, color in GROUP_COLORS.items():
            self.tree.tag_configure(group, foreground=color)
        self.tree.tag_configure("readonly", foreground=COLORS.get("muted", "#AAAAAA"))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")

        # The entire right side is vertically scrollable. The original v5.2.156
        # used a fixed stack of panels, so the lower editor/hex controls could
        # fall below the visible notebook area on smaller displays.
        self.right_canvas = tk.Canvas(
            right_host,
            highlightthickness=0,
            borderwidth=0,
            background=COLORS.get("bg", "#17191F"),
        )
        right_scroll = ttk.Scrollbar(right_host, orient="vertical", command=self.right_canvas.yview)
        self.right_canvas.configure(yscrollcommand=right_scroll.set)
        self.right_canvas.grid(row=0, column=0, sticky="nsew")
        right_scroll.grid(row=0, column=1, sticky="ns")

        right = ttk.Frame(self.right_canvas)
        right.columnconfigure(0, weight=1)
        self._right_window = self.right_canvas.create_window((0, 0), window=right, anchor="nw")

        def _sync_scrollregion(_event=None):
            self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

        def _sync_right_width(event):
            # Match the inner frame to the visible canvas width so labels wrap
            # instead of extending beyond the panel.
            self.right_canvas.itemconfigure(self._right_window, width=max(1, event.width))

        right.bind("<Configure>", _sync_scrollregion)
        self.right_canvas.bind("<Configure>", _sync_right_width)

        def _wheel(event):
            delta = -1 if event.delta > 0 else 1
            if getattr(event, "delta", 0) == 0:
                delta = -1 if getattr(event, "num", 5) == 4 else 1
            self.right_canvas.yview_scroll(delta * 3, "units")
            return "break"

        def _bind_wheel(_event):
            self.right_canvas.bind_all("<MouseWheel>", _wheel)
            self.right_canvas.bind_all("<Button-4>", _wheel)
            self.right_canvas.bind_all("<Button-5>", _wheel)

        def _unbind_wheel(_event):
            self.right_canvas.unbind_all("<MouseWheel>")
            self.right_canvas.unbind_all("<Button-4>")
            self.right_canvas.unbind_all("<Button-5>")

        self.right_canvas.bind("<Enter>", _bind_wheel)
        self.right_canvas.bind("<Leave>", _unbind_wheel)
        right.bind("<Enter>", _bind_wheel)
        right.bind("<Leave>", _unbind_wheel)

        info = ttk.LabelFrame(right, text="Material Info", padding=8)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(1, weight=1)
        self._info_row(info, 0, "Name", self.info_name_var)
        self._info_row(info, 1, "Hash", self.info_hash_var)
        self._info_row(info, 2, "Shader", self.info_shader_var)
        self._info_row(info, 3, "Profile", self.info_profile_var)
        self._info_row(info, 4, "File Size", self.info_size_var)
        self._info_row(info, 5, "Modified", self.info_dirty_var)

        selected = ttk.LabelFrame(right, text="Selected Parameter", padding=8)
        selected.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        selected.columnconfigure(1, weight=1)
        self._info_row(selected, 0, "Name", self.sel_name_var)
        self._info_row(selected, 1, "Offset", self.sel_offset_var)
        self._info_row(selected, 2, "Type", self.sel_type_var)
        self._info_row(selected, 3, "Original", self.sel_original_var)
        ttk.Label(selected, textvariable=self.sel_note_var, wraplength=360, justify="left").grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        editor = ttk.LabelFrame(right, text="Parameter Editor", padding=8)
        editor.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        editor.columnconfigure(1, weight=1)
        ttk.Label(editor, text="Value").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.value_entry = ttk.Entry(editor, textvariable=self.value_var)
        self.value_entry.grid(row=0, column=1, sticky="ew")
        self.slider = ttk.Scale(editor, from_=-25.0, to=25.0, variable=self.slider_var, command=self._slider_changed)
        self.slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        # Two-row action grid keeps all four options visible at narrow widths.
        btns = ttk.Frame(editor)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        ttk.Button(btns, text="APPLY CHANGES", command=self._apply_value).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=3)
        ttk.Button(btns, text="RESET PARAMETER", command=self._reset_parameter).grid(row=0, column=1, sticky="ew", padx=(3, 0), pady=3)
        ttk.Button(btns, text="SET 0", command=lambda: self.value_var.set("0")).grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=3)
        ttk.Button(btns, text="SET 1", command=lambda: self.value_var.set("1")).grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=3)

        hexbox = ttk.LabelFrame(right, text="Hex Context", padding=8)
        hexbox.grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self.hex_text = tk.Text(hexbox, height=7, wrap="none", font=("Consolas", 9), state="disabled")
        hex_y = ttk.Scrollbar(hexbox, orient="vertical", command=self.hex_text.yview)
        hex_x = ttk.Scrollbar(hexbox, orient="horizontal", command=self.hex_text.xview)
        self.hex_text.configure(yscrollcommand=hex_y.set, xscrollcommand=hex_x.set)
        hexbox.rowconfigure(0, weight=1)
        hexbox.columnconfigure(0, weight=1)
        self.hex_text.grid(row=0, column=0, sticky="nsew")
        hex_y.grid(row=0, column=1, sticky="ns")
        hex_x.grid(row=1, column=0, sticky="ew")

        ttk.Label(
            right,
            text="Tip: scroll this right panel to reach every MAT option on smaller screens.",
            foreground=COLORS.get("muted", "#AAAAAA"),
        ).grid(row=4, column=0, sticky="w", pady=(2, 8))

        ttk.Label(self, textvariable=self.status_var, anchor="w").grid(row=4, column=0, sticky="ew", pady=(8, 0))

    @staticmethod
    def _info_row(parent, row, label, variable):
        ttk.Label(parent, text=f"{label}:", font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=2)
        ttk.Label(parent, textvariable=variable, wraplength=390, justify="left").grid(row=row, column=1, sticky="nw", pady=2)

    def _open_mat(self):
        path = filedialog.askopenfilename(title="Open Spider-Man 3 MAT", filetypes=[("Spider-Man 3 MAT", "*.mat"), ("All files", "*.*")])
        if not path:
            return
        try:
            self.doc = load_mat(path)
            self.path_var.set(str(self.doc.path))
            self.selected_offset = None
            self._update_info()
            self._refresh_table()
            self._clear_selection_panel()
            self._set_status(f"Loaded {self.doc.path.name} ({len(self.doc.data)} bytes).")
        except Exception as exc:
            messagebox.showerror("MAT Editor", str(exc))
            self._set_status(f"Load failed: {exc}")

    def _open_folder(self):
        if not self.doc:
            messagebox.showinfo("MAT Editor", "Open a MAT file first.")
            return
        open_path(self.doc.path.parent)

    def _update_info(self):
        if not self.doc:
            return
        d = self.doc
        self.info_name_var.set(d.path.name)
        match = d.hash_matches_filename
        suffix = " (filename match)" if match is True else " (FILENAME HASH MISMATCH)" if match is False else ""
        self.info_hash_var.set(f"0x{d.material_hash:08X}{suffix}")
        self.info_shader_var.set(f"{d.shader_name}  /  0x{d.shader_hash:08X}")
        if d.profile:
            self.info_profile_var.set(f"{d.profile.confidence} — {d.profile.note}")
        else:
            self.info_profile_var.set("UNKNOWN / READ ONLY — shader profile has not been mapped yet.")
        self.info_size_var.set(f"{len(d.data):,} bytes")
        self.info_dirty_var.set(f"{'YES' if d.dirty else 'No'} — {bytes_changed(d)} changed byte(s)")

    def _format_value(self, p):
        if p.kind == "Float32":
            return f"{float(p.value):.7g}"
        if "Hash32" in p.kind or "UInt32" in p.kind:
            return f"0x{int(p.value) & 0xFFFFFFFF:08X}  ({int(p.value)})"
        return str(p.value)

    def _refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._visible_params.clear()
        if not self.doc:
            self.count_label.configure(text="No MAT loaded")
            return

        query = self.search_var.get().strip().lower()
        params = build_parameters(self.doc, include_raw=self.show_raw_var.get())
        shown = 0
        for p in params:
            current = p.value
            if p.kind == "Float32":
                current = struct.unpack_from("<f", self.doc.data, p.offset)[0]
                p.value = current
                if not self.show_zeros_var.get() and abs(float(current)) < 1e-12:
                    continue
            value_text = self._format_value(p)
            haystack = f"{p.offset_text} {p.name} {p.kind} {p.group} {value_text} {p.note}".lower()
            if query and query not in haystack:
                continue
            iid = f"off_{p.offset:04X}"
            tag = p.group if p.editable and p.group in GROUP_COLORS else "readonly" if not p.editable else p.group
            self.tree.insert("", "end", iid=iid, values=(p.offset_text, p.name, p.kind, p.group, value_text), tags=(tag,))
            self._visible_params[iid] = p
            shown += 1
        editable_count = sum(1 for p in params if p.editable)
        self.count_label.configure(text=f"Showing {shown} field(s) | {editable_count} editable shader float(s)")
        self._update_info()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        p = self._visible_params.get(sel[0])
        if not p:
            return
        self.selected_offset = p.offset
        self.sel_name_var.set(p.name)
        self.sel_offset_var.set(p.offset_text)
        self.sel_type_var.set(p.kind + (" — EDITABLE" if p.editable else ""))
        self.sel_note_var.set(p.note)
        if p.kind == "Float32" and self.doc:
            value = struct.unpack_from("<f", self.doc.data, p.offset)[0]
            orig = struct.unpack_from("<f", self.doc.original, p.offset)[0]
            self.value_var.set(f"{value:.9g}")
            self.sel_original_var.set(f"{orig:.9g}")
            self.slider_var.set(max(-25.0, min(25.0, value)))
            self.value_entry.configure(state="normal")
            self.slider.state(["!disabled"])
        else:
            self.value_var.set(self._format_value(p))
            self.sel_original_var.set(self._format_value(p))
            self.value_entry.configure(state="disabled")
            self.slider.state(["disabled"])
        self._set_hex(hex_context(self.doc, p.offset) if self.doc else "")

    def _clear_selection_panel(self):
        self.sel_name_var.set("-")
        self.sel_offset_var.set("-")
        self.sel_type_var.set("-")
        self.sel_original_var.set("-")
        self.sel_note_var.set("Select a shader-float row to edit it.")
        self.value_var.set("")
        self._set_hex("")

    def _slider_changed(self, value):
        if self.selected_offset is None or not self.doc:
            return
        # Don't overwrite the entry when a read-only row is selected.
        try:
            p = next(p for p in build_parameters(self.doc) if p.offset == self.selected_offset)
        except StopIteration:
            return
        if p.editable:
            self.value_var.set(f"{float(value):.6g}")

    def _apply_value(self):
        if not self.doc or self.selected_offset is None:
            messagebox.showinfo("MAT Editor", "Select an editable shader-float parameter first.")
            return
        try:
            write_float(self.doc, self.selected_offset, float(self.value_var.get().strip()))
            self._refresh_table()
            iid = f"off_{self.selected_offset:04X}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                self._on_select()
            self._set_status(f"Applied value at 0x{self.selected_offset:04X}. MAT size unchanged at {len(self.doc.data)} bytes.")
        except Exception as exc:
            messagebox.showerror("MAT Editor", str(exc))

    def _reset_parameter(self):
        if not self.doc or self.selected_offset is None:
            return
        try:
            reset_float(self.doc, self.selected_offset)
            self._refresh_table()
            iid = f"off_{self.selected_offset:04X}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
                self._on_select()
            self._set_status(f"Reset 0x{self.selected_offset:04X} to its original value.")
        except Exception as exc:
            messagebox.showerror("MAT Editor", str(exc))

    def _reset_all(self):
        if not self.doc:
            return
        if self.doc.dirty and not messagebox.askyesno("MAT Editor", "Reset every edited value back to the MAT as it was when opened?"):
            return
        reset_all(self.doc)
        self._refresh_table()
        self._clear_selection_panel()
        self._set_status("All in-memory MAT edits reset.")

    def _save_copy(self):
        if not self.doc:
            messagebox.showinfo("MAT Editor", "Open a MAT file first.")
            return
        default = self.doc.path.with_name(self.doc.path.stem + "_EDITED.mat")
        out = filedialog.asksaveasfilename(
            title="Save Modified MAT",
            initialdir=str(default.parent),
            initialfile=default.name,
            defaultextension=".mat",
            filetypes=[("Spider-Man 3 MAT", "*.mat"), ("All files", "*.*")],
        )
        if not out:
            return
        try:
            saved = save_copy(self.doc, out)
            self._set_status(f"Saved modified MAT copy: {saved.name}")
            messagebox.showinfo("MAT Editor", f"Modified MAT saved successfully.\n\n{saved}\n\nOriginal loaded MAT was not changed.")
        except Exception as exc:
            messagebox.showerror("MAT Editor", str(exc))

    def _save_changes(self):
        if not self.doc:
            return
        if not self.doc.dirty:
            messagebox.showinfo("MAT Editor", "There are no unsaved MAT changes.")
            return
        if not messagebox.askyesno(
            "MAT Editor — Save Changes",
            "Write the edited bytes back to the loaded extracted MAT?\n\n"
            "The editor will create a .mat.bak backup the first time.\n"
            "The MAT size and identity fields are preserved.",
        ):
            return
        try:
            path, backup = overwrite_with_backup(self.doc)
            self._set_status(f"Saved changes to {path.name}; backup: {backup.name}")
            messagebox.showinfo("MAT Editor", f"Changes saved.\n\nMAT: {path}\nBackup: {backup}")
        except Exception as exc:
            messagebox.showerror("MAT Editor", str(exc))

    def _set_hex(self, text):
        self.hex_text.configure(state="normal")
        self.hex_text.delete("1.0", "end")
        self.hex_text.insert("1.0", text)
        self.hex_text.configure(state="disabled")

    def _set_status(self, text):
        self.status_var.set(text)
        try:
            self.app_state.set_status(text)
        except Exception:
            pass
