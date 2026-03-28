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

def round_robin(processes, quantum):
    """Round Robin"""
    proc_list = [(name, data['at'], data['bt']) for name, data in processes.items()]
    
    id_map = assign_process_ids(processes)
    
    remaining_bt = {name: bt for name, at, bt in proc_list}
    arrival_time = {name: at for name, at, bt in proc_list}
    completion_time = {}
    
    time = 0
    completed = 0
    n = len(processes)
    timeline = []
    ready_queue = deque()
    proc_sorted = sorted(proc_list, key=lambda x: x[1])
    index = 0
    last_process = None
    start_time = None
    
    while completed < n:
        while index < n and proc_sorted[index][1] <= time:
            ready_queue.append(proc_sorted[index][0])
            index += 1
        
        if not ready_queue:
            time += 1
            continue
        
        current = ready_queue.popleft()
        
        if current != last_process:
            if last_process is not None:
                timeline.append((id_map[last_process], last_process, start_time, time))
            last_process = current
            start_time = time
        
        exec_time = min(quantum, remaining_bt[current])
        time += exec_time
        remaining_bt[current] -= exec_time
        
        while index < n and proc_sorted[index][1] <= time:
            ready_queue.append(proc_sorted[index][0])
            index += 1
        
        if remaining_bt[current] == 0:
            completion_time[current] = time
            timeline.append((id_map[current], current, start_time, time))
            completed += 1
            last_process = None
        else:
            ready_queue.append(current)
    
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

# ==========================================
# MAIN APPLICATION
# ==========================================
class CPUSchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CPU Scheduler - Real Process Monitor")
        self.root.geometry("1200x800")
        self.root.configure(bg="#F3F4F6")
        
        self.monitor = ProcessMonitor()
        self.selected = {}
        self.current_algo = None
        self.update_id = None
        
        self.setup_ui()
        self.refresh_processes()
        self.process_updates()
    
    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#F3F4F6")
        header.pack(pady=20)
        
        tk.Label(header, text="CPU Scheduling Simulator",
                font=("Impact", 32), bg="#F3F4F6", fg="#1F2937").pack()
        
        tk.Label(header, text="Monitor ALL Real Processes | Simulate Scheduling Algorithms",
                font=("Segoe UI", 10), bg="#F3F4F6", fg="#6B7280").pack()
        
        # Warning
        warning = tk.Frame(self.root, bg="#FEF3C7", relief="solid", borderwidth=1)
        warning.pack(pady=10, padx=50, fill="x")
        
        tk.Label(warning, text="⚠ READ-ONLY MODE - Processes are only monitored, never modified | Showing ALL processes with pagination ⚠",
                font=("Segoe UI", 10, "bold"), bg="#FEF3C7", fg="#92400E", padx=10, pady=5).pack()
        
        # Process selection frame
        self.create_process_frame()
        
        # Algorithm buttons
        self.create_algo_buttons()
        
        # Status bar
        self.status = tk.Label(self.root, text="Ready", bd=1, relief=tk.SUNKEN, 
                              anchor=tk.W, bg="#E5E7EB", fg="#374151")
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_process_frame(self):
        """Create process selection frame with pagination"""
        frame = tk.LabelFrame(self.root, text="Select Processes for Scheduling (Click to Select)",
                             font=("Segoe UI", 12, "bold"), bg="white", fg="#1F2937",
                             padx=10, pady=5)
        frame.pack(pady=10, padx=30, fill="both", expand=True)
        
        # Treeview
        tree_frame = tk.Frame(frame, bg="white")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        columns = ("Select", "ID", "PID", "Process Name", "Memory %")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        
        self.tree.heading("Select", text="Select")
        self.tree.heading("ID", text="ID")
        self.tree.heading("PID", text="PID")
        self.tree.heading("Process Name", text="Process Name")
        self.tree.heading("Memory %", text="Memory %")
        
        self.tree.column("Select", width=60, anchor="center")
        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("PID", width=80, anchor="center")
        self.tree.column("Process Name", width=450)
        self.tree.column("Memory %", width=80, anchor="center")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.tree.bind('<ButtonRelease-1>', self.on_select)
        
        # Pagination controls
        pagination_frame = tk.Frame(frame, bg="white")
        pagination_frame.pack(pady=10)
        
        self.prev_btn = tk.Button(pagination_frame, text="◀ Previous", command=self.prev_page,
                                  bg="#6B7280", fg="white", font=("Segoe UI", 9),
                                  padx=10, pady=3, relief="flat", state="disabled")
        self.prev_btn.pack(side="left", padx=5)
        
        self.page_label = tk.Label(pagination_frame, text="Page 1", bg="white", 
                                   font=("Segoe UI", 9))
        self.page_label.pack(side="left", padx=10)
        
        self.next_btn = tk.Button(pagination_frame, text="Next ▶", command=self.next_page,
                                  bg="#6B7280", fg="white", font=("Segoe UI", 9),
                                  padx=10, pady=3, relief="flat")
        self.next_btn.pack(side="left", padx=5)
        
        tk.Button(pagination_frame, text="🔄 Refresh", command=self.refresh_processes,
                 bg="#3B82F6", fg="white", font=("Segoe UI", 9),
                 padx=10, pady=3, relief="flat").pack(side="left", padx=10)
        
        tk.Button(pagination_frame, text="🗑 Clear All", command=self.clear_selection,
                 bg="#EF4444", fg="white", font=("Segoe UI", 9),
                 padx=10, pady=3, relief="flat").pack(side="left", padx=5)
        
        # Selection info
        self.selection_label = tk.Label(frame, text="No processes selected",
                                       font=("Segoe UI", 9), bg="#F3F4F6", fg="#4B5563")
        self.selection_label.pack(pady=5)
        
        # Process count
        self.count_label = tk.Label(frame, text="", font=("Segoe UI", 8),
                                   bg="white", fg="#6B7280")
        self.count_label.pack(pady=2)
    

    
    def process_updates(self):
        """Process queued updates"""
        try:
            while True:
                msg, data = self.monitor.update_queue.get_nowait()
                if msg == 'refresh':
                    self.update_display(data)
        except queue.Empty:
            pass
        
        self.update_id = self.root.after(100, self.process_updates)
    
    def update_display(self, processes):
        """Update process tree with pagination"""
        # Save current selection
        current_selected = self.selected.copy()
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add processes with sequential IDs
        for idx, (pid, info) in enumerate(processes.items(), 1):
            select_text = "✓" if pid in current_selected else "□"
            self.tree.insert("", "end", values=(
                select_text,
                f"P{idx}",
                pid,
                info['name'][:50],
                f"{info['memory']:.1f}%"
            ))
        
        self.selected = current_selected
        
        # Update pagination info
        total_pages = self.monitor.total_pages()
        self.page_label.config(text=f"Page {self.monitor.current_page + 1} of {total_pages}")
        
        # Update button states
        self.prev_btn.config(state="normal" if self.monitor.current_page > 0 else "disabled")
        self.next_btn.config(state="normal" if self.monitor.current_page + 1 < total_pages else "disabled")
        
        # Update count
        self.count_label.config(text=f"Total Processes: {len(self.monitor.process_list)} | Showing: {len(processes)}")
        
        self.update_selection_info()
    
    def refresh_processes(self):
        """Refresh process list"""
        self.status.config(text="Refreshing all processes...")
        self.monitor.refresh()
        self.root.after(1000, lambda: self.status.config(text="Ready"))
    
    def next_page(self):
        """Go to next page"""
        processes = self.monitor.next_page()
        if processes:
            self.update_display(processes)
    
    def prev_page(self):
        """Go to previous page"""
        processes = self.monitor.prev_page()
        if processes:
            self.update_display(processes)
    
    def on_select(self, event):
        """Handle process selection"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.tree.item(item, 'values')
        pid = int(values[2])  # PID is in column 2
        
        if pid in self.selected:
            del self.selected[pid]
            self.tree.item(item, values=(f"□", values[1], values[2], values[3], values[4]))
        else:
            # Get process info from current display
            current_page = self.monitor.get_page(self.monitor.current_page)
            if pid in current_page:
                self.selected[pid] = current_page[pid]
                self.tree.item(item, values=(f"✓", values[1], values[2], values[3], values[4]))
        
        self.update_selection_info()
    
    def clear_selection(self):
        """Clear all selections"""
        self.selected.clear()
        self.refresh_processes()
    
    def update_selection_info(self):
        """Update selection info"""
        count = len(self.selected)
        if count == 0:
            self.selection_label.config(text="No processes selected. Click on processes to select them.")
        else:
            names = [f"{info['name']}({pid})" for pid, info in list(self.selected.items())[:5]]
            text = f"Selected {count} process(es): {', '.join(names)}"
            if count > 5:
                text += f" and {count-5} more..."
            self.selection_label.config(text=text)
    
    def prepare_processes(self):
        """Prepare processes for scheduling"""
        if not self.selected:
            messagebox.showwarning("No Selection", "Please select at least one process!")
            return None
        
        processes = {}
        for pid, info in self.selected.items():
            # Arrival time: random between 0-5
            arrival = random.randint(0, 5)
            # Burst time: 2-8 units (reasonable for visualization)
            burst = random.randint(2, 8)
            
            processes[f"{info['name']}({pid})"] = {
                'at': arrival,
                'bt': burst,
                'name': info['name'],
                'pid': pid
            }
        
        return processes
    
    def show_results(self, timeline, df, avg_tat, avg_wt):
        """Show results window with cleaner Gantt chart"""
        win = tk.Toplevel(self.root)
        win.title(f"Results - {self.current_algo}")
        win.geometry("1100x700")
        win.configure(bg="#EEF2F7")
        
        # Scrollable area
        canvas = tk.Canvas(win, bg="#EEF2F7")
        scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#EEF2F7")
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Title
        tk.Label(scroll_frame, text=f"{self.current_algo} Results",
                font=("Impact", 24), bg="#EEF2F7", fg="#1F2937").pack(pady=15)
        
        # Legend
        legend_frame = tk.Frame(scroll_frame, bg="white", relief="solid", borderwidth=1)
        legend_frame.pack(fill="x", pady=5, padx=20)
        
        tk.Label(legend_frame, text="Gantt Chart Legend:", font=("Segoe UI", 10, "bold"),
                bg="white").pack(side="left", padx=10, pady=5)
        
        # Show process ID mapping
        unique_procs = {}
        for pid, _, _, _ in timeline:
            if pid not in unique_procs:
                unique_procs[pid] = True
        
        for i, proc_id in enumerate(sorted(unique_procs)):
            color = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7', '#A8E6CF'][i % 5]
            color_box = tk.Frame(legend_frame, bg=color, width=20, height=20)
            color_box.pack(side="left", padx=(10, 2), pady=5)
            tk.Label(legend_frame, text=proc_id, font=("Segoe UI", 9),
                    bg="white").pack(side="left", padx=2)
        
        # Gantt Chart
        gantt_frame = tk.Frame(scroll_frame, bg="white", relief="solid", borderwidth=1)
        gantt_frame.pack(fill="x", pady=10, padx=20)
        
        tk.Label(gantt_frame, text="Gantt Chart - Process Execution Timeline (Process IDs)",
                font=("Segoe UI", 12, "bold"), bg="#F8FAFC").pack(pady=8)
        
        # Draw Gantt
        canvas_gantt = tk.Canvas(gantt_frame, bg="white", height=120)
        canvas_gantt.pack(fill="x", padx=15, pady=10)
        
        max_time = max(end for _, _, _, end in timeline)
        width = min(900, max(400, max_time * 35))
        scale = width / max_time if max_time > 0 else 1
        
        colors = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7', '#A8E6CF', '#FF8B94', '#A3C4F3']
        x = 50
        
        for i, (proc_id, proc_name, start, end) in enumerate(timeline):
            w = (end - start) * scale
            if w > 2:
                color = colors[i % len(colors)]
                # Draw rectangle
                canvas_gantt.create_rectangle(x, 20, x + w, 70, fill=color, outline="black", width=2)
                # Show Process ID (P1, P2, etc.)
                canvas_gantt.create_text(x + w/2, 45, text=proc_id, 
                                        font=("Segoe UI", 11, "bold"), fill="white")
                # Show burst time in smaller text
                canvas_gantt.create_text(x + w/2, 65, text=f"BT:{end-start}", 
                                        font=("Segoe UI", 8), fill="white")
                # Time markers
                canvas_gantt.create_text(x, 95, text=str(int(start)), font=("Segoe UI", 8))
                x += w
        
        canvas_gantt.create_text(x, 95, text=str(int(max_time)), font=("Segoe UI", 8))
        canvas_gantt.configure(width=x+50)
        
        # Results table
        table_frame = tk.Frame(scroll_frame, bg="white", relief="solid", borderwidth=1)
        table_frame.pack(fill="both", expand=True, pady=10, padx=20)
        
        tk.Label(table_frame, text="Process Statistics",
                font=("Segoe UI", 12, "bold"), bg="#F8FAFC").pack(pady=8)
        
        # Treeview for results
        tree_frame = tk.Frame(table_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        columns = ['Process', 'PID', 'AT', 'BT', 'CT', 'TAT', 'WT']
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=8)
        
        tree.heading("Process", text="Process ID")
        tree.heading("PID", text="System PID")
        tree.heading("AT", text="Arrival")
        tree.heading("BT", text="Burst")
        tree.heading("CT", text="Completion")
        tree.heading("TAT", text="Turnaround")
        tree.heading("WT", text="Waiting")
        
        for col in columns:
            tree.column(col, width=100, anchor='center')
        
        for proc_id in df.index:
            row = df.loc[proc_id]
            values = [row[col] for col in ['Process', 'PID', 'AT', 'BT', 'CT', 'TAT', 'WT']]
            tree.insert('', 'end', values=values)
        
        scroll_tree = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll_tree.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scroll_tree.pack(side="right", fill="y")
        
        # Averages
        avg_frame = tk.Frame(scroll_frame, bg="#F1F5F9", relief="solid", borderwidth=1)
        avg_frame.pack(fill="x", pady=10, padx=20)
        
        tk.Label(avg_frame, text=f"📊 Average Turnaround Time: {avg_tat:.2f} time units",
                font=("Segoe UI", 11, "bold"), bg="#F1F5F9", fg="#059669").pack(pady=5)
        tk.Label(avg_frame, text=f"⏱️ Average Waiting Time: {avg_wt:.2f} time units",
                font=("Segoe UI", 11, "bold"), bg="#F1F5F9", fg="#059669").pack(pady=5)
        
        # Close button
        tk.Button(scroll_frame, text="Close", command=win.destroy,
                 bg="#EF4444", fg="white", font=("Segoe UI", 10, "bold"),
                 padx=20, pady=5, relief="flat", cursor="hand2").pack(pady=15)
    
    def run_fcfs(self):
        processes = self.prepare_processes()
        if processes:
            self.current_algo = "FCFS"
            self.status.config(text="Running FCFS...")
            self.root.update()
            timeline, df, tat, wt = fcfs(processes)
            self.show_results(timeline, df, tat, wt)
            self.status.config(text="Ready")
    
    def run_sjf(self):
        processes = self.prepare_processes()
        if processes:
            self.current_algo = "SJF"
            self.status.config(text="Running SJF...")
            self.root.update()
            timeline, df, tat, wt = sjf(processes)
            self.show_results(timeline, df, tat, wt)
            self.status.config(text="Ready")
    
    def run_srtf(self):
        processes = self.prepare_processes()
        if processes:
            self.current_algo = "SRTF"
            self.status.config(text="Running SRTF...")
            self.root.update()
            timeline, df, tat, wt = srtf(processes)
            self.show_results(timeline, df, tat, wt)
            self.status.config(text="Ready")
    
    def show_rr(self):
        if not self.selected:
            messagebox.showwarning("No Selection", "Please select at least one process!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Round Robin - Time Quantum")
        dialog.geometry("350x180")
        dialog.configure(bg="#F3F4F6")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="Enter Time Quantum:", font=("Segoe UI", 12),
                bg="#F3F4F6").pack(pady=25)
        
        entry = tk.Entry(dialog, font=("Segoe UI", 12), width=15, justify="center")
        entry.insert(0, "2")
        entry.pack(pady=10)
        
        def run():
            try:
                quantum = int(entry.get())
                if quantum <= 0:
                    raise ValueError
                dialog.destroy()
                
                processes = self.prepare_processes()
                if processes:
                    self.current_algo = f"Round Robin (Q={quantum})"
                    self.status.config(text="Running Round Robin...")
                    self.root.update()
                    timeline, df, tat, wt = round_robin(processes, quantum)
                    self.show_results(timeline, df, tat, wt)
                    self.status.config(text="Ready")
            except:
                messagebox.showerror("Error", "Please enter a valid positive integer")
        
        button_frame = tk.Frame(dialog, bg="#F3F4F6")
        button_frame.pack(pady=15)
        
        tk.Button(button_frame, text="Run", command=run,
                 bg="#10B981", fg="white", font=("Segoe UI", 10, "bold"),
                 padx=25, relief="flat", cursor="hand2").pack(side="left", padx=10)
        
        tk.Button(button_frame, text="Cancel", command=dialog.destroy,
                 bg="#6B7280", fg="white", font=("Segoe UI", 10, "bold"),
                 padx=25, relief="flat", cursor="hand2").pack(side="left", padx=10)


# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    root = tk.Tk()
    app = CPUSchedulerApp(root)
    
    def on_close():
        if app.update_id:
            root.after_cancel(app.update_id)
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()