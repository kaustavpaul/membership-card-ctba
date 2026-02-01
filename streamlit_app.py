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
    # Importing `ui` executes the Streamlit app.
    _log("importing ui")
    import ui  # noqa: F401
    _log("imported ui")
except Exception as e:
    # If something goes wrong during import, Streamlit can sometimes show a blank page.
    # Render the exception explicitly so debugging is possible on Streamlit Cloud.
    st.error("App failed to start. See details below.")
    st.exception(e)
    _log(f"startup failed: {type(e).__name__}")

