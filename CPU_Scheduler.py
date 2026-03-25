import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import time
import psutil
import threading
import random
import queue
from collections import deque

# ==========================================
# ROUNDED BUTTON CLASS
# ==========================================
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text,
                 width=280, height=100,
                 radius=25,
                 bg_color="#5A67D8",
                 hover_color="#434190",
                 click_color="#2B2F77",
                 text_color="white",
                 command=None):

        super().__init__(parent,
                         width=width,
                         height=height,
                         bg=parent["bg"],
                         highlightthickness=0)

        self.command = command
        self.default_bg = bg_color
        self.hover_bg = hover_color
        self.click_bg = click_color

        self.rect = self.create_rounded_rect(
            3, 3, width-3, height-3, radius,
            fill=self.default_bg
        )

        self.label = self.create_text(
            width/2,
            height/2,
            text=text,
            fill=text_color,
            font=("Segoe UI", 13, "bold"),
            width=width - 30,
            justify="center"
        )

        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)
        self.bind("<ButtonPress-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1+r, y1,
            x2-r, y1,
            x2, y1,
            x2, y1+r,
            x2, y2-r,
            x2, y2,
            x2-r, y2,
            x1+r, y2,
            x1, y2,
            x1, y2-r,
            x1, y1+r,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def on_hover(self, event):
        self.itemconfig(self.rect, fill=self.hover_bg)

    def on_leave(self, event):
        self.itemconfig(self.rect, fill=self.default_bg)

    def on_click(self, event):
        self.itemconfig(self.rect, fill=self.click_bg)

    def on_release(self, event):
        self.itemconfig(self.rect, fill=self.hover_bg)
        if self.command:
            self.command()

