# CTBA Membership Card Generator

Generates PDF membership cards with QR codes for CTBA (Central Texas Bengali Association) from **Excel** or CSV.

## Features

- **Upload file (Excel/CSV)**: must start with columns (in order): `Member ID, Full Name, Membership Type, Adult, Child`
- **AppSheet input** (optional): fetch rows via AppSheet REST API (“Find”) using **App ID**, **Table name**, and **Application access key**
- QR codes (member ID + name), banner, League Spartan, configurable year
- Portrait cards (2.5" × 4"); save to a folder of your choice; 6 previews in a 3×2 grid

## Requirements

- Python 3.7 or higher
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone or navigate to this directory
2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Optional: dev tools

```bash
pip install -r requirements-dev.txt
pytest
pip-audit
```

## Usage

### 🎨 Web UI (Recommended)

The easiest way to use the application is through the interactive web interface:

**From the project folder** (required):

```bash
cd /path/to/membership-card
./run_ui.sh
```

If that fails, try:

```bash
./run_local.sh
# or: python3 -m streamlit run ui.py
# or: streamlit run streamlit_app.py
```

If you see *"Streamlit not found"* or *"command not found: streamlit"*, install and run:

```bash
pip install -r requirements.txt
python3 -m streamlit run ui.py
```

This will open a web browser where you can:
- Upload **Excel** (`.xlsx`) or CSV, or use the default (Excel in `input/`)
- Or switch to **AppSheet API** as the data source
- Upload banner images or use the default
- **Select individual members** using checkboxes
- **Select multiple members** at once
- **Select all members** with one click
- Search/filter members by name
- Preview generated cards
- Generate cards for selected members

**Features:**
- ✅ Select one, a few, or all members
- 🔍 Search and filter members
- 👀 Preview cards before downloading
- 📊 Progress tracking during generation
- 📁 Easy file management

### AppSheet (optional)
In the UI sidebar, switch **Data source** to **AppSheet API**, then provide:
- **Region domain** (usually `www.appsheet.com`)
- **App ID**
- **Table name**
- **Application access key** (don’t commit this)

The app fetches rows via the AppSheet “Find” API and maps them into the required columns (`Member ID`, `Full Name`, `Membership Type`, `Adult`, `Child`).

### Streamlit Cloud deployment
- **Main file path must be `streamlit_app.py`** (not `ui.py`). This entrypoint loads the real UI and avoids module name collisions that cause blank pages.
- If the app is slow or fails to load: check the Cloud app’s **Settings → Main file path** is `streamlit_app.py`, then check **Manage app → Logs** for errors.

### 💻 Command Line

```bash
python app.py <data_file> <banner> [-o output] [-y year]
```

- `data_file`: Excel (`.xlsx`) or CSV path
- `banner`: Banner image path
- `-o`: Output directory (default: `output`)
- `-y`: Year in "Annual Member {year}" (default: `2026`)

**Example with template CSV (safe, committed to repo):**

```bash
python app.py "input/template_members.csv" "input/Central Texas Bengali Association Banner.png" -o output
```

## Input: Upload file (Excel/CSV)

Your upload must start with these columns (in order):

`Member ID, Full Name, Membership Type, Adult, Child`

Rows missing Name or Member ID are skipped. Duplicate IDs are dropped.

### Public repo note (privacy)
This repository is intended to be public and Streamlit-hosted. **Do not commit real member datasets**. Use `input/template_members.csv` as the template and upload your real file at runtime, or fetch from AppSheet with Streamlit Secrets.

### Streamlit Secrets (recommended for AppSheet)
Create `.streamlit/secrets.toml` (not committed) using `.streamlit/secrets.example.toml` as a starting point.

## Input: CSV

CSV must have a name column and a member ID column (used as-is). Example:

```csv
Name,Member_ID
John Doe,CTBA2026JDjohndoeGMA
```

## Output

- Each member card is saved as a separate PDF file
- Files are named: `{Name}.pdf`
- All PDFs are saved in the specified output directory (default: `output/`)

## Card Design

Each membership card uses a **portrait layout** (2.5" × 4") with:

**Top:** Banner image (resized to fit, aspect ratio preserved)

**Center:** QR code (centered on the card, white background) encoding **only the Member ID**

**Below QR:**  
- Member name (centered, League Spartan Bold)  
- "Annual Member CTBA 2026" (fixed text)  
- Membership type (wrapped if long)  
- Adult / Kids counts

**Style:** Background `#e5e2d1`, 1px border, project-local or system League Spartan fonts

## Notes

- **Excel:** requires `openpyxl` (`pip install openpyxl` or `pip install -r requirements.txt`).
- The app looks for `input/banner.png` or `input/Central Texas Bengali Association Banner.png` when using the default banner.
- League Spartan is loaded from `League_Spartan/static/` or the system.
- To inspect the Excel sheet and columns: `python inspect_excel.py`.

For more ideas, see [IMPROVEMENTS.md](IMPROVEMENTS.md).
