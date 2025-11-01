#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 01:12:57 2025

@author: fran
"""
# ui/volume_sheet.py
import tkinter as tk
from tkinter import ttk
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class VolumeSheet(ttk.Frame):
    """
    Tab that plots Daily Volume = sum(TXN_AMT) from the filtered DataFrame.
    Call .update_plot(df_filtered) whenever filters change.
    """
    def __init__(self, master=None):
        super().__init__(master)
        self._build()

    def _build(self):
        # Matplotlib Figure
        self.fig = Figure(figsize=(8, 3.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Daily Volume (Σ TXN_AMT)")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Volume")

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

    def update_plot(self, df: pd.DataFrame):
        self.ax.clear()
        self.ax.set_title("Daily Volume (Σ TXN_AMT)")
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Volume")

        if df is None or df.empty:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=self.ax.transAxes)
            self.canvas.draw()
            return

        # Ensure date type and aggregate
        s = df.copy()
        s["TRANSACTION_DATE"] = pd.to_datetime(s["TRANSACTION_DATE"], errors="coerce")
        grp = (
            s.dropna(subset=["TRANSACTION_DATE"])
             .groupby(s["TRANSACTION_DATE"].dt.date)["TXN_AMT"]
             .sum()
             .sort_index()
        )

        if grp.empty:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=self.ax.transAxes)
            self.canvas.draw()
            return

        # Plot as line with markers
        self.ax.plot(list(grp.index), grp.values, marker="o")
        self.ax.grid(True, alpha=0.3)
        self.fig.autofmt_xdate(rotation=30)
        self.canvas.draw()

