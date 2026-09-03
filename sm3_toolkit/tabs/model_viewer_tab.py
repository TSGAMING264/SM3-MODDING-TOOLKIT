from __future__ import annotations

import math
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path
from sm3_toolkit.services.sm3_mesh_viewer_service import (
    SM3MeshDocument,
    SM3MeshError,
    SM3MeshSection,
    load_sm3_mesh,
)

try:
    from PIL import Image, ImageDraw, ImageTk
    PIL_OK = True
    PIL_ERROR = ""
except Exception as exc:  # pragma: no cover - startup fallback
    PIL_OK = False
    PIL_ERROR = str(exc)
    Image = None
    ImageDraw = None
    ImageTk = None


class ModelViewerTab(ttk.Frame):
    """View-only native Spider-Man 3 PC .mesh viewer.

    Deliberately accepts only SM3 .mesh resources.  There are no OBJ/DAE/FBX
    import paths and no model editing/export controls in this tab.
    """

    FAST_FACE_LIMIT = 14_000

    def __init__(self, parent, app_state):
        super().__init__(parent, padding=10)
        self.app_state = app_state
        self.doc: SM3MeshDocument | None = None
        self.visible_sections: set[int] = set()

        self.path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Open a native Spider-Man 3 .mesh file to view it.")
        self.solid_var = tk.BooleanVar(value=True)
        self.wire_var = tk.BooleanVar(value=False)
        self.grid_var = tk.BooleanVar(value=True)

        self.info_name_var = tk.StringVar(value="-")
        self.info_hash_var = tk.StringVar(value="-")
        self.info_magic_var = tk.StringVar(value="-")
        self.info_size_var = tk.StringVar(value="-")
        self.info_sections_var = tk.StringVar(value="-")
        self.info_vertices_var = tk.StringVar(value="-")
        self.info_triangles_var = tk.StringVar(value="-")
        self.info_stream_var = tk.StringVar(value="-")

        # Match the Suit Editor model-viewer camera exactly.
        self.yaw = 0.6
        self.pitch = -0.3
        self.zoom = 1.0
        self._drag_mode: str | None = None
        self._last_mouse = (0, 0)
        self._render_after = None
        self._photo = None
        self._last_size = (0, 0)

        self._build_ui()
        try:
            self.app_state.on_theme_change(lambda _theme: self._schedule_render(full=True, delay=30))
        except Exception:
            pass

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="SM3 Model Viewer", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="VIEW ONLY — opens native Spider-Man 3 PC .mesh resources and displays the actual in-game geometry. No SM2/WOS/OBJ/DAE/FBX import and no model editing/export.",
            wraplength=1200,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        filebar = ttk.LabelFrame(self, text="SM3 MESH File", padding=8)
        filebar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        filebar.columnconfigure(1, weight=1)
        ttk.Button(filebar, text="OPEN SM3 MESH", command=self._open_mesh).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ttk.Entry(filebar, textvariable=self.path_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(filebar, text="OPEN FOLDER", command=self._open_folder).grid(row=0, column=2, padx=(6, 0), sticky="e")

        tools = ttk.Frame(self)
        tools.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        for label, cmd in (
            ("Front", self._front),
            ("Back", self._back),
            ("Left", self._left),
            ("Right", self._right),
            ("Fit", self._fit),
        ):
            ttk.Button(tools, text=label, command=cmd, width=8).pack(side="left", padx=(0, 5))
        ttk.Separator(tools, orient="vertical").pack(side="left", fill="y", padx=7)
        ttk.Checkbutton(tools, text="Solid", variable=self.solid_var, command=lambda: self._schedule_render(full=True)).pack(side="left", padx=4)
        ttk.Checkbutton(tools, text="Wireframe", variable=self.wire_var, command=lambda: self._schedule_render(full=True)).pack(side="left", padx=4)
        ttk.Checkbutton(tools, text="Grid", variable=self.grid_var, command=lambda: self._schedule_render(full=True)).pack(side="left", padx=4)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=3, column=0, sticky="nsew")

        view_host = ttk.Frame(body)
        side_host = ttk.Frame(body)
        body.add(view_host, weight=5)
        body.add(side_host, weight=2)
        view_host.rowconfigure(0, weight=1)
        view_host.columnconfigure(0, weight=1)

        # The model-info/section stack is taller than a laptop-height viewport.
        # Keep every control reachable with a dedicated vertical scrollbar instead
        # of letting the lower section list disappear below the tab.
        side_host.rowconfigure(0, weight=1)
        side_host.columnconfigure(0, weight=1)
        side_canvas = tk.Canvas(
            side_host,
            highlightthickness=0,
            borderwidth=0,
            background=COLORS.get("bg", "#17191F"),
        )
        side_scroll = ttk.Scrollbar(side_host, orient="vertical", command=side_canvas.yview)
        side_canvas.configure(yscrollcommand=side_scroll.set)
        side_canvas.grid(row=0, column=0, sticky="nsew")
        side_scroll.grid(row=0, column=1, sticky="ns")
        side = ttk.Frame(side_canvas, padding=(8, 0, 4, 0))
        side_window = side_canvas.create_window((0, 0), window=side, anchor="nw")
        side.rowconfigure(1, weight=1)
        side.columnconfigure(0, weight=1)

        def _sync_side_scroll(_event=None):
            try:
                side_canvas.itemconfigure(side_window, width=max(1, side_canvas.winfo_width()))
                side_canvas.configure(scrollregion=side_canvas.bbox("all"))
            except Exception:
                pass

        side.bind("<Configure>", _sync_side_scroll, add="+")
        side_canvas.bind("<Configure>", _sync_side_scroll, add="+")

        self.viewport = tk.Canvas(
            view_host,
            background="#101216",
            highlightthickness=1,
            highlightbackground=COLORS.get("border", "#444444"),
            cursor="fleur",
        )
        self.viewport.grid(row=0, column=0, sticky="nsew")
        self.viewport.bind("<Configure>", self._on_resize)
        self.viewport.bind("<ButtonPress-1>", lambda e: self._begin_drag(e, "orbit"))
        self.viewport.bind("<B1-Motion>", self._drag)
        self.viewport.bind("<ButtonRelease-1>", self._end_drag)
        self.viewport.bind("<MouseWheel>", self._wheel)
        self.viewport.bind("<Button-4>", lambda e: self._wheel_linux(+1))
        self.viewport.bind("<Button-5>", lambda e: self._wheel_linux(-1))

        info = ttk.LabelFrame(side, text="Model Info", padding=8)
        info.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(1, weight=1)
        self._info_row(info, 0, "Name", self.info_name_var)
        self._info_row(info, 1, "MESH Hash", self.info_hash_var)
        self._info_row(info, 2, "Header", self.info_magic_var)
        self._info_row(info, 3, "File Size", self.info_size_var)
        self._info_row(info, 4, "Sections", self.info_sections_var)
        self._info_row(info, 5, "Vertices", self.info_vertices_var)
        self._info_row(info, 6, "Triangles", self.info_triangles_var)
        self._info_row(info, 7, "Geometry Stream", self.info_stream_var)

        secbox = ttk.LabelFrame(side, text="In-Game Mesh Sections", padding=6)
        secbox.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        secbox.rowconfigure(1, weight=1)
        secbox.columnconfigure(0, weight=1)

        sec_tools = ttk.Frame(secbox)
        sec_tools.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ttk.Button(sec_tools, text="SHOW ALL", command=self._show_all).pack(side="left", padx=(0, 4))
        ttk.Button(sec_tools, text="HIDE ALL", command=self._hide_all).pack(side="left", padx=4)
        ttk.Button(sec_tools, text="TOGGLE SELECTED", command=self._toggle_selected).pack(side="left", padx=4)

        cols = ("visible", "sec", "verts", "tris", "stride", "mat", "scale")
        self.section_tree = ttk.Treeview(secbox, columns=cols, show="headings", selectmode="browse", height=12)
        for key, text, width in (
            ("visible", "Visible", 65),
            ("sec", "Sec", 45),
            ("verts", "Verts", 80),
            ("tris", "Tris", 80),
            ("stride", "Stride", 60),
            ("mat", "MAT Ref", 95),
            ("scale", "Pos Scale", 80),
        ):
            self.section_tree.heading(key, text=text)
            self.section_tree.column(key, width=width, minwidth=40, anchor="center", stretch=(key in {"mat"}))
        sy = ttk.Scrollbar(secbox, orient="vertical", command=self.section_tree.yview)
        sx = ttk.Scrollbar(secbox, orient="horizontal", command=self.section_tree.xview)
        self.section_tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.section_tree.grid(row=1, column=0, sticky="nsew")
        sy.grid(row=1, column=1, sticky="ns")
        sx.grid(row=2, column=0, sticky="ew")
        self.section_tree.bind("<Double-1>", lambda _e: self._toggle_selected())

        hint = ttk.LabelFrame(side, text="Viewport Controls", padding=8)
        hint.grid(row=2, column=0, sticky="ew")
        ttk.Label(
            hint,
            text="Left drag: rotate\nMouse wheel: zoom\nDouble-click a section: show/hide",
            justify="left",
        ).pack(anchor="w")

        status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        status.grid(row=4, column=0, sticky="ew", pady=(7, 0))

        if not PIL_OK:
            self.status_var.set(f"Model Viewer unavailable: Pillow failed to load ({PIL_ERROR}).")

    @staticmethod
    def _info_row(parent, row: int, label: str, variable: tk.StringVar):
        ttk.Label(parent, text=label + ":", width=16).grid(row=row, column=0, sticky="nw", pady=1)
        ttk.Label(parent, textvariable=variable, wraplength=330, justify="left").grid(row=row, column=1, sticky="ew", pady=1)

    def _open_mesh(self):
        if not PIL_OK:
            messagebox.showerror("SM3 Model Viewer", f"Pillow is required for the viewport.\n\n{PIL_ERROR}")
            return
        path = filedialog.askopenfilename(
            title="Open Spider-Man 3 MESH",
            filetypes=[("Spider-Man 3 MESH", "*.mesh"), ("MESH files", "*.MESH")],
        )
        if not path:
            return
        try:
            self.status_var.set("Decoding native SM3 geometry...")
            self.update_idletasks()
            doc = load_sm3_mesh(path)
        except Exception as exc:
            self.status_var.set("MESH load failed.")
            messagebox.showerror("SM3 Model Viewer", str(exc))
            return

        self.doc = doc
        self.visible_sections = {s.index for s in doc.sections}
        self.path_var.set(str(doc.path))
        self._populate_info()
        self._populate_sections()
        self._fit()
        warning = ("  Warning: " + " ".join(doc.warnings)) if doc.warnings else ""
        self.status_var.set(
            f"Loaded {doc.display_name}: {doc.vertex_count:,} vertices, {doc.triangle_count:,} triangles, {doc.section_count} sections.{warning}"
        )
        try:
            self.app_state.set_status(f"SM3 Model Viewer loaded {doc.path.name}.")
        except Exception:
            pass

    def _open_folder(self):
        if self.doc is None:
            messagebox.showinfo("SM3 Model Viewer", "Open an SM3 .mesh file first.")
            return
        open_path(self.doc.path.parent)

    def _populate_info(self):
        if self.doc is None:
            return
        d = self.doc
        self.info_name_var.set(d.display_name)
        self.info_hash_var.set(f"0x{d.embedded_hash:08X}")
        self.info_magic_var.set(f"0x{d.magic:08X}  flags=0x{d.flags:08X}")
        self.info_size_var.set(self._fmt_size(d.file_size))
        self.info_sections_var.set(str(d.section_count))
        self.info_vertices_var.set(f"{d.vertex_count:,}")
        self.info_triangles_var.set(f"{d.triangle_count:,}")
        self.info_stream_var.set(f"0x{d.data_start:X}")

    def _populate_sections(self):
        self.section_tree.delete(*self.section_tree.get_children())
        if self.doc is None:
            return
        for s in self.doc.sections:
            scale = "float" if s.position_type in (2, 3) else f"/{s.position_scale:g}"
            self.section_tree.insert(
                "", "end", iid=str(s.index),
                values=("YES", s.index, f"{s.vertex_count:,}", f"{s.triangle_count:,}", s.stride, s.material_label, scale),
            )

    @staticmethod
    def _fmt_size(n: int) -> str:
        value = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024.0 or unit == "GB":
                return f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            value /= 1024.0
        return f"{n} B"

    def _show_all(self):
        if self.doc is None:
            return
        self.visible_sections = {s.index for s in self.doc.sections}
        self._refresh_visibility_labels()
        self._schedule_render(full=True)

    def _hide_all(self):
        self.visible_sections.clear()
        self._refresh_visibility_labels()
        self._schedule_render(full=True)

    def _toggle_selected(self):
        sel = self.section_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if idx in self.visible_sections:
            self.visible_sections.remove(idx)
        else:
            self.visible_sections.add(idx)
        self._refresh_visibility_labels()
        self._schedule_render(full=True)

    def _refresh_visibility_labels(self):
        for iid in self.section_tree.get_children():
            values = list(self.section_tree.item(iid, "values"))
            if values:
                values[0] = "YES" if int(iid) in self.visible_sections else "NO"
                self.section_tree.item(iid, values=values)

    def _front(self):
        self.yaw = 0.0
        self.pitch = 0.0
        self.zoom = 1.0
        self._schedule_render(full=True)

    def _back(self):
        self.yaw = math.pi
        self.pitch = 0.0
        self.zoom = 1.0
        self._schedule_render(full=True)

    def _left(self):
        self.yaw = -math.pi / 2.0
        self.pitch = 0.0
        self.zoom = 1.0
        self._schedule_render(full=True)

    def _right(self):
        self.yaw = math.pi / 2.0
        self.pitch = 0.0
        self.zoom = 1.0
        self._schedule_render(full=True)

    def _fit(self):
        # Suit Editor ResetView: return to its preferred 3/4 camera.
        self.yaw = 0.6
        self.pitch = -0.3
        self.zoom = 1.0
        self._schedule_render(full=True)

    def _begin_drag(self, event, mode: str):
        self._drag_mode = mode
        self._last_mouse = (event.x, event.y)
        try:
            self.viewport.focus_set()
        except Exception:
            pass

    def _drag(self, event):
        if self._drag_mode is None:
            return
        lx, ly = self._last_mouse
        dx, dy = event.x - lx, event.y - ly
        self._last_mouse = (event.x, event.y)
        self.yaw += dx * 0.008
        self.pitch += dy * 0.008
        self._schedule_render(full=False, delay=1)

    def _end_drag(self, _event=None):
        self._drag_mode = None
        self._schedule_render(full=True, delay=5)

    def _wheel(self, event):
        self.zoom = max(0.1, min(12.0, self.zoom + (0.1 if event.delta > 0 else -0.1)))
        self._schedule_render(full=False, delay=1)
        self.after(90, lambda: self._schedule_render(full=True, delay=1))
        return "break"

    def _wheel_linux(self, direction: int):
        self.zoom = max(0.1, min(12.0, self.zoom + (0.1 if direction > 0 else -0.1)))
        self._schedule_render(full=True)
        return "break"

    def _on_resize(self, event):
        size = (event.width, event.height)
        if size != self._last_size:
            self._last_size = size
            self._schedule_render(full=True, delay=120)

    def _schedule_render(self, full: bool = True, delay: int = 10):
        if self._render_after is not None:
            try:
                self.after_cancel(self._render_after)
            except Exception:
                pass
        self._render_after = self.after(delay, lambda: self._render(full=full))

    @staticmethod
    def _hex_rgb(value: str, fallback=(16, 18, 22)):
        try:
            value = value.lstrip("#")
            if len(value) == 6:
                return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            pass
        return fallback

    @staticmethod
    def _shade(base, intensity: float):
        intensity = max(0.25, min(1.15, intensity))
        return tuple(max(0, min(255, int(c * intensity))) for c in base)

    def _visible_geometry_bounds(self):
        if self.doc is None:
            return None
        points = []
        for sec in self.doc.sections:
            if sec.index in self.visible_sections:
                points.extend(sec.positions)
        if not points:
            return None
        minx = min(p[0] for p in points); maxx = max(p[0] for p in points)
        miny = min(p[1] for p in points); maxy = max(p[1] for p in points)
        minz = min(p[2] for p in points); maxz = max(p[2] for p in points)
        return points, (minx, maxx, miny, maxy, minz, maxz)

    def _render(self, full: bool = True):
        self._render_after = None
        if not PIL_OK:
            return
        w = max(2, int(self.viewport.winfo_width()))
        h = max(2, int(self.viewport.winfo_height()))
        if w < 10 or h < 10:
            return

        bg = self._hex_rgb(COLORS.get("field", "#101216"), (16, 18, 22))
        image = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(image)

        if self.grid_var.get():
            self._draw_grid(draw, w, h, bg)

        if self.doc is None:
            text = "No SM3 .mesh loaded"
            bbox = draw.textbbox((0, 0), text)
            draw.text(((w - (bbox[2]-bbox[0]))/2, (h - (bbox[3]-bbox[1]))/2), text, fill=(170, 175, 185))
            self._show_image(image)
            return

        visible = [s for s in self.doc.sections if s.index in self.visible_sections]
        if not visible:
            draw.text((18, 18), "All mesh sections are hidden.", fill=(190, 195, 205))
            self._draw_badge(draw, w, h, "0 visible sections")
            self._show_image(image)
            return

        points = [p for sec in visible for p in sec.positions]
        minx = min(p[0] for p in points); maxx = max(p[0] for p in points)
        miny = min(p[1] for p in points); maxy = max(p[1] for p in points)
        minz = min(p[2] for p in points); maxz = max(p[2] for p in points)
        cx = (minx + maxx) * 0.5
        cy0 = (miny + maxy) * 0.5
        cz = (minz + maxz) * 0.5
        span = max(maxx-minx, maxy-miny, maxz-minz, 1e-6)
        scale = min(w, h) * 0.72 * self.zoom / span

        cosy = math.cos(self.yaw); siny = math.sin(self.yaw)
        cosp = math.cos(self.pitch); sinp = math.sin(self.pitch)

        # Project section-local arrays independently so section visibility stays cheap.
        projected_by_section: dict[int, list[tuple[float, float, float]]] = {}
        rotated_by_section: dict[int, list[tuple[float, float, float]]] = {}
        for sec in visible:
            projected = []
            rotated = []
            for x, y, z in sec.positions:
                x -= cx; y -= cy0; z -= cz
                x1 = x * cosy + z * siny
                z1 = -x * siny + z * cosy
                y1 = y * cosp - z1 * sinp
                z2 = y * sinp + z1 * cosp
                rotated.append((x1, y1, z2))
                projected.append((w * 0.5 + x1 * scale, h * 0.5 - y1 * scale, z2))
            projected_by_section[sec.index] = projected
            rotated_by_section[sec.index] = rotated

        total_faces = sum(sec.triangle_count for sec in visible)
        face_limit = None if full else self.FAST_FACE_LIMIT
        sample_step = 1.0
        if face_limit and total_faces > face_limit:
            sample_step = total_faces / face_limit

        packets = []
        global_face_counter = 0
        next_take = 0.0
        for sec in visible:
            proj = projected_by_section[sec.index]
            rot = rotated_by_section[sec.index]
            for tri in sec.triangles:
                if sample_step > 1.0:
                    if global_face_counter + 1e-9 < next_take:
                        global_face_counter += 1
                        continue
                    next_take += sample_step
                global_face_counter += 1
                a, b, c = tri
                pa, pb, pc = rot[a], rot[b], rot[c]
                ux, uy, uz = pb[0]-pa[0], pb[1]-pa[1], pb[2]-pa[2]
                vx, vy, vz = pc[0]-pa[0], pc[1]-pa[1], pc[2]-pa[2]
                nx = uy*vz - uz*vy
                ny = uz*vx - ux*vz
                nz = ux*vy - uy*vx
                nlen = math.sqrt(nx*nx + ny*ny + nz*nz)
                facing = abs(nz) / nlen if nlen > 1e-12 else 0.0
                depth = (pa[2] + pb[2] + pc[2]) / 3.0
                packets.append((depth, sec.index, a, b, c, facing))

        packets.sort(key=lambda item: item[0])
        base = self._hex_rgb(COLORS.get("muted", "#AEB4BE"), (150, 156, 166))
        border = self._hex_rgb(COLORS.get("border", "#454A52"), (70, 75, 85))

        solid = bool(self.solid_var.get())
        wire = bool(self.wire_var.get())
        for _depth, sec_index, a, b, c, facing in packets:
            proj = projected_by_section[sec_index]
            pts = [(proj[a][0], proj[a][1]), (proj[b][0], proj[b][1]), (proj[c][0], proj[c][1])]
            if solid:
                # Slight section modulation makes overlapping native submeshes readable
                # without pretending these are their actual game textures/material colors.
                mod = 0.88 + ((sec_index * 17) % 13) / 100.0
                color = self._shade(base, (0.48 + 0.55 * facing) * mod)
                draw.polygon(pts, fill=color)
            if wire:
                draw.line((pts[0], pts[1], pts[2], pts[0]), fill=border, width=1)

        shown_faces = len(packets)
        badge = f"{self.doc.vertex_count:,} verts | {self.doc.triangle_count:,} tris | {len(visible)}/{self.doc.section_count} sections | Zoom {self.zoom:.2f}x"
        if shown_faces < total_faces:
            badge += f" | interactive {shown_faces:,}/{total_faces:,} faces"
        self._draw_badge(draw, w, h, badge)
        draw.text((12, h - 24), "Drag: rotate   •   Mouse wheel: zoom", fill=(180, 185, 195))
        self._show_image(image)

    def _draw_grid(self, draw, w: int, h: int, bg):
        step = max(28, min(64, min(w, h) // 12 if min(w, h) > 0 else 40))
        grid = tuple(min(255, c + 16) for c in bg)
        axis = tuple(min(255, c + 34) for c in bg)
        ox = int(w * 0.5)
        oy = int(h * 0.5)
        start_x = ox % step
        start_y = oy % step
        for x in range(start_x, w, step):
            draw.line((x, 0, x, h), fill=grid)
        for y in range(start_y, h, step):
            draw.line((0, y, w, y), fill=grid)
        draw.line((ox, 0, ox, h), fill=axis)
        draw.line((0, oy, w, oy), fill=axis)

    @staticmethod
    def _draw_badge(draw, w: int, h: int, text: str):
        bbox = draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
        x = max(8, w - tw - 24); y = 10
        draw.rounded_rectangle((x, y, x + tw + 14, y + th + 10), radius=4, fill=(26, 29, 35), outline=(75, 82, 94))
        draw.text((x + 7, y + 5), text, fill=(220, 224, 232))

    def _show_image(self, image):
        try:
            self._photo = ImageTk.PhotoImage(image)
            self.viewport.delete("all")
            self.viewport.create_image(0, 0, image=self._photo, anchor="nw")
        except Exception as exc:
            self.status_var.set(f"Viewport render failed: {exc}")
