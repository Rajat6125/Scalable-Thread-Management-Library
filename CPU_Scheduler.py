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


# ==========================================
# ENHANCED PROCESS MONITOR (No Limits)
# ==========================================
class ProcessMonitor:
    def __init__(self):
        self.selected_processes = {}
        self.all_processes = {}
        self.update_queue = queue.Queue()
        self.is_updating = False
        self.page_size = 20  # Show 20 processes at a time
        self.current_page = 0
        self.process_list = []
        
    def get_all_processes(self):
        """Get all running processes efficiently"""
        processes = {}
        try:
            # Use psutil.process_iter() which is efficient
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['name'] and proc_info['pid']:
                        processes[proc_info['pid']] = {
                            'name': proc_info['name'],
                            'memory': proc_info['memory_percent'] or 0,
                            'pid': proc_info['pid']
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Error: {e}")
        
        return processes
    
    def refresh(self):
        """Refresh process list in background without blocking"""
        if self.is_updating:
            return
        
        def update():
            self.is_updating = True
            try:
                processes = self.get_all_processes()
                self.all_processes = processes
                # Convert to list for pagination
                self.process_list = list(processes.items())
                # Update UI with first page
                self.update_queue.put(('refresh', self.get_page(0)))
                self.current_page = 0
            finally:
                self.is_updating = False
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()
    
    def get_page(self, page_num):
        """Get a page of processes"""
        start = page_num * self.page_size
        end = start + self.page_size
        page_items = self.process_list[start:end]
        return dict(page_items)
    
    def next_page(self):
        """Get next page of processes"""
        if (self.current_page + 1) * self.page_size < len(self.process_list):
            self.current_page += 1
            return self.get_page(self.current_page)
        return None
    
    def prev_page(self):
        """Get previous page of processes"""
        if self.current_page > 0:
            self.current_page -= 1
            return self.get_page(self.current_page)
        return None
    
    def total_pages(self):
        """Get total number of pages"""
        if not self.process_list:
            return 0
        return (len(self.process_list) + self.page_size - 1) // self.page_size
