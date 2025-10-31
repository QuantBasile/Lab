#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 31 23:04:39 2025

@author: fran
"""

import tkinter as tk
from ui.main_window import MainWindow
from utils.logging_config import configure_logging


def run():
    configure_logging()
    root = tk.Tk()
    root.title("Laboratorio Marktanteil – v0.1 (Tkinter)")
    root.geometry("1200x700")
    
    
    app = MainWindow(master=root)
    app.pack(fill="both", expand=True)
    
    
    root.mainloop()