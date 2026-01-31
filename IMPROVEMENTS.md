# Codebase Review & Improvement Suggestions

## 1. Card Design Improvements

### 1.1 Visual hierarchy & polish
- **Banner frame**: Add a thin border or subtle shadow where the banner meets the middle section so the edge doesn’t look cut off.
- **Text contrast**: Consider a slightly darker tone (e.g. `#1a1a1a`) instead of pure black for better readability on `#e5e2d1`.
- **Name vs. “Annual Member 2026”**: Use **League Spartan Bold** for the name and **League Spartan Regular** for “Annual Member 2026” (both at 24pt) so the name stands out without changing size.
- **QR code**: Add a light 1px border (e.g. `#d0cec0`) around the white QR area so it doesn’t blend into the background. Optionally use a very subtle rounded rectangle for the QR container.
- **Card edge**: Add a 1–2px border (`#d0cec0` or similar) around the full card for a finished, printed look.

### 1.2 Layout refinements
- **Banner bleed**: If the banner has important content at the bottom, consider a fixed “top third” height with a small overlap into the middle (e.g. 5px) so the transition feels less hard.
- **Spacing**: Replace magic numbers (`55`, `member_y`, etc.) with named constants (`NAME_TO_MEMBER_GAP`, `MEMBER_TO_QR_GAP`) and tune for balance.
- **Long names**: Add simple word-wrap or font-size scaling for very long names (e.g. `"Prithwish Chatterjee, Tiyasa Ray"`) so they don’t overflow or look cramped.

### 1.3 Professional touches
- **“Annual Member 2026”**: Make the year configurable (e.g. from CSV, CLI, or UI) instead of hardcoded.
- **Optional member ID**: Offer a compact, smaller line for Member ID (e.g. under “Annual Member 2026”) for staff/verification, hidden by default for a cleaner look.
- **Logo / CTBA line**: Optional small “CTBA” or org line under the QR code in a smaller, muted style.
- **Card size**: Document or make configurable an option for standard 3.5"×2" if needed for certain printers or badge holders.

---

## 2. Code Quality & Architecture

### 2.1 Configuration
- **Central config**: Extract design constants (colors, sizes, paths, year) into a `config.py` or `CardConfig` dataclass so changes don’t require editing `create_card_image`.
- **Font loading**: Move the League Spartan + fallback logic into a `load_card_font(size: int) -> ImageFont.FreeTypeFont` helper; it’s reused and easier to test.
- **Banner path in UI**: Standardize default banner location/name (now `input/banner.png` or `input/Central Texas Bengali Association Banner.png`) and keep the UI fallback list aligned.

### 2.2 Reuse and structure
- **Banner loading**: `generate_all_cards` and the UI both open the banner; consider `load_banner() -> Image` on the generator to load once and pass the same `Image` to `create_card_image` in batch runs.
- **CSV parsing**: `read_members` is fine; you could add a `read_members_from_dataframe(df: pd.DataFrame) -> List[Tuple[str, str]]` for the UI to avoid writing a temp CSV. (Trade-off: more moving parts vs. a single code path.)
- **DPI and units**: Use a single `DPI = 300` and derive `card_width_px`, `card_height_px`, and any `inch`-based padding from it to avoid `72` vs `300` confusion.

### 2.3 Reliability
- **Temp file in `create_pdf`**: `temp_card.png` is written to `self.output_dir`. If two processes use the same `output_dir`, they can overwrite each other. Use `tempfile.NamedTemporaryFile` or a UUID in the name (e.g. `temp_card_{uuid}.png`).
- **CSV header**: `next(reader)` assumes a header. If the first row is data, you’ll skip a member. Consider detecting “looks like a header” (e.g. contains “name”/“id”) or make it configurable.
- **Unicode in filenames**: `safe_name` strips some characters; names with accents or symbols can collide. Appending a short hash (e.g. 6 chars of `member_id` or a slug) reduces collision risk.
- **`reportlab.lib.utils.ImageReader`**: Imported in `app.py` but unused; remove to keep deps clear.

---

## 3. UI (Streamlit) Improvements

### 3.1 UX
- **Banner preview**: In the sidebar, show a small preview of the banner when “Use default banner” is checked or when a file is uploaded.
- **Card design preview**: A “Preview design” button that generates one sample card (e.g. “Sample Member”) so users can check layout/font/colors before batch generation.
- **Select All / Deselect with filter**: When a search is active, “Select All” could mean “select all *filtered* members” with a note, to avoid confusion.
- **Batch download**: Option to zip all generated PDFs and offer a “Download ZIP” link so users don’t have to open the output folder.
- **Default output dir**: Use something like `output_YYYYMMDD` or `output/output_<timestamp>` to avoid overwriting previous runs; or at least warn when `output` already has PDFs.

### 3.2 Robustness
- **Default paths**: `default_csv` and `default_banner` are hardcoded to `/Users/kaustavpaul/...`. Prefer `Path(__file__).resolve().parent` and project-relative paths, or env vars, so it works for other users.
- **Banner when “Use default” unchecked**: If the user unchecks “Use default banner” and doesn’t upload, `st.session_state.banner_path` can stay at the old value. Clear it when the checkbox is unchecked.
- **`st.session_state.selected_members` and filters**: When the dataframe changes (e.g. new CSV), `selected_members` can contain indices that are out of range. Validate and clip to `[0, len(df)-1]` (or clear) when `df` changes.

### 3.3 Small cleanups
- **Unused import**: `import csv` and `import io` in `ui.py` appear unused; remove if so.
- **`generated_count`**: In `st.session_state` but not obviously used; remove or use (e.g. “Last run: N cards”).

---

## 4. Project & Maintainability

### 4.1 Dependencies and docs
- **`requirements.txt`**: Pin minor versions (e.g. `Pillow>=10,<11`) if you want to avoid surprises; document tested Python version (e.g. 3.9+).
- **README**: Update “Card Design” to match the current 2.5"×4" portrait, three sections (banner / member / QR), `#e5e2d1`, League Spartan, and “Annual Member 2026”. Fix `banner.png` references if you standardize on `Central Texas Bengali Association Banner.png`.
- **run.sh**: Uses `python3`; if you use a venv, `run_ui.sh` activates it but `run.sh` does not. Consider activating the venv in `run.sh` as well when present.

### 4.2 Fonts and assets
- **League Spartan in-project**: `League_Spartan/static/LeagueSpartan-Regular.ttf` exists in the repo. Add it to the font search list so it works even when the font isn’t installed for the OS (e.g. in Docker or CI).
- **`find_league_spartan.py` / `list_fonts.py`**: Handy for debugging; mention them in README under “Troubleshooting” or “Development”.

### 4.3 Testing and CI
- **`test_single.py`**: Keep banner lookup aligned with `input/` assets so local test runs match the UI defaults.
- **Snapshot/design test**: A test that renders one card to a PNG and (optionally) diffs against a golden image can catch layout regressions; add when the design is stable.

---

## 5. Quick Wins (High Impact, Low Effort)

1. **Add project-local League Spartan** to the font search:  
   `Path(__file__).resolve().parent / "League_Spartan" / "static" / "LeagueSpartan-Regular.ttf"`.
2. **Use a unique temp file in `create_pdf`**: e.g. `tempfile.NamedTemporaryFile(suffix='.png', delete=False)` and `os.unlink` after `c.save()`.
3. **Make “Annual Member” year configurable**: e.g. `--year 2026` in CLI and a `st.number_input` or `st.text_input` in the UI, passed into the generator.
4. **Banner fallback in UI**: if `input/banner.png` is missing, try `input/Central Texas Bengali Association Banner.png`.
5. **Constants for spacing**: e.g. `NAME_TO_MEMBER_PX = 55`, `MEMBER_TO_QR_PX = 50`, and use them in `create_card_image`.
6. **Remove unused import** `ImageReader` from `app.py`.
7. **Card border**: 1px `#d0cec0` around the full card in `create_card_image` for a more finished look.
8. **README**: Align with 2.5"×4", three-zone layout, #e5e2d1, League Spartan, and correct banner filename.

---

## 6. Suggested Order of Implementation

| Priority | Item |
|----------|------|
| P0 | Unique temp file in `create_pdf`; project-local League Spartan in font search; banner fallback (`banner.png` vs `Central Texas Bengali Association Banner.png`). |
| P1 | Configurable “Annual Member” year; design constants (spacing, colors); optional 1px card border; README update. |
| P2 | Font helper + League Spartan Bold for name; QR container border; long-name handling; UI default-path and session-state fixes. |
| P3 | Batch ZIP download; design preview; `read_members_from_dataframe` (or keep temp CSV); CSV header handling. |
