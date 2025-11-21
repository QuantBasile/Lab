# Marktanteil Lab

Interactive Tkinter dashboard to analyse **issuer market share** in equity derivatives, with a focus on:

- Volume and trade activity over time
- Issuer market share (% and absolute)
- CALL vs PUT behaviour (daily, weekly, rolling)
- HSBC-specific market share views

The app is designed as a **local, no-server, no-database “lab”** where you can load a large dataset (or generate synthetic data), apply fast filters, and explore multiple analytical views in parallel.

---

## ✨ Main Features

- **Desktop UI (Tkinter + ttk)**
  - Top bar with date range and product selectors
  - Side filters panel with:
    - Categorical filters (dual list, search)
    - Numeric filters (min/max)
    - Date filters (with embedded calendar widgets)
  - Central area with tabs (sheets) for different analyses

- **High-performance filtering**
  - Core data handled in **Pandas**
  - Filtering implemented in **NumPy** using cached arrays
  - Designed to work smoothly with up to ~1M rows

- **Multiple analytical sheets**
  - **Table**: paginated, sortable table of transactions
  - **Volume sheet**: time-series views of volumes over time
  - **Volume table**: issuer-level volume breakdown
  - **Volume summary** (optional): aggregate summary by issuer / period
  - **Volume %**: issuer share in %, daily / rolling / weekly / monthly
  - **CALL/PUT rolling 7d** (optional): 7-day rolling volume per issuer and CALL/PUT
  - **Call/Put Share** (optional): CALL vs PUT share dashboards (daily, weekly, issuer, global)
  - **HSBC Marktanteil** (optional): HSBC-specific market share views
  - **Top 20 Names**: top underlyings with KPIs and evolution

- **Consistent issuer coloring**
  - Colors for issuers defined centrally in `issuer_colors.py`
  - Alias system maps noisy real-world issuer names → canonical codes
  - Unknown issuers get deterministic fallback colors

- **Logging**
  - Centralised configuration with rotating file handler
  - Uniform logging for debugging and performance checks

---

## 🧱 Project Structure

A typical layout for this project:

```text
marktanteil_lab/
├─ README.md
├─ main_app.py              # CLI / entry point (creates Tk and runs the app)
├─ Datos.py                 # Vectorised fake / synthetic data generator
├─ app/
│  ├─ __init__.py
│  └─ app.py                # Builds the Tk root and launches MainWindow
├─ ui/
│  ├─ __init__.py
│  ├─ main_window.py        # Main window: topbar, filters panel, notebook with sheets
│  ├─ table_widget.py       # Generic paginated, sortable table (TableFrame)
│  ├─ filters_panel.py      # Dynamic filters (categorical, numeric, date)
│  ├─ simple_calendar.py    # Lightweight DateEntry replacement (no external tkcalendar)
│  ├─ volume_sheet.py       # Volume over time (plots)
│  ├─ volume_table.py       # Volume breakdown table per issuer / period
│  ├─ volume_summary.py     # (Optional) Summary of volumes per issuer / period
│  ├─ volume_perc.py        # VolumePercentage: % volume share per issuer (daily/rolling/weekly/monthly)
│  ├─ call_put_rolling.py   # (Optional) 7-day rolling CALL/PUT volume by issuer
│  ├─ call_put_share.py     # (Optional) CALL vs PUT share dashboards (daily/weekly/issuer/pie)
│  ├─ top20_names.py        # Top 20 names / underlyings with KPIs
│  └─ hsbc_marktanteil.py   # (Optional) HSBC-specific market share view
├─ services/
│  ├─ __init__.py
│  └─ data_service.py       # DataService: generation + NumPy-based filtering
└─ utils/
   ├─ __init__.py
   ├─ logging_config.py     # Logging configuration (rotating file handler)
   └─ issuer_colors.py      # Central issuer → color mapping + alias handling


