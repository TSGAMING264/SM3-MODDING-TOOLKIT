from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "SM3 Audio Separator v1.0.3"
MODELS = ["htdemucs", "htdemucs_ft", "mdx_extra_q"]
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_DIR))
APP_ICON_PATH = RESOURCE_ROOT / "SM3_TOOLKIT.ico"
DEPENDENCIES_DIR = APP_DIR / "Dependencies"

# Keep model/config caches isolated from the main Toolkit when both EXEs share
# one release folder. These defaults also avoid writing beside the executable.
_local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
AUDIO_DATA_DIR = _local_app_data / "SM3 Toolkit" / "Audio Separator"
os.environ.setdefault("TORCH_HOME", str(AUDIO_DATA_DIR / "Torch"))
os.environ.setdefault("HF_HOME", str(AUDIO_DATA_DIR / "HuggingFace"))

HOW_TO_GUIDE = r"""SM3 AUDIO SEPARATOR - COMPLETE HOW TO USE GUIDE

WHAT THIS TOOL DOES
This is a companion tool for the SM3 Toolkit Sound Editor. It separates an extracted Spider-Man 3 scene/cutscene audio file into two WAV files:

• *_DIALOGUE.wav = dialogue/voice-focused stem
• *_MUSIC.wav = music/no-vocals stem

The main reason to use it is Music Replacement Mode in the SM3 Toolkit. You keep the dialogue, replace the music, preview the new mix, then build a new PCSSB.

============================================================
STEP 0 - FIRST-TIME SETUP
============================================================
1. Start SM3 Audio Separator.
2. Look at the separator-support message near the top.
3. If it says support is not installed, click:
   INSTALL / REPAIR SEPARATOR SUPPORT
4. The Windows release already includes Demucs and its required audio runtime.
5. The selected separation model is downloaded automatically on first use.
6. Keep an internet connection available until the first model download finishes.

If support is already marked READY, you do not need to install it again.

============================================================
STEP 1 - EXPORT AUDIO FROM SM3 TOOLKIT
============================================================
1. Open the main SM3 Toolkit.
2. Open Sound Editor.
3. Load the .pcssb bank that contains the scene/cutscene audio you want to edit.
4. Select the sound entry.
5. Click EXPORT FOR AUDIO SEPARATOR.
6. Remember where you saved the exported audio file.

The separator also accepts normal supported audio files:
.wav  .mp3  .flac  .ogg  .m4a  .aac  .wma

============================================================
STEP 2 - CHOOSE THE AUDIO IN THIS TOOL
============================================================
1. Under STEP 1 - Extracted SM3 audio, click Browse.
2. Select the audio you exported from the SM3 Toolkit.
3. The selected file path appears in the box.
4. Click Preview if you want to hear/open the original extracted audio before separating it.

If you selected the file first, the tool automatically suggests an SM3_AUDIO_SEPARATOR_OUTPUT folder beside it.

============================================================
STEP 3 - CHOOSE THE OUTPUT FOLDER
============================================================
1. Under STEP 2 - Output folder, click Browse.
2. Choose where the separated files should be saved.
3. Click Open at any time to open that folder in File Explorer.

============================================================
STEP 4 - CHOOSE A SEPARATION MODEL
============================================================
htdemucs
Recommended normal/default choice. Start with this model. It provides a good balance for most dialogue/music separation.

htdemucs_ft
A fine-tuned Demucs model. Try this when htdemucs does not separate a difficult scene cleanly enough. It can take longer and may require an additional model download the first time.

mdx_extra_q
Another model option. Use it as an alternate attempt if the Demucs models leave too much music in the dialogue or remove too much voice.

There is no single perfect model for every cutscene. Preview the result and keep the version that sounds best.

============================================================
STEP 5 - SEPARATE DIALOGUE AND MUSIC
============================================================
1. Make sure the input audio and output folder are selected.
2. Leave the model on htdemucs for your first attempt.
3. Click SEPARATE DIALOGUE / MUSIC.
4. The status bar/log will show that Demucs is running.
5. Do not close the tool while separation is running.
6. When finished, the tool fills in three result paths.

The first run can take longer because the selected AI model may need to download.

============================================================
STEP 6 - UNDERSTAND THE RESULTS
============================================================
DIALOGUE - USE THIS IN SM3 TOOLKIT
This is the important output for music replacement. It is saved as:
*_DIALOGUE.wav

Click Preview to listen to it. You want the spoken dialogue to remain as clean as possible while most of the original music is removed.

Click Copy Path to copy the dialogue WAV path to your clipboard.

ORIGINAL MUSIC / NO-VOCALS STEM
This is saved as:
*_MUSIC.wav

It contains the separated original music/no-vocals side. Preview it if you want to compare what the AI removed from the dialogue track.

RAW MODEL OUTPUT
Demucs creates its own model output folder containing the original stems. Click Open to inspect that folder. The easy-to-use *_DIALOGUE.wav and *_MUSIC.wav copies are also placed directly in your chosen output folder.

============================================================
STEP 7 - RETURN TO SM3 TOOLKIT
============================================================
1. Open SM3 Toolkit again.
2. Go to Sound Editor.
3. Open Music Replacement.
4. For Voice / Dialogue Stem, choose the *_DIALOGUE.wav created by this tool.
5. For New Music, choose the song/music file you want to put into the scene.
6. Click PREVIEW MIX.
7. Listen carefully to the entire result.
8. Adjust your replacement music if needed.
9. When the mix sounds right, click BUILD MIX + NEW PCSSB.
10. Use the newly built PCSSB according to the normal SM3 Toolkit mod workflow.

============================================================
WHAT EACH BUTTON DOES
============================================================
Browse (input)
Chooses the extracted SM3 audio file to separate.

Preview (input)
Opens/plays the selected original input audio using your system's normal audio player.

Browse (output)
Chooses the folder where results will be saved.

Open (output)
Opens the selected output folder.

INSTALL / REPAIR SEPARATOR SUPPORT
Installs or repairs Demucs and the Python audio dependencies needed by this tool. Use this if separator support is missing or damaged.

SEPARATE DIALOGUE / MUSIC
Runs the selected AI model and creates the dialogue and music stems.

Preview (Dialogue)
Plays the generated *_DIALOGUE.wav.

Copy Path
Copies the generated dialogue file path so it is easy to find/use in the SM3 Toolkit.

Preview (Music)
Plays the generated *_MUSIC.wav.

Open (Raw model output)
Opens the detailed Demucs output folder.

HOW TO USE
Opens this complete guide.

============================================================
IMPORTANT TIPS
============================================================
• Always preview the *_DIALOGUE.wav before using it.
• AI separation is not perfect. Some music, ambience, sound effects, or artifacts can remain.
• If one model gives a poor result, try another model and compare them.
• Do not delete your original exported audio until your replacement is finished.
• The *_MUSIC.wav file is useful for checking what was removed, but Music Replacement primarily needs *_DIALOGUE.wav.
• A clean source file usually gives better separation than an already compressed/re-recorded source.
• This tool does NOT directly edit the PCSSB. The main SM3 Toolkit Sound Editor builds the final replacement PCSSB.

============================================================
COMMON PROBLEMS
============================================================
SEPARATOR SUPPORT NOT INSTALLED
Click INSTALL / REPAIR SEPARATOR SUPPORT. Make sure Python has internet access for the install/model download.

AUDIO FILE NOT FOUND
Use Browse again and select a real existing audio file.

UNSUPPORTED AUDIO FILE
Use one of the supported formats: WAV, MP3, FLAC, OGG, M4A, AAC, or WMA.

SEPARATION FAILS ON FIRST RUN
The model may not have downloaded correctly, Python/Demucs support may need repair, or internet access may have been interrupted. Run INSTALL / REPAIR SEPARATOR SUPPORT and try again.

DIALOGUE STILL HAS MUSIC IN IT
Try htdemucs_ft or mdx_extra_q and compare results. Some scenes cannot be perfectly separated because voices, effects, and music are mixed together in the original game audio.

DIALOGUE SOUNDS DAMAGED / ROBOTIC
Try another model. AI separation can sometimes remove frequencies that belong to both the voice and music.

OUTPUT FILES ARE MISSING
Check the status/log for an error. You can also click Open on the output folder and Open on Raw model output after a successful run.

============================================================
QUICK WORKFLOW
============================================================
SM3 Toolkit Sound Editor
→ EXPORT FOR AUDIO SEPARATOR
→ Open exported audio here
→ Choose output folder
→ htdemucs
→ SEPARATE DIALOGUE / MUSIC
→ Preview *_DIALOGUE.wav
→ Back to SM3 Toolkit
→ Sound Editor → Music Replacement
→ Voice / Dialogue Stem = *_DIALOGUE.wav
→ New Music = your song
→ PREVIEW MIX
→ BUILD MIX + NEW PCSSB
"""

COLORS = {
    "bg": "#16181d",
    "panel": "#1e2128",
    "field": "#111318",
    "fg": "#f0f3f8",
    "muted": "#9aa4b2",
    "accent": "#2979ff",
    "accent_hover": "#4b92ff",
    "button": "#2a2f39",
    "button_hover": "#3a404d",
    "border": "#434a58",
}

class SeparatorError(RuntimeError):
    pass


class _TailBuffer(io.TextIOBase):
    """Small in-memory sink for third-party progress output and error details."""

    def __init__(self, limit: int = 12000):
        super().__init__()
        self.limit = max(1024, int(limit))
        self._text = ""

    def write(self, value: str) -> int:
        value = str(value)
        self._text = (self._text + value)[-self.limit:]
        return len(value)

    def flush(self) -> None:
        return None

    def getvalue(self) -> str:
        return self._text


def open_path(path: str | Path):
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def find_python_candidates() -> list[str]:
    candidates: list[str] = []
    current = Path(sys.executable)
    if current.is_file():
        candidates.append(str(current))
    for name in ("py", "python", "python3"):
        path = shutil.which(name)
        if path:
            candidates.append(path)
    seen = set()
    out = []
    for c in candidates:
        k = c.lower()
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def _run_python_module(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    py = sys.executable
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
    return subprocess.run(
        [py, "-m"] + args,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        creationflags=flags,
    )


def support_status() -> tuple[bool, str]:
    try:
        import demucs  # type: ignore
        import soundfile  # type: ignore  # noqa: F401
        import torch  # type: ignore  # noqa: F401
        if IS_FROZEN:
            return True, "Built-in Demucs audio runtime is available."
        return True, getattr(demucs, "__file__", "Demucs installed")
    except Exception as exc:
        return False, str(exc)


def model_cache_status(model: str) -> tuple[bool, str]:
    """Check local HuggingFace and legacy Torch caches without using the network."""
    if model not in MODELS:
        return False, f"Unknown model: {model}"

    try:
        import yaml  # type: ignore
        from demucs.hf import DEFAULT_NAMESPACE, hf_repo_name  # type: ignore
        from huggingface_hub import hf_hub_download  # type: ignore

        repo_id = f"{DEFAULT_NAMESPACE}/{hf_repo_name(model)}"
        bag_path = hf_hub_download(
            repo_id=repo_id,
            filename=f"{model}.yaml",
            local_files_only=True,
        )
        bag = yaml.safe_load(Path(bag_path).read_text(encoding="utf-8")) or {}
        signatures = list(bag.get("models") or [])
        if signatures:
            for signature in signatures:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=f"{signature}.safetensors",
                    local_files_only=True,
                )
            return True, "HuggingFace model weights are ready."
    except Exception:
        pass

    # Demucs can fall back to its legacy .th catalogue. Recognize those cached
    # weights too so existing users are not incorrectly told to download again.
    try:
        import torch  # type: ignore
        import yaml  # type: ignore
        from demucs.pretrained import REMOTE_ROOT  # type: ignore

        bag_file = Path(REMOTE_ROOT) / f"{model}.yaml"
        files_file = Path(REMOTE_ROOT) / "files.txt"
        bag = yaml.safe_load(bag_file.read_text(encoding="utf-8")) or {}
        signatures = list(bag.get("models") or [])
        catalogue: dict[str, str] = {}
        for line in files_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("root:"):
                catalogue[line.split("-", 1)[0]] = line
        checkpoint_dir = Path(torch.hub.get_dir()) / "checkpoints"
        expected = [checkpoint_dir / catalogue[sig] for sig in signatures if sig in catalogue]
        if expected and len(expected) == len(signatures) and all(path.is_file() for path in expected):
            return True, "Legacy Demucs model weights are ready."
    except Exception:
        pass

    return False, "Model weights have not been downloaded on this PC yet."


def install_support(timeout: int = 3600) -> str:
    if IS_FROZEN:
        ok, detail = support_status()
        if ok:
            return detail
        dependency_hint = (
            f"\n\nWindows prerequisites, when supplied, are in:\n{DEPENDENCIES_DIR}"
            if DEPENDENCIES_DIR.exists()
            else ""
        )
        raise SeparatorError(
            "The compiled release already includes Demucs support. Extract the complete "
            "SM3 Toolkit folder again so the Audio Runtime folder stays beside this EXE."
            + dependency_hint
        )

    # Ensure pip exists
    pip_check = _run_python_module(["pip", "--version"], timeout=120)
    if pip_check.returncode != 0:
        ensure = _run_python_module(["ensurepip", "--upgrade"], timeout=600)
        if ensure.returncode != 0:
            tail = ((ensure.stderr or "") + "\n" + (ensure.stdout or "")).strip()[-1600:]
            raise SeparatorError("Python was found, but pip could not be enabled.\n" + tail)

    install = _run_python_module([
        "pip", "install", "--upgrade",
        "demucs>=4.0.1",
        "soundfile>=0.12.1",
    ], timeout=timeout)
    if install.returncode != 0:
        tail = ((install.stderr or "") + "\n" + (install.stdout or "")).strip()[-2000:]
        raise SeparatorError("Failed to install separator support.\n" + tail)

    ok, detail = support_status()
    if not ok:
        raise SeparatorError("Support installation finished, but Demucs could not be imported yet.\n" + detail)
    return detail


def validate_audio_input(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_file():
        raise SeparatorError(f"Audio file not found: {p}")
    if p.suffix.lower() not in AUDIO_EXTS:
        raise SeparatorError("Choose a supported audio file: .wav .mp3 .flac .ogg .m4a .aac .wma")
    return p


def run_separation(input_audio: str | Path, output_dir: str | Path, model: str) -> tuple[Path, Path, Path]:
    src = validate_audio_input(input_audio)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if model not in MODELS:
        raise SeparatorError(f"Unsupported model: {model}")

    demucs_args = [
        "--two-stems", "vocals",
        "-n", model,
        "-o", str(output_dir),
        str(src),
    ]

    # A frozen PyInstaller EXE cannot safely invoke itself with ``-m demucs``;
    # that would relaunch this GUI. Run the same Demucs entry point in the
    # existing background worker instead. Source builds use this path too.
    output = _TailBuffer()
    try:
        from demucs.separate import main as demucs_main  # type: ignore

        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            demucs_main(demucs_args)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            detail = output.getvalue().strip()[-3000:]
            raise SeparatorError("Demucs separation failed.\n" + detail) from exc
    except Exception as exc:
        detail = output.getvalue().strip()[-3000:]
        message = f"Demucs separation failed: {exc}"
        if detail:
            message += "\n" + detail
        raise SeparatorError(message) from exc

    demucs_out = output_dir / model / src.stem
    vocals = demucs_out / "vocals.wav"
    music = demucs_out / "no_vocals.wav"
    if not vocals.is_file() or not music.is_file():
        raise SeparatorError(
            "Separation finished, but expected output stems were not found.\n"
            f"Expected: {vocals} and {music}"
        )

    dialogue_copy = output_dir / f"{src.stem}_DIALOGUE.wav"
    music_copy = output_dir / f"{src.stem}_MUSIC.wav"
    shutil.copy2(vocals, dialogue_copy)
    shutil.copy2(music, music_copy)
    return dialogue_copy, music_copy, demucs_out


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x700")
        self.minsize(880, 620)
        self.configure(bg=COLORS["bg"])
        try:
            if APP_ICON_PATH.is_file():
                self.iconbitmap(default=str(APP_ICON_PATH))
        except Exception:
            pass
        self._closing = False
        self._separation_active = False
        self.protocol("WM_DELETE_WINDOW", self._close_app)
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.model_var = tk.StringVar(value="htdemucs")
        self.status_var = tk.StringVar(value="Ready.")
        self.support_var = tk.StringVar(value="Checking separator support...")
        self.model_status_var = tk.StringVar(value="Checking selected model...")
        self.dialogue_var = tk.StringVar()
        self.music_var = tk.StringVar()
        self.raw_output_var = tk.StringVar()
        self._build_ui()
        self.after(150, self.refresh_support_status)

    def _entry(self, parent, textvariable):
        return tk.Entry(
            parent, textvariable=textvariable,
            bg=COLORS["field"], fg=COLORS["fg"], insertbackground=COLORS["fg"],
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground=COLORS["border"], highlightcolor=COLORS["accent"],
            font=("Segoe UI", 10),
        )

    def _button(self, parent, text, command, accent=False):
        bg = COLORS["accent"] if accent else COLORS["button"]
        active = COLORS["accent_hover"] if accent else COLORS["button_hover"]
        return tk.Button(
            parent, text=text, command=command, bg=bg, fg=COLORS["fg"],
            activebackground=active, activeforeground=COLORS["fg"], relief="flat", bd=0,
            padx=11, pady=7, font=("Segoe UI", 9, "bold" if accent else "normal"), cursor="hand2",
        )

    def _section(self, parent, title, text):
        wrap = ttk.Frame(parent, style="Card.TFrame", padding=10)
        ttk.Label(wrap, text=title, style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(wrap, text=text, style="Muted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(4, 0))
        return wrap

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Body.TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["panel"])
        style.configure("SectionTitle.TLabel", background=COLORS["panel"], foreground=COLORS["fg"], font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("CardLabel.TLabel", background=COLORS["panel"], foreground=COLORS["fg"], font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["fg"])
        style.configure("TCombobox", fieldbackground=COLORS["field"], background=COLORS["field"], foreground=COLORS["fg"])

        root = ttk.Frame(self, style="Body.TFrame", padding=12)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(5, weight=1)

        head = ttk.Frame(root, style="Body.TFrame")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        title_row = ttk.Frame(head, style="Body.TFrame")
        title_row.pack(fill="x")
        tk.Label(title_row, text="SM3 AUDIO SEPARATOR", bg=COLORS["bg"], fg=COLORS["fg"], font=("Segoe UI", 16, "bold")).pack(side="left", anchor="w")
        self._button(title_row, "HOW TO USE", self.show_how_to, accent=True).pack(side="right")

        tk.Label(
            head,
            text="Companion tool for SM3 Toolkit. Separates an extracted scene/cutscene audio into dialogue and music stems so you can use the dialogue stem in SM3 Toolkit Music Replacement Mode.",
            bg=COLORS["bg"], fg=COLORS["muted"], font=("Segoe UI", 10), justify="left", wraplength=940,
        ).pack(anchor="w", pady=(4, 0))

        setup = ttk.Frame(root, style="Card.TFrame", padding=10)
        setup.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="STEP 1 - Extracted SM3 audio", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.input_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self._button(setup, "Browse", self.browse_input).grid(row=0, column=2, padx=4, pady=4)
        self._button(setup, "Preview", self.preview_input).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(setup, text="STEP 2 - Output folder", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.output_var).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self._button(setup, "Browse", self.browse_output).grid(row=1, column=2, padx=4, pady=4)
        self._button(setup, "Open", self.open_output).grid(row=1, column=3, padx=4, pady=4)

        ttk.Label(setup, text="Separation model", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.model_box = ttk.Combobox(setup, textvariable=self.model_var, values=MODELS, state="readonly", width=16)
        self.model_box.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.model_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh_model_status())
        self.separate_btn = self._button(setup, "SEPARATE DIALOGUE / MUSIC", self.start_separation, accent=True)
        self.separate_btn.grid(row=2, column=3, padx=4, pady=4)

        support = ttk.Frame(root, style="Card.TFrame", padding=10)
        support.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        support.columnconfigure(0, weight=1)
        ttk.Label(support, textvariable=self.support_var, style="Muted.TLabel", wraplength=720, justify="left").grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.install_btn = self._button(support, "INSTALL / REPAIR SEPARATOR SUPPORT", self.install_support_clicked)
        self.install_btn.grid(row=0, column=1, sticky="e")
        ttk.Label(
            support,
            textvariable=self.model_status_var,
            style="Muted.TLabel",
            wraplength=900,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0))

        out = ttk.Frame(root, style="Card.TFrame", padding=10)
        out.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        out.columnconfigure(1, weight=1)
        ttk.Label(out, text="STEP 3 - DIALOGUE (USE THIS IN SM3 TOOLKIT)", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self._entry(out, self.dialogue_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        actions_dialogue = ttk.Frame(out, style="Card.TFrame")
        actions_dialogue.grid(row=0, column=2, padx=4, pady=4)
        self._button(actions_dialogue, "Preview", self.preview_dialogue).pack(side="left", padx=(0, 4))
        self._button(actions_dialogue, "Copy Path", self.copy_dialogue_path).pack(side="left")

        ttk.Label(out, text="Original music / no-vocals stem", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._entry(out, self.music_var).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self._button(out, "Preview", self.preview_music).grid(row=1, column=2, padx=4, pady=4)

        ttk.Label(out, text="Raw model output", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self._entry(out, self.raw_output_var).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        self._button(out, "Open", self.open_raw_output).grid(row=2, column=2, padx=4, pady=4)

        next_step = ttk.Frame(root, style="Card.TFrame", padding=10)
        next_step.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(next_step, text="NEXT: Return to SM3 Toolkit", style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Label(
            next_step,
            text="Sound Editor -> Music Replacement -> Voice / dialogue stem = the *_DIALOGUE.wav above. New music = your replacement song. Then PREVIEW MIX -> BUILD MIX + NEW PCSSB.",
            style="Muted.TLabel", wraplength=900, justify="left"
        ).pack(anchor="w", pady=(4, 0))

        log_frame = ttk.Frame(root, style="Card.TFrame", padding=10)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, wrap="word", bg=COLORS["field"], fg=COLORS["fg"], insertbackground=COLORS["fg"], relief="flat", font=("Consolas", 9))
        yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=yscroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        foot = tk.Label(self, textvariable=self.status_var, bg=COLORS["bg"], fg=COLORS["muted"], anchor="w", padx=12)
        foot.pack(fill="x", side="bottom")

        self._log("SM3 Audio Separator ready.")
        self._log("Workflow: extract a sound from SM3 Toolkit -> separate dialogue/music here -> use *_DIALOGUE.wav back in SM3 Toolkit Music Replacement.")


    def show_how_to(self):
        win = tk.Toplevel(self)
        win.title("SM3 Audio Separator - How To Use")
        win.geometry("900x720")
        win.minsize(700, 520)
        win.configure(bg=COLORS["bg"])
        win.transient(self)

        top = ttk.Frame(win, style="Body.TFrame", padding=(14, 12, 14, 8))
        top.pack(fill="x")
        ttk.Label(top, text="HOW TO USE - COMPLETE GUIDE", style="SectionTitle.TLabel").pack(side="left", anchor="w")
        self._button(top, "CLOSE", win.destroy).pack(side="right")

        body = ttk.Frame(win, style="Card.TFrame", padding=10)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        text = tk.Text(
            body, wrap="word", bg=COLORS["field"], fg=COLORS["fg"],
            insertbackground=COLORS["fg"], relief="flat", bd=0, padx=14, pady=12,
            font=("Segoe UI", 10), spacing1=2, spacing3=4,
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        text.insert("1.0", HOW_TO_GUIDE)
        text.configure(state="disabled")

        win.bind("<Escape>", lambda _e: win.destroy())
        win.focus_set()

    def _log(self, text: str):
        self.log.insert("end", text + "\n")
        self.log.see("end")

    def _set_status(self, text: str):
        self.status_var.set(text)
        self._log(text)

    def _post_to_ui(self, callback) -> None:
        if self._closing:
            return
        try:
            self.after(0, callback)
        except tk.TclError:
            pass

    def _close_app(self) -> None:
        self._closing = True
        self.destroy()

    def refresh_support_status(self):
        ok, detail = support_status()
        if ok:
            self.support_var.set(f"Separator support READY: {detail}")
        else:
            self.support_var.set("Separator support not installed yet. First install may be large and model download happens on first separation run.")
        self.refresh_model_status()

    def refresh_model_status(self):
        model = self.model_var.get().strip()
        cached, detail = model_cache_status(model)
        if cached:
            self.model_status_var.set(f"Model ready: {model}. {detail}")
        else:
            self.model_status_var.set(
                f"First use: {model} model weights are not downloaded yet. "
                "Starting separation will download them; keep this window open and stay connected."
            )

    def browse_input(self):
        path = filedialog.askopenfilename(title="Choose extracted scene audio", filetypes=[("Audio", "*.wav *.mp3 *.flac *.ogg *.m4a *.aac *.wma"), ("All files", "*.*")])
        if path:
            self.input_var.set(path)
            if not self.output_var.get().strip():
                self.output_var.set(str(Path(path).parent / "SM3_AUDIO_SEPARATOR_OUTPUT"))

    def browse_output(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_var.set(path)

    def _open_existing(self, value: str, kind: str):
        p = Path(value.strip())
        if not p.exists():
            raise SeparatorError(f"{kind} does not exist yet.")
        open_path(p)

    def preview_input(self):
        try:
            self._open_existing(self.input_var.get(), "Input audio")
        except Exception as exc:
            messagebox.showwarning("Preview", str(exc))

    def preview_dialogue(self):
        try:
            self._open_existing(self.dialogue_var.get(), "Dialogue stem")
        except Exception as exc:
            messagebox.showwarning("Preview dialogue", str(exc))

    def copy_dialogue_path(self):
        try:
            p = Path(self.dialogue_var.get().strip())
            if not p.is_file():
                raise SeparatorError("Dialogue stem does not exist yet. Run separation first.")
            self.clipboard_clear()
            self.clipboard_append(str(p))
            self.update()
            self._set_status("Dialogue stem path copied. Use this file in SM3 Toolkit -> Sound Editor -> Music Replacement.")
        except Exception as exc:
            messagebox.showwarning("Copy dialogue path", str(exc))

    def preview_music(self):
        try:
            self._open_existing(self.music_var.get(), "Music stem")
        except Exception as exc:
            messagebox.showwarning("Preview music", str(exc))

    def open_output(self):
        try:
            out = self.output_var.get().strip()
            if not out:
                raise SeparatorError("Choose an output folder first.")
            p = Path(out)
            p.mkdir(parents=True, exist_ok=True)
            open_path(p)
        except Exception as exc:
            messagebox.showwarning("Open output", str(exc))

    def open_raw_output(self):
        try:
            self._open_existing(self.raw_output_var.get(), "Raw model output")
        except Exception as exc:
            messagebox.showwarning("Open raw output", str(exc))

    def install_support_clicked(self):
        self.install_btn.configure(state="disabled")
        self.support_var.set("Installing Demucs separator support into the Python currently running this tool...")
        self._set_status("Installing separator support...")

        def worker():
            try:
                detail = install_support()
                self._post_to_ui(lambda value=detail: self._install_done(True, value))
            except Exception as exc:
                detail = str(exc)
                self._post_to_ui(lambda value=detail: self._install_done(False, value))

        threading.Thread(target=worker, daemon=True).start()

    def _install_done(self, ok: bool, detail: str):
        self.install_btn.configure(state="normal")
        if ok:
            self.support_var.set(f"Separator support READY: {detail}")
            self._set_status("Separator support is ready.")
            messagebox.showinfo(
                "SM3 Audio Separator",
                "Separator support installed successfully.\n\n"
                "Note: the first actual separation run may still download the chosen Demucs model."
            )
        else:
            self.support_var.set("Separator support install failed. See error details.")
            self._set_status("Separator support installation failed.")
            messagebox.showerror("SM3 Audio Separator", detail)

    def start_separation(self):
        if self._separation_active:
            messagebox.showinfo("SM3 Audio Separator", "Audio separation is already running.")
            return
        try:
            src = validate_audio_input(self.input_var.get().strip())
            out = self.output_var.get().strip()
            if not out:
                raise SeparatorError("Choose an output folder.")
            out_path = Path(out)
            out_path.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            messagebox.showwarning("SM3 Audio Separator", str(exc))
            self._set_status(f"Not ready: {exc}")
            return

        model = self.model_var.get().strip()
        model_cached, _model_detail = model_cache_status(model)
        self._model_download_expected = not model_cached
        self._separation_active = True
        self.separate_btn.configure(state="disabled")
        if self._model_download_expected:
            first_use_message = (
                f"Downloading separation model for first use: {model}. "
                "This requires internet and may take several minutes. The window will remain responsive."
            )
            self.model_status_var.set(first_use_message)
            self._set_status(first_use_message)
        else:
            self._set_status("Running Demucs separation... this can take time.")

        def worker():
            try:
                dialogue, music, raw = run_separation(src, out_path, model)
                result = (dialogue, music, raw)
                self._post_to_ui(lambda value=result: self._separation_done(True, value))
            except Exception as exc:
                detail = str(exc)
                self._post_to_ui(lambda value=detail: self._separation_done(False, value))

        threading.Thread(target=worker, daemon=True).start()

    def _separation_done(self, ok: bool, detail):
        self._separation_active = False
        self.separate_btn.configure(state="normal")
        if ok:
            dialogue, music, raw = detail
            self.dialogue_var.set(str(dialogue))
            self.music_var.set(str(music))
            self.raw_output_var.set(str(raw))
            self._set_status("Separation complete. Use *_DIALOGUE.wav in SM3 Toolkit Music Replacement Mode.")
            self.refresh_model_status()
            messagebox.showinfo(
                "SM3 Audio Separator",
                "Dialogue/music separation finished successfully.\n\n"
                f"Dialogue stem:\n{dialogue}\n\n"
                f"Music stem:\n{music}\n\n"
                "NEXT: open SM3 Toolkit -> Sound Editor -> Music Replacement.\nUse the *_DIALOGUE.wav file as Voice / Dialogue Stem.\nChoose your replacement song as New Music."
            )
        else:
            self._set_status("Separation failed.")
            if getattr(self, "_model_download_expected", False):
                self.model_status_var.set(
                    "The first-use model download did not complete. Check the internet connection and try again."
                )
                detail = (
                    "The selected separation model was not already downloaded, and its first-use "
                    "download did not complete. Check your internet connection and try again.\n\n" + str(detail)
                )
            messagebox.showerror("SM3 Audio Separator", detail)


if __name__ == "__main__":
    if "--verify-runtime" in sys.argv:
        runtime_ok, _runtime_detail = support_status()
        raise SystemExit(0 if runtime_ok else 2)
    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        log_path = AUDIO_DATA_DIR / "Logs" / "startup-error.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            log_path = None
        try:
            detail = f"\n\nTechnical details were saved to:\n{log_path}" if log_path else ""
            messagebox.showerror(
                APP_TITLE,
                f"The Audio Separator could not start.\n\n{exc}{detail}\n\n"
                "Make sure the complete release folder was extracted.",
            )
        except Exception:
            pass
