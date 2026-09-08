from __future__ import annotations

from pathlib import Path
import traceback


def _write_startup_error() -> Path:
    out = Path(__file__).resolve().parent / "SM3_TOOLKIT_STARTUP_ERROR.txt"
    out.write_text(traceback.format_exc(), encoding="utf-8")
    return out


try:
    from sm3_toolkit.app import APP_NAME, APP_VERSION, SM3ToolsApp, main
except Exception:
    try:
        _write_startup_error()
    finally:
        raise


__all__ = ["APP_NAME", "APP_VERSION", "SM3ToolsApp", "main"]


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_file = _write_startup_error()
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "SM3 Modding Toolkit startup error",
                f"The toolkit could not start.\n\nA traceback was saved to:\n{error_file}",
            )
            root.destroy()
        except Exception:
            pass
        raise
