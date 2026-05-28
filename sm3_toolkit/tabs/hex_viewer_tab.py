from __future__ import annotations

from pathlib import Path
import html
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path


class HexViewerTab(ttk.Frame):
    """Read-only integrated hex viewer.

    Designed for release use: opens any file type, searches text/hex/TEX markers,
    and exports the current page to HTML or TXT without modifying the source file.
    """

    def __init__(self, parent, app):
        super().__init__(parent, style="Body.TFrame", padding=12)
        self.app = app
        self.file_var = tk.StringVar()
        self.offset_var = tk.StringVar(value="0x0")
        self.find_hex_var = tk.StringVar()
        self.find_text_var = tk.StringVar()
        self.page_size_var = tk.StringVar(value="0x4000")
        self.status_var = tk.StringVar(value="Open any file to view hex, search text/hex, or export the current page.")
        self.inspector_var = tk.StringVar(value="Byte Inspector: select a byte in the hex pane.")
        self.path: Path | None = None
        self.file_size = 0
        self.current_offset = 0
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="Body.TFrame")
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Hex Viewer", style="SectionTitle.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Read-only viewer for PCPACK, TOC, DLL, EXE, HTML, TXT, BIN, and any file type. It never edits originals.",
            style="Muted.TLabel",
        ).pack(side="left", padx=(12, 0))

        controls = ttk.Frame(self, style="Card.TFrame", padding=10)
        controls.pack(fill="x", pady=(0, 8))
        for col in (1, 5, 8):
            controls.columnconfigure(col, weight=1)

        ttk.Button(controls, text="Open File", command=self.open_file, style="Accent.TButton").grid(row=0, column=0, padx=4, pady=3, sticky="ew")
        ttk.Entry(controls, textvariable=self.file_var).grid(row=0, column=1, columnspan=9, sticky="ew", padx=4, pady=3)
        ttk.Button(controls, text="Reveal Folder", command=self.reveal_file).grid(row=0, column=10, padx=4, pady=3, sticky="ew")

        ttk.Label(controls, text="Go to offset:", style="CardLabel.TLabel").grid(row=1, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.offset_var, width=14).grid(row=1, column=1, padx=4, pady=3, sticky="w")
        ttk.Button(controls, text="Go", command=self.go_offset).grid(row=1, column=2, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Previous", command=lambda: self.move_page(-1)).grid(row=1, column=3, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Next", command=lambda: self.move_page(1)).grid(row=1, column=4, padx=4, pady=3, sticky="ew")
        ttk.Label(controls, text="Page:", style="CardLabel.TLabel").grid(row=1, column=5, padx=4, pady=3, sticky="e")
        ttk.Combobox(controls, textvariable=self.page_size_var, values=["0x1000", "0x4000", "0x8000", "0x10000"], width=10, state="readonly").grid(row=1, column=6, padx=4, pady=3, sticky="w")
        ttk.Button(controls, text="Reload", command=self.render_page).grid(row=1, column=7, padx=4, pady=3, sticky="ew")

        ttk.Label(controls, text="Find Hex:", style="CardLabel.TLabel").grid(row=2, column=0, padx=4, pady=3, sticky="w")
        ttk.Entry(controls, textvariable=self.find_hex_var).grid(row=2, column=1, columnspan=3, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Find Hex", command=self.find_hex).grid(row=2, column=4, padx=4, pady=3, sticky="ew")
        ttk.Label(controls, text="Find Text:", style="CardLabel.TLabel").grid(row=2, column=5, padx=4, pady=3, sticky="e")
        ttk.Entry(controls, textvariable=self.find_text_var).grid(row=2, column=6, columnspan=3, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Find Text", command=self.find_text).grid(row=2, column=9, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Find TEX", command=self.find_tex_string).grid(row=2, column=10, padx=4, pady=3, sticky="ew")

        ttk.Label(controls, text="Export:", style="CardLabel.TLabel").grid(row=3, column=0, padx=4, pady=3, sticky="w")
        ttk.Button(controls, text="Export Page HTML", command=self.export_current_page_html).grid(row=3, column=1, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Export Page TXT", command=self.export_current_page_text).grid(row=3, column=2, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Open HTML Preview", command=self.open_html_preview).grid(row=3, column=3, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Clear", command=self.clear_view).grid(row=3, column=10, padx=4, pady=3, sticky="ew")

        panes = ttk.Frame(self, style="Body.TFrame")
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=3)
        panes.columnconfigure(1, weight=2)
        panes.rowconfigure(0, weight=1)

        self.hex_text = tk.Text(
            panes,
            wrap="none",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Consolas", 10),
            undo=False,
        )
        self.hex_text.grid(row=0, column=0, sticky="nsew")
        self.ascii_text = tk.Text(
            panes,
            wrap="none",
            bg=COLORS["field"],
            fg=COLORS["muted"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Consolas", 10),
            undo=False,
            width=36,
        )
        self.ascii_text.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ybar = ttk.Scrollbar(panes, orient="vertical", command=self._scroll_both)
        ybar.grid(row=0, column=2, sticky="ns")
        self.hex_text.configure(yscrollcommand=lambda *a: self._sync_scrollbar(ybar, *a))
        xbar = ttk.Scrollbar(panes, orient="horizontal", command=self.hex_text.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        self.hex_text.configure(xscrollcommand=xbar.set)
        self.hex_text.bind("<ButtonRelease-1>", self.update_byte_inspector)
        self.hex_text.bind("<KeyRelease>", self.update_byte_inspector)
        self.hex_text.bind("<MouseWheel>", self._wheel_both)
        self.ascii_text.bind("<MouseWheel>", self._wheel_both)

        bottom = ttk.Frame(self, style="Card.TFrame", padding=8)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Label(bottom, textvariable=self.status_var, style="CardLabel.TLabel").pack(anchor="w")
        ttk.Label(bottom, textvariable=self.inspector_var, style="CardLabel.TLabel").pack(anchor="w", pady=(4, 0))
        self.clear_view()

    def _page_size(self):
        try:
            return max(0x100, int(self.page_size_var.get().strip(), 0))
        except Exception:
            return 0x4000

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open any file in Hex Viewer",
            filetypes=[
                ("All supported / any file", "*.*"),
                ("Game / binary files", "*.PCPACK *.pcpack *.PCAPK *.pcapk *.APKF *.apkf *.toc *.dll *.exe *.bin *.dat"),
                ("Text / HTML", "*.html *.htm *.txt *.csv *.json *.xml *.log"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.path = Path(path)
        try:
            self.file_size = self.path.stat().st_size
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))
            return
        self.file_var.set(str(self.path))
        self.current_offset = 0
        self.render_page()

    def reveal_file(self):
        if self.path and self.path.exists():
            open_path(self.path.parent)
        else:
            messagebox.showinfo("No file", "Open a file first.")

    def clear_view(self):
        self.hex_text.configure(state="normal")
        self.ascii_text.configure(state="normal")
        self.hex_text.delete("1.0", "end")
        self.ascii_text.delete("1.0", "end")
        self.hex_text.insert("1.0", "Offset     00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F\n")
        self.ascii_text.insert("1.0", "ASCII\n")
        self.status_var.set("Open any file to view hex. Supports PCPACK, TOC, DLL, EXE, HTML, TXT, BIN, and more.")
        self.inspector_var.set("Byte Inspector: select a byte in the hex pane.")

    def _read_page(self):
        if not self.path:
            return b""
        start = max(0, min(self.current_offset, max(0, self.file_size - 1))) if self.file_size else 0
        start -= start % 16
        self.current_offset = start
        with self.path.open("rb") as f:
            f.seek(start)
            return f.read(self._page_size())

    def render_page(self):
        if not self.path:
            self.clear_view()
            return
        try:
            data = self._read_page()
        except Exception as exc:
            messagebox.showerror("Read failed", str(exc))
            return
        hex_lines = ["Offset     00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F"]
        ascii_lines = ["ASCII"]
        for row_start in range(0, len(data), 16):
            chunk = data[row_start:row_start + 16]
            off = self.current_offset + row_start
            hex_lines.append(f"{off:08X}:  {' '.join(f'{b:02X}' for b in chunk).ljust(47)}")
            ascii_lines.append(f"{off:08X}:  {''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)}")
        self.hex_text.delete("1.0", "end")
        self.ascii_text.delete("1.0", "end")
        self.hex_text.insert("1.0", "\n".join(hex_lines))
        self.ascii_text.insert("1.0", "\n".join(ascii_lines))
        end_offset = self.current_offset + max(0, len(data) - 1)
        self.offset_var.set(f"0x{self.current_offset:X}")
        self.status_var.set(f"{self.path.name} | size 0x{self.file_size:X} ({self.file_size:,}) | showing 0x{self.current_offset:X}-0x{end_offset:X}")

    def go_offset(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        try:
            off = int(self.offset_var.get().strip().replace("_", ""), 0)
        except Exception:
            messagebox.showerror("Bad offset", "Use decimal or hex, for example 0x1000.")
            return
        if off < 0 or off >= self.file_size:
            messagebox.showerror("Offset out of range", f"File range is 0x0 to 0x{max(0, self.file_size - 1):X}")
            return
        self.current_offset = off - (off % 16)
        self.render_page()

    def move_page(self, direction):
        if self.path:
            self.current_offset = max(0, min(max(0, self.file_size - 1), self.current_offset + direction * self._page_size()))
            self.current_offset -= self.current_offset % 16
            self.render_page()

    def _scroll_both(self, *args):
        self.hex_text.yview(*args)
        self.ascii_text.yview(*args)

    def _sync_scrollbar(self, bar, first, last):
        bar.set(first, last)
        self.ascii_text.yview_moveto(first)

    def _wheel_both(self, event):
        delta = -1 if event.delta > 0 else 1
        self.hex_text.yview_scroll(delta, "units")
        self.ascii_text.yview_scroll(delta, "units")
        return "break"

    def _selected_absolute_byte_offset(self):
        try:
            line_s, col_s = self.hex_text.index("insert").split(".")
            line = int(line_s)
            col = int(col_s)
        except Exception:
            return None
        if line <= 1:
            return None
        rel = col - 11
        if rel < 0:
            return None
        byte_index = rel // 3
        if byte_index < 0 or byte_index > 15:
            return None
        abs_off = self.current_offset + (line - 2) * 16 + byte_index
        return abs_off if abs_off < self.file_size else None

    def update_byte_inspector(self, _event=None):
        abs_off = self._selected_absolute_byte_offset()
        if abs_off is None or not self.path:
            return
        try:
            with self.path.open("rb") as f:
                f.seek(abs_off)
                data = f.read(8)
        except Exception:
            return
        if not data:
            return
        b = data[0]
        le = lambda n: int.from_bytes(data[:n].ljust(n, b"\x00"), "little")
        ch = chr(b) if 32 <= b <= 126 else "."
        self.inspector_var.set(f"Byte Inspector | offset 0x{abs_off:X} dec {abs_off} | u8 0x{b:02X}/{b} | u16LE 0x{le(2):04X} | u32LE 0x{le(4):08X} | char '{ch}'")

    def _find_bytes_stream(self, needle, start):
        if not self.path or not needle:
            return -1
        chunk_size = 1024 * 1024
        overlap = max(0, len(needle) - 1)
        pos = max(0, start)
        prev = b""
        with self.path.open("rb") as f:
            f.seek(pos)
            while True:
                block = f.read(chunk_size)
                if not block:
                    return -1
                search = prev + block
                hit = search.find(needle)
                if hit >= 0:
                    return pos - len(prev) + hit
                pos += len(block)
                prev = search[-overlap:] if overlap else b""

    def find_hex(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        raw = self.find_hex_var.get().strip().replace("0x", "").replace(" ", "").replace("-", "")
        if not raw or len(raw) % 2:
            messagebox.showerror("Bad hex", "Enter hex bytes, for example: 41 50 4B 46")
            return
        try:
            needle = bytes.fromhex(raw)
        except Exception:
            messagebox.showerror("Bad hex", "Hex string could not be parsed.")
            return
        self._jump_to_find(needle, "hex")

    def find_tex_string(self):
        """Quick search for common TEX/string markers in game packs and exports."""
        self.find_text_var.set("TEX")
        self.find_text()

    def find_text(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        text = self.find_text_var.get()
        if text:
            self._jump_to_find(text.encode("utf-8", errors="ignore"), "text")

    def _jump_to_find(self, needle, label):
        hit = self._find_bytes_stream(needle, self.current_offset + 1)
        if hit < 0:
            hit = self._find_bytes_stream(needle, 0)
        if hit < 0:
            messagebox.showinfo("Not found", f"{label.title()} not found.")
            return
        self.current_offset = hit - (hit % 16)
        self.render_page()
        self.status_var.set(f"Found {label} at 0x{hit:X}; page starts at 0x{self.current_offset:X}")

    def _current_view_text(self):
        hex_dump = self.hex_text.get("1.0", "end-1c")
        ascii_dump = self.ascii_text.get("1.0", "end-1c")
        return hex_dump, ascii_dump

    def _default_export_name(self, suffix):
        stem = self.path.stem if self.path else "hex_view"
        return f"{stem}_offset_{self.current_offset:08X}{suffix}"

    def export_current_page_text(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export current hex page as text",
            defaultextension=".txt",
            initialfile=self._default_export_name(".txt"),
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        hex_dump, ascii_dump = self._current_view_text()
        try:
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"File: {self.path}\n")
                f.write(f"Size: 0x{self.file_size:X} ({self.file_size:,})\n")
                f.write(f"Page offset: 0x{self.current_offset:X}\n\n")
                f.write("HEX VIEW\n")
                f.write(hex_dump)
                f.write("\n\nASCII VIEW\n")
                f.write(ascii_dump)
                f.write("\n")
            self.status_var.set(f"Exported text page: {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def export_current_page_html(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export current hex page as HTML",
            defaultextension=".html",
            initialfile=self._default_export_name(".html"),
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self._write_html_export(Path(path))
            self.status_var.set(f"Exported HTML page: {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def _write_html_export(self, out_path: Path) -> None:
        hex_dump, ascii_dump = self._current_view_text()
        title = f"Hex View - {self.path.name if self.path else 'file'}"
        body = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ background:#15171c; color:#f2f4f8; font-family:Segoe UI, Arial, sans-serif; margin:20px; }}
h1 {{ color:#d9e3f0; }}
.meta {{ color:#aeb9c8; margin-bottom:16px; }}
.wrap {{ display:flex; gap:18px; align-items:flex-start; }}
pre {{ background:#20242c; color:#f2f4f8; border:1px solid #4a5363; padding:12px; overflow:auto; font-family:Consolas, monospace; font-size:13px; line-height:1.35; }}
.ascii {{ color:#c7ccd6; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta">File: {html.escape(str(self.path))}<br>Size: 0x{self.file_size:X} ({self.file_size:,})<br>Page offset: 0x{self.current_offset:X}</div>
<div class="wrap"><pre>{html.escape(hex_dump)}</pre><pre class="ascii">{html.escape(ascii_dump)}</pre></div>
</body></html>
"""
        out_path.write_text(body, encoding="utf-8")

    def open_html_preview(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        try:
            out_path = Path(tempfile.gettempdir()) / self._default_export_name(".html")
            self._write_html_export(out_path)
            webbrowser.open(out_path.resolve().as_uri())
            self.status_var.set(f"Opened HTML preview: {out_path}")
        except Exception as exc:
            messagebox.showerror("HTML preview failed", str(exc))
