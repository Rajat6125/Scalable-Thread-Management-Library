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


# ==========================================
# SCHEDULING ALGORITHMS (With Process IDs)
# ==========================================
def assign_process_ids(processes):
    """Assign sequential IDs to processes for display"""
    id_mapping = {}
    for i, (name, data) in enumerate(processes.items(), 1):
        id_mapping[name] = f"P{i}"
    return id_mapping

def fcfs(processes):
    """First Come First Serve"""
    proc_list = [(name, data['at'], data['bt']) for name, data in processes.items()]
    proc_list.sort(key=lambda x: x[1])
    
    # Assign IDs
    id_map = assign_process_ids(processes)
    
    timeline = []
    current_time = 0
    results = {}
    
    for name, at, bt in proc_list:
        if current_time < at:
            current_time = at
        start = current_time
        current_time += bt
        end = current_time
        
        timeline.append((id_map[name], name, start, end))
        
        ct = end
        tat = ct - at
        wt = tat - bt
        
        results[id_map[name]] = {
            'Process': name.split('(')[0],
            'PID': name.split('(')[1].rstrip(')') if '(' in name else '',
            'AT': at, 'BT': bt, 'CT': ct, 'TAT': tat, 'WT': wt
        }
    
    df = pd.DataFrame.from_dict(results, orient='index')
    return timeline, df, df['TAT'].mean(), df['WT'].mean()

def sjf(processes):
    """Shortest Job First"""
    proc_list = [(name, data['at'], data['bt']) for name, data in processes.items()]
    proc_list.sort(key=lambda x: x[1])
    
    id_map = assign_process_ids(processes)
    
    timeline = []
    current_time = 0
    results = {}
    remaining = proc_list.copy()
    
    while remaining:
        available = [p for p in remaining if p[1] <= current_time]
        
        if not available:
            current_time = min(p[1] for p in remaining)
            continue
        
        shortest = min(available, key=lambda x: x[2])
        remaining.remove(shortest)
        name, at, bt = shortest
        
        start = current_time
        current_time += bt
        end = current_time
        
        timeline.append((id_map[name], name, start, end))
        
        ct = end
        tat = ct - at
        wt = tat - bt
        
        results[id_map[name]] = {
            'Process': name.split('(')[0],
            'PID': name.split('(')[1].rstrip(')') if '(' in name else '',
            'AT': at, 'BT': bt, 'CT': ct, 'TAT': tat, 'WT': wt
        }
    
    df = pd.DataFrame.from_dict(results, orient='index')
    return timeline, df, df['TAT'].mean(), df['WT'].mean()

def srtf(processes):
    """Shortest Remaining Time First"""
    proc_list = [(name, data['at'], data['bt']) for name, data in processes.items()]
    
    id_map = assign_process_ids(processes)
    reverse_id_map = {v: k for k, v in id_map.items()}
    
    remaining_bt = {name: bt for name, at, bt in proc_list}
    arrival_time = {name: at for name, at, bt in proc_list}
    completion_time = {}
    
    time = 0
    completed = 0
    n = len(processes)
    timeline = []
    last_process = None
    start_time = None
    
    while completed < n:
        available = [name for name in processes if arrival_time[name] <= time and remaining_bt[name] > 0]
        
        if not available:
            time += 1
            continue
        
        current = min(available, key=lambda x: remaining_bt[x])
        
        if current != last_process:
            if last_process is not None:
                timeline.append((id_map[last_process], last_process, start_time, time))
            last_process = current
            start_time = time
        
        remaining_bt[current] -= 1
        time += 1
        
        if remaining_bt[current] == 0:
            completion_time[current] = time
            timeline.append((id_map[current], current, start_time, time))
            completed += 1
            last_process = None
    
    results = {}
    for name, at, bt in proc_list:
        ct = completion_time[name]
        tat = ct - at
        wt = tat - bt
        
        results[id_map[name]] = {
            'Process': name.split('(')[0],
            'PID': name.split('(')[1].rstrip(')') if '(' in name else '',
            'AT': at, 'BT': bt, 'CT': ct, 'TAT': tat, 'WT': wt
        }
    
    df = pd.DataFrame.from_dict(results, orient='index')
    return timeline, df, df['TAT'].mean(), df['WT'].mean()