#!/usr/bin/env python3
# ============================================================
# SM3 TEXTURE FOLDER PREVIEWER v0.9
# Released by TSGAMING264
#
# Purpose:
# - Dark theme restored.
# - Classic list + preview layout like the earlier DDS previewer builds.
# - Select a folder, scan supported texture/image files, preload ALL previews,
#   use persistent thumbnail cache, click a file, view it instantly when cached,
#   inspect metadata, open/reveal externally.
# - v0.7 restores the old Explorer /select jump-to-image behavior, but
#   fixes the buggy duplicate/misfire behavior from rapid/double clicks.
# - v0.8 adds stronger list filtering: size search, format filter,
#   mip filter, status filter, category filter, square/power-of-two/common suit toggles.
#
# Supported image inputs:
#   DDS, PNG, JPG/JPEG, BMP, DIB, TGA, PPM/PGM/PNM, HDR, PFM
#
# Notes:
# - This is a viewer only.
# - It does NOT edit textures.
# - It does NOT patch PCPACK/PCAPK/XEPACK files.
# - DDS support depends on Pillow's DDS decoder for actual image preview.
#   The tool still reads DDS header metadata even if Pillow cannot decode it.
# ============================================================

from __future__ import annotations

import os
import sys
import json
import time
import math
import struct
import queue
import array
import threading
import webbrowser
import traceback
import hashlib
from pathlib import Path
from collections import OrderedDict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps
    PIL_OK = True
    PIL_ERROR = ""
except Exception as exc:
    PIL_OK = False
    PIL_ERROR = str(exc)
    Image = None
    ImageTk = None
    ImageDraw = None
    ImageFont = None
    ImageOps = None

try:
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
except Exception:
    pass

APP_TITLE = "SM3 Texture Folder Previewer v0.9"
APP_VERSION = "v0.9"
RELEASED_BY = "TSGAMING264"
CACHE_FILENAME = ".sm3_wos_texture_viewer_cache_v05.json"
THUMB_CACHE_DIRNAME = ".sm3_wos_texture_viewer_thumbs_v05"
CACHE_VERSION = 5

SUPPORTED_EXTS = {
    ".dds", ".png", ".jpg", ".jpeg", ".bmp", ".dib", ".tga",
    ".ppm", ".pgm", ".pnm", ".hdr", ".pfm"
}
EXT_LABELS = "DDS, PNG, JPG, BMP, DIB, TGA, PPM, HDR, PFM"


# ------------------------------------------------------------
# v0.9 Strong Reveal in Explorer helpers
# ------------------------------------------------------------
def _open_folder_cross_platform(folder: str):
    folder = os.path.abspath(os.path.normpath(folder))
    if os.name == "nt":
        os.startfile(folder)  # type: ignore[attr-defined]
    else:
        webbrowser.open(Path(folder).resolve().as_uri())


def _windows_explorer_select_file(path: str) -> bool:
    """Open Explorer and force it to jump/select the exact image file.

    v0.9 uses a stronger Windows route than v0.8:
    1) ShellExecuteW with Explorer parameters /n,/select,"FULL_PATH"
       - /n asks Explorer for a fresh window, which usually scrolls/jumps to
         the selected file better than reusing an already-open folder window.
    2) Classic Explorer command-line fallback.

    This keeps the good old behavior the user wanted: Reveal in Explorer should
    take you directly to the selected DDS/image, not just open its folder.
    """
    if os.name != "nt":
        return False
    norm = os.path.abspath(os.path.normpath(str(path)))
    params = f'/n,/select,"{norm}"'

    # Preferred: ShellExecuteW gives Windows Explorer exactly the same parameters
    # as typing: explorer.exe /n,/select,"LOCAL_PATH_REDACTED"
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(None, "open", "explorer.exe", params, None, 1)
        if int(rc) > 32:
            return True
    except Exception:
        pass

    return False


def reveal_path_in_folder(path: str) -> str:
    """Reveal/select the chosen image file in the OS file manager.

    v0.9 goal:
    - jump to and highlight the exact selected image more reliably;
    - do not merely open the containing folder when the file exists;
    - use folder-only fallback only if the file is missing or Explorer launch
      completely fails.
    """
    if not path:
        raise FileNotFoundError("No selected file path.")

    norm = os.path.abspath(os.path.normpath(str(path)))
    parent = os.path.dirname(norm)

    if not os.path.exists(norm):
        if parent and os.path.isdir(parent):
            _open_folder_cross_platform(parent)
            return f"Selected file no longer exists. Opened parent folder: {parent}"
        raise FileNotFoundError(f"Selected file does not exist:\n{norm}")

    if os.path.isdir(norm):
        _open_folder_cross_platform(norm)
        return f"Opened folder: {norm}"

    if os.name == "nt":
        if _windows_explorer_select_file(norm):
            return f"Revealed and selected in Explorer: {os.path.basename(norm)}"
        _open_folder_cross_platform(parent)
        return f"Explorer select failed. Opened containing folder: {parent}"

    if sys.platform == "darwin":
        webbrowser.open(Path(parent).resolve().as_uri())
        return f"Revealed in Finder: {os.path.basename(norm)}"

    _open_folder_cross_platform(parent)
    return f"Opened containing folder: {parent}"

# Dark theme colors. The goal is to restore the clean dark look from the earlier build.
DARK_BG = "#121417"
DARK_PANEL = "#1B1F24"
DARK_PANEL_2 = "#232932"
DARK_FIELD = "#101216"
DARK_TEXT = "#E8EAED"
DARK_MUTED = "#A9B0BA"
DARK_ACCENT = "#3A4658"
DARK_SELECT = "#404B64"
DARK_BORDER = "#343B45"
DARK_ERROR = "#FFB4A8"

TREE_BATCH_SIZE = 250
QUEUE_DRAIN_LIMIT = 300
SEARCH_DEBOUNCE_MS = 180
PREVIEW_CACHE_LIMIT = 20000
PRELOAD_THUMB_MAX_W = 900
PRELOAD_THUMB_MAX_H = 700
CONTACT_THUMB_W = 160
CONTACT_THUMB_H = 120
CONTACT_MAX_ITEMS = 800

DXGI_FORMATS = {
    2: "R32G32B32A32_FLOAT",
    10: "R16G16B16A16_FLOAT",
    24: "R10G10B10A2_UNORM",
    28: "R8G8B8A8_UNORM",
    29: "R8G8B8A8_UNORM_SRGB",
    41: "R32_FLOAT",
    49: "R8G8_UNORM",
    54: "R16_FLOAT",
    61: "R8_UNORM",
    71: "BC1_UNORM / DXT1",
    72: "BC1_UNORM_SRGB / DXT1",
    74: "BC2_UNORM / DXT3",
    75: "BC2_UNORM_SRGB / DXT3",
    77: "BC3_UNORM / DXT5",
    78: "BC3_UNORM_SRGB / DXT5",
    80: "BC4_UNORM",
    83: "BC5_UNORM",
    87: "B8G8R8A8_UNORM",
    88: "B8G8R8X8_UNORM",
    95: "BC6H_UF16",
    96: "BC6H_SF16",
    98: "BC7_UNORM",
    99: "BC7_UNORM_SRGB",
}

FOURCC_NAMES = {
    "DXT1": "DXT1 / BC1",
    "DXT2": "DXT2",
    "DXT3": "DXT3 / BC2",
    "DXT4": "DXT4",
    "DXT5": "DXT5 / BC3",
    "ATI1": "ATI1 / BC4",
    "BC4U": "BC4_UNORM",
    "BC4S": "BC4_SNORM",
    "ATI2": "ATI2 / BC5",
    "BC5U": "BC5_UNORM",
    "BC5S": "BC5_SNORM",
    "DX10": "DX10 extended DDS",
}


def fmt_size(num: int) -> str:
    try:
        n = float(num)
    except Exception:
        return str(num)
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024.0 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.1f} GB"


def safe_rel(path: str, root: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(Path(root).resolve()))
    except Exception:
        return os.path.basename(path)


def read_u32(data: bytes, off: int, default: int = 0) -> int:
    if off + 4 > len(data):
        return default
    return struct.unpack_from("<I", data, off)[0]


def parse_dds_header(path: str) -> dict:
    meta = {
        "kind": "DDS",
        "width": "?",
        "height": "?",
        "format": "DDS",
        "mips": "?",
        "status": "Header read",
        "extra": "",
    }
    try:
        with open(path, "rb") as f:
            data = f.read(180)
        if len(data) < 128 or data[0:4] != b"DDS ":
            meta["status"] = "Bad DDS header"
            return meta
        header_size = read_u32(data, 4)
        height = read_u32(data, 12)
        width = read_u32(data, 16)
        mips = read_u32(data, 28)
        pf_flags = read_u32(data, 80)
        fourcc_raw = data[84:88]
        rgb_bits = read_u32(data, 88)
        rmask = read_u32(data, 92)
        gmask = read_u32(data, 96)
        bmask = read_u32(data, 100)
        amask = read_u32(data, 104)
        fourcc = fourcc_raw.decode("ascii", "ignore").rstrip("\x00 ")
        fmt = "DDS"
        extra = []
        if fourcc:
            fmt = FOURCC_NAMES.get(fourcc, fourcc)
            if fourcc == "DX10" and len(data) >= 148:
                dxgi = read_u32(data, 128)
                array_size = read_u32(data, 140)
                fmt = DXGI_FORMATS.get(dxgi, f"DXGI_FORMAT_{dxgi}")
                extra.append(f"DX10 array={array_size}")
        else:
            if rgb_bits:
                fmt = f"RGB/RGBA {rgb_bits}-bit"
                if rgb_bits == 32:
                    if (rmask, gmask, bmask, amask) == (0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000):
                        fmt = "BGRA32 / A8R8G8B8"
                    elif (rmask, gmask, bmask, amask) == (0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000):
                        fmt = "RGBA32"
                elif rgb_bits == 8:
                    fmt = "L8 / 8-bit"
            else:
                fmt = f"DDS pf_flags=0x{pf_flags:08X}"
        if mips == 0:
            mips = 1
        meta.update({
            "width": str(width) if width else "?",
            "height": str(height) if height else "?",
            "format": fmt,
            "mips": str(mips),
            "status": "OK",
            "extra": "; ".join(extra),
        })
        if header_size != 124:
            meta["status"] = f"Odd header size {header_size}"
        return meta
    except Exception as exc:
        meta["status"] = f"Header error: {exc}"
        return meta


def parse_pfm_header(path: str) -> dict:
    meta = {
        "kind": "PFM",
        "width": "?",
        "height": "?",
        "format": "PFM",
        "mips": "1",
        "status": "Header read",
        "extra": "",
    }
    try:
        with open(path, "rb") as f:
            magic = f.readline().strip()
            dims = f.readline().strip()
            while dims.startswith(b"#"):
                dims = f.readline().strip()
            scale = f.readline().strip()
        if magic not in (b"PF", b"Pf"):
            meta["status"] = "Bad PFM header"
            return meta
        parts = dims.split()
        if len(parts) >= 2:
            w, h = int(parts[0]), int(parts[1])
            channels = 3 if magic == b"PF" else 1
            endian = "little" if float(scale) < 0 else "big"
            meta.update({
                "width": str(w),
                "height": str(h),
                "format": f"PFM {'RGB float32' if channels == 3 else 'Gray float32'}",
                "status": "OK",
                "extra": f"endian={endian}, scale={scale.decode('ascii','ignore')}",
            })
        return meta
    except Exception as exc:
        meta["status"] = f"Header error: {exc}"
        return meta


def parse_generic_image_header(path: str) -> dict:
    ext = Path(path).suffix.lower().lstrip(".").upper()
    meta = {
        "kind": ext,
        "width": "?",
        "height": "?",
        "format": ext,
        "mips": "1",
        "status": "Needs Pillow",
        "extra": "",
    }
    if not PIL_OK:
        return meta
    try:
        with Image.open(path) as im:
            meta.update({
                "width": str(im.width),
                "height": str(im.height),
                "format": f"{im.format or ext} {im.mode}",
                "status": "OK",
                "extra": getattr(im, "info", {}).get("compression", "") or "",
            })
    except Exception as exc:
        meta["status"] = f"Preview/header unsupported: {exc}"
    return meta


def parse_image_meta(path: str) -> dict:
    ext = Path(path).suffix.lower()
    if ext == ".dds":
        return parse_dds_header(path)
    if ext == ".pfm":
        return parse_pfm_header(path)
    return parse_generic_image_header(path)


def load_pfm_as_image(path: str):
    if not PIL_OK:
        raise RuntimeError("Pillow is required")
    with open(path, "rb") as f:
        magic = f.readline().strip()
        if magic not in (b"PF", b"Pf"):
            raise ValueError("Not a PFM file")
        dims = f.readline().strip()
        while dims.startswith(b"#"):
            dims = f.readline().strip()
        width, height = [int(x) for x in dims.split()[:2]]
        scale_line = f.readline().strip()
        scale = float(scale_line)
        little = scale < 0
        channels = 3 if magic == b"PF" else 1
        count = width * height * channels
        raw = f.read(count * 4)
        if len(raw) < count * 4:
            raise ValueError("PFM file is truncated")
    vals = array.array("f")
    vals.frombytes(raw[:count * 4])
    need_swap = (sys.byteorder == "little" and not little) or (sys.byteorder == "big" and little)
    if need_swap:
        vals.byteswap()
    if not vals:
        raise ValueError("PFM has no pixels")
    # Normalize floats into 8-bit for preview.
    finite_sample = [v for v in vals[::max(1, len(vals)//200000)] if math.isfinite(v)]
    if not finite_sample:
        mn, mx = 0.0, 1.0
    else:
        mn, mx = min(finite_sample), max(finite_sample)
        if abs(mx - mn) < 1e-12:
            mx = mn + 1.0
    inv = 255.0 / (mx - mn)
    if channels == 1:
        out = bytearray(width * height)
        for i in range(width * height):
            v = vals[i]
            if not math.isfinite(v):
                v = mn
            out[i] = max(0, min(255, int((v - mn) * inv + 0.5)))
        im = Image.frombytes("L", (width, height), bytes(out))
    else:
        out = bytearray(width * height * 3)
        for i in range(width * height * 3):
            v = vals[i]
            if not math.isfinite(v):
                v = mn
            out[i] = max(0, min(255, int((v - mn) * inv + 0.5)))
        im = Image.frombytes("RGB", (width, height), bytes(out))
    return ImageOps.flip(im)


def open_image_any(path: str):
    if not PIL_OK:
        raise RuntimeError("Pillow is not installed. Install requirements with: py -3 -m pip install -r requirements.txt")
    ext = Path(path).suffix.lower()
    if ext == ".pfm":
        return load_pfm_as_image(path)
    im = Image.open(path)
    im.load()
    return im


def make_checkerboard(size, cell=16):
    w, h = size
    bg = Image.new("RGBA", size, (215, 215, 215, 255))
    draw = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2:
                draw.rectangle([x, y, min(x + cell - 1, w - 1), min(y + cell - 1, h - 1)], fill=(170, 170, 170, 255))
    return bg


def image_for_display(im):
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bg = make_checkerboard(rgba.size)
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    if im.mode not in ("RGB", "L"):
        try:
            return im.convert("RGB")
        except Exception:
            return im.copy()
    return im.copy()


def thumbnail_for_path(path: str, max_w: int, max_h: int):
    im = open_image_any(path)
    im = image_for_display(im)
    im.thumbnail((max_w, max_h), Image.LANCZOS)
    return im.copy()


class PreviewCache:
    def __init__(self, limit=PREVIEW_CACHE_LIMIT):
        self.limit = int(limit)
        self.lock = threading.RLock()
        self.cache = OrderedDict()

    def get(self, key):
        with self.lock:
            val = self.cache.get(key)
            if val is not None:
                self.cache.move_to_end(key)
            return val

    def put(self, key, val):
        with self.lock:
            self.cache[key] = val
            self.cache.move_to_end(key)
            while len(self.cache) > self.limit:
                self.cache.popitem(last=False)

    def clear(self):
        with self.lock:
            self.cache.clear()

    def __len__(self):
        with self.lock:
            return len(self.cache)


class TextureFolderViewerTab(tk.Frame):
    def __init__(self, master=None, app_state=None):
        super().__init__(master)
        self.app_state = app_state
        self.embedded = True
        self.window = self.winfo_toplevel()

        self.folder = ""
        self.records = []
        self.filtered = []
        self.item_to_index = {}
        self.scan_queue = queue.Queue()
        self.preview_queue = queue.Queue()
        self.stop_scan = threading.Event()
        self.stop_preload = threading.Event()
        self.scan_thread = None
        self.preload_thread = None
        self.current_path = None
        self.current_pil_image = None
        self._last_reveal_click_time = 0.0
        self._last_reveal_path = ""
        self.current_tk_image = None
        self.preview_cache = PreviewCache(PREVIEW_CACHE_LIMIT)
        self.search_after_id = None
        self.zoom_mode = tk.StringVar(value="fit")
        self.zoom_value = 1.0
        self.auto_preview = tk.BooleanVar(value=True)
        self.auto_preload = tk.BooleanVar(value=True)
        self.disk_cache_enabled = tk.BooleanVar(value=True)
        self.recursive = tk.BooleanVar(value=True)
        self.show_unsupported = tk.BooleanVar(value=True)
        # v0.8 list filters
        self.size_search_var = tk.StringVar()
        self.format_filter_var = tk.StringVar(value="All Formats")
        self.mip_filter_var = tk.StringVar(value="All Mips")
        self.status_filter_var = tk.StringVar(value="All Status")
        self.category_filter_var = tk.StringVar(value="All Categories")
        self.square_only_var = tk.BooleanVar(value=False)
        self.power2_only_var = tk.BooleanVar(value=False)
        self.common_suit_sizes_var = tk.BooleanVar(value=False)

        self._build_style()
        self._build_ui()
        self.after(80, self._drain_scan_queue)
        self.after(90, self._drain_preview_queue)
        if not self.embedded:
            self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self):
        self.configure(bg=DARK_BG)
        style = ttk.Style(self.window if self.embedded else self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Global dark ttk look.
        style.configure(".",
            background=DARK_BG,
            foreground=DARK_TEXT,
            fieldbackground=DARK_FIELD,
            bordercolor=DARK_BORDER,
            lightcolor=DARK_BORDER,
            darkcolor=DARK_BORDER,
            troughcolor=DARK_FIELD,
            selectbackground=DARK_SELECT,
            selectforeground="#FFFFFF",
            font=("Segoe UI", 9),
        )
        style.configure("TFrame", background=DARK_BG)
        style.configure("TLabelframe", background=DARK_BG, bordercolor=DARK_BORDER)
        style.configure("TLabelframe.Label", background=DARK_BG, foreground=DARK_TEXT)
        style.configure("TLabel", background=DARK_BG, foreground=DARK_TEXT)
        style.configure("Header.TLabel", background=DARK_BG, foreground=DARK_TEXT, font=("Segoe UI", 12, "bold"))
        style.configure("Small.TLabel", background=DARK_BG, foreground=DARK_MUTED, font=("Segoe UI", 9))
        style.configure("TButton", background=DARK_PANEL_2, foreground=DARK_TEXT, bordercolor=DARK_BORDER, padding=(8, 4))
        style.map("TButton", background=[("active", "#2C3440"), ("pressed", "#171B21")], foreground=[("disabled", "#777777")])
        style.configure("Accent.TButton", background=DARK_ACCENT, foreground="#FFFFFF", font=("Segoe UI", 9, "bold"), padding=(9, 4))
        style.map("Accent.TButton", background=[("active", "#46566B"), ("pressed", "#263247")], foreground=[("disabled", "#999999")])
        style.configure("TCheckbutton", background=DARK_BG, foreground=DARK_TEXT)
        style.map("TCheckbutton", background=[("active", DARK_BG)], foreground=[("disabled", "#777777")])
        style.configure("TRadiobutton", background=DARK_BG, foreground=DARK_TEXT)
        style.map("TRadiobutton", background=[("active", DARK_BG)])
        style.configure("TEntry", fieldbackground=DARK_FIELD, foreground=DARK_TEXT, insertcolor=DARK_TEXT, bordercolor=DARK_BORDER)
        style.map("TEntry",
            fieldbackground=[("disabled", DARK_FIELD), ("readonly", DARK_FIELD), ("focus", DARK_FIELD)],
            foreground=[("disabled", DARK_MUTED), ("readonly", DARK_TEXT), ("focus", DARK_TEXT)],
        )
        style.configure("TCombobox",
            fieldbackground=DARK_FIELD,
            background=DARK_FIELD,
            foreground=DARK_TEXT,
            selectbackground=DARK_FIELD,
            selectforeground=DARK_TEXT,
            insertcolor=DARK_TEXT,
            arrowcolor=DARK_TEXT,
            bordercolor=DARK_BORDER,
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", DARK_FIELD), ("disabled", DARK_FIELD), ("focus", DARK_FIELD)],
            background=[("readonly", DARK_FIELD), ("disabled", DARK_FIELD), ("active", DARK_PANEL_2)],
            foreground=[("readonly", DARK_TEXT), ("disabled", DARK_MUTED), ("focus", DARK_TEXT)],
            selectbackground=[("readonly", DARK_FIELD), ("focus", DARK_FIELD)],
            selectforeground=[("readonly", DARK_TEXT), ("focus", DARK_TEXT)],
        )
        try:
            self.option_add("*TCombobox*Listbox.background", DARK_FIELD)
            self.option_add("*TCombobox*Listbox.foreground", DARK_TEXT)
            self.option_add("*TCombobox*Listbox.selectBackground", DARK_SELECT)
            self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
            self.option_add("*Entry.background", DARK_FIELD)
            self.option_add("*Entry.foreground", DARK_TEXT)
            self.option_add("*Entry.insertBackground", DARK_TEXT)
        except Exception:
            pass
        style.configure("Treeview", background=DARK_FIELD, fieldbackground=DARK_FIELD, foreground=DARK_TEXT, rowheight=24, bordercolor=DARK_BORDER)
        style.configure("Treeview.Heading", background=DARK_PANEL_2, foreground=DARK_TEXT, bordercolor=DARK_BORDER, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", DARK_SELECT)], foreground=[("selected", "#FFFFFF")])
        style.configure("Horizontal.TScrollbar", background=DARK_PANEL_2, troughcolor=DARK_FIELD, bordercolor=DARK_BORDER, arrowcolor=DARK_TEXT)
        style.configure("Vertical.TScrollbar", background=DARK_PANEL_2, troughcolor=DARK_FIELD, bordercolor=DARK_BORDER, arrowcolor=DARK_TEXT)
        style.configure("TProgressbar", background=DARK_ACCENT, troughcolor=DARK_FIELD, bordercolor=DARK_BORDER)

    def _build_ui(self):
        if not self.embedded:
            self._build_menu()

        top = ttk.Frame(self, padding=(8, 6, 8, 4))
        top.pack(side=tk.TOP, fill=tk.X)

        title_frame = ttk.Frame(top)
        title_frame.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(title_frame, text=f"SM3 Texture Folder Previewer {APP_VERSION}", style="Header.TLabel").pack(side=tk.LEFT)

        controls = ttk.Frame(top)
        controls.pack(side=tk.TOP, fill=tk.X, pady=(6, 0))
        ttk.Button(controls, text="Choose Folder", style="Accent.TButton", command=self.choose_folder).pack(side=tk.LEFT)
        ttk.Button(controls, text="Rescan", command=self.rescan).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(controls, text="Stop", command=self.stop_current_work).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Checkbutton(controls, text="Recursive", variable=self.recursive).pack(side=tk.LEFT, padx=(14, 0))
        ttk.Checkbutton(controls, text="Auto Preview", variable=self.auto_preview).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(controls, text="Preload ALL Textures", variable=self.auto_preload).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(controls, text="Use Disk Cache", variable=self.disk_cache_enabled).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(controls, text="Show Unsupported", variable=self.show_unsupported, command=self.apply_filter).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(controls, text="Search:").pack(side=tk.LEFT, padx=(16, 4))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(controls, textvariable=self.search_var, width=34)
        self.search_entry.pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *_: self._debounce_filter())
        ttk.Button(controls, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(controls, text="Reset Filters", command=self.reset_filters).pack(side=tk.LEFT, padx=(5, 0))

        filters = ttk.Frame(top)
        filters.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        ttk.Label(filters, text="Size Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.size_search_entry = ttk.Entry(filters, textvariable=self.size_search_var, width=16)
        self.size_search_entry.pack(side=tk.LEFT)
        self.size_search_var.trace_add("write", lambda *_: self._debounce_filter())
        ttk.Button(filters, text="Clear Size", command=self.clear_size_search).pack(side=tk.LEFT, padx=(5, 10))

        self.format_combo = ttk.Combobox(filters, textvariable=self.format_filter_var, width=15, state="readonly", values=[
            "All Formats", "DDS", "DXT1 / BC1", "DXT3 / BC2", "DXT5 / BC3", "BGRA/RGBA", "RGB", "L8/R8/Gray", "Compressed DDS", "Uncompressed", "Other"
        ])
        self.format_combo.pack(side=tk.LEFT)
        self.format_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.mip_combo = ttk.Combobox(filters, textvariable=self.mip_filter_var, width=10, state="readonly", values=[
            "All Mips", "1", "7", "8", "10", "11", ">=8", ">=10", "No Mips/Unknown"
        ])
        self.mip_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.mip_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.status_combo = ttk.Combobox(filters, textvariable=self.status_filter_var, width=12, state="readonly", values=[
            "All Status", "OK Only", "Problem Only"
        ])
        self.status_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.status_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        self.category_combo = ttk.Combobox(filters, textvariable=self.category_filter_var, width=20, state="readonly", values=[
            "All Categories", "Large Body 1024+", "Medium 512", "Small 64/128", "Suit Common Sizes", "Wide/Lookup", "Non-Square", "Alpha-Capable", "Normal-Map Names", "Webbing/Alpha Names", "Spider/Emblem Names"
        ])
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        ttk.Checkbutton(filters, text="Square", variable=self.square_only_var, command=self.apply_filter).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(filters, text="Power2", variable=self.power2_only_var, command=self.apply_filter).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Checkbutton(filters, text="Common Suit Sizes", variable=self.common_suit_sizes_var, command=self.apply_filter).pack(side=tk.LEFT, padx=(5, 0))

        actions = ttk.Frame(top)
        actions.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))
        ttk.Button(actions, text="Preview Selected", command=self.preview_selected).pack(side=tk.LEFT)
        ttk.Button(actions, text="Large Preview", command=self.large_preview).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions, text="Open Externally", command=self.open_selected).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions, text="Reveal in Explorer", command=self.reveal_selected).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions, text="Export Contact Sheet", command=self.export_contact_sheet).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(actions, text="Clear Cache", command=self.clear_cache).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(actions, text=f"Supported: {EXT_LABELS}", style="Small.TLabel").pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value="Choose a folder to scan textures.")
        self.progress = ttk.Progressbar(top, mode="indeterminate", length=180)
        self.progress.pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT, pady=(4, 0))

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=6)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        columns = ("ext", "size", "dimensions", "format", "mips", "status", "folder")
        self.tree = ttk.Treeview(left, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Texture Name")
        self.tree.column("#0", width=300, stretch=True)
        for col, text, width in [
            ("ext", "Ext", 62),
            ("size", "Size", 84),
            ("dimensions", "Dimensions", 100),
            ("format", "Format", 170),
            ("mips", "Mips", 52),
            ("status", "Status", 150),
            ("folder", "Folder", 230),
        ]:
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=width, anchor=tk.W, stretch=(col in ("format", "status", "folder")))
        self.tree.heading("#0", command=lambda: self.sort_by("name"))

        ybar = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        xbar = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.large_preview())

        right_top = ttk.Frame(right)
        right_top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(right_top, text="Preview", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Radiobutton(right_top, text="Fit", variable=self.zoom_mode, value="fit", command=self.redraw_preview).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Radiobutton(right_top, text="100%", variable=self.zoom_mode, value="100", command=self.redraw_preview).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(right_top, text="-", width=3, command=lambda: self.adjust_zoom(0.8)).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Button(right_top, text="+", width=3, command=lambda: self.adjust_zoom(1.25)).pack(side=tk.LEFT, padx=(3, 0))
        ttk.Button(right_top, text="Reset", command=self.reset_zoom).pack(side=tk.LEFT, padx=(5, 0))

        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(5, 4))
        self.canvas = tk.Canvas(canvas_frame, bg=DARK_FIELD, highlightthickness=1, highlightbackground=DARK_BORDER)
        self.canvas_x = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas_y = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.canvas_x.set, yscrollcommand=self.canvas_y.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas_y.grid(row=0, column=1, sticky="ns")
        self.canvas_x.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self.canvas.bind("<Configure>", lambda e: self.redraw_preview())
        self.canvas.bind("<Control-MouseWheel>", self._ctrl_mousewheel)
        self.canvas.bind("<MouseWheel>", self._canvas_mousewheel)

        info_frame = ttk.LabelFrame(right, text="Texture Info")
        info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.info_text = tk.Text(info_frame, height=9, wrap="word", font=("Consolas", 9), bg=DARK_FIELD, fg=DARK_TEXT, insertbackground=DARK_TEXT, selectbackground=DARK_SELECT, relief="flat")
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scroll.set)
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._set_info("No texture selected yet.")

    def _build_menu(self):
        menubar = tk.Menu(self, bg=DARK_PANEL, fg=DARK_TEXT, activebackground=DARK_SELECT, activeforeground="#FFFFFF")
        file_menu = tk.Menu(menubar, tearoff=0, bg=DARK_PANEL, fg=DARK_TEXT, activebackground=DARK_SELECT, activeforeground="#FFFFFF")
        file_menu.add_command(label="Choose Folder", command=self.choose_folder)
        file_menu.add_command(label="Rescan", command=self.rescan)
        file_menu.add_separator()
        file_menu.add_command(label="Open Selected Externally", command=self.open_selected)
        file_menu.add_command(label="Reveal Selected in Explorer", command=self.reveal_selected)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0, bg=DARK_PANEL, fg=DARK_TEXT, activebackground=DARK_SELECT, activeforeground="#FFFFFF")
        tools_menu.add_command(label="Preview Selected", command=self.preview_selected)
        tools_menu.add_command(label="Large Preview", command=self.large_preview)
        tools_menu.add_command(label="Export Contact Sheet", command=self.export_contact_sheet)
        tools_menu.add_command(label="Clear Cache", command=self.clear_cache)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=DARK_PANEL, fg=DARK_TEXT, activebackground=DARK_SELECT, activeforeground="#FFFFFF")
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.window.config(menu=menubar)

    def show_about(self):
        messagebox.showinfo(
            "About",
            f"SM3 Texture Folder Previewer {APP_VERSION}\n\n"
            f"Supported: {EXT_LABELS}\n\n"
            "Viewer only. Does not edit or patch game packs."
        )

    def _set_info(self, text: str):
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, text)
        self.info_text.configure(state="disabled")

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Select SM3 texture image folder")
        if not folder:
            return
        self.folder = folder
        self.start_scan(folder)

    def rescan(self):
        if not self.folder:
            self.choose_folder()
            return
        self.start_scan(self.folder)

    def stop_current_work(self):
        self.stop_scan.set()
        self.stop_preload.set()
        self.status_var.set("Stopping current scan/preload...")

    def clear_search(self):
        self.search_var.set("")
        self.apply_filter()

    def clear_size_search(self):
        self.size_search_var.set("")
        self.apply_filter()

    def reset_filters(self):
        self.search_var.set("")
        self.size_search_var.set("")
        self.format_filter_var.set("All Formats")
        self.mip_filter_var.set("All Mips")
        self.status_filter_var.set("All Status")
        self.category_filter_var.set("All Categories")
        self.square_only_var.set(False)
        self.power2_only_var.set(False)
        self.common_suit_sizes_var.set(False)
        self.show_unsupported.set(True)
        self.apply_filter()

    @staticmethod
    def _is_power_of_two(n):
        try:
            n = int(n)
            return n > 0 and (n & (n - 1)) == 0
        except Exception:
            return False

    @staticmethod
    def _parse_int_safe(value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def _size_query_matches(self, width, height, query: str) -> bool:
        q = (query or "").strip().lower().replace(" ", "")
        if not q:
            return True
        w = self._parse_int_safe(width)
        h = self._parse_int_safe(height)
        if not w or not h:
            return False
        # Supports: 512, 512x512, 1024x, x512, >=512, <=128, >512, <256
        # Also supports comma/semicolon/pipe lists: 64,128,512x512
        parts = [p for p in q.replace(";", ",").replace("|", ",").split(",") if p]
        if not parts:
            parts = [q]
        for part in parts:
            try:
                if "x" in part:
                    a, b = part.split("x", 1)
                    ok_w = (not a) or (w == int(a))
                    ok_h = (not b) or (h == int(b))
                    if ok_w and ok_h:
                        return True
                    continue
                handled = False
                for op in (">=", "<=", ">", "<"):
                    if part.startswith(op):
                        handled = True
                        val = int(part[len(op):])
                        bigger = max(w, h)
                        if op == ">=" and bigger >= val:
                            return True
                        if op == "<=" and bigger <= val:
                            return True
                        if op == ">" and bigger > val:
                            return True
                        if op == "<" and bigger < val:
                            return True
                        break
                if handled:
                    continue
                val = int(part)
                if w == val or h == val:
                    return True
            except Exception:
                continue
        return False

    def _format_filter_matches(self, rec, meta) -> bool:
        filt = self.format_filter_var.get()
        if filt == "All Formats":
            return True
        ext = str(rec.get("ext", "")).upper()
        fmt = str(meta.get("format", "")).upper()
        if filt == "DDS":
            return ext == "DDS"
        if filt == "DXT1 / BC1":
            return "DXT1" in fmt or "BC1" in fmt
        if filt == "DXT3 / BC2":
            return "DXT3" in fmt or "BC2" in fmt
        if filt == "DXT5 / BC3":
            return "DXT5" in fmt or "BC3" in fmt
        if filt == "BGRA/RGBA":
            return "BGRA" in fmt or "B8G8R8A8" in fmt or "RGBA" in fmt or "R8G8B8A8" in fmt
        if filt == "RGB":
            return "RGB" in fmt and "RGBA" not in fmt and "BGRA" not in fmt
        if filt == "L8/R8/Gray":
            return "L8" in fmt or "R8" in fmt or "GRAY" in fmt or "GREY" in fmt or "LUMINANCE" in fmt
        if filt == "Compressed DDS":
            return any(x in fmt for x in ("DXT", "BC1", "BC2", "BC3", "BC4", "BC5", "BC6", "BC7"))
        if filt == "Uncompressed":
            return not any(x in fmt for x in ("DXT", "BC1", "BC2", "BC3", "BC4", "BC5", "BC6", "BC7"))
        if filt == "Other":
            return ext != "DDS" or fmt in ("DDS", "UNKNOWN") or not fmt
        return True

    def _mip_filter_matches(self, meta) -> bool:
        filt = self.mip_filter_var.get()
        if filt == "All Mips":
            return True
        raw = str(meta.get("mips", "")).strip()
        try:
            mips = int(raw)
        except Exception:
            mips = 0
        if filt == "No Mips/Unknown":
            return mips <= 1 or raw in ("", "?", "0")
        if filt.startswith(">="):
            try:
                return mips >= int(filt[2:])
            except Exception:
                return True
        try:
            return mips == int(filt)
        except Exception:
            return True

    def _category_filter_matches(self, rec, meta) -> bool:
        cat = self.category_filter_var.get()
        if cat == "All Categories":
            return True
        name = str(rec.get("name", "")).lower()
        fmt = str(meta.get("format", "")).upper()
        w = self._parse_int_safe(meta.get("width"))
        h = self._parse_int_safe(meta.get("height"))
        bigger = max(w, h)
        smaller = min(w, h) if w and h else 0
        if cat == "Large Body 1024+":
            return w >= 1024 or h >= 1024
        if cat == "Medium 512":
            return w == 512 or h == 512
        if cat == "Small 64/128":
            return bigger in (64, 128) or (w in (64, 128) or h in (64, 128))
        if cat == "Suit Common Sizes":
            return (w, h) in {(1024,1024),(512,512),(256,256),(128,128),(64,64),(2,256),(256,2),(4,4),(8,8),(16,16),(32,32)}
        if cat == "Wide/Lookup":
            return bool(w and h and w != h and (w <= 16 or h <= 16 or smaller <= 4))
        if cat == "Non-Square":
            return bool(w and h and w != h)
        if cat == "Alpha-Capable":
            return "DXT5" in fmt or "BC3" in fmt or "DXT3" in fmt or "BC2" in fmt or "RGBA" in fmt or "BGRA" in fmt or "A8" in fmt
        if cat == "Normal-Map Names":
            return any(x in name for x in ("_nor", "normal", "norm", "nrm"))
        if cat == "Webbing/Alpha Names":
            return any(x in name for x in ("web", "webbing", "alpha"))
        if cat == "Spider/Emblem Names":
            return any(x in name for x in ("spider", "emblem", "logo"))
        return True

    def clear_cache(self):
        self.preview_cache.clear()
        deleted = 0
        if self.folder:
            cache_dir = os.path.join(self.folder, THUMB_CACHE_DIRNAME)
            if os.path.isdir(cache_dir):
                try:
                    for fn in os.listdir(cache_dir):
                        if fn.lower().endswith(".png"):
                            try:
                                os.remove(os.path.join(cache_dir, fn))
                                deleted += 1
                            except Exception:
                                pass
                except Exception:
                    pass
        self.status_var.set(f"Preview cache cleared. Disk thumbnails deleted: {deleted}.")

    def start_scan(self, folder: str):
        self.stop_current_work()
        time.sleep(0.02)
        self.stop_scan = threading.Event()
        self.stop_preload = threading.Event()
        self.preview_cache.clear()
        self.records.clear()
        self.filtered.clear()
        self.item_to_index.clear()
        self.tree.delete(*self.tree.get_children())
        self.current_path = None
        self.current_pil_image = None
        self.current_tk_image = None
        self.canvas.delete("all")
        self._set_info("Scanning folder...\n\n" + folder + "\n\nv0.8 will preload supported textures into RAM after scan, with disk cache and size/format/mip filters ready.")
        self.progress.start(12)
        self.status_var.set(f"Scanning {folder} ...")
        self.scan_thread = threading.Thread(target=self._scan_worker, args=(folder,), daemon=True)
        self.scan_thread.start()

    def _load_folder_cache(self, folder: str) -> dict:
        cache_path = os.path.join(folder, CACHE_FILENAME)
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") == CACHE_VERSION:
                return data.get("items", {})
        except Exception:
            pass
        return {}

    def _save_folder_cache(self, folder: str, cache_items: dict):
        cache_path = os.path.join(folder, CACHE_FILENAME)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"version": CACHE_VERSION, "items": cache_items}, f, indent=2)
        except Exception:
            pass

    def _scan_worker(self, folder: str):
        started = time.time()
        total = 0
        cache_items = self._load_folder_cache(folder)
        new_cache = {}
        try:
            walker = os.walk(folder) if self.recursive.get() else [(folder, [], os.listdir(folder))]
            for root, dirs, files in walker:
                if self.stop_scan.is_set():
                    break
                # Do not scan this tool's own thumbnail cache back into the texture list.
                try:
                    dirs[:] = [d for d in dirs if not d.startswith(".sm3_wos_texture_viewer_thumbs") and d != "__pycache__"]
                except Exception:
                    pass
                files = sorted(files, key=lambda x: x.lower())
                for filename in files:
                    if self.stop_scan.is_set():
                        break
                    ext = Path(filename).suffix.lower()
                    if ext not in SUPPORTED_EXTS:
                        continue
                    path = os.path.join(root, filename)
                    try:
                        st = os.stat(path)
                    except Exception:
                        continue
                    cache_key = os.path.relpath(path, folder).replace("\\", "/")
                    cached = cache_items.get(cache_key)
                    if cached and cached.get("mtime") == st.st_mtime and cached.get("size_bytes") == st.st_size:
                        meta = cached.get("meta", {})
                    else:
                        meta = parse_image_meta(path)
                    rec = {
                        "path": path,
                        "name": filename,
                        "ext": ext.upper().lstrip("."),
                        "size_bytes": st.st_size,
                        "size": fmt_size(st.st_size),
                        "mtime": st.st_mtime,
                        "folder": safe_rel(root, folder),
                        "meta": meta,
                    }
                    new_cache[cache_key] = {"mtime": st.st_mtime, "size_bytes": st.st_size, "meta": meta}
                    total += 1
                    self.scan_queue.put(("record", rec))
                    if total % 100 == 0:
                        self.scan_queue.put(("status", f"Scanning... {total} supported image files found"))
            self._save_folder_cache(folder, new_cache)
            if self.stop_scan.is_set():
                self.scan_queue.put(("done", f"Scan stopped. Loaded {total} files."))
            else:
                self.scan_queue.put(("done", f"Scan complete. Loaded {total} files in {time.time() - started:.1f}s."))
        except Exception as exc:
            self.scan_queue.put(("error", f"Scan error: {exc}\n{traceback.format_exc()}"))

    def _drain_scan_queue(self):
        count = 0
        should_refilter = False
        try:
            while count < QUEUE_DRAIN_LIMIT:
                msg, payload = self.scan_queue.get_nowait()
                count += 1
                if msg == "record":
                    self.records.append(payload)
                    should_refilter = True
                elif msg == "status":
                    self.status_var.set(payload)
                elif msg == "done":
                    self.progress.stop()
                    self.status_var.set(payload)
                    self.apply_filter()
                    if self.auto_preload.get() and self.records:
                        self.start_preload()
                elif msg == "error":
                    self.progress.stop()
                    self.status_var.set("Scan error.")
                    messagebox.showerror("Scan Error", payload)
        except queue.Empty:
            pass
        if should_refilter:
            # During active scan, update in chunks without expensive full rebuild every single file.
            if len(self.records) % TREE_BATCH_SIZE < count:
                self.apply_filter()
        self.after(80, self._drain_scan_queue)

    def _debounce_filter(self):
        if self.search_after_id is not None:
            try:
                self.after_cancel(self.search_after_id)
            except Exception:
                pass
        self.search_after_id = self.after(SEARCH_DEBOUNCE_MS, self.apply_filter)

    def apply_filter(self):
        q = self.search_var.get().strip().lower()
        size_q = self.size_search_var.get().strip().lower()
        show_bad = self.show_unsupported.get()
        status_filter = self.status_filter_var.get()
        rows = []
        for idx, rec in enumerate(self.records):
            meta = rec.get("meta", {})
            status = str(meta.get("status", ""))
            width = self._parse_int_safe(meta.get("width"))
            height = self._parse_int_safe(meta.get("height"))

            if not show_bad and status != "OK":
                continue
            if status_filter == "OK Only" and status != "OK":
                continue
            if status_filter == "Problem Only" and status == "OK":
                continue

            hay = " ".join([
                rec.get("name", ""), rec.get("ext", ""), rec.get("folder", ""),
                str(meta.get("format", "")), str(meta.get("width", "")), str(meta.get("height", "")),
                f"{meta.get('width','?')}x{meta.get('height','?')}",
                str(meta.get("mips", "")), status, str(meta.get("extra", "")),
            ]).lower()
            if q and q not in hay:
                continue
            if not self._size_query_matches(width, height, size_q):
                continue
            if self.square_only_var.get() and (not width or not height or width != height):
                continue
            if self.power2_only_var.get() and not (self._is_power_of_two(width) and self._is_power_of_two(height)):
                continue
            if self.common_suit_sizes_var.get() and (width, height) not in {(1024,1024),(512,512),(256,256),(128,128),(64,64),(2,256),(256,2),(4,4),(8,8),(16,16),(32,32)}:
                continue
            if not self._format_filter_matches(rec, meta):
                continue
            if not self._mip_filter_matches(meta):
                continue
            if not self._category_filter_matches(rec, meta):
                continue
            rows.append((idx, rec))
        self.filtered = rows
        self._rebuild_tree()
        active = []
        if q:
            active.append(f"search='{q}'")
        if size_q:
            active.append(f"size='{size_q}'")
        for label, val, default in [
            ("fmt", self.format_filter_var.get(), "All Formats"),
            ("mips", self.mip_filter_var.get(), "All Mips"),
            ("status", self.status_filter_var.get(), "All Status"),
            ("cat", self.category_filter_var.get(), "All Categories"),
        ]:
            if val != default:
                active.append(f"{label}={val}")
        if self.square_only_var.get():
            active.append("square")
        if self.power2_only_var.get():
            active.append("power2")
        if self.common_suit_sizes_var.get():
            active.append("common-suit")
        suffix = (" | Filters: " + ", ".join(active)) if active else ""
        self.status_var.set(f"Showing {len(self.filtered)} / {len(self.records)} files. RAM cache ready: {len(self.preview_cache)} previews.{suffix}")

    def _rebuild_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.item_to_index.clear()
        for idx, rec in self.filtered:
            meta = rec.get("meta", {})
            dimensions = f"{meta.get('width','?')}x{meta.get('height','?')}"
            item = self.tree.insert(
                "", tk.END,
                text=rec.get("name", ""),
                values=(
                    rec.get("ext", ""),
                    rec.get("size", ""),
                    dimensions,
                    meta.get("format", ""),
                    meta.get("mips", ""),
                    meta.get("status", ""),
                    rec.get("folder", ""),
                )
            )
            self.item_to_index[item] = idx

    def sort_by(self, col: str):
        reverse = getattr(self, "_sort_reverse", False)
        self._sort_reverse = not reverse
        def key(pair):
            idx, rec = pair
            meta = rec.get("meta", {})
            if col == "name":
                return rec.get("name", "").lower()
            if col == "size":
                return rec.get("size_bytes", 0)
            if col == "dimensions":
                try:
                    return int(meta.get("width", 0)) * int(meta.get("height", 0))
                except Exception:
                    return 0
            if col == "format":
                return str(meta.get("format", "")).lower()
            if col == "mips":
                try:
                    return int(meta.get("mips", 0))
                except Exception:
                    return 0
            return str(rec.get(col, meta.get(col, ""))).lower()
        self.filtered.sort(key=key, reverse=reverse)
        self._rebuild_tree()

    def selected_record(self):
        # v0.9: prefer the focused row, not just the first selected row.
        # This matters when multiple rows are selected or filters/sorts changed;
        # Reveal in Explorer should jump to the image the user just clicked.
        sel = list(self.tree.selection())
        focus = self.tree.focus()
        item = None
        if focus and (not sel or focus in sel):
            item = focus
        elif sel:
            # Use the last selected row as a better "current click" fallback than
            # sel[0], which can point at an older multi-selection row.
            item = sel[-1]
        if not item:
            return None
        idx = self.item_to_index.get(item)
        if idx is None or idx < 0 or idx >= len(self.records):
            return None
        return self.records[idx]

    def _on_tree_select(self, event=None):
        rec = self.selected_record()
        if rec:
            self.show_info(rec)
            if self.auto_preview.get():
                self.preview_record(rec)

    def show_info(self, rec):
        meta = rec.get("meta", {})
        text = []
        text.append(f"Name: {rec.get('name','')}")
        text.append(f"Path: {rec.get('path','')}")
        text.append(f"Folder: {rec.get('folder','')}")
        text.append(f"Extension: {rec.get('ext','')}")
        text.append(f"Size: {rec.get('size','')} ({rec.get('size_bytes',0)} bytes)")
        text.append(f"Dimensions: {meta.get('width','?')} x {meta.get('height','?')}")
        text.append(f"Format: {meta.get('format','?')}")
        text.append(f"Mips: {meta.get('mips','?')}")
        text.append(f"Status: {meta.get('status','?')}")
        if meta.get("extra"):
            text.append(f"Extra: {meta.get('extra')}")
        text.append("")
        text.append("SM3 note: use this viewer to inspect exported texture files only. Patch game packs with your texture swapper/tool after confirming format/size/mips.")
        self._set_info("\n".join(text))

    def preview_selected(self):
        rec = self.selected_record()
        if not rec:
            messagebox.showwarning("No Selection", "Select a texture first.")
            return
        self.preview_record(rec, force=True)

    def preview_record(self, rec, force=False):
        path = rec.get("path")
        if not path:
            return
        self.current_path = path
        cached = self.preview_cache.get(path)
        if cached is not None:
            self.current_pil_image = cached.copy()
            self.redraw_preview()
            self.status_var.set(f"Preview from RAM cache: {os.path.basename(path)}")
            return
        disk_cached = self._load_preview_from_disk_cache(path)
        if disk_cached is not None:
            self.preview_cache.put(path, disk_cached.copy())
            self.current_pil_image = disk_cached.copy()
            self.redraw_preview()
            self.status_var.set(f"Preview from disk cache: {os.path.basename(path)}")
            return
        self.canvas.delete("all")
        self.canvas.create_text(20, 20, anchor="nw", fill=DARK_TEXT, text="Loading preview...")
        self.status_var.set(f"Loading preview: {os.path.basename(path)}")
        threading.Thread(target=self._preview_worker, args=(path,), daemon=True).start()

    def _preview_worker(self, path: str):
        try:
            im, source = self._get_or_make_preview(path)
            self.preview_queue.put(("preview", path, im))
            self.scan_queue.put(("status", f"Preview ready from {source}: {os.path.basename(path)}"))
        except Exception as exc:
            self.preview_queue.put(("preview_error", path, str(exc)))

    def _drain_preview_queue(self):
        count = 0
        try:
            while count < 40:
                msg, path, payload = self.preview_queue.get_nowait()
                count += 1
                if msg == "preview":
                    if path == self.current_path:
                        self.current_pil_image = payload.copy()
                        self.redraw_preview()
                        self.status_var.set(f"Preview ready: {os.path.basename(path)}")
                elif msg == "preview_error":
                    if path == self.current_path:
                        self.current_pil_image = None
                        self.current_tk_image = None
                        self.canvas.delete("all")
                        self.canvas.create_text(
                            20, 20, anchor="nw", fill=DARK_ERROR, width=max(300, self.canvas.winfo_width()-40),
                            text=f"Preview failed for:\n{os.path.basename(path)}\n\n{payload}\n\nDDS header metadata may still be valid even when Pillow cannot decode the image."
                        )
                        self.status_var.set("Preview failed. See panel.")
        except queue.Empty:
            pass
        self.after(90, self._drain_preview_queue)

    def redraw_preview(self):
        if self.current_pil_image is None:
            return
        if not PIL_OK:
            return
        try:
            im = self.current_pil_image.copy()
            cw = max(1, self.canvas.winfo_width() - 4)
            ch = max(1, self.canvas.winfo_height() - 4)
            if self.zoom_mode.get() == "fit":
                scale = min(cw / max(1, im.width), ch / max(1, im.height), 1.0)
            elif self.zoom_mode.get() == "100":
                scale = 1.0
            else:
                scale = self.zoom_value
            if self.zoom_mode.get() not in ("fit", "100"):
                scale = self.zoom_value
            new_w = max(1, int(im.width * scale))
            new_h = max(1, int(im.height * scale))
            if (new_w, new_h) != im.size:
                im = im.resize((new_w, new_h), Image.NEAREST if scale >= 1.0 else Image.LANCZOS)
            self.current_tk_image = ImageTk.PhotoImage(im)
            self.canvas.delete("all")
            x = max(0, (cw - new_w) // 2)
            y = max(0, (ch - new_h) // 2)
            self.canvas.create_image(x, y, anchor="nw", image=self.current_tk_image)
            self.canvas.configure(scrollregion=(0, 0, max(cw, new_w), max(ch, new_h)))
        except Exception as exc:
            self.canvas.delete("all")
            self.canvas.create_text(20, 20, anchor="nw", fill=DARK_ERROR, text=f"Redraw error: {exc}")

    def adjust_zoom(self, factor: float):
        if self.zoom_mode.get() in ("fit", "100"):
            self.zoom_value = 1.0 if self.zoom_mode.get() == "100" else 0.75
        self.zoom_mode.set("custom")
        self.zoom_value = max(0.05, min(16.0, self.zoom_value * factor))
        self.redraw_preview()

    def reset_zoom(self):
        self.zoom_mode.set("fit")
        self.zoom_value = 1.0
        self.redraw_preview()

    def _ctrl_mousewheel(self, event):
        self.adjust_zoom(1.1 if event.delta > 0 else 0.9)
        return "break"

    def _canvas_mousewheel(self, event):
        self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        return "break"

    def _thumb_cache_path(self, path: str) -> str:
        """Persistent thumbnail path for the current folder and file state."""
        folder = self.folder or os.path.dirname(path)
        try:
            st = os.stat(path)
            rel = os.path.relpath(path, folder).replace("\\", "/")
            raw = f"{rel}|{st.st_size}|{getattr(st, 'st_mtime_ns', int(st.st_mtime * 1e9))}|{PRELOAD_THUMB_MAX_W}x{PRELOAD_THUMB_MAX_H}"
        except Exception:
            raw = f"{path}|{PRELOAD_THUMB_MAX_W}x{PRELOAD_THUMB_MAX_H}"
        name = hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest() + ".png"
        return os.path.join(folder, THUMB_CACHE_DIRNAME, name)

    def _load_preview_from_disk_cache(self, path: str):
        if not PIL_OK or not self.disk_cache_enabled.get():
            return None
        try:
            cp = self._thumb_cache_path(path)
            if not os.path.isfile(cp):
                return None
            with Image.open(cp) as im:
                im.load()
                return im.convert("RGB").copy()
        except Exception:
            return None

    def _save_preview_to_disk_cache(self, path: str, im):
        if not PIL_OK or not self.disk_cache_enabled.get():
            return
        try:
            cp = self._thumb_cache_path(path)
            os.makedirs(os.path.dirname(cp), exist_ok=True)
            im.convert("RGB").save(cp, "PNG", optimize=True)
        except Exception:
            pass

    def _get_or_make_preview(self, path: str):
        """Load preview from RAM cache, disk thumbnail cache, or build it once."""
        im = self.preview_cache.get(path)
        if im is not None:
            return im.copy(), "ram"
        im = self._load_preview_from_disk_cache(path)
        if im is not None:
            self.preview_cache.put(path, im.copy())
            return im.copy(), "disk"
        im = thumbnail_for_path(path, PRELOAD_THUMB_MAX_W, PRELOAD_THUMB_MAX_H)
        self.preview_cache.put(path, im.copy())
        self._save_preview_to_disk_cache(path, im)
        return im.copy(), "built"

    def start_preload(self):
        self.stop_preload.set()
        time.sleep(0.01)
        self.stop_preload = threading.Event()
        paths = [rec["path"] for rec in self.records]
        self.preload_thread = threading.Thread(target=self._preload_worker, args=(paths,), daemon=True)
        self.preload_thread.start()

    def _preload_worker(self, paths):
        loaded = 0
        failed = 0
        disk_hits = 0
        built = 0
        ram_hits = 0
        total = len(paths)
        self.scan_queue.put(("status", f"Preloading ALL textures into RAM cache... 0/{total}"))
        for i, path in enumerate(paths, 1):
            if self.stop_preload.is_set():
                self.scan_queue.put(("status", f"Preload stopped. RAM cache has {len(self.preview_cache)} previews."))
                return
            try:
                _, source = self._get_or_make_preview(path)
                loaded += 1
                if source == "disk":
                    disk_hits += 1
                elif source == "built":
                    built += 1
                else:
                    ram_hits += 1
            except Exception:
                failed += 1
            if i % 10 == 0 or i == total:
                self.scan_queue.put(("status", f"Preloading ALL textures... {i}/{total} ready={loaded} disk_cache={disk_hits} built={built} failed={failed} RAM={len(self.preview_cache)}"))
        self.scan_queue.put(("status", f"Preload complete. All possible textures are ready in RAM. Ready={loaded}/{total}, disk_cache={disk_hits}, built={built}, failed={failed}."))

    def large_preview(self):
        rec = self.selected_record()
        if not rec:
            messagebox.showwarning("No Selection", "Select a texture first.")
            return
        path = rec.get("path")
        try:
            # Large preview uses full image if possible, not the downscaled cache.
            im = image_for_display(open_image_any(path))
        except Exception as exc:
            messagebox.showerror("Large Preview Failed", f"Could not load full preview:\n{path}\n\n{exc}")
            return
        win = tk.Toplevel(self)
        win.title(f"Large Preview - {os.path.basename(path)}")
        win.geometry("1100x800")
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(frame, bg=DARK_FIELD, highlightthickness=1, highlightbackground=DARK_BORDER)
        xbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        ybar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        info = ttk.Label(win, text=f"{os.path.basename(path)}  |  {im.width}x{im.height}  |  Mouse wheel scroll, Ctrl+wheel not used here")
        info.pack(side=tk.BOTTOM, fill=tk.X)
        tk_img = ImageTk.PhotoImage(im)
        canvas._img_ref = tk_img
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas.configure(scrollregion=(0, 0, im.width, im.height))
        canvas.bind("<MouseWheel>", lambda e: (canvas.yview_scroll(-1 * int(e.delta / 120), "units"), "break"))

    def open_selected(self):
        rec = self.selected_record()
        if not rec:
            messagebox.showwarning("No Selection", "Select a texture first.")
            return
        path = rec.get("path")
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                webbrowser.open(Path(path).resolve().as_uri())
        except Exception as exc:
            messagebox.showerror("Open Failed", str(exc))

    def reveal_selected(self):
        rec = self.selected_record()
        if not rec:
            messagebox.showwarning("No Selection", "Select a texture first.")
            return
        path = rec.get("path")

        # v0.9: keep reveal responsive while still blocking accidental rapid
        # duplicate clicks. The block is short so a second intentional click can
        # still retry the Explorer jump.
        now = time.time()
        if path == self._last_reveal_path and (now - self._last_reveal_click_time) < 0.20:
            self.status_var.set("Reveal ignored: duplicate click blocked.")
            return
        self._last_reveal_path = path
        self._last_reveal_click_time = now

        try:
            msg = reveal_path_in_folder(path)
            self.status_var.set(msg)
        except Exception as exc:
            messagebox.showerror("Reveal Failed", str(exc))

    def export_contact_sheet(self):
        if not PIL_OK:
            messagebox.showerror("Missing Pillow", "Pillow is required. Install requirements with: py -3 -m pip install -r requirements.txt")
            return
        if not self.filtered:
            messagebox.showwarning("No Files", "No visible textures to export.")
            return
        out = filedialog.asksaveasfilename(
            title="Save contact sheet PNG",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            initialfile="SM3_TEXTURE_CONTACT_SHEET_TSGAMING264.png"
        )
        if not out:
            return
        pairs = self.filtered[:CONTACT_MAX_ITEMS]
        cols = 5
        cell_w = CONTACT_THUMB_W + 30
        cell_h = CONTACT_THUMB_H + 60
        rows = math.ceil(len(pairs) / cols)
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (25, 28, 33))
        draw = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            font = None
        for n, (idx, rec) in enumerate(pairs):
            x = (n % cols) * cell_w + 15
            y = (n // cols) * cell_h + 10
            path = rec["path"]
            try:
                im = self.preview_cache.get(path)
                if im is None:
                    im, _src = self._get_or_make_preview(path)
                else:
                    im = im.copy()
                im.thumbnail((CONTACT_THUMB_W, CONTACT_THUMB_H), Image.LANCZOS)
                bx = x + (CONTACT_THUMB_W - im.width) // 2
                by = y + (CONTACT_THUMB_H - im.height) // 2
                sheet.paste(im.convert("RGB"), (bx, by))
            except Exception:
                draw.rectangle([x, y, x + CONTACT_THUMB_W, y + CONTACT_THUMB_H], outline=(90, 96, 108), fill=(40, 45, 52))
                draw.text((x + 6, y + 6), "No preview", fill=(230, 230, 230), font=font)
            name = rec.get("name", "")
            if len(name) > 32:
                name = name[:29] + "..."
            draw.text((x, y + CONTACT_THUMB_H + 6), name, fill=(232, 235, 240), font=font)
            meta = rec.get("meta", {})
            draw.text((x, y + CONTACT_THUMB_H + 22), f"{meta.get('width','?')}x{meta.get('height','?')} {rec.get('ext','')}", fill=(170, 178, 190), font=font)
            fmt = str(meta.get("format", ""))
            if len(fmt) > 30:
                fmt = fmt[:27] + "..."
            draw.text((x, y + CONTACT_THUMB_H + 38), fmt, fill=(170, 178, 190), font=font)
        try:
            sheet.save(out)
            messagebox.showinfo("Contact Sheet Saved", f"Saved:\n{out}\n\nItems: {len(pairs)}")
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def _on_close(self):
        self.stop_current_work()
        if self.embedded:
            self.destroy()
        else:
            self.window.destroy()

