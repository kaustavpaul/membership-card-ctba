"""
Streamlit Cloud entrypoint.

Streamlit Cloud defaults to running `streamlit_app.py` (if present). Our CLI lives in `app.py`,
and the Streamlit UI lives in `ui.py`, so this file simply imports and runs the UI script.
"""

import time
_T0 = time.perf_counter()

def _log(msg: str) -> None:
    # Streamlit Cloud captures stdout in logs.
    print(f"[startup] +{time.perf_counter() - _T0:.3f}s {msg}", flush=True)

_log("streamlit_app.py start")

import streamlit as st
_log("imported streamlit")

try:
    # Import the local ui.py explicitly (avoid name collisions with any installed "ui" package).
    _log("loading local ui.py")
    import importlib.util
    import sys
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    ui_path = app_dir / "ui.py"
    if not ui_path.exists():
        raise FileNotFoundError(f"Missing ui.py at {ui_path}")

    spec = importlib.util.spec_from_file_location("ctba_ui", ui_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec for {ui_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _log(f"loaded ui from {ui_path}")
except Exception as e:
    # If something goes wrong during import, Streamlit can sometimes show a blank page.
    # Render the exception explicitly so debugging is possible on Streamlit Cloud.
    st.error("App failed to start. See details below.")
    st.exception(e)
    _log(f"startup failed: {type(e).__name__}")

