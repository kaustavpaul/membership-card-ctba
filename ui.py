#!/usr/bin/env python3
"""
Streamlit UI for CTBA Membership Card Generator
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
import traceback
import time

import streamlit as st

import pandas as pd

from config import (
    MAX_INDIVIDUAL_DOWNLOADS,
    PREVIEW_COLUMNS_DESKTOP,
    PREVIEW_COLUMNS_MOBILE,
    PREVIEW_WIDTH_DESKTOP,
    PREVIEW_WIDTH_MOBILE,
    ZIP_SPOOL_MAX_BYTES,
)
from data_loaders import load_members_dataframe, load_members_dataframe_appsheet
from utils import safe_pdf_filename

_UI_DIR = Path(__file__).resolve().parent
_FALLBACK_CSV = Path.home() / "Downloads" / "CTBA Annual Membership Mock Master List - Form Responses 1.csv"

# Startup timing (logged to stdout for Streamlit Cloud logs)
_UI_T0 = time.perf_counter()
def _ui_log(msg: str) -> None:
    print(f"[ui] +{time.perf_counter() - _UI_T0:.3f}s {msg}", flush=True)

_ui_log("ui.py start")

# Page config
st.set_page_config(
    page_title="CTBA Membership Card Generator",
    page_icon="🎴",
    layout="centered"
)

# Simple CSS to keep the app readable on mobile
st.markdown(
    """
<style>
  /* Minimal polish that won't fight Streamlit theme */
  button, input, textarea, select {
    border-radius: 10px !important;
  }
  /* Tighten vertical rhythm a bit */
  .main h1, .main h2, .main h3 {
    margin-top: 0.6rem !important;
    margin-bottom: 0.35rem !important;
  }
  .main p, .main label, .main .stMarkdown {
    margin-bottom: 0.35rem !important;
  }

  .main .block-container {
    max-width: 980px;
    padding-top: 1rem;
    padding-bottom: 2.5rem;
  }
  @media (max-width: 640px) {
    .main .block-container {
      padding-left: 0.75rem;
      padding-right: 0.75rem;
    }
  }
</style>
""",
    unsafe_allow_html=True,
)
_ui_log("rendered CSS/theme")

# --- Header ---
st.markdown(
    """
<div style="margin-top: 0.25rem; margin-bottom: 0.25rem;">
  <div style="font-size: 1.8rem; font-weight: 750; line-height: 1.15;">
    CTBA Membership Card Generator
  </div>
  <div style="font-size: 1.05rem; opacity: 0.8; margin-top: 0.2rem;">
    Generate PDF membership cards with QR codes for CTBA members
  </div>
</div>
""",
    unsafe_allow_html=True,
)
_ui_log("rendered header")

# Sidebar (collapsible in Streamlit UI)
with st.sidebar:
    with st.expander("About", expanded=False):
        st.markdown("**CTBA Membership Card Generator**")
        st.markdown("Built for Central Texas Bengali Association")
        st.markdown("Created by Kaustav Paul")
_ui_log("rendered sidebar")

# Initialize session state
if 'members_df' not in st.session_state:
    st.session_state.members_df = None
if 'banner_path' not in st.session_state:
    st.session_state.banner_path = None
if 'generated_count' not in st.session_state:
    st.session_state.generated_count = 0
if "selected_member_ids" not in st.session_state:
    # Track selection by Member_ID (stable across filtering/search)
    st.session_state.selected_member_ids = []
if "selected_member_ids_widget" not in st.session_state:
    # Widget state for multiselect (must not be directly reassigned after widget instantiates)
    st.session_state.selected_member_ids_widget = []
if "search_term" not in st.session_state:
    # Applied search term (use a form to avoid rerun-per-keystroke)
    st.session_state.search_term = ""
if "generated_items" not in st.session_state:
    # For <=10: list of {name, membership_type, adult, child, img_png_bytes, pdf_bytes, filename}
    st.session_state.generated_items = []
if "generated_zip" not in st.session_state:
    # For >10: {"zip_bytes": bytes, "zip_name": str, "count": int}
    st.session_state.generated_zip = None
if "_tmp_data_path" not in st.session_state:
    st.session_state._tmp_data_path = None
if "_tmp_banner_path" not in st.session_state:
    st.session_state._tmp_banner_path = None
if "_last_appsheet_error" not in st.session_state:
    st.session_state._last_appsheet_error = None

def _reset_loaded_data():
    st.session_state.members_df = None
    st.session_state.selected_member_ids = []
    st.session_state.search_term = ""
    st.session_state.generated_items = []
    st.session_state.generated_zip = None
    # Clean up temp files created from uploads
    for k in ("_tmp_data_path", "_tmp_banner_path"):
        p = st.session_state.get(k)
        if p and isinstance(p, str) and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
        st.session_state[k] = None


# Default the data source to AppSheet API (only on first run)
if "data_source" not in st.session_state:
    st.session_state.data_source = "AppSheet API"

st.subheader("Data source")
_ui_log("before data source radio")
source = st.radio(
    "Choose where to load members from",
    options=["AppSheet API", "Upload file (Excel/CSV)"],
    index=0,
    horizontal=True,
    key="data_source",
    label_visibility="collapsed",
    on_change=_reset_loaded_data,
)
_ui_log("rendered data source section")

# Optional mobile-friendly rendering tweaks
mobile_mode = st.checkbox("Mobile-friendly layout", value=False, help="Reduces multi-column sections for small screens.")

st.markdown("---")

if source == "AppSheet API":
    st.markdown("### AppSheet Access")
    secrets_appsheet = {}
    try:
        secrets_appsheet = dict(st.secrets.get("appsheet", {}))  # type: ignore[attr-defined]
    except Exception:
        secrets_appsheet = {}

    with st.form("appsheet_fetch_form", clear_on_submit=False):
        c1, c2 = st.columns([1, 1])
        with c1:
            appsheet_region = st.text_input("Region", value=secrets_appsheet.get("region", "www.appsheet.com"), help="Usually `www.appsheet.com`.")
            appsheet_table = st.text_input("Table", value=secrets_appsheet.get("table", ""))
        with c2:
            appsheet_app_id = st.text_input("App ID", value=secrets_appsheet.get("app_id", ""))
            # For Streamlit Cloud hosting: keep key in secrets. Only show input if not provided via secrets.
            if secrets_appsheet.get("access_key"):
                st.caption("Using AppSheet access key from Streamlit Secrets.")
                appsheet_key = secrets_appsheet.get("access_key", "")
            else:
                appsheet_key = st.text_input("Access key", value="", type="password")
        fetch = st.form_submit_button("Fetch members")
    if fetch:
        st.session_state._last_appsheet_error = None
        try:
            with st.spinner("Fetching members from AppSheet (can take ~10–30s)…"):
                df = load_members_dataframe_appsheet(
                    app_id=appsheet_app_id,
                    table_name=appsheet_table,
                    application_access_key=appsheet_key,
                    region=appsheet_region,
                    timeout_s=30,
                    max_attempts=2,
                )
            st.session_state.members_df = df
            stats = getattr(df, "attrs", {}).get("load_stats")
            if stats:
                st.success(
                    f"Loaded **{stats.get('loaded_rows', len(df))}** members from AppSheet "
                    f"(source rows: {stats.get('source_rows')}, "
                    f"dropped duplicate member id: {stats.get('dropped_duplicate_member_id', 0)})."
                )
            else:
                st.success(f"Loaded {len(df)} members from AppSheet")
        except (ValueError, RuntimeError, ImportError) as e:
            st.session_state._last_appsheet_error = traceback.format_exc()
            st.error(f"Error fetching from AppSheet: {e}")
        except Exception as e:
            st.session_state._last_appsheet_error = traceback.format_exc()
            st.error(f"Unexpected error fetching from AppSheet: {e}")

    # Always show last error details if present (helps debugging Streamlit Cloud blanks)
    if st.session_state._last_appsheet_error:
        with st.expander("Show AppSheet error details", expanded=False):
            st.code(st.session_state._last_appsheet_error)
else:
    st.markdown("### Upload file (Excel/CSV)")
    st.caption("Uploaded file must match the default template format (same for Excel and CSV).")

    required_columns_order = ["Member ID", "Full Name", "Membership Type", "Adult", "Child"]
    st.markdown("**Required columns (in order):**")
    st.table(pd.DataFrame({"Column (in order)": required_columns_order}))

    def _uploaded_file_matches_required_format(uploaded) -> bool:
        """
        Strict validation: uploaded file must match the default schema.
        Expected columns (case-insensitive) in this exact order as the first 5 columns:
        Member ID, Full Name, Membership Type, Adult, Child.
        Additional columns are allowed after these.
        """
        if uploaded is None:
            return False
        name = (uploaded.name or "").lower()
        try:
            if name.endswith((".xlsx", ".xls")):
                raw = pd.read_excel(uploaded, sheet_name="Sheet1")
                cols = [str(c).strip() for c in raw.columns]
                if len(cols) < len(required_columns_order):
                    return False
                first = [c.lower() for c in cols[: len(required_columns_order)]]
                required = [c.lower() for c in required_columns_order]
                return first == required
            if name.endswith(".csv"):
                raw = pd.read_csv(uploaded)
                cols = [str(c).strip() for c in raw.columns]
                if len(cols) < len(required_columns_order):
                    return False
                first = [c.lower() for c in cols[: len(required_columns_order)]]
                required = [c.lower() for c in required_columns_order]
                return first == required
        except Exception:
            return False
        return False

    with st.form("local_load_form", clear_on_submit=False):
        data_file = st.file_uploader(
            "Upload data (Excel or CSV)",
            type=["csv", "xlsx"],
            help="Excel/CSV must start with these columns (in this order): Member ID, Full Name, Membership Type, Adult, Child.",
        )
        load_uploaded = st.form_submit_button("📥 Load uploaded file")
    if load_uploaded:
        if data_file is None:
            st.warning("Please upload a file first.")
        elif not _uploaded_file_matches_required_format(data_file):
            st.error("The uploaded file doesn't meet the required format.")
        else:
            try:
                # Write to a secure temp file (ignore user-provided filename)
                prev = st.session_state.get("_tmp_data_path")
                if prev and os.path.exists(prev):
                    try:
                        os.remove(prev)
                    except OSError:
                        pass
                suffix = ".xlsx" if str(data_file.name).lower().endswith(".xlsx") else ".csv"
                with tempfile.NamedTemporaryFile(prefix="members_", suffix=suffix, delete=False) as tmp:
                    tmp.write(data_file.getbuffer())
                    st.session_state._tmp_data_path = tmp.name

                df = load_members_dataframe(st.session_state._tmp_data_path)
                st.session_state.members_df = df
                stats = getattr(df, "attrs", {}).get("load_stats")
                if stats:
                    st.success(
                        f"Loaded **{stats.get('loaded_rows', len(df))}** members from **{data_file.name}** "
                        f"(source rows: {stats.get('source_rows')}, "
                        f"skipped missing name: {stats.get('skipped_missing_name', 0)}, "
                        f"skipped missing member id: {stats.get('skipped_missing_member_id', 0)}, "
                        f"dropped duplicate member id: {stats.get('dropped_duplicate_member_id', 0)})."
                    )
                else:
                    st.success(f"Loaded {len(df)} members from {data_file.name}")
            except (ValueError, ImportError, OSError) as e:
                st.error(f"Error reading {data_file.name}: {e}")
            except Exception as e:
                st.error(f"Unexpected error reading {data_file.name}: {e}")

    default_path = str(_UI_DIR / "input" / "template_members.csv")
    if not os.path.exists(default_path) and _FALLBACK_CSV.exists():
        default_path = str(_FALLBACK_CSV)
    if default_path:
        with st.expander("Use default template (advanced)", expanded=False):
            st.caption(f"Default template: `{Path(default_path).name}`")
            if st.button(f"📥 Load default ({Path(default_path).name})"):
                try:
                    df = load_members_dataframe(default_path)
                    st.session_state.members_df = df
                    stats = getattr(df, "attrs", {}).get("load_stats")
                    if stats:
                        st.success(
                            f"Loaded **{stats.get('loaded_rows', len(df))}** members from **{Path(default_path).name}** "
                            f"(source rows: {stats.get('source_rows')}, "
                            f"skipped missing name: {stats.get('skipped_missing_name', 0)}, "
                            f"skipped missing member id: {stats.get('skipped_missing_member_id', 0)}, "
                            f"dropped duplicate member id: {stats.get('dropped_duplicate_member_id', 0)})."
                        )
                    else:
                        st.success(f"Loaded {len(df)} members from {Path(default_path).name}")
                except Exception as e:
                    st.error(f"Error loading default: {e}")
    else:
        st.caption("Default input not found (tried Excel and CSV).")

st.markdown("---")
with st.expander("Banner (optional)", expanded=False):
    st.caption("Default banner is recommended. Expand only if you need to change it.")
    banner_file = st.file_uploader(
        "Upload Banner Image",
        type=["png", "jpg", "jpeg"],
        help="Banner image for the membership cards",
    )
    use_default_banner = st.checkbox("Use default banner", value=True)
    if banner_file is not None:
        # Write banner to a secure temp file (ignore user-provided filename)
        prev = st.session_state.get("_tmp_banner_path")
        if prev and os.path.exists(prev):
            try:
                os.remove(prev)
            except OSError:
                pass
        with tempfile.NamedTemporaryFile(prefix="banner_", suffix=".png", delete=False) as tmp:
            tmp.write(banner_file.getbuffer())
            st.session_state._tmp_banner_path = tmp.name
        st.session_state.banner_path = st.session_state._tmp_banner_path
        st.success("Banner image uploaded")
    elif use_default_banner:
        for name in ("banner.png", "Central Texas Bengali Association Banner.png"):
            p = _UI_DIR / "input" / name
            if p.exists():
                st.session_state.banner_path = str(p)
                break

if st.button("🧼 Clear loaded data"):
    _reset_loaded_data()

# Display member selection interface
if st.session_state.members_df is not None and st.session_state.banner_path is not None:
    df = st.session_state.members_df
    
    st.header("👥 Select Members")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"**Total members:** {len(df)}")
    
    with col2:
        if st.button("✅ Select All", use_container_width=True):
            st.session_state.selected_member_ids = list(df["Member_ID"].astype(str))
        if st.button("❌ Deselect All", use_container_width=True):
            st.session_state.selected_member_ids = []
    
    # Create scrollable table for member selection
    st.markdown("### Member List")
    
    # Search/filter
    with st.form("search_form", clear_on_submit=False):
        s1, s2 = st.columns([4, 1])
        with s1:
            search_term_input = st.text_input(
                "Search members",
                value=st.session_state.search_term,
                placeholder="Search by name or member id…",
                label_visibility="collapsed",
            )
        with s2:
            apply_search = st.form_submit_button("Apply")
    if apply_search:
        st.session_state.search_term = search_term_input.strip()

    search_term = (st.session_state.search_term or "").strip()
    cclear, cinfo = st.columns([1, 3])
    with cclear:
        if st.button("Clear search", use_container_width=True):
            st.session_state.search_term = ""
            search_term = ""
    with cinfo:
        if search_term:
            st.caption(f"Search applied: `{search_term}`")
    if search_term:
        name_mask = df["Name"].astype(str).str.contains(search_term, case=False, na=False)
        id_mask = df["Member_ID"].astype(str).str.contains(search_term, case=False, na=False)
        filtered_df = df[name_mask | id_mask].copy()
    else:
        filtered_df = df.copy()
    
    # Create a scrollable table with checkboxes
    # Build display dataframe with Select column initialized from session state
    for col in ("Membership_Type", "Adult", "Child"):
        if col not in filtered_df.columns:
            filtered_df[col] = ""
    display_df = filtered_df[["Name", "Membership_Type", "Adult", "Child", "Member_ID"]].copy().reset_index(drop=True)
    selected_set = set(map(str, st.session_state.selected_member_ids))
    display_df["Member_ID"] = display_df["Member_ID"].astype(str)
    display_df["Select"] = display_df["Member_ID"].apply(lambda mid: mid in selected_set)
    display_df_for_editor = display_df[["Select", "Name", "Membership_Type", "Adult", "Child", "Member_ID"]].copy()
    baseline_state = dict(zip(display_df["Member_ID"].tolist(), display_df["Select"].tolist()))
    
    st.caption("Scroll to see all members (table has internal scrollbar).")
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("Select filtered", use_container_width=True):
            sel = set(map(str, st.session_state.selected_member_ids))
            sel.update(display_df["Member_ID"].astype(str).tolist())
            st.session_state.selected_member_ids = sorted(sel)
    with b2:
        if st.button("Clear filtered", use_container_width=True):
            sel = set(map(str, st.session_state.selected_member_ids))
            for mid in display_df["Member_ID"].astype(str).tolist():
                sel.discard(mid)
            st.session_state.selected_member_ids = sorted(sel)

    # Selected members (full-width, so more names are visible)
    id_to_name = dict(zip(df["Member_ID"].astype(str), df["Name"].astype(str)))
    # Keep widget state in sync BEFORE creating widget this run
    st.session_state.selected_member_ids_widget = list(st.session_state.selected_member_ids)

    def _sync_multiselect_to_selection():
        st.session_state.selected_member_ids = sorted(set(map(str, st.session_state.selected_member_ids_widget)))

    st.multiselect(
        "Selected members",
        options=df["Member_ID"].astype(str).tolist(),
        default=st.session_state.selected_member_ids,
        format_func=lambda mid: f"{id_to_name.get(mid, '')} ({mid})" if id_to_name.get(mid) else mid,
        key="selected_member_ids_widget",
        on_change=_sync_multiselect_to_selection,
    )
    
    # Configure columns for the data editor
    column_config = {
        "Select": st.column_config.CheckboxColumn("Select", width="small"),
        "Name": st.column_config.TextColumn("Name", width="medium"),
        "Membership_Type": st.column_config.TextColumn("Membership Type", width="medium"),
        "Adult": st.column_config.NumberColumn("Adult", width="small"),
        "Child": st.column_config.NumberColumn("Kids", width="small"),
        "Member_ID": st.column_config.TextColumn("Member ID", width="large"),
    }
    
    # Display as scrollable table with fixed height (creates internal scrollbar)
    edited_df = st.data_editor(
        display_df_for_editor,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=500,  # Fixed height - creates internal scrollbar
        key=f"member_table_{hash(search_term)}"  # changes only when you Apply search
    )
    
    # Sync selection state from the edited dataframe.
    # Key behavior: filtering/searching should NEVER implicitly deselect anything.
    # We only remove if we detect an explicit True -> False toggle for a row that was shown as selected.
    sel = set(map(str, st.session_state.selected_member_ids))
    visible_ids = display_df["Member_ID"].astype(str).tolist()
    current_state = {}
    for idx, row in edited_df.iterrows():
        if idx >= len(visible_ids):
            continue
        mid = visible_ids[idx]
        checked = bool(row.get("Select"))
        current_state[mid] = checked

        was_checked = bool(baseline_state.get(mid, False))
        if checked and not was_checked:
            sel.add(mid)
        elif (not checked) and was_checked:
            sel.discard(mid)
        # If baseline was False and remains False, do nothing (prevents implicit deselects).
    st.session_state.selected_member_ids = sorted(sel)
    # Table state is derived from selected_member_ids; no need to persist a second copy.
    
    # Generation section
    st.markdown("---")
    st.header("🎨 Generate Cards")
    
    selected_count = len(st.session_state.selected_member_ids)
    st.info(f"**{selected_count}** member(s) selected for card generation")

    # Show selected members explicitly (so selection feels persistent and visible)
    with st.expander("✅ Selected members (click to view)", expanded=True if selected_count <= 15 else False):
        if selected_count == 0:
            st.caption("No members selected yet. Search → check a row → keep searching and adding more.")
        else:
            selected_ids = set(map(str, st.session_state.selected_member_ids))
            selected_view = df[df["Member_ID"].astype(str).isin(selected_ids)].copy()
            # Preserve the selection ordering
            order = {mid: i for i, mid in enumerate(st.session_state.selected_member_ids)}
            selected_view["_ord"] = selected_view["Member_ID"].astype(str).map(order).fillna(10**9)
            selected_view = selected_view.sort_values("_ord").drop(columns=["_ord"])
            for col in ("Membership_Type", "Adult", "Child"):
                if col not in selected_view.columns:
                    selected_view[col] = ""
            st.dataframe(
                selected_view[["Name", "Membership_Type", "Adult", "Child", "Member_ID"]],
                use_container_width=True,
                height=220,
            )
            # Quick remove via multiselect (explicit deselect)
            id_to_name_all = dict(zip(df["Member_ID"].astype(str), df["Name"].astype(str)))
            to_remove = st.multiselect(
                "Remove selected (explicit deselect)",
                options=st.session_state.selected_member_ids,
                default=[],
                format_func=lambda mid: f"{id_to_name_all.get(mid, '')} ({mid})" if id_to_name_all.get(mid) else mid,
                key="remove_selected_ids_widget",
            )
            if to_remove:
                st.session_state.selected_member_ids = sorted(selected_ids - set(map(str, to_remove)), key=lambda x: order.get(x, 10**9))
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        preview_mode = st.checkbox("Show previews", value=True)
    with col2:
        st.caption("No files are written to disk. PDFs are generated in-memory for download.")
    with col3:
        if st.button("🧹 Clear generated previews", use_container_width=True):
            st.session_state.generated_items = []
            st.session_state.generated_zip = None
    
    st.caption(
        f"Download behavior: up to **{MAX_INDIVIDUAL_DOWNLOADS}** selected → individual PDFs + previews. "
        f"More than **{MAX_INDIVIDUAL_DOWNLOADS}** → one ZIP download."
    )

    if st.button("🚀 Generate downloads", type="primary", use_container_width=True):
        if selected_count == 0:
            st.warning("Please select at least one member to generate cards")
        else:
            with st.spinner(f"Generating {selected_count} card(s)..."):
                try:
                    # Reset previous outputs
                    st.session_state.generated_items = []
                    st.session_state.generated_zip = None

                    # Import heavy rendering code only when needed (improves Streamlit Cloud startup)
                    from app import MembershipCardGenerator

                    selected_ids = set(map(str, st.session_state.selected_member_ids))
                    selected_df = df[df["Member_ID"].astype(str).isin(selected_ids)].copy()
                    for col in ("Membership_Type", "Adult", "Child"):
                        if col not in selected_df.columns:
                            selected_df[col] = ""

                    # Initialize generator (no output dir usage in UI)
                    generator = MembershipCardGenerator(
                        csv_path="",
                        banner_path=st.session_state.banner_path,
                        output_dir="output",
                    )
                    # Load banner once for this run
                    banner_base = generator.load_banner_image()
                    
                    # Generate cards
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    members_list = list(selected_df[["Name", "Member_ID", "Membership_Type", "Adult", "Child"]].itertuples(index=False, name=None))
                    total = len(members_list)

                    if total > MAX_INDIVIDUAL_DOWNLOADS:
                        # Use a spooled temp file so large ZIPs spill to disk instead of RAM.
                        zip_buf = tempfile.SpooledTemporaryFile(max_size=ZIP_SPOOL_MAX_BYTES)
                        skipped = 0
                        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                            for i, (name, member_id, membership_type, adult, child) in enumerate(members_list):
                                if not str(name).strip() or not str(member_id).strip():
                                    skipped += 1
                                    continue
                                qr_img = generator.generate_qr_code(member_id, name)
                                banner_img = banner_base.copy()
                                card_img = generator.create_card_image(
                                    name,
                                    member_id,
                                    qr_img,
                                    banner_img,
                                    membership_type=membership_type,
                                    adult=str(adult),
                                    child=str(child),
                                )
                                pdf_bytes = generator.create_pdf_bytes(card_img)
                                zf.writestr(safe_pdf_filename(str(name)), pdf_bytes)

                                progress_bar.progress((i + 1) / total)
                                status_text.text(f"Prepared {i + 1}/{total}: {name}")

                        progress_bar.empty()
                        status_text.empty()
                        zip_name = "CTBA_2026_membership_cards.zip"
                        zip_buf.seek(0)
                        st.session_state.generated_zip = {
                            "zip_bytes": zip_buf.read(),
                            "zip_name": zip_name,
                            "count": total,
                        }
                        if skipped:
                            st.warning(f"Skipped {skipped} row(s) due to missing Name/Member ID.")
                    else:
                        skipped = 0
                        for i, (name, member_id, membership_type, adult, child) in enumerate(members_list):
                            if not str(name).strip() or not str(member_id).strip():
                                skipped += 1
                                continue
                            qr_img = generator.generate_qr_code(member_id, name)
                            banner_img = banner_base.copy()
                            card_img = generator.create_card_image(
                                name,
                                member_id,
                                qr_img,
                                banner_img,
                                membership_type=membership_type,
                                adult=str(adult),
                                child=str(child),
                            )
                            pdf_bytes = generator.create_pdf_bytes(card_img)

                            img_buf = io.BytesIO()
                            card_img.save(img_buf, format="PNG")

                            st.session_state.generated_items.append(
                                {
                                    "name": str(name),
                                    "membership_type": str(membership_type or ""),
                                    "adult": str(adult or ""),
                                    "child": str(child or ""),
                                    "img_png_bytes": img_buf.getvalue(),
                                    "pdf_bytes": pdf_bytes,
                                    "filename": safe_pdf_filename(str(name)),
                                }
                            )

                            progress_bar.progress((i + 1) / total)
                            status_text.text(f"Prepared {i + 1}/{total}: {name}")

                        progress_bar.empty()
                        status_text.empty()
                        if skipped:
                            st.warning(f"Skipped {skipped} row(s) due to missing Name/Member ID.")
                    
                except (FileNotFoundError, OSError, ValueError) as e:
                    st.error(f"Error during generation: {e}")
                except Exception as e:
                    st.error(f"Unexpected error during generation: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    # Render generated outputs (persisted in session)
    if st.session_state.generated_zip is not None:
        z = st.session_state.generated_zip
        st.warning(f"More than 10 selected (**{z['count']}**). Download as a single ZIP.")
        st.download_button(
            "⬇️ Download ZIP",
            data=z["zip_bytes"],
            file_name=z["zip_name"],
            mime="application/zip",
            key="dl_zip",
        )
    elif st.session_state.generated_items:
        st.success(f"Prepared **{len(st.session_state.generated_items)}** PDF(s).")
        if preview_mode:
            st.markdown("### Previews (up to 10)")
            columns_per_row = PREVIEW_COLUMNS_MOBILE if mobile_mode else PREVIEW_COLUMNS_DESKTOP
            PREVIEW_WIDTH = PREVIEW_WIDTH_MOBILE if mobile_mode else PREVIEW_WIDTH_DESKTOP
            items = st.session_state.generated_items[:10]
            for start in range(0, len(items), columns_per_row):
                row_items = items[start : start + columns_per_row]
                cols = st.columns(columns_per_row)
                for c, it in enumerate(row_items):
                    idx = start + c
                    with cols[c]:
                        st.image(it["img_png_bytes"], width=PREVIEW_WIDTH)
                        parts = []
                        if it["membership_type"]:
                            parts.append(it["membership_type"])
                        if it["adult"] and str(it["adult"]).lower() != "nan":
                            parts.append(f"Adults {it['adult']}")
                        if it["child"] and str(it["child"]).lower() != "nan":
                            parts.append(f"Kids {it['child']}")
                        cap = it["name"] + ((" — " + ", ".join(parts)) if parts else "")
                        st.caption(cap)
                        st.download_button(
                            "Download",
                            data=it["pdf_bytes"],
                            file_name=it["filename"],
                            mime="application/pdf",
                            key=f"dl_pdf_{idx}_{it['filename']}",
                        )
        else:
            st.markdown("### Downloads")
            for idx, it in enumerate(st.session_state.generated_items[:10]):
                st.download_button(
                    f"⬇️ {it['filename']}",
                    data=it["pdf_bytes"],
                    file_name=it["filename"],
                    mime="application/pdf",
                    key=f"dl_list_{idx}_{it['filename']}",
                )

elif st.session_state.members_df is None:
    st.info("👈 Choose a data source above (AppSheet API or Upload file), then click **Load** / **Fetch** to load members.")
elif st.session_state.banner_path is None:
    st.info("👈 Please upload a banner image above (or enable the default banner).")

# Footer
st.markdown("---")
