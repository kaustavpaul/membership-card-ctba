#!/usr/bin/env python3
"""
CTBA Membership Card Generator
Generates PDF business cards with QR codes for each member from CSV or Excel.
Excel: sheet 'Form Responses 1'; uses existing Member ID column (no computation).
"""

from __future__ import annotations

import csv
from io import BytesIO
import os
import re
import sys
import time
import random
from pathlib import Path
from typing import List, Tuple, Optional, Any
from urllib.parse import quote

from config import CARD_FONT_SIZE, NAME_TO_MEMBER_GAP_PX

# Design constants
_APP_DIR = Path(__file__).resolve().parent
DPI = 300
BACKGROUND_COLOR = (229, 226, 209)  # #e5e2d1
CARD_BORDER_COLOR = (208, 206, 192)  # #d0cec0

# Default input for demos (safe template committed to repo)
DEFAULT_EXCEL = _APP_DIR / "input" / "template_members.csv"


def _san(s) -> str:
    """Sanitize for ID: alphanumeric only."""
    if s is None or (isinstance(s, float) and str(s) == "nan"):
        return ""
    return re.sub(r"[^a-zA-Z0-9]", "", str(s).strip())


def make_member_id(name: str, email: str, membership_type: str) -> str:
    """Build unique ID: CTBA2026 + name + email + membership type (alphanumeric)."""
    return f"CTBA2026{_san(name)}{_san(email)}{_san(membership_type)}"


def _find_column(df: Any, exact: Optional[str], *subs) -> Optional[str]:
    """Find column by exact name or by substrings (all must match, case-insensitive)."""
    df_cols = [str(c).strip() for c in df.columns]
    if exact and exact in df_cols:
        return exact
    low = exact.lower() if exact else ""
    for c in df.columns:
        cs = str(c).strip()
        if exact and cs.lower() == low:
            return c
        if subs and all(s.lower() in cs.lower() for s in subs):
            return c
    return None


def load_members_dataframe(path: str, sheet: str = "Sheet1"):
    """
    Load members from Excel or CSV into a DataFrame with columns:
    Name, Member_ID, Membership_Type, Adult, Child.
    - Excel (.xlsx/.xls): prefers an existing Member ID column (used as-is).
      If no Member ID column exists, raises an error (source-of-truth is the sheet).
    - CSV: expects name and member-id-like columns; Member_ID used as-is.
    """
    import pandas as pd

    p = Path(path)
    suf = p.suffix.lower()
    if suf in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(path, sheet_name=sheet)
        except ImportError as e:
            if "openpyxl" in str(e).lower():
                raise ImportError(
                    "Reading Excel requires openpyxl. Install it with:\n  pip install openpyxl\n"
                    "Or: pip install -r requirements.txt"
                ) from e
            raise
        df.columns = [str(c).strip() for c in df.columns]
        # Enriched dataset columns (preferred)
        name_col = (
            _find_column(df, "Full Name")
            or _find_column(df, "Member Name")
            or _find_column(df, None, "full", "name")
            or _find_column(df, None, "name")
            or df.columns[0]
        )

        member_id_col = (
            _find_column(df, "Member ID")
            or _find_column(df, "Unique Member ID")
            or _find_column(df, None, "member", "id")
            or next(
                (
                    c
                    for c in df.columns
                    if ("member" in str(c).lower() and "id" in str(c).lower())
                    or "member id" in str(c).lower()
                ),
                None,
            )
        )
        if not member_id_col:
            raise ValueError(
                "Could not find a Member ID column in the Excel sheet. "
                "Expected something like 'Member ID' or 'Unique Member ID'. "
                f"Columns: {list(df.columns)}"
            )

        membership_col = (
            _find_column(df, "Membership Type")
            or _find_column(df, None, "membership", "type")
            or _find_column(df, None, "membership")
        )
        adult_col = _find_column(df, "Adult") or _find_column(df, None, "adult")
        child_col = _find_column(df, "Child") or _find_column(df, "Kids") or _find_column(df, None, "child")

        total_rows = len(df)
        missing_name = 0
        missing_member_id = 0
        rows = []
        for _, r in df.iterrows():
            name = str(r.get(name_col, "") or "").strip()
            if not name or name.lower() == "nan":
                missing_name += 1
                continue

            mid = str(r.get(member_id_col, "") or "").strip()
            if not mid or mid.lower() == "nan":
                missing_member_id += 1
                continue
            membership_type = ""
            if membership_col:
                membership_type = str(r.get(membership_col, "") or "").strip()
                if membership_type.lower() == "nan":
                    membership_type = ""
            adult_val = r.get(adult_col, "") if adult_col else ""
            child_val = r.get(child_col, "") if child_col else ""
            # Keep counts as ints when possible
            def _to_int(v):
                try:
                    if v is None or (isinstance(v, float) and str(v) == "nan"):
                        return ""
                    if isinstance(v, str) and not v.strip():
                        return ""
                    return int(float(v))
                except Exception:
                    return str(v).strip()
            rows.append(
                {
                    "Name": name,
                    "Member_ID": mid,
                    "Membership_Type": membership_type,
                    "Adult": _to_int(adult_val),
                    "Child": _to_int(child_val),
                }
            )

        out = pd.DataFrame(rows)
        before_dedup = len(out)
        out = out.drop_duplicates(subset=["Member_ID"]).reset_index(drop=True)
        out.attrs["load_stats"] = {
            "source_rows": total_rows,
            "kept_rows_before_dedup": before_dedup,
            "loaded_rows": len(out),
            "skipped_missing_name": missing_name,
            "skipped_missing_member_id": missing_member_id,
            "dropped_duplicate_member_id": before_dedup - len(out),
        }
        return out
    # CSV
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    name_col = "Name" if "Name" in df.columns else next(
        (c for c in df.columns if "name" in c.lower() or "first" in c.lower()), df.columns[0]
    )
    id_col = "Member_ID" if "Member_ID" in df.columns else next(
        (c for c in df.columns if "member" in c.lower() or "id" in c.lower()), df.columns[1] if len(df.columns) > 1 else None
    )
    if id_col is None:
        raise ValueError("CSV must have a member ID column.")
    membership_col = (
        "Membership_Type"
        if "Membership_Type" in df.columns
        else next((c for c in df.columns if "membership" in c.lower()), None)
    )
    adult_col = "Adult" if "Adult" in df.columns else next((c for c in df.columns if c.lower() == "adult"), None)
    child_col = "Child" if "Child" in df.columns else next((c for c in df.columns if c.lower() in ("child", "kids")), None)

    df = df.rename(columns={name_col: "Name", id_col: "Member_ID"})
    if membership_col and membership_col in df.columns and membership_col != "Membership_Type":
        df = df.rename(columns={membership_col: "Membership_Type"})
    if "Membership_Type" not in df.columns:
        df["Membership_Type"] = ""
    if adult_col and adult_col in df.columns and adult_col != "Adult":
        df = df.rename(columns={adult_col: "Adult"})
    if child_col and child_col in df.columns and child_col != "Child":
        df = df.rename(columns={child_col: "Child"})
    if "Adult" not in df.columns:
        df["Adult"] = ""
    if "Child" not in df.columns:
        df["Child"] = ""
    total_rows = len(df)
    df = df[df["Name"].notna() & (df["Name"].astype(str).str.strip() != "") & df["Member_ID"].notna() & (df["Member_ID"].astype(str).str.strip() != "")]
    df["Membership_Type"] = df["Membership_Type"].fillna("").astype(str)
    out = df[["Name", "Member_ID", "Membership_Type", "Adult", "Child"]].reset_index(drop=True)
    out.attrs["load_stats"] = {
        "source_rows": total_rows,
        "loaded_rows": len(out),
        "skipped_rows": total_rows - len(out),
    }
    return out


def load_members_dataframe_appsheet(
    *,
    app_id: str,
    table_name: str,
    application_access_key: str,
    region: str = "www.appsheet.com",
    selector: Optional[str] = None,
    run_as_user_email: Optional[str] = None,
    timeout_s: int = 30,
    max_attempts: int = 2,
) -> Any:
    """
    Load members from AppSheet REST API into a DataFrame with columns:
    Name, Member_ID, Membership_Type, Adult, Child.

    Uses the AppSheet "Find" action:
      POST https://{region}/api/v2/apps/{appId}/tables/{tableName}/Action?applicationAccessKey=...
    """
    import pandas as pd
    try:
        import requests  # type: ignore
    except Exception as e:  # pragma: no cover
        raise ImportError(
            "AppSheet integration requires 'requests'. Install it with:\n"
            "  pip install requests\n"
            "Or: pip install -r requirements.txt"
        ) from e

    app_id = (app_id or "").strip()
    table_name = (table_name or "").strip()
    application_access_key = (application_access_key or "").strip()
    region = (region or "www.appsheet.com").strip()
    if not app_id or not table_name or not application_access_key:
        raise ValueError("AppSheet requires app_id, table_name, and application_access_key.")

    # AppSheet supports key in header (preferred) or query string (less secure).
    # We'll try a few variants because some deployments behave inconsistently.
    params_query = {"applicationAccessKey": application_access_key}
    headers_value = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ApplicationAccessKey": application_access_key,
        "User-Agent": "ctba-membership-card/1.0",
    }
    # Some examples/documentation show "ApplicationAccessKey=<key>" as the header value.
    headers_assignment = {
        **{k: v for k, v in headers_value.items() if k != "ApplicationAccessKey"},
        "ApplicationAccessKey": f"ApplicationAccessKey={application_access_key}",
    }
    body: dict = {
        "Action": "Find",
        "Properties": {
            "Locale": "en-US",
            "Timezone": "UTC",
        },
        "Rows": [],
    }
    if selector:
        body["Properties"]["Selector"] = selector
    if run_as_user_email:
        body["Properties"]["RunAsUserEmail"] = run_as_user_email

    def _call(region_domain: str, *, mode: str):
        endpoint = f"https://{region_domain}/api/v2/apps/{app_id}/tables/{quote(table_name, safe='')}/Action"
        if mode == "header_value":
            headers = headers_value
            params = None
        elif mode == "header_assignment":
            headers = headers_assignment
            params = None
        elif mode == "query_only":
            headers = {k: v for k, v in headers_value.items() if k != "ApplicationAccessKey"}
            params = params_query
        else:
            # default: include both (header wins if both supplied)
            headers = headers_value
            params = params_query
        last_exc: Optional[Exception] = None
        last_resp = None
        # Keep Cloud UX responsive: cap retries/timeouts so the UI doesn't look hung.
        for attempt in range(max(1, int(max_attempts))):
            try:
                resp = requests.post(
                    endpoint,
                    params=params,
                    headers=headers,
                    json=body,
                    timeout=(10, max(10, int(timeout_s))),
                    allow_redirects=False,
                )
                last_resp = resp
                # Retry transient errors with backoff
                if resp.status_code in (429, 500, 502, 503):
                    sleep_s = min(6.0, 0.6 * (2**attempt) + random.random() * 0.25)
                    time.sleep(sleep_s)
                    continue
                return endpoint, resp
            except Exception as e:
                # Requests may raise connection/timeouts/etc. Retry a few times.
                last_exc = e
                sleep_s = min(6.0, 0.6 * (2**attempt) + random.random() * 0.25)
                time.sleep(sleep_s)
                continue
        if last_resp is not None:
            return endpoint, last_resp
        raise RuntimeError(f"AppSheet request failed after retries: {last_exc}") from last_exc

    endpoint, resp = _call(region, mode="both")

    def _raise_with_response(prefix: str, endpoint_for_msg: str, resp_for_msg):
        ct = (resp_for_msg.headers.get("Content-Type") or "").split(";")[0].strip() or "unknown"
        cl = len(resp_for_msg.content or b"")
        loc = (resp_for_msg.headers.get("Location") or "")[:200]
        snippet = (resp_for_msg.text or "")[:500]
        raise RuntimeError(
            f"{prefix} (status: {resp_for_msg.status_code}, content-type: {ct}, content-length: {cl}). "
            f"Endpoint: {endpoint_for_msg}. "
            f"{('Location: ' + loc + '. ') if loc else ''}"
            f"Body (first 500 chars): {snippet}"
        )

    # Common failure mode: HTML/redirect response instead of JSON.
    if resp.status_code in (301, 302, 303, 307, 308):
        _raise_with_response("AppSheet API redirect", endpoint, resp)

    # Another failure mode seen in the wild: 200 OK with an empty body.
    # We'll retry with a few key-placement/header variants and (if needed) api.appsheet.com.
    if resp.status_code == 200 and not (resp.content or b""):
        tried = [(endpoint, resp)]

        for mode in ("header_value", "query_only", "header_assignment"):
            endpoint2, resp2 = _call(region, mode=mode)
            tried.append((endpoint2, resp2))
            if resp2.status_code == 200 and (resp2.content or b""):
                endpoint, resp = endpoint2, resp2
                break
        else:
            # Domain fallback if still empty
            if region != "api.appsheet.com":
                for mode in ("both", "header_value", "query_only", "header_assignment"):
                    endpoint3, resp3 = _call("api.appsheet.com", mode=mode)
                    tried.append((endpoint3, resp3))
                    if resp3.status_code == 200 and (resp3.content or b""):
                        endpoint, resp = endpoint3, resp3
                        break
                else:
                    # All attempts returned empty
                    last_ep, last_resp = tried[-1]
                    _raise_with_response(
                        "AppSheet returned empty response body after retries. "
                        "Check that the API is enabled for the app, the access key is valid, "
                        "and your plan supports the AppSheet API",
                        last_ep,
                        last_resp,
                    )
            else:
                _raise_with_response(
                    "AppSheet returned empty response body after retries. "
                    "Check that the API is enabled for the app, the access key is valid, "
                    "and your plan supports the AppSheet API",
                    endpoint,
                    resp,
                )

    if resp.status_code != 200:
        if resp.status_code == 403:
            _raise_with_response(
                "AppSheet API forbidden (403). Check: API enabled for app, access key valid, and plan supports API",
                endpoint,
                resp,
            )
        if resp.status_code == 404:
            _raise_with_response(
                "AppSheet API not found (404). Check: App ID and Table name",
                endpoint,
                resp,
            )
        _raise_with_response("AppSheet API error", endpoint, resp)

    try:
        data = resp.json()
    except Exception as e:
        # Re-raise with helpful response diagnostics, preserving original exception context
        try:
            _raise_with_response("AppSheet response was not valid JSON", endpoint, resp)
        except Exception as raised:
            raise raised from e
    # AppSheet usually returns: {"Rows": [ ... ]}, but some setups return a raw list.
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("Rows", data.get("rows", []))
    else:
        raise RuntimeError(f"Unexpected AppSheet response type: {type(data).__name__}")
    if not isinstance(rows, list):
        raise RuntimeError("Unexpected AppSheet response: missing 'Rows' list.")

    df = pd.DataFrame(rows)
    if df.empty:
        out = pd.DataFrame(columns=["Name", "Member_ID", "Membership_Type", "Adult", "Child"])
        out.attrs["load_stats"] = {"source_rows": 0, "loaded_rows": 0}
        return out

    # Map columns similarly to the enriched Excel
    df.columns = [str(c).strip() for c in df.columns]
    name_col = (
        _find_column(df, "Full Name")
        or _find_column(df, "Member Name")
        or _find_column(df, None, "full", "name")
        or _find_column(df, None, "name")
        or df.columns[0]
    )
    member_id_col = (
        _find_column(df, "Member ID")
        or _find_column(df, "Member_ID")
        or _find_column(df, "Unique Member ID")
        or _find_column(df, None, "member", "id")
    )
    if not member_id_col:
        raise ValueError(f"Could not find a Member ID column in AppSheet rows. Columns: {list(df.columns)}")

    membership_col = (
        _find_column(df, "Membership Type")
        or _find_column(df, "Membership_Type")
        or _find_column(df, None, "membership", "type")
        or _find_column(df, None, "membership")
    )
    adult_col = _find_column(df, "Adult") or _find_column(df, None, "adult")
    child_col = _find_column(df, "Child") or _find_column(df, "Kids") or _find_column(df, None, "child")

    out = df.rename(
        columns={
            name_col: "Name",
            member_id_col: "Member_ID",
        }
    ).copy()
    if membership_col and membership_col in out.columns and membership_col != "Membership_Type":
        out = out.rename(columns={membership_col: "Membership_Type"})
    if "Membership_Type" not in out.columns:
        out["Membership_Type"] = ""
    if adult_col and adult_col in out.columns and adult_col != "Adult":
        out = out.rename(columns={adult_col: "Adult"})
    if child_col and child_col in out.columns and child_col != "Child":
        out = out.rename(columns={child_col: "Child"})
    if "Adult" not in out.columns:
        out["Adult"] = ""
    if "Child" not in out.columns:
        out["Child"] = ""

    total_rows = len(out)
    out["Name"] = out["Name"].fillna("").astype(str).str.strip()
    out["Member_ID"] = out["Member_ID"].fillna("").astype(str).str.strip()
    out = out[(out["Name"] != "") & (out["Member_ID"] != "")]
    before_dedup = len(out)
    out = out.drop_duplicates(subset=["Member_ID"]).reset_index(drop=True)
    out = out[["Name", "Member_ID", "Membership_Type", "Adult", "Child"]]
    out.attrs["load_stats"] = {
        "source_rows": total_rows,
        "kept_rows_before_dedup": before_dedup,
        "loaded_rows": len(out),
        "dropped_duplicate_member_id": before_dedup - len(out),
    }
    return out


class MembershipCardGenerator:
    """Generates membership cards with QR codes."""
    
    def __init__(self, csv_path: str, banner_path: str, output_dir: str = "output", member_year: str = "2026"):
        """
        Initialize the generator.
        
        Args:
            csv_path: Path to the CSV file with member data
            banner_path: Path to the banner image
            output_dir: Directory to save generated cards
            member_year: Year to show in "Annual Member {year}" (default: 2026)
        """
        self.csv_path = csv_path
        self.banner_path = banner_path
        self.output_dir = Path(output_dir)
        # Don't mkdir here; UI may not want any output folder created.
        # CLI path creation is handled right before writing files.
        self.member_year = member_year
        self._font_name: Optional[Any] = None
        self._font_member: Optional[Any] = None
        self._banner_img_cache: Optional[Any] = None
        
        # Card dimensions (portrait style: 2.5" x 4")
        inch_pt = 72.0  # reportlab's inch unit in points
        self.card_width = 2.5 * inch_pt
        self.card_height = 4 * inch_pt

    def _get_fonts(self, font_size: int):
        """Load and cache fonts once per generator instance."""
        from PIL import ImageFont

        if self._font_name is not None and self._font_member is not None:
            return self._font_name, self._font_member

        league_spartan_regular = [
            str(_APP_DIR / "League_Spartan" / "static" / "LeagueSpartan-Regular.ttf"),
            os.path.expanduser("~/Library/Fonts/LeagueSpartan-Regular.ttf"),
            "/Library/Fonts/LeagueSpartan-Regular.ttf",
            "/System/Library/Fonts/Supplemental/LeagueSpartan-Regular.ttf",
        ]
        league_spartan_bold = [
            str(_APP_DIR / "League_Spartan" / "static" / "LeagueSpartan-Bold.ttf"),
            os.path.expanduser("~/Library/Fonts/LeagueSpartan-Bold.ttf"),
            "/Library/Fonts/LeagueSpartan-Bold.ttf",
            "/System/Library/Fonts/Supplemental/LeagueSpartan-Bold.ttf",
        ]
        fallback_font_paths = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/ArialHB.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Avenir.ttc",
        ]

        def _load(path: str):
            p = os.path.expanduser(path) if isinstance(path, str) and "~" in path else path
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, font_size)
                except Exception:
                    return None
            return None

        font_member = None
        for path in league_spartan_regular + fallback_font_paths:
            font_member = _load(path)
            if font_member:
                break
        if font_member is None:
            font_member = ImageFont.load_default()

        font_name = None
        for path in league_spartan_bold:
            font_name = _load(path)
            if font_name:
                break
        if font_name is None:
            font_name = font_member

        self._font_name = font_name
        self._font_member = font_member
        return font_name, font_member

    def load_banner_image(self) -> "Image.Image":
        """Load and cache banner image once per generator instance."""
        from PIL import Image

        if self._banner_img_cache is not None:
            return self._banner_img_cache
        banner_img = Image.open(self.banner_path)
        if banner_img.mode != "RGB":
            banner_img = banner_img.convert("RGB")
        self._banner_img_cache = banner_img
        return banner_img
        
    def read_members(self) -> List[Tuple[str, str, str, str, str]]:
        """
        Read member data from CSV or Excel.
        Excel: uses load_members_dataframe (Member_ID column is the source of truth).
        CSV: name and member ID columns.
        """
        path = Path(self.csv_path)
        if path.suffix.lower() in (".xlsx", ".xls"):
            df = load_members_dataframe(str(path))
            return list(df.itertuples(index=False, name=None))
        members = []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 2:
                        name = (row[0] or "").strip()
                        member_id = (row[1] or "").strip()
                        membership_type = (row[2] or "").strip() if len(row) >= 3 else ""
                        adult = (row[3] or "").strip() if len(row) >= 4 else ""
                        child = (row[4] or "").strip() if len(row) >= 5 else ""
                        if name and member_id:
                            members.append((name, member_id, membership_type, adult, child))
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)
        return members
    
    def generate_qr_code(self, member_id: str, name: str):
        """
        Generate QR code for a member.
        Encodes only the Member ID (numeric) for scanning.
        
        Args:
            member_id: Unique member ID (numeric)
            name: Member name (unused; kept for API compatibility)
            
        Returns:
            PIL Image of the QR code
        """
        # QR code data: only the Member ID (numeric)
        qr_data = str(member_id).strip()
        
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        return qr_img
    
    def create_card_image(
        self,
        name: str,
        member_id: str,
        qr_img,
        banner_img,
        membership_type: str = "",
        adult: str = "",
        child: str = "",
    ):
        """
        Create a membership card: banner on top, QR code at center, then:
        Full Name, 'Annual Member CTBA 2026', Membership Type.
        Adult/child counts are no longer shown on the card (params kept for API compatibility).
        
        Args:
            name: Member name
            member_id: Member ID (numeric; used in QR code)
            qr_img: QR code image
            banner_img: Banner image
            membership_type: Membership type (optional)
            adult: Unused (kept for compatibility)
            child: Unused (kept for compatibility)
            
        Returns:
            Combined card image
        """
        # Create card canvas (portrait: 2.5" x 4" at DPI)
        card_width_px = int(self.card_width * DPI / 72)
        card_height_px = int(self.card_height * DPI / 72)

        # Simple RGB card background (keeps PDF rendering straightforward)
        from PIL import Image, ImageDraw

        card = Image.new("RGB", (card_width_px, card_height_px), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(card)
        border_radius = int(0.08 * DPI)  # small curve for a rounded-corner impression
        
        # === TOP: BANNER ===
        top_third_height = card_height_px // 3
        
        banner_aspect = banner_img.width / banner_img.height
        banner_width = card_width_px
        banner_height = int(banner_width / banner_aspect)
        if banner_height > top_third_height:
            banner_height = top_third_height
            banner_width = int(banner_height * banner_aspect)
        
        banner_resized = banner_img.resize((banner_width, banner_height), Image.Resampling.LANCZOS)
        banner_x = (card_width_px - banner_width) // 2
        if banner_resized.mode == "RGBA":
            card.paste(banner_resized, (banner_x, 0), banner_resized)
        else:
            card.paste(banner_resized, (banner_x, 0))
        
        # === CENTER: QR CODE ===
        qr_size = int(card_width_px * 0.40)
        qr_resized = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
        # Vertical center of the full card
        qr_y = (card_height_px - qr_size) // 2
        qr_x = (card_width_px - qr_size) // 2
        qr_padding = int(0.08 * DPI)
        qr_bg = Image.new("RGB", (qr_size + qr_padding * 2, qr_size + qr_padding * 2), (255, 255, 255))
        qr_bg.paste(qr_resized, (qr_padding, qr_padding))
        card.paste(qr_bg, (qr_x - qr_padding, qr_y - qr_padding))
        
        # === BELOW QR: NAME, "ANNUAL MEMBER {YEAR}", MEMBERSHIP TYPE ===
        font_size = CARD_FONT_SIZE
        font_name, font_member = self._get_fonts(font_size)
        
        def get_text_width(text, font):
            try:
                if hasattr(draw, 'textbbox'):
                    bbox = draw.textbbox((0, 0), text, font=font)
                    return bbox[2] - bbox[0]
                else:
                    return draw.textsize(text, font=font)[0]
            except:
                return len(text) * 15
        
        # Position text below the QR code
        text_start_y = qr_y + qr_size + qr_padding * 2 + 15
        # Fixed phrase as requested
        member_text = "Annual Member CTBA 2026"
        
        name_width = get_text_width(name, font_name)
        member_width = get_text_width(member_text, font_member)
        name_x = (card_width_px - name_width) // 2
        member_x = (card_width_px - member_width) // 2
        
        text_color = (0, 0, 0)
        draw.text((name_x, text_start_y), name, font=font_name, fill=text_color)
        draw.text((member_x, text_start_y + NAME_TO_MEMBER_GAP_PX), member_text, font=font_member, fill=text_color)

        # Membership type (same font size; wrap to max 2 lines)
        membership_type = (membership_type or "").strip()
        if membership_type and membership_type.lower() != "nan":
            max_w = int(card_width_px * 0.9)
            words = membership_type.split()
            lines = []
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if get_text_width(test, font_member) <= max_w:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
                if len(lines) >= 2:
                    break
            if cur and len(lines) < 2:
                lines.append(cur)

            y = text_start_y + NAME_TO_MEMBER_GAP_PX * 2
            for line in lines:
                x = (card_width_px - get_text_width(line, font_member)) // 2
                draw.text((x, y), line, font=font_member, fill=text_color)
                y += font_size + 6

        # Thin black border with small corner curve (works consistently in PDF)
        draw.rounded_rectangle(
            [(1, 1), (card_width_px - 2, card_height_px - 2)],
            radius=border_radius,
            outline=(0, 0, 0),
            width=2,
        )
        
        return card
    
    def create_pdf_bytes(self, card_img: "Image.Image") -> bytes:
        """
        Create a PDF (bytes) from card image (no filesystem writes).

        Args:
            card_img: Card image

        Returns:
            PDF bytes
        """
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader

        img = card_img.convert("RGB")
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(self.card_width, self.card_height))
        c.drawImage(ImageReader(img), 0, 0, width=self.card_width, height=self.card_height)
        c.showPage()
        c.save()
        return buf.getvalue()

    def create_pdf(self, card_img: "Image.Image", output_path: str) -> None:
        """
        Create PDF from card image.
        
        Args:
            card_img: Card image
            output_path: Path to save PDF
        """
        pdf_bytes = self.create_pdf_bytes(card_img)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    
    def generate_all_cards(self):
        """Generate cards for all members."""
        # Check if banner exists
        if not os.path.exists(self.banner_path):
            print(f"Error: Banner image not found at {self.banner_path}")
            sys.exit(1)
        
        # Load banner image (cached)
        try:
            banner_img = self.load_banner_image()
        except (FileNotFoundError, OSError) as e:
            print(f"Error loading banner image: {e}")
            sys.exit(1)
        
        # Read members
        members = self.read_members()
        print(f"Found {len(members)} members with valid IDs")
        
        # Generate cards
        self.output_dir.mkdir(exist_ok=True, parents=True)
        for i, m in enumerate(members, 1):
            # Backwards compatible unpacking
            if len(m) >= 5:
                name, member_id, membership_type, adult, child = m[:5]
            elif len(m) == 3:
                name, member_id, membership_type = m
                adult, child = "", ""
            else:
                name, member_id = m  # type: ignore[misc]
                membership_type, adult, child = "", "", ""
            print(f"Generating card {i}/{len(members)}: {name} ({member_id})")
            
            try:
                # Generate QR code
                qr_img = self.generate_qr_code(member_id, name)
                
                # Create card image
                card_img = self.create_card_image(
                    name,
                    member_id,
                    qr_img,
                    banner_img.copy(),
                    membership_type=membership_type,
                    adult=str(adult),
                    child=str(child),
                )
                
                # Create PDF
                # Sanitize filename (name only, no member ID)
                safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
                safe_name = safe_name.replace(' ', '_')
                pdf_path = self.output_dir / f"{safe_name}.pdf"
                
                self.create_pdf(card_img, str(pdf_path))
                
            except Exception as e:
                print(f"Error generating card for {name}: {e}")
                continue
        
        print(f"\nCompleted! Generated {len(members)} cards in '{self.output_dir}' directory")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CTBA membership cards with QR codes')
    parser.add_argument('data', help='Path to Excel (.xlsx) or CSV with member data')
    parser.add_argument('banner', help='Path to banner image')
    parser.add_argument('-o', '--output', default='output', help='Output directory (default: output)')
    parser.add_argument('-y', '--year', default='2026', help='Year in "Annual Member {year}" (default: 2026)')
    
    args = parser.parse_args()
    
    generator = MembershipCardGenerator(args.data, args.banner, args.output, member_year=args.year)
    generator.generate_all_cards()


if __name__ == '__main__':
    main()
