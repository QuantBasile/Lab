#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 19 09:13:33 2025

@author: fran
"""
# ui/simple_calendar.py
import tkinter as tk
from tkinter import ttk
import calendar
import datetime as dt


class SimpleDateEntry(ttk.Frame):
    """
    DateEntry sencillo sin dependencias externas:
      - Caja de texto + botón 📅
      - Popup con calendario del mes
      - Navegación mes anterior / siguiente
      - Devuelve fecha como string en el patrón dado (por defecto yyyy-mm-dd)
    """

    def __init__(self, master=None, textvariable=None, date_pattern="yyyy-mm-dd", **kwargs):
        super().__init__(master)

        self._var = textvariable or tk.StringVar()
        self._date_pattern = date_pattern
        self._current_date = dt.date.today()

        # --- Entry ---
        width = kwargs.pop("width", 12)

        self.entry = ttk.Entry(self, textvariable=self._var, width=width, **kwargs)
        self.entry.pack(side="left", fill="x", expand=True)

        # --- Botón calendario ---
        self.btn = tk.Button(
            self,
            text="📅",
            relief="flat",
            bd=0,
            padx=4,
            pady=0,
            cursor="hand2",
            bg="white",
            activebackground="#e5e7eb",
        )
        self.btn.pack(side="left", padx=(4, 0))
        self.btn.bind("<Button-1>", self._open_popup)

        # Si no hay valor inicial, poner hoy
        if not self._var.get().strip():
            self.set_date(self._current_date)

        # Popup
        self._top = None

    # -------- API sencilla --------
    def set_date(self, date_obj: dt.date):
        if not isinstance(date_obj, dt.date):
            return
        self._current_date = date_obj
        self._var.set(self._format_date(date_obj))

    def get_date(self):
        """Devuelve un datetime.date o None si el contenido no es válido."""
        try:
            return self._parse_date(self._var.get())
        except Exception:
            return None

    # -------- Popup calendario --------
    def _open_popup(self, event=None):
        if self._top is not None and tk.Toplevel.winfo_exists(self._top):
            # Si ya está abierto, no repetir
            return

        self._top = tk.Toplevel(self)
        self._top.wm_overrideredirect(True)  # sin borde
        self._top.configure(bg="white")

        # Colocar justo debajo del widget
        self._top.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self._top.geometry(f"+{x}+{y}")

        # Cerrar si pierde foco o se pulsa Escape
        self._top.bind("<FocusOut>", lambda e: self._close_popup())
        self._top.bind("<Escape>", lambda e: self._close_popup())
        self._top.focus_set()

        self._build_calendar(self._top, self._current_date)

    def _close_popup(self):
        if self._top is not None:
            try:
                self._top.destroy()
            except Exception:
                pass
            self._top = None

    def _build_calendar(self, parent, date_obj: dt.date):
        for w in parent.winfo_children():
            w.destroy()

        cal = calendar.Calendar(firstweekday=0)  # Lunes = 0 si quieres; 0 = Monday, 6 = Sunday
        year = date_obj.year
        month = date_obj.month

        # --- Header con navegación ---
        header = tk.Frame(parent, bg="white")
        header.pack(fill="x", pady=4, padx=4)

        btn_prev = tk.Button(
            header,
            text="◀",
            relief="flat",
            bg="white",
            activebackground="#e5e7eb",
            cursor="hand2",
            command=lambda: self._change_month(-1),
        )
        btn_prev.pack(side="left")

        lbl_title = tk.Label(
            header,
            text=f"{calendar.month_name[month]} {year}",
            bg="white",
            fg="#111827",
            font=("Segoe UI Semibold", 10),
        )
        lbl_title.pack(side="left", expand=True)

        btn_next = tk.Button(
            header,
            text="▶",
            relief="flat",
            bg="white",
            activebackground="#e5e7eb",
            cursor="hand2",
            command=lambda: self._change_month(1),
        )
        btn_next.pack(side="right")

        # --- Cabecera de días de la semana ---
        days_frame = tk.Frame(parent, bg="white")
        days_frame.pack(fill="both", padx=4)

        # si quieres lunes primero, usa:
        weekday_names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for i, name in enumerate(weekday_names):
            tk.Label(
                days_frame,
                text=name,
                bg="white",
                fg="#6b7280",
                font=("Segoe UI", 9),
                width=3,
                anchor="center",
            ).grid(row=0, column=i, padx=1, pady=1)

        # --- Días ---
        grid = tk.Frame(parent, bg="white")
        grid.pack(fill="both", padx=4, pady=(0, 4))

        month_days = cal.monthdatescalendar(year, month)
        today = dt.date.today()

        for r, week in enumerate(month_days, start=1):
            for c, d in enumerate(week):
                # Los días fuera del mes actual los mostramos “apagados”
                in_month = (d.month == month)
                txt = str(d.day)
                is_today = (d == today)

                bg = "white"
                fg = "#111827" if in_month else "#d1d5db"
                if is_today and in_month:
                    bg = "#dbeafe"
                btn = tk.Button(
                    grid,
                    text=txt,
                    width=3,
                    relief="flat",
                    bg=bg,
                    fg=fg,
                    activebackground="#bfdbfe",
                    activeforeground="#111827",
                    cursor="hand2",
                    command=lambda dd=d: self._on_pick(dd),
                )
                btn.grid(row=r, column=c, padx=1, pady=1)

        # Borde/“tarjeta”
        parent.update_idletasks()
        w = parent.winfo_width()
        h = parent.winfo_height()
        parent.geometry(f"{w}x{h}+{parent.winfo_x()}+{parent.winfo_y()}")

    def _change_month(self, delta: int):
        # delta = +1 / -1
        d = self._current_date
        month = d.month + delta
        year = d.year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        new_date = dt.date(year, month, min(d.day, calendar.monthrange(year, month)[1]))
        self._current_date = new_date
        if self._top is not None and tk.Toplevel.winfo_exists(self._top):
            self._build_calendar(self._top, new_date)

    def _on_pick(self, date_obj: dt.date):
        self.set_date(date_obj)
        self._close_popup()

    # -------- Formato / parse --------
    def _format_date(self, d: dt.date) -> str:
        if self._date_pattern == "dd.mm.yyyy":
            return d.strftime("%d.%m.%Y")
        # por defecto: yyyy-mm-dd
        return d.strftime("%Y-%m-%d")

    def _parse_date(self, s: str) -> dt.date:
        s = (s or "").strip()
        if not s:
            raise ValueError("empty date")
        if self._date_pattern == "dd.mm.yyyy":
            return dt.datetime.strptime(s, "%d.%m.%Y").date()
        return dt.datetime.strptime(s, "%Y-%m-%d").date()

