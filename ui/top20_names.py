# ui/top20_names.py
# ---------------------------------------------------------------------
# Top 20 Names v3 – English version
#   • Table (left 60%)
#   • KPI box (right 40%)
#   • 3 plots in a single row:
#         1. 7-day rolling volume
#         2. 7-day rolling market share
#         3. Weekly volume
#   • Background: light purple (#F5EDFF)
#   • HSBC in red (#d00000), market in grey (#555555)
#   • Very fast thanks to NumPy
# ---------------------------------------------------------------------

import tkinter as tk
from tkinter import ttk

import numpy as np
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

HSBC_RED = "#d00000"
MARKET_GREY = "#555555"
BG_LILA = "#F5EDFF"


class Top20Names(ttk.Frame):
    """
    Top 20 names dashboard.

    Top area:
        • Table on the left (~60%)
        • KPI box on the right (~40%)

    Bottom area:
        • 3 plots in a single row:
            1) 7-day rolling volume
            2) 7-day rolling market share
            3) Weekly volume
    """

    def __init__(self, master=None):
        super().__init__(master)

        # NumPy caches
        self._names = None
        self._txn = None
        self._dates = None
        self._is_hsbc = None
        self._callopt = None

        self._df = None
        self._current_name = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI – full layout
    # ------------------------------------------------------------------
    def _build_ui(self):

        # Global background
        self.configure(style="Lila.TFrame")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # STYLE
        style = ttk.Style(self)
        style.configure("Lila.TFrame", background=BG_LILA)
        style.configure("Lila.TLabel", background=BG_LILA, foreground="black")

        # Card style for KPIs: white cards on purple background
        style.configure(
            "KPI.Card.TFrame",
            background="white",
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "KPI.Title.TLabel",
            background="white",
            foreground="#4c1d95",   # dark purple
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "KPI.Value.TLabel",
            background="white",
            foreground="#111111",
            font=("Segoe UI", 11),
        )

        # ================================================================
        # TOP AREA: table (left) + KPI box (right)
        # ================================================================
        top = ttk.Frame(self, style="Lila.TFrame")
        top.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Column distribution - 60% / 40%
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)
        top.rowconfigure(0, weight=1)

        # ---------------------------------------------------------------
        # 1) Table on the left
        # ---------------------------------------------------------------
        table_frame = ttk.Frame(top, style="Lila.TFrame")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        lbl_tab = ttk.Label(
            table_frame,
            text="Top 20 names by total volume",
            style="Lila.TLabel",
            font=("Segoe UI Semibold", 12),
        )
        lbl_tab.pack(anchor="w", pady=(0, 6))

        self.tree = ttk.Treeview(
            table_frame,
            columns=("name", "vol", "vol_hsbc", "share", "dw", "dm"),
            show="headings",
            height=12,
        )

        self.tree.heading("name", text="Name")
        self.tree.heading("vol", text="Total volume")
        self.tree.heading("vol_hsbc", text="HSBC volume")
        self.tree.heading("share", text="Market share (%)")
        self.tree.heading("dw", text="Δ week (%)")
        self.tree.heading("dm", text="Δ month (%)")

        # Alignment
        self.tree.column("name", width=200, anchor="w")
        for c in ("vol", "vol_hsbc", "share", "dw", "dm"):
            self.tree.column(c, width=120, anchor="center")

        self.tree.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ---------------------------------------------------------------
        # 2) KPI box on the right (40%)
        # ---------------------------------------------------------------
        kpi_box = ttk.Frame(top, style="Lila.TFrame")
        kpi_box.grid(row=0, column=1, sticky="nsew")

        lbl_kpi = ttk.Label(
            kpi_box,
            text="Key figures",
            style="Lila.TLabel",
            font=("Segoe UI Semibold", 14),
        )
        lbl_kpi.pack(anchor="w", pady=(0, 6))

        kpi_grid = ttk.Frame(kpi_box, style="Lila.TFrame")
        kpi_grid.pack(fill="both", expand=True)

        # 2 columns for cards
        for c in (0, 1):
            kpi_grid.columnconfigure(c, weight=1)

        row = 0
        self.kpi_share = self._create_kpi_card(
            kpi_grid, "Current market share (HSBC)", row, 1
        )

        self.kpi_callput = self._create_kpi_card(
            kpi_grid, "Call/Put ratio (HSBC vs market)", row, 0
        )

        row += 1
        self.kpi_best_week = self._create_kpi_card(
            kpi_grid, "Best week (market share, HSBC)", row, 0
        )
        self.kpi_worst_week = self._create_kpi_card(
            kpi_grid, "Worst week (market share, HSBC)", row, 1
        )

        row += 1
        self.kpi_best_month = self._create_kpi_card(
            kpi_grid, "Best month (market share, HSBC)", row, 0
        )
        self.kpi_worst_month = self._create_kpi_card(
            kpi_grid, "Worst month (market share, HSBC)", row, 1
        )

        row += 1
        self.kpi_best_cp_day = self._create_kpi_card(
            kpi_grid, "Highest Call/Put ratio (name)", row, 0
        )
        self.kpi_worst_cp_day = self._create_kpi_card(
            kpi_grid, "Lowest Call/Put ratio (name)", row, 1
        )

        row += 1
        self.kpi_issuer_week_change = self._create_kpi_card(
            kpi_grid, "Largest increase by issuer (week)", row, 0
        )
        self.kpi_issuer_month_change = self._create_kpi_card(
            kpi_grid, "Largest increase by issuer (month)", row, 1
        )

        row += 1
        self.kpi_best_issuer = self._create_kpi_card(
            kpi_grid, "Best issuer (name)", row, 0
        )

        # ================================================================
        # BOTTOM AREA: single row with 3 plots
        # ================================================================
        bottom = ttk.Frame(self, style="Lila.TFrame")
        bottom.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(2, weight=1)
        bottom.rowconfigure(0, weight=1)

        # One Figure with 3 subplots side-by-side
        self.fig = Figure(figsize=(14, 4.5), dpi=100)
        gs = self.fig.add_gridspec(1, 3, wspace=0.32)
        self.fig.subplots_adjust(bottom=0.25, left=0.06, right=0.98)

        self.ax_rollvol = self.fig.add_subplot(gs[0, 0])
        self.ax_rollshare = self.fig.add_subplot(gs[0, 1])
        self.ax_weekvol = self.fig.add_subplot(gs[0, 2])

        self.canvas = FigureCanvasTkAgg(self.fig, master=bottom)
        self.canvas.get_tk_widget().grid(
            row=0, column=0, columnspan=3, sticky="nsew"
        )

    # ------------------------------------------------------------------
    # Helper to create KPI cards (grid, 2 columns)
    # ------------------------------------------------------------------
    def _create_kpi_card(self, parent, title, row, col):
        frame = ttk.Frame(parent, style="KPI.Card.TFrame")
        frame.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
        parent.rowconfigure(row, weight=0)

        lbl_title = ttk.Label(
            frame,
            text=title,
            style="KPI.Title.TLabel",
        )
        lbl_title.pack(anchor="w", padx=8, pady=(6, 2))

        lbl_value = ttk.Label(
            frame,
            text="–",
            style="KPI.Value.TLabel",
        )
        lbl_value.pack(anchor="w", padx=8, pady=(0, 6))

        return lbl_value

    # ------------------------------------------------------------------
    # EVENT – name selected
    # ------------------------------------------------------------------
    def _on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        name = sel[0]
        self._current_name = name

        self._update_kpis(name)
        self._update_roll_plots(name)
        self._update_week_plot(name)
        self.canvas.draw_idle()

    # ======================================================================
    #   UPDATE – main data intake from filtered DF
    # ======================================================================
    def update_plot(self, df):
        """Called from MainWindow._refresh_views()."""
        if df is None or df.empty:
            self._df = None
            self.tree.delete(*self.tree.get_children())
            self._clear_all_plots_and_kpis()
            return

        self._df = df.copy()

        # Convert to NumPy for maximum speed
        self._names = self._df["NAME"].to_numpy()
        self._txn = self._df["TXN_AMT"].to_numpy(dtype=float)
        self._dates = pd.to_datetime(self._df["TRANSACTION_DATE"]).to_numpy()
        self._is_hsbc = (self._df["ISSUER_NAME"].to_numpy() == "HSBC")
        self._callopt = self._df["CALL_OPTION"].to_numpy()
        self._issuers = self._df["ISSUER_NAME"].to_numpy()
        self._weeks = self._df["WEEK"].to_numpy()

        # Rebuild table
        self._build_top20_table()

        # Clear KPI box and plots
        self._clear_all_plots_and_kpis()

        # Global KPIs (Call/Put overall, best issuer) – currently unused
        # self._compute_global_stats()

    # ======================================================================
    #   TOP 20 COMPUTATION – very fast NumPy implementation
    # ======================================================================
    def _build_top20_table(self):

        names = self._names
        txn = self._txn
        dates = self._dates
        is_hsbc = self._is_hsbc

        # --------------------------------------------------------------
        # 1) All names → unique + inverse index
        # --------------------------------------------------------------
        uniq_names, inv = np.unique(names, return_inverse=True)
        n_unique = uniq_names.size

        # --------------------------------------------------------------
        # 2) Total volume per name
        # --------------------------------------------------------------
        vol_total = np.bincount(inv, weights=txn, minlength=n_unique)

        # --------------------------------------------------------------
        # 3) HSBC volume per name
        # --------------------------------------------------------------
        vol_hsbc = np.bincount(inv, weights=txn * is_hsbc, minlength=n_unique)

        # --------------------------------------------------------------
        # 4) Market share (%)
        # --------------------------------------------------------------
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(vol_total > 0, vol_hsbc / vol_total, 0.0)

        # --------------------------------------------------------------
        # 5) Weekly / monthly deltas – windows in days
        # --------------------------------------------------------------
        d_int = dates.astype("datetime64[D]").astype(int)
        d_max = d_int.max()

        w_now = d_max - 7
        w_prev = d_max - 14
        m_now = d_max - 30
        m_prev = d_max - 60

        mask_week = (d_int >= w_now)
        mask_week_prev = (d_int >= w_prev) & (d_int < w_now)
        mask_month = (d_int >= m_now)
        mask_month_prev = (d_int >= m_prev) & (d_int < m_now)

        def fast_share(mask):
            if not mask.any():
                return np.zeros(n_unique)
            inv_m = inv[mask]
            t_m = txn[mask]
            h_m = is_hsbc[mask]

            tot = np.bincount(inv_m, weights=t_m, minlength=n_unique)
            hs = np.bincount(inv_m, weights=t_m * h_m, minlength=n_unique)

            with np.errstate(divide="ignore", invalid="ignore"):
                return np.where(tot > 0, hs / tot, 0.0)

        share_w = fast_share(mask_week)
        share_w_prev = fast_share(mask_week_prev)
        share_m = fast_share(mask_month)
        share_m_prev = fast_share(mask_month_prev)

        d_week = (share_w - share_w_prev) * 100.0
        d_month = (share_m - share_m_prev) * 100.0

        # --------------------------------------------------------------
        # 6) Top 20 by total volume
        # --------------------------------------------------------------
        idx_top = np.argsort(vol_total)[::-1][:20]

        # --------------------------------------------------------------
        # 7) Fill table
        # --------------------------------------------------------------
        self.tree.delete(*self.tree.get_children())

        self._uniq_names = uniq_names
        self._vol_total = vol_total
        self._vol_hsbc = vol_hsbc
        self._share = share
        self._d_week = d_week
        self._d_month = d_month
        self._inv = inv  # used later for KPIs and plots

        for i in idx_top:
            nm = uniq_names[i]
            vt = vol_total[i]
            vh = vol_hsbc[i]
            sh = share[i] * 100
            dw = d_week[i]
            dm = d_month[i]

            self.tree.insert(
                "",
                "end",
                iid=nm,
                values=(
                    nm,
                    f"{vt:,.0f}",
                    f"{vh:,.0f}",
                    f"{sh:.2f}",
                    f"{dw:+.2f}",
                    f"{dm:+.2f}",
                ),
            )

    # ======================================================================
    #   GLOBAL KPIs – overall Call/Put + best issuer (currently unused)
    # ======================================================================
    def _compute_global_stats(self):
        """Compute KPIs over the entire filtered universe."""
        if self._df is None or self._df.empty:
            self._cp_best_day = None
            self._cp_worst_day = None
            self._best_issuer_name = None
            return

        # ---------- Call/Put ratio per day (total market) ----------
        d_all = self._dates.astype("datetime64[D]").astype(int)
        days_unique, inv_days = np.unique(d_all, return_inverse=True)
        n_days = days_unique.size

        mask_call = (self._callopt == "CALL")
        mask_put = (self._callopt == "PUT")

        vol_call = np.bincount(
            inv_days, weights=self._txn * mask_call, minlength=n_days
        )
        vol_put = np.bincount(
            inv_days, weights=self._txn * mask_put, minlength=n_days
        )

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(vol_put > 0, vol_call / vol_put, np.nan)

        valid = ~np.isnan(ratio)
        if valid.any():
            idx_max = np.nanargmax(ratio)
            idx_min = np.nanargmin(ratio)

            self._cp_best_day = days_unique[idx_max].astype("datetime64[D]")
            self._cp_best_ratio = ratio[idx_max]

            self._cp_worst_day = days_unique[idx_min].astype("datetime64[D]")
            self._cp_worst_ratio = ratio[idx_min]
        else:
            self._cp_best_day = None
            self._cp_worst_day = None

        # ---------- Best issuer (overall) ----------
        issuers = self._df["ISSUER_NAME"].to_numpy()
        uniq_iss, inv_iss = np.unique(issuers, return_inverse=True)
        vol_iss = np.bincount(inv_iss, weights=self._txn, minlength=uniq_iss.size)

        idx_best = np.argmax(vol_iss)
        self._best_issuer_name = uniq_iss[idx_best]
        self._best_issuer_vol = vol_iss[idx_best]

        # HSBC volume for that issuer
        hsbc_vol = 0.0
        hs_idx = np.where(uniq_iss == "HSBC")[0]
        if hs_idx.size > 0:
            hsbc_vol = vol_iss[hs_idx[0]]

        self._best_issuer_hsbc_share = (
            hsbc_vol / self._best_issuer_vol * 100.0
            if self._best_issuer_vol > 0
            else 0.0
        )

    # ======================================================================
    # CLEAR EVERYTHING (KPIs + 3 plots)
    # ======================================================================
    def _clear_all_plots_and_kpis(self):

        # Reset KPI values
        for lbl in (
            self.kpi_callput,
            self.kpi_share,
            self.kpi_best_week,
            self.kpi_worst_week,
            self.kpi_best_month,
            self.kpi_worst_month,
            self.kpi_best_cp_day,
            self.kpi_worst_cp_day,
            self.kpi_issuer_week_change,
            self.kpi_issuer_month_change,
            self.kpi_best_issuer,
        ):
            lbl.config(text="–")

        # Clear all axes
        self.ax_rollvol.clear()
        self.ax_rollshare.clear()
        self.ax_weekvol.clear()
        self.canvas.draw_idle()

    # ======================================================================
    #   KPI COMPUTATION FOR A SINGLE NAME
    # ======================================================================
    def _update_kpis(self, name):

        if self._df is None:
            return

        mask = (self._names == name)
        if not mask.any():
            return

        tsel = self._txn[mask]
        hsel = self._is_hsbc[mask]
        csel = self._callopt[mask]
        dsel = self._dates[mask]

        # ---------- 1) Call/Put ratio (HSBC vs market) ----------
        mask_call = (csel == "CALL")
        mask_put = (csel == "PUT")

        vol_call_h = np.sum(tsel[mask_call] * hsel[mask_call])
        vol_put_h = np.sum(tsel[mask_put] * hsel[mask_put])

        vol_call_r = np.sum(tsel[mask_call] * (~hsel[mask_call]))
        vol_put_r = np.sum(tsel[mask_put] * (~hsel[mask_put]))

        def ratio(a, b):
            return a / b if b > 0 else np.nan

        r_h = ratio(vol_call_h, vol_put_h)
        r_r = ratio(vol_call_r, vol_put_r)

        if not np.isnan(r_h) and not np.isnan(r_r):
            cp_text = f"HSBC: {r_h:.2f}   |   Market: {r_r:.2f}"
        else:
            cp_text = "–"
        self.kpi_callput.config(text=cp_text)

        # ---------- 2) Current market share (HSBC) ----------
        total = np.sum(tsel)
        hs = np.sum(tsel * hsel)
        share = (hs / total * 100.0) if total > 0 else 0.0
        self.kpi_share.config(text=f"{share:.2f} %")

        # ---------- 3) Best / worst week (market share, W-MON from WEEK) ----------
        if self._weeks is not None:
            wsel = self._weeks[mask]
            weeks = pd.to_datetime(wsel).to_numpy(dtype="datetime64[D]")
        else:
            dt = pd.to_datetime(dsel)
            p = dt.to_period("W-MON")
            weeks = p.start_time.values.astype("datetime64[D]")

        uniq_weeks, inv_w = np.unique(weeks, return_inverse=True)
        n_weeks = uniq_weeks.size

        tot_w = np.bincount(inv_w, weights=tsel, minlength=n_weeks)
        hs_w = np.bincount(inv_w, weights=tsel * hsel, minlength=n_weeks)

        with np.errstate(divide="ignore", invalid="ignore"):
            share_w = np.where(tot_w > 0, hs_w / tot_w * 100.0, np.nan)

        valid_w = ~np.isnan(share_w)
        if valid_w.any():
            idx_best = np.nanargmax(share_w)
            idx_worst = np.nanargmin(share_w)
            self.kpi_best_week.config(
                text=f"{str(uniq_weeks[idx_best])}: {share_w[idx_best]:.2f} %"
            )
            self.kpi_worst_week.config(
                text=f"{str(uniq_weeks[idx_worst])}: {share_w[idx_worst]:.2f} %"
            )
        else:
            self.kpi_best_week.config(text="–")
            self.kpi_worst_week.config(text="–")

        # ---------- 4) Best / worst month (market share) ----------
        month_int = dsel.astype("datetime64[M]").astype(int)
        mmin = month_int.min()
        mmax = month_int.max()
        n_months = mmax - mmin + 1
        pos_m = month_int - mmin

        tot_m = np.zeros(n_months)
        hs_m = np.zeros(n_months)
        np.add.at(tot_m, pos_m, tsel)
        np.add.at(hs_m, pos_m, tsel * hsel)

        with np.errstate(divide="ignore", invalid="ignore"):
            share_m = np.where(tot_m > 0, hs_m / tot_m * 100.0, np.nan)

        months = np.arange(mmin, mmax + 1).astype("datetime64[M]")
        valid_m = ~np.isnan(share_m)
        if valid_m.any():
            idx_bestm = np.nanargmax(share_m)
            idx_worstm = np.nanargmin(share_m)
            self.kpi_best_month.config(
                text=f"{str(months[idx_bestm])}: {share_m[idx_bestm]:.2f} %"
            )
            self.kpi_worst_month.config(
                text=f"{str(months[idx_worstm])}: {share_m[idx_worstm]:.2f} %"
            )
        else:
            self.kpi_best_month.config(text="–")
            self.kpi_worst_month.config(text="–")

        # ---------- 5) Highest / lowest Call/Put (for this name) ----------
        # per day: total market and HSBC separately
        d_all = dsel.astype("datetime64[D]").astype(int)
        days_unique, inv_days = np.unique(d_all, return_inverse=True)
        n_days = days_unique.size

        mask_call = (csel == "CALL")
        mask_put = (csel == "PUT")

        # Market (all issuers for this name)
        vol_call_m = np.bincount(
            inv_days, weights=tsel * mask_call, minlength=n_days
        )
        vol_put_m = np.bincount(
            inv_days, weights=tsel * mask_put, minlength=n_days
        )

        # HSBC only
        vol_call_h_d = np.bincount(
            inv_days, weights=tsel * mask_call * hsel, minlength=n_days
        )
        vol_put_h_d = np.bincount(
            inv_days, weights=tsel * mask_put * hsel, minlength=n_days
        )

        with np.errstate(divide="ignore", invalid="ignore"):
            ratio_m = np.where(vol_put_m > 0, vol_call_m / vol_put_m, np.nan)
            ratio_h = np.where(vol_put_h_d > 0, vol_call_h_d / vol_put_h_d, np.nan)

        valid = ~np.isnan(ratio_m)
        if valid.any():
            idx_best = np.nanargmax(ratio_m)
            idx_worst = np.nanargmin(ratio_m)

            day_best = days_unique[idx_best].astype("datetime64[D]")
            day_worst = days_unique[idx_worst].astype("datetime64[D]")

            text_best = (
                f"{str(day_best)}  –  Market: {ratio_m[idx_best]:.2f}   "
                f"|   HSBC: {ratio_h[idx_best]:.2f}"
            )
            text_worst = (
                f"{str(day_worst)}  –  Market: {ratio_m[idx_worst]:.2f}   "
                f"|   HSBC: {ratio_h[idx_worst]:.2f}"
            )
            self.kpi_best_cp_day.config(text=text_best)
            self.kpi_worst_cp_day.config(text=text_worst)
        else:
            self.kpi_best_cp_day.config(text="–")
            self.kpi_worst_cp_day.config(text="–")

        # ---------- 6) Best issuer for this name ----------
        issuers_sel = self._issuers[mask]
        uniq_iss, inv_iss = np.unique(issuers_sel, return_inverse=True)
        vol_iss = np.bincount(inv_iss, weights=tsel, minlength=uniq_iss.size)

        idx_best = np.argmax(vol_iss)
        best_name = uniq_iss[idx_best]
        best_vol = vol_iss[idx_best]

        # Market share of this issuer within this name
        total_name_vol = np.sum(tsel)
        share_best = (
            best_vol / total_name_vol * 100.0 if total_name_vol > 0 else 0.0
        )

        txt = (
            f"Issuer: {best_name}\n"
            f"Volume (name): {best_vol:,.0f}\n"
            f"Market share (name): {share_best:.2f} %"
        )
        self.kpi_best_issuer.config(text=txt)

        # ---------- 7) Issuer with largest increase (week / month) ----------
        # Basis: last week vs previous week, last month vs previous month
        if dsel.size > 0:
            d_int_full = dsel.astype("datetime64[D]").astype(int)
            d_max = d_int_full.max()

            # Weekly windows
            w_now = d_max - 7
            w_prev = d_max - 14

            mask_w_now = (d_int_full >= w_now)
            mask_w_prev = (d_int_full >= w_prev) & (d_int_full < w_now)

            # Monthly windows (30 days)
            m_now = d_max - 30
            m_prev = d_max - 60

            mask_m_now = (d_int_full >= m_now)
            mask_m_prev = (d_int_full >= m_prev) & (d_int_full < m_now)

            issuers_sel = self._issuers[mask]

            def best_issuer_change(mask_now, mask_prev, min_vol=10.0):
                if (not mask_now.any()) and (not mask_prev.any()):
                    return None, None

                iss_now = issuers_sel[mask_now]
                vol_now = tsel[mask_now]
                iss_prev = issuers_sel[mask_prev]
                vol_prev = tsel[mask_prev]

                if iss_now.size == 0:
                    return None, None

                uniq_now, inv_now = np.unique(
                    iss_now, return_inverse=True
                )
                vol_now_tot = np.bincount(
                    inv_now, weights=vol_now, minlength=uniq_now.size
                )

                # Map previous-period volume onto the same issuer set
                vol_prev_map = np.zeros_like(vol_now_tot)
                if iss_prev.size > 0:
                    uniq_prev, inv_prev = np.unique(
                        iss_prev, return_inverse=True
                    )
                    vol_prev_tot = np.bincount(
                        inv_prev, weights=vol_prev, minlength=uniq_prev.size
                    )
                    for i, issuer in enumerate(uniq_now):
                        j = np.where(uniq_prev == issuer)[0]
                        if j.size > 0:
                            vol_prev_map[i] = vol_prev_tot[j[0]]

                # Only issuers with "significant" volume in both periods
                mask_valid = (vol_prev_map >= min_vol) & (
                    vol_now_tot >= min_vol
                )
                if not mask_valid.any():
                    return None, None

                vol_now_sig = vol_now_tot[mask_valid]
                vol_prev_sig = vol_prev_map[mask_valid]
                uniq_sig = uniq_now[mask_valid]

                # Relative change in %
                change = (
                    (vol_now_sig - vol_prev_sig) / vol_prev_sig * 100.0
                )

                idx_best = np.argmax(change)
                return uniq_sig[idx_best], change[idx_best]

            best_w_issuer, best_w_change = best_issuer_change(
                mask_w_now, mask_w_prev
            )
            if best_w_issuer is not None:
                if np.isinf(best_w_change):
                    txt_w = (
                        f"{best_w_issuer}: +∞ % (previous week 0 volume)"
                    )
                else:
                    txt_w = f"{best_w_issuer}: {best_w_change:+.2f} %"
                self.kpi_issuer_week_change.config(text=txt_w)
            else:
                self.kpi_issuer_week_change.config(text="–")

            best_m_issuer, best_m_change = best_issuer_change(
                mask_m_now, mask_m_prev
            )
            if best_m_issuer is not None:
                if np.isinf(best_m_change):
                    txt_m = (
                        f"{best_m_issuer}: +∞ % (previous month 0 volume)"
                    )
                else:
                    txt_m = f"{best_m_issuer}: {best_m_change:+.2f} %"
                self.kpi_issuer_month_change.config(text=txt_m)
            else:
                self.kpi_issuer_month_change.config(text="–")
        else:
            self.kpi_issuer_week_change.config(text="–")
            self.kpi_issuer_month_change.config(text="–")

    # ======================================================================
    #   ROLLING VOLUME + ROLLING MARKET SHARE (7 days)
    # ======================================================================
    def _update_roll_plots(self, name):
        """
        7-day rolling volume + 7-day rolling market share.
        Logic analogous to VolumeSheet (volume) and VolumePercentage (share).
        """
        if self._df is None:
            return

        s = self._df[self._df["NAME"] == name].copy()
        if s.empty:
            self.ax_rollvol.clear()
            self.ax_rollshare.clear()
            return

        # DAY as date (similar to VolumeSheet/VolumePercentage)
        s["DAY"] = pd.to_datetime(s["DAY"])
        s["IS_HSBC"] = (s["ISSUER_NAME"] == "HSBC")

        # Full daily range
        full_range = pd.date_range(s["DAY"].min(), s["DAY"].max(), freq="D")

        # ---------- 1) DAILY VOLUME (total, HSBC, rest) ----------
        daily_tot = (
            s.groupby("DAY")["TXN_AMT"]
            .sum()
            .reindex(full_range)
            .fillna(0.0)
        )
        daily_hs = (
            s[s["IS_HSBC"]]
            .groupby("DAY")["TXN_AMT"]
            .sum()
            .reindex(full_range)
            .fillna(0.0)
        )
        daily_rest = daily_tot - daily_hs

        # ---------- 2) 7-DAY ROLLING (volume) ----------
        roll_tot = daily_tot.rolling(window=7, min_periods=1).mean()
        roll_hs = daily_hs.rolling(window=7, min_periods=1).mean()
        roll_rest = daily_rest.rolling(window=7, min_periods=1).mean()

        x = full_range.to_pydatetime()

        # Plot – rolling volume
        ax = self.ax_rollvol
        ax.clear()

        ax.plot(x, roll_hs.values, color=HSBC_RED, linewidth=2.0, label="HSBC (7d)")
        ax.plot(
            x,
            roll_rest.values,
            color=MARKET_GREY,
            linewidth=1.6,
            label="Market (7d)",
        )

        ax.set_title(f"Rolling volume (7 days) – {name}")
        ax.grid(True, alpha=0.3)
        self._set_date_xticks(ax, np.array(x, dtype="datetime64[D]"))
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._fmt_big))
        ax.legend()

        # ---------- 3) DAILY % SHARE (HSBC of daily total) ----------
        tot_vals = daily_tot.values
        hs_vals = daily_hs.values
        pct_daily = np.full_like(tot_vals, np.nan, dtype=float)

        mask_valid = tot_vals > 0.0
        pct_daily[mask_valid] = (
            hs_vals[mask_valid] / tot_vals[mask_valid]
        ) * 100.0

        # Rolling mean of daily % share (like VolumePercentage)
        roll_share = (
            pd.Series(pct_daily, index=full_range)
            .rolling(window=7, min_periods=1)
            .mean()
        )

        # Plot – rolling market share
        ax = self.ax_rollshare
        ax.clear()

        ax.plot(x, roll_share.values, color=HSBC_RED, linewidth=2.2)

        ax.set_title(f"Rolling market share (7 days) – {name}")
        ax.grid(True, alpha=0.3)
        self._set_date_xticks(ax, np.array(x, dtype="datetime64[D]"))
        ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.1f}%"))
        ax.set_ylim(bottom=0)

    # ======================================================================
    #   HELPER – formatting large numbers (k / M)
    # ======================================================================
    def _fmt_big(self, x, pos):
        if x >= 1_000_000:
            return f"{x/1_000_000:.1f}M"
        if x >= 1_000:
            return f"{x/1_000:.0f}k"
        return f"{x:.0f}"

    # ======================================================================
    #   WEEKLY VOLUME (HSBC vs market) – third plot
    # ======================================================================
    def _update_week_plot(self, name):

        mask = (self._names == name)
        if not mask.any():
            self.ax_weekvol.clear()
            return

        dsel = self._dates[mask]
        tsel = self._txn[mask]
        hsel = self._is_hsbc[mask]

        # Week start (Monday) directly from WEEK column, if present
        if self._weeks is not None:
            wsel = self._weeks[mask]
            weeks = pd.to_datetime(wsel).to_numpy(dtype="datetime64[D]")
        else:
            # Fallback: compute W-MON as in Daten.py
            dt = pd.to_datetime(dsel)
            p = dt.to_period("W-MON")
            weeks = p.start_time.values.astype("datetime64[D]")

        # Unique weeks + mapping
        uniq_weeks, inv = np.unique(weeks, return_inverse=True)
        n_weeks = uniq_weeks.size

        tot = np.bincount(inv, weights=tsel, minlength=n_weeks)
        hs = np.bincount(inv, weights=tsel * hsel, minlength=n_weeks)
        rest = tot - hs

        # --------------------------------------------------------------
        # Plot – weekly volume
        # --------------------------------------------------------------
        ax = self.ax_weekvol
        ax.clear()

        x = np.arange(n_weeks)
        bw = 0.42

        ax.bar(
            x - bw / 2,
            hs,
            width=bw,
            color=HSBC_RED,
            alpha=0.85,
            label="HSBC",
        )
        ax.bar(
            x + bw / 2,
            rest,
            width=bw,
            color=MARKET_GREY,
            alpha=0.85,
            label="Market",
        )

        ax.set_title(f"Weekly volume – {name}")
        ax.grid(True, axis="y", alpha=0.3)

        # X-ticks: max 5 weeks, incl. first and last, angled labels
        if n_weeks <= 5:
            tick_pos = x
            tick_weeks = uniq_weeks
        else:
            idx = np.linspace(0, n_weeks - 1, num=5, dtype=int)
            tick_pos = x[idx]
            tick_weeks = uniq_weeks[idx]

        labels = [str(w) for w in tick_weeks]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels(labels, rotation=25, ha="right")

        ax.yaxis.set_major_formatter(mticker.FuncFormatter(self._fmt_big))
        ax.legend()

    # ======================================================================
    #   CLEAR PLOTS ONLY
    # ======================================================================
    def _clear_all_plots(self):
        self.ax_rollvol.clear()
        self.ax_rollshare.clear()
        self.ax_weekvol.clear()
        self.canvas.draw_idle()

    # ======================================================================
    #   HELPER – few date ticks (max 5, incl. first/last)
    # ======================================================================
    def _set_date_xticks(self, ax, dates):
        dates = np.unique(dates)
        n = dates.size
        if n == 0:
            return
        if n <= 5:
            ticks = dates
        else:
            idx = np.linspace(0, n - 1, num=5, dtype=int)
            ticks = dates[idx]

        ax.set_xticks(ticks)
        labels = [str(d.astype("datetime64[D]")) for d in ticks]
        ax.set_xticklabels(labels, rotation=25, ha="right")
