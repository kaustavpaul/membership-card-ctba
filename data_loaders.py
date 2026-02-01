"""
Lightweight data loading helpers.

Important: Keep imports light at module import time (Streamlit Cloud startup).
We import pandas/requests only inside functions.
"""

from pathlib import Path
from typing import Optional, Any


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


def load_members_dataframe(path: str, sheet: str = "Sheet1") -> Any:
    """
    Load members from Excel or CSV into a DataFrame with columns:
    Name, Member_ID, Membership_Type, Adult, Child.
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

        def _to_int(v):
            try:
                if v is None or (isinstance(v, float) and str(v) == "nan"):
                    return ""
                if isinstance(v, str) and not v.strip():
                    return ""
                return int(float(v))
            except Exception:
                return str(v).strip()

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
        (c for c in df.columns if "member" in c.lower() or "id" in c.lower()),
        df.columns[1] if len(df.columns) > 1 else None,
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
    df = df[
        df["Name"].notna()
        & (df["Name"].astype(str).str.strip() != "")
        & df["Member_ID"].notna()
        & (df["Member_ID"].astype(str).str.strip() != "")
    ]
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
    timeout_s: int = 30,
    max_attempts: int = 2,
) -> Any:
    """
    Load members from AppSheet REST API into a DataFrame with columns:
    Name, Member_ID, Membership_Type, Adult, Child.
    """
    import random
    import time
    from urllib.parse import quote

    import pandas as pd
    import requests

    app_id = (app_id or "").strip()
    table_name = (table_name or "").strip()
    application_access_key = (application_access_key or "").strip()
    region = (region or "www.appsheet.com").strip()
    if not app_id or not table_name or not application_access_key:
        raise ValueError("AppSheet requires app_id, table_name, and application_access_key.")

    params_query = {"applicationAccessKey": application_access_key}
    headers_value = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ApplicationAccessKey": application_access_key,
        "User-Agent": "ctba-membership-card/1.0",
    }
    headers_assignment = {
        **{k: v for k, v in headers_value.items() if k != "ApplicationAccessKey"},
        "ApplicationAccessKey": f"ApplicationAccessKey={application_access_key}",
    }
    body: dict = {"Action": "Find", "Properties": {"Locale": "en-US", "Timezone": "UTC"}, "Rows": []}

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
            headers = headers_value
            params = params_query

        last_exc: Optional[Exception] = None
        last_resp = None
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
                if resp.status_code in (429, 500, 502, 503):
                    time.sleep(min(6.0, 0.6 * (2**attempt) + random.random() * 0.25))
                    continue
                return endpoint, resp
            except Exception as e:
                last_exc = e
                time.sleep(min(6.0, 0.6 * (2**attempt) + random.random() * 0.25))
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

    if resp.status_code in (301, 302, 303, 307, 308):
        _raise_with_response("AppSheet API redirect", endpoint, resp)
    if resp.status_code == 200 and not (resp.content or b""):
        # retry other auth modes/domain
        tried = [(endpoint, resp)]
        for mode in ("header_value", "query_only", "header_assignment"):
            endpoint2, resp2 = _call(region, mode=mode)
            tried.append((endpoint2, resp2))
            if resp2.status_code == 200 and (resp2.content or b""):
                endpoint, resp = endpoint2, resp2
                break
        else:
            if region != "api.appsheet.com":
                for mode in ("both", "header_value", "query_only", "header_assignment"):
                    endpoint3, resp3 = _call("api.appsheet.com", mode=mode)
                    tried.append((endpoint3, resp3))
                    if resp3.status_code == 200 and (resp3.content or b""):
                        endpoint, resp = endpoint3, resp3
                        break
                else:
                    last_ep, last_resp = tried[-1]
                    _raise_with_response(
                        "AppSheet returned empty response body after retries. Check API enabled/key/plan",
                        last_ep,
                        last_resp,
                    )
            else:
                _raise_with_response(
                    "AppSheet returned empty response body after retries. Check API enabled/key/plan",
                    endpoint,
                    resp,
                )
    if resp.status_code != 200:
        if resp.status_code == 403:
            _raise_with_response("AppSheet API forbidden (403). Check API enabled/key/plan", endpoint, resp)
        if resp.status_code == 404:
            _raise_with_response("AppSheet API not found (404). Check App ID/Table name", endpoint, resp)
        _raise_with_response("AppSheet API error", endpoint, resp)

    data = resp.json()
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

    out = df.rename(columns={name_col: "Name", member_id_col: "Member_ID"}).copy()
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

