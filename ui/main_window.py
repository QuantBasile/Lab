import threading
import traceback
from datetime import date, timedelta

import tkinter as tk
from tkinter import messagebox, ttk

from services.data_service import DataService
from ui.filters_panel import FiltersPanel
from ui.table_widget import TableFrame
from ui.volume_sheet import VolumeSheet
from ui.volume_summary import VolumeSummary
from ui.volume_perc import VolumePercentage
from ui.volume_table import VolumeTable
from ui.call_put_share import CallPutShare
from ui.call_put_rolling import CallPutRolling
from ui.hsbc_marktanteil import HSBCMarktanteil
from ui.top20_names import Top20Names
from ui.simple_calendar import SimpleDateEntry as DateEntry

# ---- QUICK SHEET CONFIG -------------------------------------
# Sheets that are disabled (not created, not updated)
DISABLED_SHEETS = {
    "CALL/PUT rolling 7d",
    "Call/Put Share",
    "Volume Summary",
    # "HSBC Market Share",
}
# ---------------------------------------------------------------


class MainWindow(tk.Frame):
    """
    Main application window for the Marktanteil dashboard.
    Handles layout, user interaction and coordination with DataService.
    """

    MAX_DISPLAY = 1000

    def __init__(self, master: tk.Misc | None = None) -> None:
        super().__init__(master)
        self.service = DataService()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI BUILD
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # ======== Topbar ========
        topbar = ttk.Frame(self, style="Topbar.TFrame")
        topbar.pack(side="top", fill="x")
        ttk.Label(
            topbar,
            text="Marktanteil Dashboard",
            style="Topbar.TLabel",
        ).pack(side="left", padx=12, pady=10)

        # ======== Shell without sidebar ========
        shell = ttk.Frame(self, style="Card.TFrame")
        shell.pack(side="top", fill="both", expand=True, padx=12, pady=12)

        # --- Content (takes all space) ---
        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(content, style="CardInner.TFrame")
        inner.pack(fill="both", expand=True)
        # keep a reference for sizing helpers
        self.inner = inner  # type: ignore[attr-defined]

        # === Actions Row: dates + product type ===
        actions = ttk.Frame(inner, style="Actions.TFrame")
        actions.pack(side="top", fill="x", padx=10, pady=8)

        # ----- Date range: From / To -----
        ttk.Label(actions, text="From:").pack(side="left")
        self.von_var = tk.StringVar()
        self.von_date = DateEntry(
            actions,
            textvariable=self.von_var,
            date_pattern="yyyy-mm-dd",
            width=12,
        )
        self._style_green(self.von_date)
        self.von_date.pack(side="left", padx=(4, 10))

        ttk.Label(actions, text="To:").pack(side="left")
        self.bis_var = tk.StringVar()
        self.bis_date = DateEntry(
            actions,
            textvariable=self.bis_var,
            date_pattern="yyyy-mm-dd",
            width=12,
        )
        self._style_green(self.bis_date)
        self.bis_date.pack(side="left", padx=(4, 16))

        # Default date range: last 90 days
        today = date.today()
        self.bis_date.set_date(today)
        self.von_date.set_date(today - timedelta(days=90))

        # ----- Product buttons (input) in light purple -----
        btn_input_kwargs = dict(
            bg="#e9d5ff",
            fg="#000000",
            activebackground="#ddd6fe",
            relief="flat",
            padx=10,
            pady=5,
            cursor="hand2",
        )

        self.btn_alle = tk.Button(
            actions,
            text="All",
            command=lambda: self.on_generate("ALLE"),
            **btn_input_kwargs,
        )
        self.btn_alle.pack(side="left", padx=(0, 6))

        self.btn_turbo = tk.Button(
            actions,
            text="Turbo",
            command=lambda: self.on_generate("TURBO"),
            **btn_input_kwargs,
        )
        self.btn_turbo.pack(side="left", padx=(0, 6))

        self.btn_vanilla = tk.Button(
            actions,
            text="Vanilla",
            command=lambda: self.on_generate("VANILLA"),
            **btn_input_kwargs,
        )
        self.btn_vanilla.pack(side="left", padx=(0, 12))

        # Toggle filters button
        self.btn_toggle_filters = tk.Button(
            actions,
            text="Hide filters ▲",
            bg="#e0ecff",
            fg="#0b0b0b",
            activebackground="#cfe2ff",
            relief="flat",
            padx=10,
            pady=5,
            command=self._toggle_filters,
            cursor="hand2",
        )
        self.btn_toggle_filters.pack(side="left", padx=(0, 12))

        # Apply / Clear filters
        self.btn_apply = tk.Button(
            actions,
            text="Apply filters",
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            relief="flat",
            padx=12,
            pady=6,
            command=self.on_apply_filters,
            cursor="hand2",
        )
        self.btn_apply.config(state="disabled")
        self.btn_apply.pack(side="left")

        self.btn_clear = tk.Button(
            actions,
            text="Clear filters",
            bg="#e0ecff",
            fg="#0b0b0b",
            activebackground="#cfe2ff",
            relief="flat",
            padx=10,
            pady=5,
            command=self.on_clear_filters,
            cursor="hand2",
        )
        self.btn_clear.config(state="disabled")
        self.btn_clear.pack(side="left", padx=(8, 0))

        # --- Vertical splitter: filters on top / notebook below ---
        self.split = ttk.Panedwindow(inner, orient="vertical")
        self.split.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Pane 1: filters (wrap + panel inside)
        self.filters_wrap = ttk.Frame(self.split, style="Card.TFrame")
        self.filters_panel = FiltersPanel(self.filters_wrap)
        self.filters_panel.pack(side="top", fill="both", expand=True)

        # Pane 2: notebook
        self.nb_wrap = ttk.Frame(self.split, style="Card.TFrame")
        self.nb = ttk.Notebook(self.nb_wrap, style="CustomNotebook")
        self.nb.pack(side="top", fill="both", expand=True)

        self.split.add(self.filters_wrap, weight=1)
        self.split.add(self.nb_wrap, weight=3)

        # ----- Tabs -----
        tab_table = ttk.Frame(self.nb)
        self.table = TableFrame(tab_table)
        self.table.pack(fill="both", expand=True)
        self.nb.add(tab_table, text="Table")

        tab_volume = ttk.Frame(self.nb)
        self.volume_sheet = VolumeSheet(tab_volume)
        self.volume_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_volume, text="Volume")

        # OPTIONAL: Volume Summary
        if "Volume Summary" not in DISABLED_SHEETS:
            tab_vol_summary = ttk.Frame(self.nb)
            self.volume_summary = VolumeSummary(tab_vol_summary)
            self.volume_summary.pack(fill="both", expand=True)
            self.nb.add(tab_vol_summary, text="Volume Summary")

        tab_volpct = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.volume_percentage = VolumePercentage(tab_volpct)
        self.volume_percentage.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_volpct, text="Volume %")

        tab_vtable = ttk.Frame(self.nb, style="CardInner.TFrame")
        self.volume_table = VolumeTable(tab_vtable)
        self.volume_table.pack(side="top", fill="both", expand=True)
        self.nb.add(tab_vtable, text="Volume table")

        # OPTIONAL: Call/Put Share
        if "Call/Put Share" not in DISABLED_SHEETS:
            tab_cp_share = ttk.Frame(self.nb)
            self.call_put_share = CallPutShare(tab_cp_share)
            self.call_put_share.pack(fill="both", expand=True)
            self.nb.add(tab_cp_share, text="Call/Put Share")

        # OPTIONAL: CALL/PUT rolling 7d
        if "CALL/PUT rolling 7d" not in DISABLED_SHEETS:
            tab_cp_roll = ttk.Frame(self.nb)
            self.call_put_rolling = CallPutRolling(tab_cp_roll)
            self.call_put_rolling.pack(fill="both", expand=True)
            self.nb.add(tab_cp_roll, text="CALL/PUT rolling 7d")

        # OPTIONAL: HSBC Market Share
        if "HSBC Market Share" not in DISABLED_SHEETS:
            tab_hsbc = ttk.Frame(self.nb)
            self.hsbc_marktanteil = HSBCMarktanteil(tab_hsbc)
            self.hsbc_marktanteil.pack(fill="both", expand=True)
            self.nb.add(tab_hsbc, text="HSBC Market Share")

        tab_top20 = ttk.Frame(self.nb)
        self.top20_sheet = Top20Names(tab_top20)
        self.top20_sheet.pack(fill="both", expand=True)
        self.nb.add(tab_top20, text="Top 20 Names")

    # ------------------------------------------------------------------
    # FILTERS TOGGLE
    # ------------------------------------------------------------------
    def _show_filters(self) -> None:
        panes = self.split.panes()
        if str(self.filters_wrap) in panes:
            return
        self.split.insert(0, self.filters_wrap)
        self.split.paneconfigure(self.filters_wrap, weight=1, minsize=120)
        try:
            if hasattr(self, "_last_sash"):
                self.split.sashpos(0, self._last_sash)
        except Exception:
            pass
        self.btn_toggle_filters.configure(text="Hide filters ▲", state="normal")

    def _hide_filters(self) -> None:
        try:
            self._last_sash = self.split.sashpos(0)
        except Exception:
            self._last_sash = None
        try:
            self.split.forget(self.filters_wrap)
        except Exception:
            pass
        self.btn_toggle_filters.configure(text="Show filters ▼", state="normal")

    # ------------------------------------------------------------------
    # LOGIC
    # ------------------------------------------------------------------
    def on_generate(self, produktart: str) -> None:
        """Generate data using the selected date range and product type."""
        von = (self.von_var.get() or "").strip() or None
        bis = (self.bis_var.get() or "").strip() or None

        # Disable product buttons while generating
        for btn in (self.btn_alle, self.btn_turbo, self.btn_vanilla):
            btn.config(state="disabled")
        self.update_idletasks()

        # Show loading dialog
        self._show_loading("Loading data...\nThis may take a few minutes.")

        def worker() -> None:
            df = None
            error: Exception | None = None
            try:
                df = self.service.generate_fake_transactions(
                    von=von,
                    bis=bis,
                    produktart=produktart,
                    n_rows=1_000_000,
                )
            except Exception as e:
                error = e

            self.after(0, lambda: self._on_generate_finished(df, error, produktart))

        threading.Thread(target=worker, daemon=True).start()

    def on_apply_filters(self) -> None:
        try:
            spec = self.filters_panel.get_filters()
            self.service.apply_filters(spec)
        except Exception:
            traceback.print_exc()
            messagebox.showerror("Error", "Error applying filters.")
            return
        self._refresh_views()

    def on_clear_filters(self) -> None:
        self.filters_panel.reset()
        self.service.apply_filters({})
        self._refresh_views()

    def _refresh_views(self) -> None:
        """
        Refresh only the sheets that actually exist.
        Disabled sheets are simply skipped (fast & safe).
        """
        df_view = self.service.dataframe_filtered.head(self.MAX_DISPLAY).copy()
        self.table.show_dataframe(df_view)

        df_full = self.service.dataframe_filtered

        # --- Always-active sheets ---
        if hasattr(self, "volume_sheet"):
            self.volume_sheet.update_plot(df_full)

        if hasattr(self, "volume_table"):
            self.volume_table.update_view(df_full)

        # --- Optional / disabled sheets ---
        if hasattr(self, "volume_summary"):
            self.volume_summary.update_view(df_full)

        if hasattr(self, "volume_percentage"):
            self.volume_percentage.update_plot(df_full)

        if hasattr(self, "call_put_share"):
            self.call_put_share.update_plot(df_full)

        if hasattr(self, "call_put_rolling"):
            self.call_put_rolling.update_plot(df_full)

        if hasattr(self, "hsbc_marktanteil"):
            self.hsbc_marktanteil.update_plot(df_full)

        if hasattr(self, "top20_sheet"):
            self.top20_sheet.update_plot(df_full)

    # ------------------------------------------------------------------
    # SPLIT HELPERS
    # ------------------------------------------------------------------
    def _get_split_height(self) -> int:
        """Return useful height for the panedwindow, with fallbacks."""
        try:
            self.update_idletasks()
            h = self.split.winfo_height()
            if h <= 1 and hasattr(self, "inner"):
                h = self.inner.winfo_height()  # type: ignore[attr-defined]
            return max(100, h)
        except Exception:
            return 600

    def _set_filters_height_px(self, pixels: int) -> None:
        """Set sash position so that the top pane (filters) has the given height."""
        try:
            self.update_idletasks()
            self.split.sashpos(0, max(0, int(pixels)))
        except Exception:
            pass

    def _show_filters_half(self) -> None:
        """Show filters with ~50% height."""
        total_h = self._get_split_height()
        target = int(total_h * 0.5)
        self._last_filters_px = target
        self._set_filters_height_px(target)
        self.btn_toggle_filters.configure(text="Hide filters ▲")

    def _hide_filters_collapse(self) -> None:
        """Collapse filters to their minimum height."""
        try:
            pane_conf = self.split.pane(self.filters_wrap)
            minsize = int(pane_conf.get("minsize", 0))
        except Exception:
            minsize = 0
        target = minsize
        self._set_filters_height_px(target)
        self.btn_toggle_filters.configure(text="Show filters ▼")

    def _toggle_filters(self) -> None:
        """Toggle between collapsed and ~half-page filters height."""
        self.update_idletasks()
        current = self.split.sashpos(0)
        try:
            pane_conf = self.split.pane(self.filters_wrap)
            minsize = int(pane_conf.get("minsize", 0))
        except Exception:
            minsize = 0

        near_collapsed = current <= minsize + 4
        if near_collapsed:
            target = getattr(
                self, "_last_filters_px", int(self._get_split_height() * 0.5)
            )
            self._set_filters_height_px(target)
            self.btn_toggle_filters.configure(text="Hide filters ▲")
        else:
            self._last_filters_px = current
            self._hide_filters_collapse()

    # ------------------------------------------------------------------
    # STYLING & DIALOGS
    # ------------------------------------------------------------------
    def _style_green(self, date_entry: DateEntry) -> None:
        """Apply light green background to the SimpleDateEntry widget."""
        try:
            date_entry.entry.configure(
                background="#E6F4EA",
                foreground="#000000",
            )
            date_entry.btn.configure(
                background="#E6F4EA",
                activebackground="#C7DFC9",
            )
        except Exception:
            # If we are using tkcalendar.DateEntry instead of SimpleDateEntry
            try:
                date_entry.configure(
                    background="#E6F4EA",
                    foreground="#000000",
                )
            except Exception:
                pass

    def _show_loading(self, text: str = "Loading...") -> None:
        """Show a simple loading window with an indeterminate progress bar."""
        if (
            hasattr(self, "_loading_win")
            and self._loading_win
            and self._loading_win.winfo_exists()
        ):
            self._loading_label.config(text=text)
            return

        win = tk.Toplevel(self)
        self._loading_win = win
        win.title("Loading")
        win.geometry("320x110")
        win.configure(bg="white")
        win.resizable(False, False)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        lbl = ttk.Label(frame, text=text, justify="center")
        lbl.pack(pady=(0, 10))
        self._loading_label = lbl

        pb = ttk.Progressbar(frame, mode="indeterminate", length=260)
        pb.pack()
        pb.start(10)
        self._loading_pb = pb

        self.update_idletasks()
        try:
            x = self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2
            y = self.winfo_rooty() + (self.winfo_height() - win.winfo_height()) // 2
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_generate_finished(self, df, error: Exception | None, produktart: str) -> None:
        """Callback executed in the main thread when data generation finishes."""
        win = getattr(self, "_loading_win", None)
        if win and win.winfo_exists():
            try:
                pb = getattr(self, "_loading_pb", None)
                if pb:
                    pb.stop()
                win.destroy()
            except Exception:
                pass

        for btn in (self.btn_alle, self.btn_turbo, self.btn_vanilla):
            btn.config(state="normal")

        if error is not None or df is None:
            messagebox.showerror("Error", "Data could not be generated.")
            return

        self.btn_apply.config(state="normal")
        self.btn_clear.config(state="normal")

        self.filters_panel.build(df)
        self._refresh_all_views_for(produktart)

        self._show_done_popup("Data load completed successfully.")

    def _refresh_all_views_for(self, produktart: str) -> None:
        """
        Wrapper for the async on_generate flow.
        Currently just refreshes views based on the filtered DataFrame.
        """
        self._refresh_views()

    def _show_done_popup(self, text: str = "Operation completed.") -> None:
        """
        Small toast-like window at bottom-right of the screen.
        Does not restore the main window if it was minimized.
        """
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)

        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)

        label = ttk.Label(frame, text=text, justify="left")
        label.pack(pady=(0, 8))

        btn = ttk.Button(frame, text="OK", command=win.destroy)
        btn.pack(ipadx=10, pady=(0, 4))

        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        ww = win.winfo_width()
        wh = win.winfo_height()

        margin_x = 20
        margin_y = 60
        x = sw - ww - margin_x
        y = sh - wh - margin_y
        win.geometry(f"+{x}+{y}")

        win.lift()
        win.focus_force()
