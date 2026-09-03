from __future__ import annotations

import os
from pathlib import Path
import sys
import traceback


def _write_startup_error() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    out = local_app_data / "SM3 Toolkit" / "Toolkit" / "Logs" / "startup-error.log"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(traceback.format_exc(), encoding="utf-8")
    return out


def _show_startup_error(error_file: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "SM3 Toolkit startup error",
            "The Toolkit could not start. Make sure the complete release folder was extracted."
            f"\n\nTechnical details were saved to:\n{error_file}",
        )
        root.destroy()
    except Exception:
        pass


try:
    from sm3_toolkit.app import APP_NAME, APP_VERSION, SM3ToolsApp, main
except Exception:
    error_file = _write_startup_error()
    if getattr(sys, "frozen", False):
        _show_startup_error(error_file)
        raise SystemExit(1)
    raise


__all__ = ["APP_NAME", "APP_VERSION", "SM3ToolsApp", "main"]


if __name__ == "__main__":
    if "--verify-runtime" in sys.argv:
        raise SystemExit(0)
    try:
        main()
    except Exception:
        error_file = _write_startup_error()
        _show_startup_error(error_file)
        if not getattr(sys, "frozen", False):
            raise
