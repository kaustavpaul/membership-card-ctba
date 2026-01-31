"""
Streamlit Cloud entrypoint.

Streamlit Cloud defaults to running `streamlit_app.py` (if present). Our CLI lives in `app.py`,
and the Streamlit UI lives in `ui.py`, so this file simply imports and runs the UI script.
"""

# Importing `ui` executes the Streamlit app.
import ui  # noqa: F401

