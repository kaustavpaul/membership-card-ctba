"""
Streamlit Cloud entrypoint.

Streamlit Cloud defaults to running `streamlit_app.py` (if present). Our CLI lives in `app.py`,
and the Streamlit UI lives in `ui.py`, so this file simply imports and runs the UI script.
"""

import streamlit as st

try:
    # Importing `ui` executes the Streamlit app.
    import ui  # noqa: F401
except Exception as e:
    # If something goes wrong during import, Streamlit can sometimes show a blank page.
    # Render the exception explicitly so debugging is possible on Streamlit Cloud.
    st.error("App failed to start. See details below.")
    st.exception(e)

