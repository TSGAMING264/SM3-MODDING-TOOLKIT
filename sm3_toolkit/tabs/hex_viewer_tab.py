from __future__ import annotations

from pathlib import Path
import html
import io
import json
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
import re
import threading
import tempfile
import zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from html.parser import HTMLParser
import webbrowser

from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path


SMART_TEXT_WIDGET_LIMIT = 1_200_000
BIG_TEXT_AUTO_SIZE = 2_000_000
TEXT_MODE_EXTS = {
    ".txt", ".log", ".csv", ".json", ".jsonl", ".c", ".cpp", ".h", ".hpp",
    ".html", ".htm", ".xml", ".map", ".lst", ".md", ".ii", ".ini", ".cfg", ".conf",
    ".docx", ".odt", ".rtf", ".ct", ".yaml", ".yml", ".toml",
    ".lua", ".py", ".bat", ".cmd", ".ps1", ".zip"
}
TEXT_FILE_EXTS = TEXT_MODE_EXTS - {".zip", ".docx", ".odt"}


class _HTMLTextParser(HTMLParser):
    """Small text extractor adapted from the user's Ghidra Export Explorer helper."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("script", "style"):
            self.skip = True
        if tag in ("br", "tr", "p", "div", "li", "pre", "h1", "h2", "h3", "h4"):
            self._nl()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style"):
            self.skip = False
        if tag in ("tr", "p", "div", "li", "pre", "h1", "h2", "h3", "h4"):
            self._nl()

    def handle_data(self, data):
        if not self.skip and data:
            self.out.append(data)

    def _nl(self):
        if not self.out or not str(self.out[-1]).endswith("\n"):
            self.out.append("\n")

    def get_text(self):
        text = html.unescape("".join(self.out)).replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text


def _decode_text_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("latin-1", "replace")


def _html_to_text(raw_html: str) -> str:
    parser = _HTMLTextParser()
    try:
        parser.feed(raw_html)
        return parser.get_text()
    except Exception:
        text = re.sub(r"<(script|style).*?</\1>", "", raw_html, flags=re.I | re.S)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"</(div|p|tr|li|pre|h\d)>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        return html.unescape(text).replace("\xa0", " ")




def _pretty_json_text(raw_text: str) -> str:
    """Pretty-print JSON/JSONL when practical; fall back to original text."""
    stripped = raw_text.strip()
    if not stripped:
        return raw_text
    try:
        obj = json.loads(stripped)
        return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    except Exception:
        pass
    # JSONL: pretty-print each object while keeping record boundaries.
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if lines:
        out = []
        try:
            for idx, line in enumerate(lines, 1):
                obj = json.loads(line)
                out.append(f"--- JSONL RECORD {idx} ---")
                out.append(json.dumps(obj, indent=2, ensure_ascii=False))
            return "\n".join(out) + "\n"
        except Exception:
            pass
    return raw_text


def _pretty_xml_text(raw_text: str) -> str:
    """Pretty-print XML safely with stdlib; fall back to original text."""
    stripped = raw_text.strip()
    if not stripped:
        return raw_text
    try:
        dom = minidom.parseString(stripped.encode("utf-8", "replace"))
        pretty = dom.toprettyxml(indent="  ")
        pretty = "\n".join(line for line in pretty.splitlines() if line.strip())
        return pretty + "\n"
    except Exception:
        return raw_text


def _rtf_extract_text(raw: bytes) -> str:
    """Small dependency-free RTF text extractor for Text Mode.

    It preserves common paragraph/line/tab/unicode escapes and ignores destination
    groups such as font/color tables, pictures, objects and metadata. This is a
    readable-text view, not a Word-compatible RTF renderer.
    """
    data = raw.decode("latin-1", "replace")
    # Destinations whose content is formatting/binary metadata rather than readable body text.
    destinations = {
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header", "footer",
        "generator", "filetbl", "listtable", "listoverridetable", "rsidtbl", "xmlnstbl",
        "themedata", "datastore", "colorschememapping"
    }
    out = []
    stack = []
    skip = False
    uc_skip = 1
    i = 0
    pending_skip_chars = 0
    while i < len(data):
        ch = data[i]
        if ch == "{":
            stack.append((skip, uc_skip))
            i += 1
            continue
        if ch == "}":
            if stack:
                skip, uc_skip = stack.pop()
            i += 1
            continue
        if ch != "\\":
            if not skip:
                if pending_skip_chars > 0:
                    pending_skip_chars -= 1
                else:
                    out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(data):
            break
        nxt = data[i]
        if nxt in "\\{}":
            if not skip:
                if pending_skip_chars > 0:
                    pending_skip_chars -= 1
                else:
                    out.append(nxt)
            i += 1
            continue
        if nxt == "'" and i + 2 < len(data):
            try:
                decoded = bytes([int(data[i+1:i+3], 16)]).decode("cp1252", "replace")
            except Exception:
                decoded = ""
            if not skip:
                if pending_skip_chars > 0:
                    pending_skip_chars -= 1
                else:
                    out.append(decoded)
            i += 3
            continue
        if nxt == "*":
            skip = True
            i += 1
            continue
        # Control symbol.
        if not nxt.isalpha():
            if not skip:
                if nxt == "~": out.append(" ")
                elif nxt == "_": out.append("-")
                elif nxt == "-": out.append("\u00ad")
            i += 1
            continue
        start = i
        while i < len(data) and data[i].isalpha():
            i += 1
        word = data[start:i].lower()
        sign = 1
        if i < len(data) and data[i] == "-":
            sign = -1; i += 1
        num_start = i
        while i < len(data) and data[i].isdigit():
            i += 1
        arg = None
        if i > num_start:
            try: arg = sign * int(data[num_start:i])
            except Exception: arg = None
        if i < len(data) and data[i] == " ":
            i += 1
        if word in destinations:
            skip = True
            continue
        if word == "uc" and arg is not None:
            uc_skip = max(0, arg)
            continue
        if skip:
            continue
        if word in ("par", "line"):
            out.append("\n")
        elif word == "tab":
            out.append("\t")
        elif word == "emdash":
            out.append("—")
        elif word == "endash":
            out.append("–")
        elif word == "bullet":
            out.append("•")
        elif word == "lquote":
            out.append("‘")
        elif word == "rquote":
            out.append("’")
        elif word == "ldblquote":
            out.append("“")
        elif word == "rdblquote":
            out.append("”")
        elif word == "u" and arg is not None:
            codepoint = arg if arg >= 0 else 65536 + arg
            try: out.append(chr(codepoint))
            except Exception: pass
            pending_skip_chars = uc_skip
    text = "".join(out).replace("\r", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


_ODT_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_ODT_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_ODT_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_ODT_META_NS = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
_ODT_DC_NS = "http://purl.org/dc/elements/1.1/"


def _odt_node_text(node) -> str:
    parts = []
    if node.text:
        parts.append(node.text)
    for child in list(node):
        local = child.tag.split("}")[-1]
        if local == "tab":
            parts.append("\t")
        elif local == "line-break":
            parts.append("\n")
        elif local == "s":
            count = 1
            for key, value in child.attrib.items():
                if key.endswith("}c") or key == "c":
                    try: count = max(1, int(value))
                    except Exception: pass
            parts.append(" " * count)
        parts.append(_odt_node_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def _odt_text_mode_block(source, display_name: str = "document.odt") -> str:
    holder = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    with zipfile.ZipFile(holder) as z:
        try:
            root = ET.fromstring(z.read("content.xml"))
        except KeyError as exc:
            raise ValueError("ODT is missing content.xml") from exc
        lines = []
        paragraph_count = 0
        heading_count = 0
        table_count = 0
        row_count = 0
        for elem in root.iter():
            local = elem.tag.split("}")[-1]
            if local == "h":
                heading_count += 1
                text = _odt_node_text(elem).strip()
                if text:
                    level = 1
                    for k,v in elem.attrib.items():
                        if k.endswith("}outline-level"):
                            try: level = max(1,min(6,int(v)))
                            except Exception: pass
                    lines.extend(["#"*level + " " + text, ""])
            elif local == "p":
                # Avoid duplicating paragraphs nested inside table cells; tables are rendered separately below.
                parentish = False
                text = _odt_node_text(elem).strip()
                if text:
                    paragraph_count += 1
                    lines.append(text)
            elif local == "table":
                table_count += 1
                lines.append("")
                for row in [x for x in elem.iter() if x.tag.split("}")[-1] == "table-row"]:
                    cells=[]
                    for cell in [x for x in list(row) if x.tag.split("}")[-1] in ("table-cell","covered-table-cell")]:
                        cells.append(_odt_node_text(cell).strip().replace("\n"," / "))
                    if cells:
                        lines.append(" | ".join(cells))
                        row_count += 1
                lines.append("")
        # Metadata when available.
        props=[]
        try:
            meta_root=ET.fromstring(z.read("meta.xml"))
            wanted={"title":"Title","subject":"Subject","creator":"Creator","description":"Description","keyword":"Keyword","creation-date":"Created","date":"Modified"}
            for elem in meta_root.iter():
                local=elem.tag.split("}")[-1]
                if local in wanted and elem.text and elem.text.strip():
                    props.append((wanted[local],elem.text.strip()))
        except Exception:
            pass
    clean=[]; blank=False
    for line in lines:
        line=line.rstrip()
        if not line:
            if not blank: clean.append("")
            blank=True
        else:
            clean.append(line); blank=False
    content="\n".join(clean).strip()+"\n"
    header=[
        f"[ODT TEXT MODE] {display_name}",
        f"Paragraphs: {paragraph_count} | Headings: {heading_count} | Tables: {table_count} | Table rows: {row_count} | Extracted characters: {len(content):,}",
    ]
    for k,v in props: header.append(f"{k}: {v}")
    header += ["", "NOTE: Text Mode extracts readable ODT content; it does not reproduce LibreOffice/Writer page layout.", "", "===== DOCUMENT CONTENT =====", ""]
    return "\n".join(header)+content


def _ct_clean_text(value: str | None) -> str:
    if value is None: return ""
    return str(value).strip()


def _ct_text_mode_block(raw: bytes, display_name: str = "table.ct") -> str:
    """Render Cheat Engine XML into a compact reverse-engineering friendly summary."""
    text = _decode_text_bytes(raw)
    try:
        root = ET.fromstring(text)
    except Exception as exc:
        raise ValueError(f"CT XML parse failed: {exc}") from exc
    entries = root.find("CheatEntries")
    lines=[f"[CHEAT ENGINE CT TEXT MODE] {display_name}", ""]
    count=0
    def emit(entry, depth=0):
        nonlocal count
        count += 1
        ind="  "*depth
        desc=_ct_clean_text(entry.findtext("Description")).strip('"') or "(unnamed entry)"
        lines.append(f"{ind}[{count}] {desc}")
        fields=[
            ("ID", entry.findtext("ID")),
            ("VariableType", entry.findtext("VariableType")),
            ("Address", entry.findtext("Address")),
            ("ModuleName", entry.findtext("ModuleName")),
            ("ModuleOffset", entry.findtext("ModuleOffset")),
            ("ShowAsHex", entry.findtext("ShowAsHex")),
            ("ByteLength", entry.findtext("ByteLength")),
            ("BitStart", entry.findtext("BitStart")),
            ("BitLength", entry.findtext("BitLength")),
        ]
        for label,val in fields:
            val=_ct_clean_text(val)
            if val: lines.append(f"{ind}  {label}: {val}")
        offsets=entry.find("Offsets")
        if offsets is not None:
            vals=[_ct_clean_text(x.text) for x in list(offsets) if _ct_clean_text(x.text)]
            if vals: lines.append(f"{ind}  Offsets: " + " -> ".join(vals))
        hotkeys=entry.find("Hotkeys")
        if hotkeys is not None:
            for hk in list(hotkeys):
                action=_ct_clean_text(hk.findtext("Action")); keys=[_ct_clean_text(x.text) for x in hk.findall("./Keys/*")]
                combo=" + ".join(x for x in keys if x)
                if action or combo: lines.append(f"{ind}  Hotkey: {action}" + (f" | {combo}" if combo else ""))
        script=_ct_clean_text(entry.findtext("AssemblerScript")) or _ct_clean_text(entry.findtext("Script"))
        if script:
            lines.append(f"{ind}  ----- SCRIPT -----")
            lines.extend(ind+"  "+ln for ln in script.splitlines())
            lines.append(f"{ind}  ----- END SCRIPT -----")
        child_container=entry.find("CheatEntries")
        if child_container is not None:
            for child in child_container.findall("CheatEntry"):
                emit(child, depth+1)
        lines.append("")
    if entries is not None:
        for entry in entries.findall("CheatEntry"):
            emit(entry)
    # Include symbols/comments that are useful in RE tables.
    symbols=root.find("UserdefinedSymbols")
    if symbols is not None and list(symbols):
        lines += ["===== USER DEFINED SYMBOLS ====="]
        for sym in list(symbols):
            name=_ct_clean_text(sym.findtext("Name")); addr=_ct_clean_text(sym.findtext("Address"))
            if name or addr: lines.append(f"{name}: {addr}".strip())
        lines.append("")
    comments=_ct_clean_text(root.findtext("Comments"))
    if comments:
        lines += ["===== COMMENTS =====", comments, ""]
    lines.insert(1, f"Cheat entries: {count}")
    lines.insert(2, "NOTE: Text Mode summarizes useful Cheat Engine XML fields. Hex Mode still shows the original raw .CT bytes.")
    return "\n".join(lines).rstrip()+"\n"

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_DCTERMS_NS = "http://purl.org/dc/terms/1.1/"


def _w_tag(name: str) -> str:
    return f"{{{_W_NS}}}{name}"


def _docx_paragraph_text(p) -> str:
    """Extract visible text from one Word paragraph while preserving tabs/line breaks."""
    out = []
    for node in p.iter():
        if node.tag == _w_tag("t"):
            out.append(node.text or "")
        elif node.tag == _w_tag("tab"):
            out.append("\t")
        elif node.tag in (_w_tag("br"), _w_tag("cr")):
            out.append("\n")
    return "".join(out).strip()


def _docx_paragraph_style(p) -> str:
    ppr = p.find(_w_tag("pPr"))
    if ppr is None:
        return ""
    pstyle = ppr.find(_w_tag("pStyle"))
    if pstyle is None:
        return ""
    return str(pstyle.attrib.get(_w_tag("val"), "") or "")


def _docx_core_properties(z: zipfile.ZipFile) -> dict:
    props = {}
    try:
        root = ET.fromstring(z.read("docProps/core.xml"))
    except Exception:
        return props
    wanted = {
        f"{{{_DC_NS}}}title": "Title",
        f"{{{_DC_NS}}}subject": "Subject",
        f"{{{_DC_NS}}}creator": "Creator",
        f"{{{_CP_NS}}}keywords": "Keywords",
        f"{{{_DC_NS}}}description": "Description",
        f"{{{_CP_NS}}}lastModifiedBy": "Last Modified By",
        f"{{{_CP_NS}}}revision": "Revision",
        f"{{{_DCTERMS_NS}}}created": "Created",
        f"{{{_DCTERMS_NS}}}modified": "Modified",
    }
    for child in root:
        label = wanted.get(child.tag)
        if label and child.text:
            props[label] = child.text.strip()
    return props


def _docx_extract_text(source) -> tuple[str, dict]:
    """Read a DOCX from a Path/bytes and return readable Text Mode content + stats.

    Uses only the Python standard library. It intentionally extracts readable Word
    content rather than trying to reproduce Word's page layout. Paragraph order,
    headings, tables, tabs, and line breaks are preserved in a plain-text form.
    """
    holder = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    with zipfile.ZipFile(holder) as z:
        try:
            root = ET.fromstring(z.read("word/document.xml"))
        except KeyError as exc:
            raise ValueError("DOCX is missing word/document.xml") from exc
        props = _docx_core_properties(z)
        body = root.find(_w_tag("body"))
        if body is None:
            raise ValueError("DOCX document body was not found")

        lines = []
        paragraph_count = 0
        table_count = 0
        table_row_count = 0
        for child in list(body):
            if child.tag == _w_tag("p"):
                paragraph_count += 1
                text = _docx_paragraph_text(child)
                if not text:
                    if lines and lines[-1] != "":
                        lines.append("")
                    continue
                style = _docx_paragraph_style(child).lower()
                if style.startswith("title"):
                    lines.extend([text, "=" * min(100, max(8, len(text))), ""])
                elif style.startswith("heading"):
                    digits = "".join(ch for ch in style if ch.isdigit())
                    level = max(1, min(6, int(digits or "1")))
                    lines.extend([("#" * level) + " " + text, ""])
                else:
                    lines.append(text)
            elif child.tag == _w_tag("tbl"):
                table_count += 1
                if lines and lines[-1] != "":
                    lines.append("")
                for tr in child.findall(_w_tag("tr")):
                    cells = []
                    for tc in tr.findall(_w_tag("tc")):
                        cell_parts = []
                        for p in tc.findall('.//' + _w_tag("p")):
                            t = _docx_paragraph_text(p)
                            if t:
                                cell_parts.append(t)
                        cells.append(" / ".join(cell_parts))
                    lines.append(" | ".join(cells).rstrip())
                    table_row_count += 1
                lines.append("")

        # Include headers/footers after the main document so important text is not lost.
        extras = []
        for name in sorted(z.namelist()):
            lower = name.lower()
            if not ((lower.startswith("word/header") or lower.startswith("word/footer")) and lower.endswith(".xml")):
                continue
            try:
                extra_root = ET.fromstring(z.read(name))
            except Exception:
                continue
            chunk = []
            for p in extra_root.iter(_w_tag("p")):
                t = _docx_paragraph_text(p)
                if t:
                    chunk.append(t)
            if chunk:
                extras.append((name, chunk))
        if extras:
            lines.extend(["", "===== HEADERS / FOOTERS =====", ""])
            for name, chunk in extras:
                lines.append(f"--- {name} ---")
                lines.extend(chunk)
                lines.append("")

        # Collapse excessive blank lines without destroying section spacing.
        clean = []
        blank = False
        for line in lines:
            line = line.rstrip()
            if not line:
                if not blank:
                    clean.append("")
                blank = True
            else:
                clean.append(line)
                blank = False
        text = "\n".join(clean).strip() + "\n"
        stats = {
            "paragraphs": paragraph_count,
            "tables": table_count,
            "table_rows": table_row_count,
            "characters": len(text),
            "properties": props,
        }
        return text, stats


def _docx_text_mode_block(source, display_name: str = "document.docx") -> str:
    text, stats = _docx_extract_text(source)
    props = stats.get("properties", {})
    header = [
        f"[DOCX TEXT MODE] {display_name}",
        f"Paragraphs: {stats.get('paragraphs', 0)} | Tables: {stats.get('tables', 0)} | Table rows: {stats.get('table_rows', 0)} | Extracted characters: {stats.get('characters', 0):,}",
    ]
    for key in ("Title", "Subject", "Creator", "Keywords", "Description", "Last Modified By", "Revision", "Created", "Modified"):
        value = props.get(key)
        if value:
            header.append(f"{key}: {value}")
    header.extend([
        "",
        "NOTE: Text Mode extracts readable DOCX content. It does not reproduce Microsoft Word page layout, fonts, margins, or floating objects.",
        "",
        "===== DOCUMENT CONTENT =====",
        "",
    ])
    return "\n".join(header) + text


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
        self.status_var = tk.StringVar(value="Open any file to view Hex/Text. View Only is checked by default; uncheck it to type in the view, then export a copy.")
        self.inspector_var = tk.StringVar(value="Byte Inspector: select a byte in the hex pane.")
        self.text_find_var = tk.StringVar()
        self.text_line_var = tk.StringVar()
        self.text_status_var = tk.StringVar(value="Text Mode: DOCX/ODT/RTF/CT plus TXT/JSON/XML/YAML/TOML/code/config/Ghidra exports.")
        self.big_text_status_var = tk.StringVar(value="Big Text Mode: best for Ghidra exports, folders, ZIP text bundles, and giant files.")
        self.big_text_find_var = tk.StringVar()
        self.big_text_line_var = tk.StringVar()
        self.view_only_var = tk.BooleanVar(value=True)
        self.big_text_window = None
        self.big_text_text = None
        self.path: Path | None = None
        self.file_size = 0
        self.current_offset = 0
        self.view_mode = "hex"
        self.loaded_text = ""
        self.text_loaded_full = False
        self._text_search_pos = "1.0"
        self._build()

    def _build(self):
        header = ttk.Frame(self, style="Body.TFrame")
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Hex/Text Viewer", style="SectionTitle.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="Hex/Text viewer for PCPACK/APKF plus DOCX, ODT, RTF, CT, JSON/XML, YAML/TOML, code/config, Ghidra exports, and more. View Only is on by default.",
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
        ttk.Button(controls, text="Export Page TXT/Text", command=self.export_current_page_text).grid(row=3, column=2, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Open HTML Preview", command=self.open_html_preview).grid(row=3, column=3, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Text Mode", command=lambda: self.load_text_mode(force_full=False)).grid(row=3, column=4, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Hex Mode", command=self.show_hex_mode).grid(row=3, column=5, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Load Full Text", command=lambda: self.load_text_mode(force_full=True)).grid(row=3, column=6, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Open Text Folder", command=self.open_text_folder).grid(row=3, column=7, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Big Text Window", command=self.open_big_text_window_for_current).grid(row=3, column=8, padx=4, pady=3, sticky="ew")
        ttk.Checkbutton(controls, text="View Only", variable=self.view_only_var, command=self.apply_view_only_state).grid(row=3, column=9, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Export Edited Copy", command=self.export_edited_copy).grid(row=3, column=10, padx=4, pady=3, sticky="ew")
        ttk.Button(controls, text="Clear", command=self.clear_view).grid(row=3, column=11, padx=4, pady=3, sticky="ew")

        self.hex_panes = ttk.Frame(self, style="Body.TFrame")
        panes = self.hex_panes
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

        self.text_frame = ttk.Frame(self, style="Body.TFrame")
        self.text_frame.columnconfigure(0, weight=1)
        self.text_frame.rowconfigure(1, weight=1)
        text_toolbar = ttk.Frame(self.text_frame, style="Card.TFrame", padding=8)
        text_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        text_toolbar.columnconfigure(1, weight=1)
        ttk.Label(text_toolbar, text="Find in Text:", style="CardLabel.TLabel").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        ttk.Entry(text_toolbar, textvariable=self.text_find_var).grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        ttk.Button(text_toolbar, text="Find Next", command=self.find_text_mode).grid(row=0, column=2, padx=4, pady=2, sticky="ew")
        ttk.Button(text_toolbar, text="Find All Count", command=self.count_text_mode_matches).grid(row=0, column=3, padx=4, pady=2, sticky="ew")
        ttk.Label(text_toolbar, text="Line:", style="CardLabel.TLabel").grid(row=0, column=4, padx=(10, 4), pady=2, sticky="e")
        ttk.Entry(text_toolbar, textvariable=self.text_line_var, width=9).grid(row=0, column=5, padx=4, pady=2, sticky="ew")
        ttk.Button(text_toolbar, text="Go To Line", command=self.goto_text_mode_line).grid(row=0, column=6, padx=4, pady=2, sticky="ew")
        ttk.Button(text_toolbar, text="Back to Hex Mode", command=self.show_hex_mode).grid(row=0, column=7, padx=4, pady=2, sticky="ew")
        ttk.Button(text_toolbar, text="Export Text", command=self.export_text_mode_text).grid(row=0, column=8, padx=4, pady=2, sticky="ew")
        ttk.Label(text_toolbar, textvariable=self.text_status_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=9, sticky="w", padx=4, pady=(4, 0))
        self.text_mode_text = tk.Text(
            self.text_frame,
            wrap="none",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Consolas", 10),
            undo=False,
        )
        self.text_mode_text.grid(row=1, column=0, sticky="nsew")
        self.text_mode_text.bind("<Button-1>", lambda _event: self.text_mode_text.focus_set())
        self.text_mode_text.bind("<KeyPress-Up>", lambda _event: self.text_mode_text.focus_set())
        self.text_mode_text.bind("<KeyPress-Down>", lambda _event: self.text_mode_text.focus_set())
        text_ybar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_mode_text.yview)
        text_ybar.grid(row=1, column=1, sticky="ns")
        text_xbar = ttk.Scrollbar(self.text_frame, orient="horizontal", command=self.text_mode_text.xview)
        text_xbar.grid(row=2, column=0, sticky="ew")
        self.text_mode_text.configure(yscrollcommand=text_ybar.set, xscrollcommand=text_xbar.set)

        bottom = ttk.Frame(self, style="Card.TFrame", padding=8)
        bottom.pack(fill="x", pady=(8, 0))
        ttk.Label(bottom, textvariable=self.status_var, style="CardLabel.TLabel").pack(anchor="w")
        ttk.Label(bottom, textvariable=self.inspector_var, style="CardLabel.TLabel").pack(anchor="w", pady=(4, 0))
        self.clear_view()

    def apply_view_only_state(self):
        """Toggle viewer editability. This never edits the original file on disk."""
        state = "disabled" if self.view_only_var.get() else "normal"
        widgets = [getattr(self, "hex_text", None), getattr(self, "ascii_text", None), getattr(self, "text_mode_text", None), getattr(self, "big_text_text", None)]
        for widget in widgets:
            try:
                if widget and widget.winfo_exists():
                    widget.configure(state=state)
            except Exception:
                pass
        msg = "View Only ON: original file is protected." if self.view_only_var.get() else "View Only OFF: you can type in the viewer; use Export Edited Copy to save a new file. Original is not edited."
        self.status_var.set(msg)
        self.text_status_var.set(msg)
        self.big_text_status_var.set(msg)

    def _make_widget_editable_for_insert(self, widget: tk.Text):
        try:
            widget.configure(state="normal")
        except Exception:
            pass

    def _restore_view_only_after_insert(self, widget: tk.Text):
        try:
            if self.view_only_var.get():
                widget.configure(state="disabled")
            else:
                widget.configure(state="normal")
        except Exception:
            pass

    def _text_widget_contents(self, widget: tk.Text | None) -> str:
        if not widget:
            return ""
        try:
            return widget.get("1.0", "end-1c")
        except Exception:
            return ""

    def export_text_mode_text(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a text file/export first.")
            return
        content = self._text_widget_contents(self.text_mode_text)
        self._export_text_content(content, default_suffix="_text_mode_export.txt", title="Export Text Mode as text")

    def export_big_text_mode_text(self):
        content = self._text_widget_contents(self.big_text_text)
        if not content:
            messagebox.showinfo("No Big Text", "Open Big Text Mode first.")
            return
        self._export_text_content(content, default_suffix="_big_text_export.txt", title="Export Big Text Mode as text")

    def _export_text_content(self, content: str, default_suffix: str, title: str):
        if not content:
            messagebox.showinfo("Nothing to export", "The current text view is empty.")
            return
        stem = self.path.stem if self.path else "hex_text"
        path = filedialog.asksaveasfilename(
            title=title,
            defaultextension=".txt",
            initialfile=f"{stem}{default_suffix}",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8", errors="replace")
            self.status_var.set(f"Exported text copy: {path}")
        except Exception as exc:
            messagebox.showerror("Text export failed", str(exc))

    def _edited_hex_page_bytes(self) -> bytes:
        """Parse the visible hex pane back into page bytes for safe copy export."""
        raw = self._text_widget_contents(self.hex_text)
        out = bytearray()
        for line in raw.splitlines():
            if ":" not in line:
                continue
            left, right = line.split(":", 1)
            if not re.fullmatch(r"[0-9A-Fa-f]{1,16}", left.strip()):
                continue
            tokens = re.findall(r"\b[0-9A-Fa-f]{2}\b", right)
            # The visible hex pane has only the hex side, so tokens are expected to be bytes.
            for token in tokens[:16]:
                out.append(int(token, 16))
        if not out:
            raise ValueError("No hex bytes could be parsed from the visible Hex pane.")
        return bytes(out)

    def export_edited_copy(self):
        """Export viewer edits to a new file. Never modifies the opened original."""
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        if self.view_mode == "text":
            self.export_text_mode_text()
            return
        if self.path.is_dir():
            self.export_text_mode_text()
            return
        try:
            page_bytes = self._edited_hex_page_bytes()
        except Exception as exc:
            messagebox.showerror("Export Edited Copy failed", str(exc))
            return
        initial = f"{self.path.stem}_edited_copy{self.path.suffix or '.bin'}"
        path = filedialog.asksaveasfilename(
            title="Export edited Hex page into a new copy",
            defaultextension=self.path.suffix or ".bin",
            initialfile=initial,
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        try:
            original = self.path.read_bytes()
            start = max(0, min(self.current_offset, len(original)))
            end = min(len(original), start + len(page_bytes))
            new_data = original[:start] + page_bytes[: max(0, end - start)] + original[end:]
            # If the user typed extra bytes past EOF/page end, append only when current page reaches EOF.
            if len(page_bytes) > max(0, end - start) and start + max(0, end - start) >= len(original):
                new_data += page_bytes[max(0, end - start):]
            Path(path).write_bytes(new_data)
            self.status_var.set(f"Exported edited copy: {path} | original was not modified")
            messagebox.showinfo("Export complete", "Edited copy exported. The original file was not modified.")
        except Exception as exc:
            messagebox.showerror("Export Edited Copy failed", str(exc))

    def _page_size(self):
        try:
            return max(0x100, int(self.page_size_var.get().strip(), 0))
        except Exception:
            return 0x4000

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open any file in Hex/Text",
            filetypes=[
                ("All supported / any file", "*.*"),
                ("Game / binary files", "*.PCPACK *.pcpack *.PCAPK *.pcapk *.APKF *.apkf *.toc *.dll *.exe *.bin *.dat *.ihex *.hex"),
                ("Text / documents / Ghidra exports", "*.txt *.log *.csv *.json *.jsonl *.c *.cpp *.h *.hpp *.html *.htm *.xml *.map *.lst *.md *.ii *.ini *.cfg *.conf *.docx *.odt *.rtf *.ct *.yaml *.yml *.toml *.lua *.py *.bat *.cmd *.ps1 *.zip"),
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
        if self.path.suffix.lower() in TEXT_MODE_EXTS:
            self.load_text_mode(force_full=False, force_big=self._should_use_big_text_window(self.path))
        else:
            self.show_hex_mode()
            self.render_page()

    def open_text_folder(self):
        path = filedialog.askdirectory(title="Open Ghidra/text export folder in Text Mode")
        if not path:
            return
        self.path = Path(path)
        self.file_size = 0
        self.file_var.set(str(self.path))
        self.current_offset = 0
        self.load_text_mode(force_full=False, force_big=True)

    def reveal_file(self):
        if self.path and self.path.exists():
            open_path(self.path if self.path.is_dir() else self.path.parent)
        else:
            messagebox.showinfo("No file", "Open a file first.")

    def clear_view(self):
        self.loaded_text = ""
        self.text_loaded_full = False
        self._text_search_pos = "1.0"
        try:
            self.show_hex_mode()
        except Exception:
            pass
        self.hex_text.configure(state="normal")
        self.ascii_text.configure(state="normal")
        self.hex_text.delete("1.0", "end")
        self.ascii_text.delete("1.0", "end")
        self.hex_text.insert("1.0", "Offset     00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F\n")
        self.ascii_text.insert("1.0", "ASCII\n")
        self._restore_view_only_after_insert(self.hex_text)
        self._restore_view_only_after_insert(self.ascii_text)
        self.status_var.set("Open any file to view Hex/Text. View Only protects the original; uncheck only to type/edit the viewer copy, then export a new file.")
        self.inspector_var.set("Byte Inspector: select a byte in the hex pane.")
        if self.big_text_text and self.big_text_window and self.big_text_window.winfo_exists():
            self.big_text_text.configure(state="normal")
            self.big_text_text.delete("1.0", "end")
            self.big_text_text.insert("1.0", "Big Text Mode cleared. Open a Ghidra/text export to view it here.\n")
            self.big_text_status_var.set("Big Text Mode cleared.")
            self._restore_view_only_after_insert(self.big_text_text)

    def _format_char_count(self, n: int) -> str:
        return f"{n:,}"

    def _is_text_like(self, path: Path) -> bool:
        return path.is_dir() or path.suffix.lower() in TEXT_MODE_EXTS

    def _should_use_big_text_window(self, path: Path | None = None) -> bool:
        """Auto-expand Text Mode for Ghidra exports and files that need more room."""
        p = path or self.path
        if not p:
            return False
        try:
            if p.is_dir():
                return True
            suffix = p.suffix.lower()
            if suffix == ".zip":
                return True
            if suffix in {".html", ".htm", ".c", ".cpp", ".h", ".hpp", ".map", ".lst", ".ii", ".xml"}:
                return True
            return p.stat().st_size >= BIG_TEXT_AUTO_SIZE
        except Exception:
            return False

    def open_big_text_window_for_current(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a text/Ghidra export first.")
            return
        self.load_text_mode(force_full=False, force_big=True)

    def open_big_text_window(self):
        """Open a large read-only text window for Ghidra exports / huge text bundles."""
        if self.big_text_window and self.big_text_window.winfo_exists():
            self.big_text_window.lift()
            try:
                self.big_text_text.focus_set()
            except Exception:
                pass
            return self.big_text_window
        win = tk.Toplevel(self)
        self.big_text_window = win
        win.title("Hex/Text Viewer - Big Text Mode")
        win.geometry("1720x940")
        win.minsize(1200, 720)
        win.configure(bg=COLORS["bg"])
        try:
            win.state("zoomed")
        except Exception:
            pass
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(win, style="Card.TFrame", padding=8)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.columnconfigure(3, weight=1)
        ttk.Label(toolbar, text="Big Text Mode", style="SectionTitle.TLabel").grid(row=0, column=0, padx=4, sticky="w")
        ttk.Button(toolbar, text="Load Full Text", command=lambda: self.load_text_mode(force_full=True, force_big=True)).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Label(toolbar, text="Find:", style="CardLabel.TLabel").grid(row=0, column=2, padx=(12, 4), sticky="e")
        ttk.Entry(toolbar, textvariable=self.big_text_find_var).grid(row=0, column=3, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Find Next", command=self.find_big_text_mode).grid(row=0, column=4, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Find All Count", command=self.count_big_text_mode_matches).grid(row=0, column=5, padx=4, sticky="ew")
        ttk.Label(toolbar, text="Line:", style="CardLabel.TLabel").grid(row=0, column=6, padx=(10, 4), sticky="e")
        ttk.Entry(toolbar, textvariable=self.big_text_line_var, width=9).grid(row=0, column=7, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Go To Line", command=self.goto_big_text_mode_line).grid(row=0, column=8, padx=4, sticky="ew")
        ttk.Checkbutton(toolbar, text="View Only", variable=self.view_only_var, command=self.apply_view_only_state).grid(row=0, column=9, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Export Text", command=self.export_big_text_mode_text).grid(row=0, column=10, padx=4, sticky="ew")
        ttk.Button(toolbar, text="Close Big Text", command=win.destroy).grid(row=0, column=11, padx=4, sticky="ew")
        ttk.Label(toolbar, textvariable=self.big_text_status_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=12, padx=4, pady=(4, 0), sticky="w")

        text = tk.Text(
            win,
            wrap="none",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Consolas", 10),
            undo=False,
        )
        self.big_text_text = text
        text.grid(row=1, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        ybar.grid(row=1, column=1, sticky="ns")
        xbar = ttk.Scrollbar(win, orient="horizontal", command=text.xview)
        xbar.grid(row=2, column=0, sticky="ew")
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        text.bind("<Button-1>", lambda _event: text.focus_set())
        text.bind("<KeyPress-Up>", lambda _event: text.focus_set())
        text.bind("<KeyPress-Down>", lambda _event: text.focus_set())
        text.focus_set()

        def on_close():
            self.big_text_window = None
            self.big_text_text = None
            try:
                win.destroy()
            except Exception:
                pass
        win.protocol("WM_DELETE_WINDOW", on_close)
        return win

    def _insert_big_text(self, text: str):
        if self.big_text_text and self.big_text_window and self.big_text_window.winfo_exists():
            self._insert_text_chunked(self.big_text_text, text)
            try:
                self.big_text_text.focus_set()
            except Exception:
                pass

    def find_big_text_mode(self):
        if not self.big_text_text:
            return
        query = self.big_text_find_var.get()
        if not query:
            messagebox.showinfo("No search text", "Type text to find first.")
            return
        widget = self.big_text_text
        widget.tag_remove("hit", "1.0", "end")
        start = widget.index("insert") or "1.0"
        hit = widget.search(query, f"{start}+1c", nocase=True, stopindex="end")
        if not hit:
            hit = widget.search(query, "1.0", nocase=True, stopindex="end")
        if not hit:
            messagebox.showinfo("Not found", "Text not found in Big Text Mode.")
            return
        end = f"{hit}+{len(query)}c"
        widget.tag_add("hit", hit, end)
        widget.tag_configure("hit", background=COLORS["select"], foreground=COLORS["fg"])
        widget.see(hit)
        widget.mark_set("insert", hit)
        widget.focus_set()
        self.big_text_status_var.set(f"Found text at {hit}. Click inside the text area, then Up/Down arrows scroll normally.")

    def _insert_text_chunked(self, widget: tk.Text, text: str, chunk: int = 120_000) -> None:
        # Adapted from the user's Ghidra Export Explorer v1.6 chunked-loading pattern.
        self._make_widget_editable_for_insert(widget)
        try:
            widget.configure(undo=False, autoseparators=False, maxundo=0)
        except Exception:
            pass
        widget.delete("1.0", "end")
        for index, pos in enumerate(range(0, len(text), chunk), 1):
            widget.insert("end", text[pos:pos + chunk])
            if index % 4 == 0:
                self.update_idletasks()
        if len(text) > chunk:
            self.update_idletasks()
        self._restore_view_only_after_insert(widget)

    def _smart_large_file_note(self, total: int, shown: int) -> str:
        return (
            "\n\n[SMART LARGE FILE MODE] This file is large. "
            f"Showing {self._format_char_count(shown)} of about {self._format_char_count(total)} bytes/chars so the UI stays responsive. "
            "Use Load Full Text if you really need the full export loaded.\n"
        )

    def _decode_named_text(self, name: str, raw: bytes) -> str:
        suffix = Path(name).suffix.lower()
        if suffix == ".docx":
            return _docx_text_mode_block(raw, display_name=name)
        text = _decode_text_bytes(raw)
        if suffix in (".html", ".htm"):
            text = _html_to_text(text)
        return text

    def _iter_text_files_in_folder(self, folder: Path):
        for child in sorted(folder.rglob("*"), key=lambda p: str(p).lower()):
            if child.is_file() and child.suffix.lower() in TEXT_FILE_EXTS:
                yield child

    def _read_folder_text_bundle(self, folder: Path, force_full: bool = False) -> tuple[str, bool, int, int]:
        # Folder/large export loading adapted from the user's Ghidra helper load_path pattern.
        parts = [f"[TEXT FOLDER MODE] {folder}\n"]
        total_bytes = 0
        shown_chars = 0
        full = True
        files_loaded = 0
        for child in self._iter_text_files_in_folder(folder):
            try:
                raw = child.read_bytes()
            except Exception as exc:
                parts.append(f"\n--- FILE: {child.name} READ ERROR: {exc} ---\n")
                continue
            total_bytes += len(raw)
            try:
                rel = child.relative_to(folder).as_posix()
            except Exception:
                rel = child.name
            text = self._decode_named_text(child.name, raw)
            block = f"\n\n===== FILE: {rel} =====\n{text}"
            if not force_full and shown_chars + len(block) > SMART_TEXT_WIDGET_LIMIT:
                remain = max(0, SMART_TEXT_WIDGET_LIMIT - shown_chars)
                parts.append(block[:remain])
                shown_chars += remain
                full = False
                break
            parts.append(block)
            shown_chars += len(block)
            files_loaded += 1
            if files_loaded % 10 == 0:
                self.text_status_var.set(f"Loading text folder... {files_loaded} files")
        text = "".join(parts)
        if not full:
            text += self._smart_large_file_note(total_bytes, len(text))
        return text, full, len(text), total_bytes

    def _read_zip_text_bundle(self, zip_path: Path, force_full: bool = False) -> tuple[str, bool, int, int]:
        # ZIP text loading adapted from the user's Ghidra helper load_path ZIP support.
        parts = [f"[TEXT ZIP MODE] {zip_path}\n"]
        shown_chars = 0
        total_bytes = zip_path.stat().st_size
        full = True
        files_loaded = 0
        with zipfile.ZipFile(zip_path) as z:
            infos = [i for i in z.infolist() if not i.is_dir() and Path(i.filename).suffix.lower() in TEXT_FILE_EXTS]
            infos.sort(key=lambda i: i.filename.lower())
            for info in infos:
                try:
                    raw = z.read(info.filename)
                except Exception as exc:
                    block = f"\n--- ZIP FILE: {info.filename} READ ERROR: {exc} ---\n"
                else:
                    block = f"\n\n===== ZIP FILE: {info.filename} =====\n{self._decode_named_text(info.filename, raw)}"
                if not force_full and shown_chars + len(block) > SMART_TEXT_WIDGET_LIMIT:
                    remain = max(0, SMART_TEXT_WIDGET_LIMIT - shown_chars)
                    parts.append(block[:remain])
                    shown_chars += remain
                    full = False
                    break
                parts.append(block)
                shown_chars += len(block)
                files_loaded += 1
                if files_loaded % 10 == 0:
                    self.text_status_var.set(f"Loading Ghidra/text ZIP... {files_loaded} files")
        text = "".join(parts)
        if not full:
            text += self._smart_large_file_note(total_bytes, len(text))
        return text, full, len(text), total_bytes

    def _read_text_for_mode(self, path: Path, force_full: bool = False) -> tuple[str, bool, int, int]:
        if path.is_dir():
            return self._read_folder_text_bundle(path, force_full=force_full)
        if path.suffix.lower() == ".zip":
            return self._read_zip_text_bundle(path, force_full=force_full)
        size = path.stat().st_size
        suffix = path.suffix.lower()
        if suffix == ".docx":
            text = _docx_text_mode_block(path, display_name=path.name)
            shown = len(text)
            if not force_full and shown > SMART_TEXT_WIDGET_LIMIT:
                preview = text[:SMART_TEXT_WIDGET_LIMIT]
                preview += self._smart_large_file_note(size, len(preview))
                return preview, False, len(preview), size
            return text, True, shown, size
        if suffix == ".odt":
            text = _odt_text_mode_block(path, display_name=path.name)
            shown = len(text)
            if not force_full and shown > SMART_TEXT_WIDGET_LIMIT:
                preview = text[:SMART_TEXT_WIDGET_LIMIT]
                preview += self._smart_large_file_note(size, len(preview))
                return preview, False, len(preview), size
            return text, True, shown, size
        if suffix == ".rtf":
            raw = path.read_bytes() if force_full or size <= SMART_TEXT_WIDGET_LIMIT * 4 else path.read_bytes()[:SMART_TEXT_WIDGET_LIMIT * 4]
            body = _rtf_extract_text(raw)
            text = (
                f"[RTF TEXT MODE] {path.name}\n"
                "NOTE: Readable text extraction; RTF page/font layout is not reproduced.\n\n"
                "===== DOCUMENT CONTENT =====\n\n"
                + body
            )
            shown = len(text)
            full = force_full or size <= SMART_TEXT_WIDGET_LIMIT * 4
            if not force_full and shown > SMART_TEXT_WIDGET_LIMIT:
                text = text[:SMART_TEXT_WIDGET_LIMIT] + self._smart_large_file_note(size, SMART_TEXT_WIDGET_LIMIT)
                return text, False, len(text), size
            return text, full, shown, size
        if suffix == ".ct":
            raw = path.read_bytes()
            text = _ct_text_mode_block(raw, display_name=path.name)
            shown = len(text)
            if not force_full and shown > SMART_TEXT_WIDGET_LIMIT:
                preview = text[:SMART_TEXT_WIDGET_LIMIT] + self._smart_large_file_note(size, SMART_TEXT_WIDGET_LIMIT)
                return preview, False, len(preview), size
            return text, True, shown, size
        if not force_full and size > SMART_TEXT_WIDGET_LIMIT:
            with path.open("rb") as f:
                raw = f.read(SMART_TEXT_WIDGET_LIMIT)
            text = _decode_text_bytes(raw)
            if suffix in (".html", ".htm"):
                text = _html_to_text(text)
            elif suffix in (".json", ".jsonl"):
                text = _pretty_json_text(text)
            elif suffix == ".xml":
                text = _pretty_xml_text(text)
            shown = len(text)
            text += self._smart_large_file_note(size, shown)
            return text, False, shown, size
        raw = path.read_bytes()
        text = _decode_text_bytes(raw)
        if suffix in (".html", ".htm"):
            text = _html_to_text(text)
        elif suffix in (".json", ".jsonl"):
            text = _pretty_json_text(text)
        elif suffix == ".xml":
            text = _pretty_xml_text(text)
        return text, True, len(text), size

    def _show_loading_text_mode(self, message: str, force_big: bool = False) -> None:
        self.show_text_mode()
        self._make_widget_editable_for_insert(self.text_mode_text)
        self.text_mode_text.delete("1.0", "end")
        self.text_mode_text.insert("1.0", message)
        if force_big:
            self.open_big_text_window()
            if self.big_text_text:
                self._make_widget_editable_for_insert(self.big_text_text)
                self.big_text_text.delete("1.0", "end")
                self.big_text_text.insert("1.0", message)
                self.big_text_text.focus_set()
            self.big_text_status_var.set(message.strip())
        self.text_status_var.set(message.strip())
        self.status_var.set(message.strip())
        self._restore_view_only_after_insert(self.text_mode_text)
        if force_big and self.big_text_text:
            self._restore_view_only_after_insert(self.big_text_text)
        self.update_idletasks()

    def load_text_mode(self, force_full: bool = False, force_big: bool = False):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        path = self.path
        force_big = bool(force_big or self._should_use_big_text_window(path))
        self._show_loading_text_mode("Loading text mode... giant Ghidra exports can take a moment.\n", force_big=force_big)

        def worker():
            try:
                return self._read_text_for_mode(path, force_full=force_full)
            except Exception as exc:
                return exc

        def done(result):
            if isinstance(result, Exception):
                messagebox.showerror("Text Mode failed", str(result))
                self.status_var.set(f"Text Mode failed: {result}")
                return
            text, full, shown, total = result
            self.loaded_text = text
            self.text_loaded_full = full
            self._text_search_pos = "1.0"
            self.show_text_mode()
            self._insert_text_chunked(self.text_mode_text, text)
            self.text_mode_text.focus_set()
            if force_big:
                self.open_big_text_window()
                self._insert_big_text(text)
            mode = "FULL TEXT" if full else "SMART PREVIEW"
            target = "Big Text Window + Text Mode" if force_big else "Text Mode"
            self.text_status_var.set(f"{path.name} | {mode} | shown {self._format_char_count(shown)} | file size {total:,} bytes")
            self.big_text_status_var.set(f"{path.name} | {mode} | shown {self._format_char_count(shown)} | file size {total:,} bytes")
            self.status_var.set(f"{target} loaded: {path.name} | {mode}")

        # Structured document parsers are fast and dependency-free. Keep them on
        # the Tk/main thread so Text Mode updates reliably on every Python/Tk build.
        if path.suffix.lower() in {".docx", ".odt", ".rtf", ".ct"}:
            done(worker())
            return

        def background_load():
            result = worker()
            self.after(0, lambda result=result: done(result))
        threading.Thread(target=background_load, daemon=True).start()

    def show_text_mode(self):
        self.view_mode = "text"
        try:
            self.hex_panes.pack_forget()
        except Exception:
            pass
        try:
            self.text_frame.pack(fill="both", expand=True, before=self.text_frame.master.winfo_children()[-1])
        except Exception:
            try:
                self.text_frame.pack(fill="both", expand=True)
            except Exception:
                pass

    def show_hex_mode(self):
        self.view_mode = "hex"
        try:
            self.text_frame.pack_forget()
        except Exception:
            pass
        try:
            self.hex_panes.pack(fill="both", expand=True, before=self.hex_panes.master.winfo_children()[-1])
        except Exception:
            try:
                self.hex_panes.pack(fill="both", expand=True)
            except Exception:
                pass

    def find_text_mode(self):
        query = self.text_find_var.get()
        if not query:
            messagebox.showinfo("No search text", "Type text to find first.")
            return
        if self.view_mode != "text":
            self.load_text_mode(force_full=False)
            return
        self.text_mode_text.tag_remove("hit", "1.0", "end")
        start = self._text_search_pos or "1.0"
        hit = self.text_mode_text.search(query, start, nocase=True, stopindex="end")
        if not hit:
            hit = self.text_mode_text.search(query, "1.0", nocase=True, stopindex="end")
        if not hit:
            messagebox.showinfo("Not found", "Text not found in the loaded Text Mode view.")
            return
        end = f"{hit}+{len(query)}c"
        self.text_mode_text.tag_add("hit", hit, end)
        self.text_mode_text.tag_configure("hit", background=COLORS["select"], foreground=COLORS["fg"])
        self.text_mode_text.see(hit)
        self.text_mode_text.mark_set("insert", hit)
        self.text_mode_text.focus_set()
        self._text_search_pos = end
        self.text_status_var.set(f"Found text at {hit}. Up/Down arrows and scrollbar work after clicking inside the text.")


    def _count_matches_in_widget(self, widget: tk.Text, query: str) -> int:
        if not query:
            return 0
        count = 0
        pos = "1.0"
        while True:
            hit = widget.search(query, pos, nocase=True, stopindex="end")
            if not hit:
                break
            count += 1
            pos = f"{hit}+{max(1, len(query))}c"
            if count > 200000:
                break
        return count

    def count_text_mode_matches(self):
        query = self.text_find_var.get()
        if not query:
            messagebox.showinfo("No search text", "Type text to count first.")
            return
        if self.view_mode != "text":
            self.load_text_mode(force_full=False)
        count = self._count_matches_in_widget(self.text_mode_text, query)
        self.text_status_var.set(f"Find All Count: {count:,} match(es) for '{query}' in the loaded Text Mode view.")

    def goto_text_mode_line(self):
        raw = self.text_line_var.get().strip()
        try:
            line = max(1, int(raw))
        except Exception:
            messagebox.showinfo("Invalid line", "Type a line number like 1500.")
            return
        if self.view_mode != "text":
            self.load_text_mode(force_full=False)
        index = f"{line}.0"
        self.text_mode_text.see(index)
        self.text_mode_text.mark_set("insert", index)
        self.text_mode_text.focus_set()
        self.text_status_var.set(f"Go To Line: {line:,}. Click inside the text area, then Up/Down arrows scroll normally.")

    def count_big_text_mode_matches(self):
        if not self.big_text_text:
            return
        query = self.big_text_find_var.get()
        if not query:
            messagebox.showinfo("No search text", "Type text to count first.")
            return
        count = self._count_matches_in_widget(self.big_text_text, query)
        self.big_text_status_var.set(f"Find All Count: {count:,} match(es) for '{query}' in Big Text Mode.")

    def goto_big_text_mode_line(self):
        if not self.big_text_text:
            return
        raw = self.big_text_line_var.get().strip()
        try:
            line = max(1, int(raw))
        except Exception:
            messagebox.showinfo("Invalid line", "Type a line number like 1500.")
            return
        index = f"{line}.0"
        self.big_text_text.see(index)
        self.big_text_text.mark_set("insert", index)
        self.big_text_text.focus_set()
        self.big_text_status_var.set(f"Go To Line: {line:,}. Click inside the text area, then Up/Down arrows scroll normally.")

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
        if self.path.is_dir():
            self.load_text_mode(force_full=False)
            return
        self.show_hex_mode()
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
        self._make_widget_editable_for_insert(self.hex_text)
        self._make_widget_editable_for_insert(self.ascii_text)
        self.hex_text.delete("1.0", "end")
        self.ascii_text.delete("1.0", "end")
        self.hex_text.insert("1.0", "\n".join(hex_lines))
        self.ascii_text.insert("1.0", "\n".join(ascii_lines))
        self._restore_view_only_after_insert(self.hex_text)
        self._restore_view_only_after_insert(self.ascii_text)
        end_offset = self.current_offset + max(0, len(data) - 1)
        self.offset_var.set(f"0x{self.current_offset:X}")
        self.status_var.set(f"{self.path.name} | size 0x{self.file_size:X} ({self.file_size:,}) | showing 0x{self.current_offset:X}-0x{end_offset:X}")

    def go_offset(self):
        if not self.path:
            messagebox.showinfo("No file", "Open a file first.")
            return
        if self.path.is_dir():
            messagebox.showinfo("Text folder", "Text folders use Text Mode, not byte offsets.")
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
        if self.path and not self.path.is_dir():
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
        if not self.path or self.path.is_dir() or not needle:
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
        if self.view_mode == "text":
            self.text_find_var.set(text)
            self.find_text_mode()
            return
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
        if self.view_mode == "text":
            self.export_text_mode_text()
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
            self.status_var.set(f"Exported text page: {path} | original was not modified")
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
