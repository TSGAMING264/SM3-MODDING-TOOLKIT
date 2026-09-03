from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.services.sound_editor_service import (
    SoundEditorError,
    SoundEntry,
    audio_support_status,
    build_music_mix,
    extract_entry,
    install_audio_support_current_python,
    replace_entry,
    scan_pcssb,
    validate_replacement,
)
from sm3_toolkit.theme import COLORS, refresh_tk_widget_colors
from sm3_toolkit.widgets import open_path


class SoundEditorTab(ttk.Frame):
    """Safe fixed-slot PCSSB editor + dialogue-preserving music replacement."""

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=12)
        self.app_state = app_state
        self.bank_var = tk.StringVar()
        self.replacement_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.selected_var = tk.StringVar(value="Selected: none")
        self.status_var = tk.StringVar(value="Sound Editor ready.")

        # Music Replacement Mode
        self.voice_stem_var = tk.StringVar()
        self.music_file_var = tk.StringVar()
        self.voice_volume_var = tk.IntVar(value=100)
        self.music_volume_var = tk.IntVar(value=35)
        self.loop_music_var = tk.BooleanVar(value=True)
        self.bitrate_var = tk.StringVar(value="Auto safe")
        self.mix_status_var = tk.StringVar(
            value="Select a sound, a dialogue/voice stem, and new music."
        )
        self.audio_support_var = tk.StringVar(value="Audio support: checking...")

        self.entries: list[SoundEntry] = []
        self.last_output: Path | None = None
        self.last_mix: Path | None = None
        self._build()
        self.after(150, self.refresh_audio_support_status)
        if self.app_state is not None:
            try:
                self.app_state.on_theme_change(lambda _theme: self._on_theme_changed())
            except Exception:
                pass

    def _on_theme_changed(self):
        try:
            refresh_tk_widget_colors(self)
        except Exception:
            pass

    def _set_status(self, text: str):
        self.status_var.set(text)
        try:
            self.winfo_toplevel().toolkit_status_var.set(text)
        except Exception:
            pass
        self._log(text)

    def _entry(self, parent, variable: tk.StringVar) -> tk.Entry:
        return tk.Entry(
            parent,
            textvariable=variable,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS.get("border", "#555555"),
            highlightcolor=COLORS.get("accent", "#777777"),
            font=("Segoe UI", 10),
        )

    def _button(self, parent, text, command, accent=False):
        bg = COLORS["accent"] if accent else COLORS["button"]
        active = COLORS["accent_hover"] if accent else COLORS["button_hover"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=COLORS["fg"],
            activebackground=active,
            activeforeground=COLORS["fg"],
            relief="flat",
            bd=0,
            padx=11,
            pady=7,
            font=("Segoe UI", 9, "bold" if accent else "normal"),
            cursor="hand2",
        )

    def _scale(self, parent, variable: tk.IntVar) -> tk.Scale:
        return tk.Scale(
            parent,
            from_=0,
            to=150,
            resolution=5,
            orient="horizontal",
            variable=variable,
            showvalue=True,
            length=250,
            bg=COLORS["panel"],
            fg=COLORS["fg"],
            activebackground=COLORS["accent"],
            troughcolor=COLORS["field"],
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 8),
        )

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="Body.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="SM3 SOUND EDITOR", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "Direct fixed-slot PCSSB replacement + dialogue-preserving Music Replacement Mode. "
                "Original PCSSB files are never modified."
            ),
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

        setup = ttk.Frame(self, style="Card.TFrame", padding=10)
        setup.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="PCSSB sound bank", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.bank_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self._button(setup, "Browse", self.browse_bank).grid(row=0, column=2, padx=4, pady=4)
        self._button(setup, "LOAD BANK", self.load_bank, accent=True).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(setup, text="Output folder", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.output_var).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self._button(setup, "Browse", self.browse_output).grid(row=1, column=2, padx=4, pady=4)
        self._button(setup, "Open Output", self.open_output).grid(row=1, column=3, padx=4, pady=4)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew")

        left = ttk.Frame(body, style="Card.TFrame", padding=10)
        right = ttk.Frame(body, style="Card.TFrame", padding=10)
        body.add(left, weight=3)
        body.add(right, weight=2)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        ttk.Label(left, text="Sounds detected in PCSSB", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 7))
        columns = ("num", "name", "fsb", "audio", "size", "type", "rate", "ch")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        headings = {
            "num": "#", "name": "Sound Name", "fsb": "FSB3 Offset", "audio": "Audio Offset",
            "size": "Slot Bytes", "type": "Audio Type", "rate": "Hz", "ch": "Ch",
        }
        widths = {"num": 42, "name": 230, "fsb": 105, "audio": 105, "size": 105, "type": 125, "rate": 75, "ch": 45}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=35, stretch=(col in {"name", "type"}))
        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        action_row = ttk.Frame(left, style="Card.TFrame")
        action_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(action_row, "EXTRACT SELECTED", self.extract_selected).pack(side="left", padx=(0, 6))
        self._button(action_row, "EXPORT FOR AUDIO SEPARATOR", self.export_for_separator).pack(side="left", padx=6)
        self._button(action_row, "PREVIEW SELECTED", self.preview_selected).pack(side="left", padx=6)

        ttk.Label(right, text="Selected Sound", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right, textvariable=self.selected_var, style="CardLabel.TLabel", wraplength=545, justify="left").grid(
            row=1, column=0, sticky="ew", pady=(5, 8)
        )

        self.mode_tabs = ttk.Notebook(right)
        self.mode_tabs.grid(row=2, column=0, sticky="nsew")
        direct = self._make_scrollable_mode_page("Direct Audio Replace")
        music = self._make_scrollable_mode_page("Music Replacement")
        log_frame = ttk.Frame(self.mode_tabs, style="Card.TFrame", padding=8)
        self.mode_tabs.add(log_frame, text="Log")
        self._build_direct_mode(direct)
        self._build_music_mode(music)

        # The log used to sit below the mode notebook and was clipped on laptop
        # displays. Keeping it as a third mode page preserves every message while
        # giving Direct/Music the full available vertical space.
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            height=6,
            wrap="word",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            relief="flat",
            font=("Consolas", 9),
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self._log("Sound Editor ready. Load an SM3 .pcssb bank to scan 0x8000-aligned FSB3 sound slots.")

    def _make_scrollable_mode_page(self, title: str):
        """Create a notebook page whose controls stay reachable on short screens."""
        host = ttk.Frame(self.mode_tabs, style="Card.TFrame")
        host.rowconfigure(0, weight=1)
        host.columnconfigure(0, weight=1)
        canvas = tk.Canvas(
            host,
            highlightthickness=0,
            borderwidth=0,
            bg=COLORS["panel"],
        )
        scroll = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        inner = ttk.Frame(canvas, style="Card.TFrame", padding=10)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def sync(_event=None):
            try:
                canvas.itemconfigure(window, width=max(1, canvas.winfo_width()))
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass

        inner.bind("<Configure>", sync, add="+")
        canvas.bind("<Configure>", sync, add="+")
        self.mode_tabs.add(host, text=title)
        return inner

    def _build_direct_mode(self, parent):
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="Replacement audio", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w")
        rep_row = ttk.Frame(parent, style="Card.TFrame")
        rep_row.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        rep_row.columnconfigure(0, weight=1)
        self._entry(rep_row, self.replacement_var).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._button(rep_row, "Browse", self.browse_replacement).grid(row=0, column=1)

        self.validation_var = tk.StringVar(value="Choose a sound and replacement audio.")
        ttk.Label(parent, textvariable=self.validation_var, style="Muted.TLabel", wraplength=520, justify="left").grid(
            row=2, column=0, sticky="ew", pady=(0, 8)
        )
        self._button(parent, "VALIDATE REPLACEMENT", self.validate_selected).grid(row=3, column=0, sticky="ew", pady=3)
        self._button(parent, "REPLACE SELECTED -> NEW PCSSB", self.replace_selected, accent=True).grid(
            row=4, column=0, sticky="ew", pady=3
        )
        ttk.Label(
            parent,
            text=(
                "Universal route for the SM3 PCSSB banks verified so far. Raw MPEG slots use safe fixed-slot replacement; "
                "Xbox IMA ADPCM slots automatically convert normal audio to the game's 0x24-byte/64-sample frame format. "
                "No sound name is hardcoded and the original PCSSB is never modified."
            ),
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=5, column=0, sticky="ew", pady=(8, 0))

    def _build_music_mode(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(
            parent,
            text=(
                "STEP 1: use SM3 Audio Separator on the extracted game audio. STEP 2: put its *_DIALOGUE.wav here. "
                "STEP 3: choose your new music, preview, then build. The Toolkit does not perform AI separation itself."
            ),
            style="Muted.TLabel",
            wraplength=520,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        ttk.Label(parent, text="Voice / dialogue stem (*_DIALOGUE.wav)", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        self._entry(parent, self.voice_stem_var).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        self._button(parent, "Browse", self.browse_voice_stem).grid(row=1, column=2, pady=3)

        ttk.Label(parent, text="New music", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        self._entry(parent, self.music_file_var).grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        self._button(parent, "Browse", self.browse_music_file).grid(row=2, column=2, pady=3)

        ttk.Label(parent, text="Voice volume %", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", pady=2)
        self._scale(parent, self.voice_volume_var).grid(row=3, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(parent, text="Music volume %", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", pady=2)
        self._scale(parent, self.music_volume_var).grid(row=4, column=1, columnspan=2, sticky="ew", pady=2)

        options = ttk.Frame(parent, style="Card.TFrame")
        options.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 6))
        ttk.Checkbutton(options, text="Loop music to voice-stem length", variable=self.loop_music_var).pack(side="left")
        ttk.Label(options, text="MP3 bitrate:", style="CardLabel.TLabel").pack(side="left", padx=(14, 5))
        ttk.Combobox(
            options,
            textvariable=self.bitrate_var,
            values=("Auto safe", "320 kbps", "256 kbps", "224 kbps", "192 kbps", "160 kbps", "128 kbps", "112 kbps", "96 kbps", "80 kbps", "64 kbps"),
            state="readonly",
            width=11,
        ).pack(side="left")

        ttk.Label(parent, textvariable=self.mix_status_var, style="Muted.TLabel", wraplength=520, justify="left").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6)
        )

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=7, column=0, columnspan=3, sticky="ew")
        self._button(actions, "PREVIEW MIX", self.preview_music_mix).pack(side="left", padx=(0, 5))
        self._button(actions, "BUILD MIX ONLY", self.build_music_mix_only).pack(side="left", padx=5)
        self._button(actions, "BUILD MIX + NEW PCSSB", self.build_music_and_pcssb, accent=True).pack(side="left", padx=5)

        support = ttk.Frame(parent, style="Card.TFrame")
        support.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(9, 0))
        support.columnconfigure(0, weight=1)
        ttk.Label(
            support,
            textvariable=self.audio_support_var,
            style="Muted.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.audio_install_button = self._button(
            support, "INSTALL / REPAIR AUDIO SUPPORT", self.install_audio_support
        )
        self.audio_install_button.grid(row=0, column=1, sticky="e")

    def refresh_audio_support_status(self):
        ok, detail = audio_support_status()
        if ok:
            self.audio_support_var.set(f"Audio support READY: {Path(detail).name}")
        else:
            self.audio_support_var.set("Audio support not installed. Direct PCSSB tools still work.")

    def install_audio_support(self):
        try:
            self.audio_install_button.configure(state="disabled")
        except Exception:
            pass
        self.audio_support_var.set("Installing audio support into the Python that is running this toolkit...")
        self._set_status("Sound Editor: installing Music Replacement audio support...")

        def worker():
            try:
                ffmpeg = install_audio_support_current_python()
            except Exception as exc:
                self.after(0, lambda: self._audio_install_finished(False, str(exc)))
                return
            self.after(0, lambda: self._audio_install_finished(True, ffmpeg))

        threading.Thread(target=worker, daemon=True).start()

    def _audio_install_finished(self, ok: bool, detail: str):
        try:
            self.audio_install_button.configure(state="normal")
        except Exception:
            pass
        if ok:
            self.audio_support_var.set(f"Audio support READY: {Path(detail).name}")
            self._set_status("Sound Editor: Music Replacement audio support is ready.")
            messagebox.showinfo(
                "Sound Editor Audio Support",
                "SUCCESS - Music Replacement audio support is ready.\n\n"
                f"FFmpeg: {detail}\n\n"
                "No separate Python detection was used; the toolkit installed it into the interpreter currently running SM3 Toolkit.",
            )
        else:
            self.audio_support_var.set("Audio support install failed. See the error for details.")
            self._set_status("Sound Editor: audio support installation failed.")
            messagebox.showerror("Sound Editor Audio Support", detail)

    def _log(self, text: str):
        try:
            self.log.insert("end", text + "\n")
            self.log.see("end")
        except Exception:
            pass

    def browse_bank(self):
        path = filedialog.askopenfilename(
            title="Open SM3 PCSSB",
            filetypes=[("SM3 PCSSB", "*.pcssb *.PCSSB *.MOD"), ("All files", "*.*")],
        )
        if path:
            self.bank_var.set(path)
            if not self.output_var.get().strip():
                self.output_var.set(str(Path(path).parent / "SM3_SOUND_EDITOR_OUTPUT"))

    def browse_replacement(self):
        path = filedialog.askopenfilename(
            title="Choose replacement audio",
            filetypes=[("Audio / raw", "*.mp3 *.wav *.bin *.dat"), ("All files", "*.*")],
        )
        if path:
            self.replacement_var.set(path)
            self.validate_selected(silent=True)

    def browse_voice_stem(self):
        path = filedialog.askopenfilename(
            title="Choose *_DIALOGUE.wav from SM3 Audio Separator",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac"), ("All files", "*.*")],
        )
        if path:
            self.voice_stem_var.set(path)
            self.mix_status_var.set("Voice stem selected. Choose new music and preview/build the mix.")

    def browse_music_file(self):
        path = filedialog.askopenfilename(
            title="Choose new music",
            filetypes=[("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac"), ("All files", "*.*")],
        )
        if path:
            self.music_file_var.set(path)
            self.mix_status_var.set("New music selected. PREVIEW MIX is recommended before building the PCSSB.")

    def browse_output(self):
        path = filedialog.askdirectory(title="Choose Sound Editor output folder")
        if path:
            self.output_var.set(path)

    def load_bank(self):
        try:
            path = Path(self.bank_var.get().strip())
            self.entries = scan_pcssb(path)
            for item in self.tree.get_children():
                self.tree.delete(item)
            for e in self.entries:
                self.tree.insert("", "end", iid=str(e.index), values=(
                    e.index + 1, e.name, f"0x{e.fsb_offset:08X}", f"0x{e.audio_offset:08X}",
                    f"{e.slot_size:,}", e.audio_type, e.sample_rate or "-", e.channels or "-",
                ))
            self.selected_var.set("Selected: none")
            self.validation_var.set("Choose a sound and replacement audio.")
            self.mix_status_var.set("Select a sound, a dialogue/voice stem, and new music.")
            self._set_status(f"Sound Editor: loaded {len(self.entries)} FSB3 sound slots from {path.name}.")
        except Exception as exc:
            self.entries = []
            messagebox.showerror("Sound Editor", str(exc))
            self._set_status(f"Sound Editor load failed: {exc}")

    def _selected_entry(self) -> SoundEntry:
        selection = self.tree.selection()
        if not selection:
            raise SoundEditorError("Select a sound first.")
        idx = int(selection[0])
        if idx < 0 or idx >= len(self.entries):
            raise SoundEditorError("Selected sound is no longer valid. Reload the bank.")
        return self.entries[idx]

    def _on_select(self, _event=None):
        try:
            e = self._selected_entry()
            self.selected_var.set(
                f"{e.name}\nFSB3: 0x{e.fsb_offset:08X}   Audio: 0x{e.audio_offset:08X}\n"
                f"Slot: {e.slot_size:,} bytes   Type: {e.audio_type}   Rate: {e.sample_rate or '?'} Hz   Channels: {e.channels or '?'}"
            )
            self.validate_selected(silent=True)
            if e.codec == "xbox_ima":
                self.mix_status_var.set(
                    f"{e.name} is an Xbox IMA music slot. Use Direct Audio Replace: choose MP3/WAV/FLAC/etc. and the toolkit auto-converts it."
                )
            else:
                self.mix_status_var.set(
                    f"Music mode target: {e.name} | {e.slot_size:,} byte slot | {e.sample_rate or '?'} Hz | {e.channels or '?'} ch"
                )
        except Exception:
            pass

    def validate_selected(self, silent=False):
        try:
            e = self._selected_entry()
            rep = Path(self.replacement_var.get().strip())
            size, pad, kind = validate_replacement(self.bank_var.get().strip(), e, rep)
            self.validation_var.set(
                f"PASS: {kind} | replacement {size:,} / slot {e.slot_size:,} bytes | zero padding {pad:,} bytes"
            )
            if not silent:
                self._set_status(f"Replacement fits {e.name}: {size:,} bytes, {pad:,} bytes padding.")
            return True
        except Exception as exc:
            self.validation_var.set(f"NOT READY: {exc}")
            if not silent:
                messagebox.showwarning("Sound Editor validation", str(exc))
                self._set_status(f"Sound Editor validation: {exc}")
            return False

    def _suggest_extract_name(self, entry: SoundEntry) -> str:
        base = Path(entry.name).stem or f"sound_{entry.index+1:03d}"
        if entry.codec == "xbox_ima":
            ext = ".wav"
        elif entry.audio_type.startswith("MPEG") or entry.audio_type.startswith("MP3"):
            ext = ".mp3"
        elif entry.audio_type.startswith("WAV"):
            ext = ".wav"
        elif entry.audio_type.startswith("Ogg"):
            ext = ".ogg"
        elif entry.audio_type == "FLAC":
            ext = ".flac"
        else:
            ext = ".bin"
        return base + "_extracted" + ext

    def extract_selected(self):
        try:
            e = self._selected_entry()
            out = filedialog.asksaveasfilename(
                title="Extract selected sound",
                initialfile=self._suggest_extract_name(e),
                defaultextension="",
            )
            if not out:
                return
            path = extract_entry(self.bank_var.get().strip(), e, out)
            self._set_status(f"Extracted {e.name} -> {path}")
        except Exception as exc:
            messagebox.showerror("Extract sound", str(exc))
            self._set_status(f"Sound extraction failed: {exc}")

    def export_for_separator(self):
        """One-click handoff file for the standalone SM3 Audio Separator companion tool."""
        try:
            e = self._selected_entry()
            out_dir = self._output_dir()
            base = Path(e.name).stem or f"sound_{e.index+1:03d}"
            suggested = self._suggest_extract_name(e)
            ext = Path(suggested).suffix or ".bin"
            output = out_dir / f"{base}_FOR_AUDIO_SEPARATOR{ext}"
            path = extract_entry(self.bank_var.get().strip(), e, output)
            self._set_status(f"Audio Separator handoff created: {path.name}")
            messagebox.showinfo(
                "Sound Editor -> SM3 Audio Separator",
                f"Extracted:\n{path}\n\n"
                "NEXT:\n"
                "1. Open SM3 Audio Separator.\n"
                "2. Use this file as Input Audio.\n"
                "3. Click SEPARATE DIALOGUE / MUSIC.\n"
                "4. Come back here and use the generated *_DIALOGUE.wav in Music Replacement."
            )
        except Exception as exc:
            messagebox.showerror("Export for Audio Separator", str(exc))
            self._set_status(f"Audio Separator export failed: {exc}")

    def preview_selected(self):
        try:
            e = self._selected_entry()
            preview_dir = Path(tempfile.gettempdir()) / "SM3_TOOLKIT_SOUND_PREVIEW"
            preview_dir.mkdir(parents=True, exist_ok=True)
            out = preview_dir / self._suggest_extract_name(e)
            extract_entry(self.bank_var.get().strip(), e, out)
            open_path(out)
            self._set_status(f"Opened preview for {e.name} using the system audio player.")
        except Exception as exc:
            messagebox.showerror("Preview sound", str(exc))
            self._set_status(f"Sound preview failed: {exc}")

    def _output_dir(self) -> Path:
        raw = self.output_var.get().strip()
        if not raw:
            raise SoundEditorError("Choose an output folder.")
        out = Path(raw)
        out.mkdir(parents=True, exist_ok=True)
        return out

    def replace_selected(self):
        try:
            e = self._selected_entry()
            if not self.validate_selected(silent=True):
                raise SoundEditorError(self.validation_var.get().replace("NOT READY: ", "", 1))
            source = Path(self.bank_var.get().strip())
            out_dir = self._output_dir()
            suffix = source.suffix if source.suffix.lower() == ".pcssb" else ".pcssb"
            output = out_dir / f"{source.stem}_SOUND_MOD{suffix}"
            result = replace_entry(source, e, self.replacement_var.get().strip(), output)
            self.last_output = result.output_path
            self.validation_var.set(
                f"BUILT: {result.replacement_size:,} bytes written + {result.padded_bytes:,} zero padding. "
                f"PCSSB stayed {result.output_size:,} bytes."
            )
            self._set_status(f"Sound Editor built: {result.output_path.name}")
            self._log(f"SHA256: {result.output_sha256}")
            messagebox.showinfo(
                "Sound Editor - Success",
                f"New PCSSB created successfully.\n\nSound: {e.name}\nReplacement: {result.replacement_size:,} bytes\n"
                f"Zero padding: {result.padded_bytes:,} bytes\nPCSSB size: {result.output_size:,} bytes (unchanged)\n\n{result.output_path}"
            )
        except Exception as exc:
            messagebox.showerror("Replace sound", str(exc))
            self._set_status(f"Sound replacement failed: {exc}")

    def _selected_bitrate(self) -> int | None:
        text = self.bitrate_var.get().strip()
        if not text or text.lower().startswith("auto"):
            return None
        try:
            return int(text.split()[0])
        except Exception as exc:
            raise SoundEditorError(f"Invalid bitrate selection: {text}") from exc

    def _mix_output_name(self, entry: SoundEntry, preview=False) -> str:
        base = Path(entry.name).stem or f"sound_{entry.index+1:03d}"
        return f"{base}_{'MUSIC_PREVIEW' if preview else 'MUSIC_MIX'}.mp3"

    def _create_music_mix(self, *, preview=False):
        e = self._selected_entry()
        source = Path(self.bank_var.get().strip())
        voice = Path(self.voice_stem_var.get().strip())
        music = Path(self.music_file_var.get().strip())
        if preview:
            out_dir = Path(tempfile.gettempdir()) / "SM3_TOOLKIT_MUSIC_PREVIEW"
            out_dir.mkdir(parents=True, exist_ok=True)
        else:
            out_dir = self._output_dir()
        output = out_dir / self._mix_output_name(e, preview=preview)
        self.mix_status_var.set("Building dialogue + new music mix with FFmpeg...")
        self.update_idletasks()
        result = build_music_mix(
            source,
            e,
            voice,
            music,
            output,
            voice_volume_percent=self.voice_volume_var.get(),
            music_volume_percent=self.music_volume_var.get(),
            loop_music=self.loop_music_var.get(),
            bitrate_kbps=self._selected_bitrate(),
        )
        self.last_mix = result.output_path
        self.mix_status_var.set(
            f"PASS: {result.bitrate_kbps} kbps raw MP3 | {result.output_size:,} / {e.slot_size:,} bytes | "
            f"padding {result.padded_bytes:,} | {result.duration_seconds:.2f}s"
        )
        self._log(
            f"Music mix: {e.name} | voices {result.voice_volume_percent}% | music {result.music_volume_percent}% | "
            f"{result.bitrate_kbps} kbps | {result.output_size:,} bytes"
        )
        return result

    def preview_music_mix(self):
        try:
            result = self._create_music_mix(preview=True)
            open_path(result.output_path)
            self._set_status(
                f"Music preview ready for {result.entry.name}: voices {result.voice_volume_percent}% + music {result.music_volume_percent}%."
            )
        except Exception as exc:
            messagebox.showerror("Music Replacement - Preview", str(exc))
            self.mix_status_var.set(f"NOT READY: {exc}")
            self._set_status(f"Music preview failed: {exc}")

    def build_music_mix_only(self):
        try:
            result = self._create_music_mix(preview=False)
            self.replacement_var.set(str(result.output_path))
            self.validate_selected(silent=True)
            self._set_status(f"Music mix built: {result.output_path.name}")
            messagebox.showinfo(
                "Music Replacement - Mix Ready",
                f"Music mix created successfully.\n\nSound: {result.entry.name}\nDuration: {result.duration_seconds:.2f}s\n"
                f"Bitrate: {result.bitrate_kbps} kbps\nMix size: {result.output_size:,} bytes\n"
                f"Room left in slot: {result.padded_bytes:,} bytes\n\n{result.output_path}\n\n"
                "The mix was also loaded into Direct Audio Replace as the current replacement."
            )
        except Exception as exc:
            messagebox.showerror("Music Replacement", str(exc))
            self.mix_status_var.set(f"NOT READY: {exc}")
            self._set_status(f"Music mix failed: {exc}")

    def build_music_and_pcssb(self):
        try:
            mix = self._create_music_mix(preview=False)
            source = Path(self.bank_var.get().strip())
            out_dir = self._output_dir()
            suffix = source.suffix if source.suffix.lower() == ".pcssb" else ".pcssb"
            output = out_dir / f"{source.stem}_MUSIC_MOD{suffix}"
            replaced = replace_entry(source, mix.entry, mix.output_path, output)
            self.last_output = replaced.output_path
            self.replacement_var.set(str(mix.output_path))
            self.validation_var.set(
                f"MUSIC MIX BUILT: {mix.output_size:,} bytes + {mix.padded_bytes:,} zero padding. "
                f"PCSSB stayed {replaced.output_size:,} bytes."
            )
            self._set_status(f"Music Replacement built: {replaced.output_path.name}")
            self._log(f"Music PCSSB SHA256: {replaced.output_sha256}")
            messagebox.showinfo(
                "Music Replacement - Success",
                f"Dialogue-preserving music PCSSB created successfully.\n\n"
                f"Sound: {mix.entry.name}\nVoice volume: {mix.voice_volume_percent}%\nMusic volume: {mix.music_volume_percent}%\n"
                f"Bitrate: {mix.bitrate_kbps} kbps\nMix: {mix.output_size:,} bytes\nZero padding: {mix.padded_bytes:,} bytes\n"
                f"PCSSB size: {replaced.output_size:,} bytes (unchanged)\n\nMix file:\n{mix.output_path}\n\nPCSSB:\n{replaced.output_path}"
            )
        except Exception as exc:
            messagebox.showerror("Music Replacement", str(exc))
            self.mix_status_var.set(f"NOT READY: {exc}")
            self._set_status(f"Music Replacement failed: {exc}")

    def open_output(self):
        try:
            if self.last_output is not None and self.last_output.exists():
                open_path(self.last_output.parent)
                return
            if self.last_mix is not None and self.last_mix.exists():
                open_path(self.last_mix.parent)
                return
            raw = self.output_var.get().strip()
            if raw and Path(raw).is_dir():
                open_path(Path(raw))
                return
            raise SoundEditorError("Output folder does not exist yet.")
        except Exception as exc:
            messagebox.showwarning("Open output", str(exc))
