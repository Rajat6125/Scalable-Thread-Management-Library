import tkinter as tk
import customtkinter as ctk
import tkinter.ttk as ttk
from tkinter import messagebox
import random
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import psutil

from backend_core import ProcessMonitor, ProcessController, run_fcfs, run_rr, SynchronizationManager

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ProcessDashboard(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.monitor = ProcessMonitor()
        self.sync_mgr = SynchronizationManager()
        self.selected = {}  # Format: {pid: proc_info_dict}
        self.search_var = ctk.StringVar(value="") # <-- NEW LINE FOR SEARCH
        
        self.setup_graph()
        self.setup_middle_panel()
        self.setup_tabs()
        
        # Initial fetch
        self.refresh_processes()

    # --- 1. LIVE GRAPH ---
    def setup_graph(self):
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill="x", pady=5)
        
        self.num_cores = psutil.cpu_count()
        self.x_data = list(range(50))
        self.y_data = [[0] * 50 for _ in range(self.num_cores)]

        self.fig, self.ax = plt.subplots(figsize=(10, 2), facecolor='#2b2b2b')
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.9, bottom=0.2)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.set_ylim(0, 100)
        self.ax.set_xlim(0, 50)
        
        self.lines = []
        for i in range(self.num_cores):
            line, = self.ax.plot(self.x_data, self.y_data[i], label=f'Core {i}')
            self.lines.append(line)
            
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.top_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.ani = animation.FuncAnimation(self.fig, self.update_graph, interval=1000, cache_frame_data=False)

    def update_graph(self, frame):
        cpu_percents = psutil.cpu_percent(percpu=True)
        for i in range(self.num_cores):
            self.y_data[i].pop(0)
            self.y_data[i].append(cpu_percents[i])
            self.lines[i].set_ydata(self.y_data[i])
        return self.lines

    # --- 2. STABLE PROCESS TABLE ---
    def setup_middle_panel(self):
        self.mid_frame = ctk.CTkFrame(self)
        self.mid_frame.pack(fill="both", expand=True, pady=5)
        
        columns = ("Select", "PID", "Name", "CPU %", "Mem %", "Nice")
        self.tree = ttk.Treeview(self.mid_frame, columns=columns, show="headings", height=10)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=25)
        style.map('Treeview', background=[('selected', '#1f538d')])
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80, anchor="center")
        self.tree.column("Name", width=300, anchor="w")
        self.tree.column("Select", width=50)
        
        scrollbar = ttk.Scrollbar(self.mid_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        self.tree.bind('<ButtonRelease-1>', self.on_select)
        
        # Pagination & Random Select Controls
        ctrl_frame = ctk.CTkFrame(self.mid_frame, fg_color="transparent")
        ctrl_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(ctrl_frame, text="◀ Prev", width=60, command=self.prev_page).pack(side="left", padx=5)
        self.page_label = ctk.CTkLabel(ctrl_frame, text="Page 1")
        self.page_label.pack(side="left", padx=10)
        ctk.CTkButton(ctrl_frame, text="Next ▶", width=60, command=self.next_page).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_frame, text="🔄 Refresh", fg_color="#10B981", width=80, command=self.refresh_processes).pack(side="left", padx=10)
        
        # --- NEW SEARCH BAR ---
        self.search_entry = ctk.CTkEntry(ctrl_frame, textvariable=self.search_var, placeholder_text="Search Name/PID...", width=140)
        self.search_entry.pack(side="left", padx=(10, 0))
        self.search_entry.bind("<Return>", lambda e: self.refresh_processes()) # Press Enter to search
        ctk.CTkButton(ctrl_frame, text="🔍", width=30, command=self.refresh_processes).pack(side="left", padx=5)
        # ----------------------
        
        ctk.CTkLabel(ctrl_frame, text="Select Random:").pack(side="left", padx=(15,5))
        self.rand_entry = ctk.CTkEntry(ctrl_frame, width=40)
        self.rand_entry.insert(0, "5")
        self.rand_entry.pack(side="left")
        ctk.CTkButton(ctrl_frame, text="Go", width=40, fg_color="#F59E0B", command=self.select_random_n).pack(side="left", padx=5)
        
        self.selection_label = ctk.CTkLabel(ctrl_frame, text="Selected: 0 processes", text_color="#3B82F6")
        self.selection_label.pack(side="right", padx=10)

    # --- LIST LOGIC (FIXED REFRESH) ---
    def refresh_processes(self):
        self.monitor.refresh()
        
        # --- NEW FILTER LOGIC ---
        query = self.search_var.get().lower().strip()
        if query:
            self.monitor.process_list = [
                (pid, info) for pid, info in self.monitor.process_list
                if query in info['name'].lower() or query in str(pid)
            ]
        # ------------------------
        
        # Purge any selected processes that have died since the last refresh
        active_pids = self.monitor.all_processes.keys()
        self.selected = {pid: info for pid, info in self.selected.items() if pid in active_pids}
        
        # Reset to page 1 so the user actually sees the UI update
        self.monitor.current_page = 0 
        self.update_display()
        
    def update_display(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        page_data = self.monitor.get_page(self.monitor.current_page)
        for pid, info in page_data.items():
            checkbox = "✓" if pid in self.selected else "□"
            self.tree.insert("", "end", values=(checkbox, pid, info['name'][:40], f"{info['cpu']:.1f}", f"{info['memory']:.1f}", info['nice']))
            
        total = self.monitor.total_pages() or 1
        self.page_label.configure(text=f"Page {self.monitor.current_page + 1} of {total}")
        self.selection_label.configure(text=f"Selected: {len(self.selected)} processes")

    def prev_page(self):
        if self.monitor.current_page > 0:
            self.monitor.current_page -= 1
            self.update_display()

    def next_page(self):
        if self.monitor.current_page < self.monitor.total_pages() - 1:
            self.monitor.current_page += 1
            self.update_display()

    def on_select(self, event):
        selection = self.tree.selection()
        if not selection: return
        item = selection[0]
        values = self.tree.item(item, 'values')
        pid = int(values[1])
        
        if pid in self.selected:
            del self.selected[pid]
            self.tree.item(item, values=("□", values[1], values[2], values[3], values[4], values[5]))
        else:
            page_data = self.monitor.get_page(self.monitor.current_page)
            if pid in page_data:
                self.selected[pid] = page_data[pid]
                self.tree.item(item, values=("✓", values[1], values[2], values[3], values[4], values[5]))
        self.selection_label.configure(text=f"Selected: {len(self.selected)} processes")

    def select_random_n(self):
        try:
            n = int(self.rand_entry.get())
            all_pids = [p[0] for p in self.monitor.process_list] 
            if n > len(all_pids): n = len(all_pids)
            
            chosen_pids = random.sample(all_pids, n)
            self.selected.clear()
            
            for pid in chosen_pids:
                self.selected[pid] = self.monitor.all_processes[pid]
            
            self.update_display() 
        except ValueError:
            messagebox.showerror("Error", "Enter a valid integer")

    # --- 3. BOTTOM TABS ---
    def setup_tabs(self):
        self.tabview = ctk.CTkTabview(self, height=120)
        self.tabview.pack(fill="x", pady=5)
        
        t1 = self.tabview.add("Real OS Controls")
        t2 = self.tabview.add("Simulate Scheduling")
        t3 = self.tabview.add("Sync Demo")
        
        # Tab 1: OS Control 
        ctk.CTkButton(t1, text="Kill", fg_color="#EF4444", width=70, command=lambda: self.batch_os_action("kill")).pack(side="left", padx=5)
        ctk.CTkButton(t1, text="Suspend", fg_color="#F59E0B", width=70, command=lambda: self.batch_os_action("suspend")).pack(side="left", padx=5)
        ctk.CTkButton(t1, text="Resume", fg_color="#10B981", width=70, command=lambda: self.batch_os_action("resume")).pack(side="left", padx=5)
        
        ctk.CTkButton(t1, text="⚙️ Change Priority", fg_color="#3B82F6", command=self.open_priority_dialog).pack(side="left", padx=15)
        # UPDATED METHOD NAME HERE
        ctk.CTkButton(t1, text="📊 Analyze Resources", fg_color="#8B5CF6", command=self.show_resource_analytics).pack(side="left", padx=5)
        
        # Tab 2: Simulation
        ctk.CTkLabel(t2, text="Run Simulation on Selected:").pack(side="left", padx=10)
        ctk.CTkButton(t2, text="Run FCFS", command=lambda: self.run_sim("fcfs")).pack(side="left", padx=5)
        ctk.CTkButton(t2, text="Run Round Robin (Q=2)", command=lambda: self.run_sim("rr")).pack(side="left", padx=5)
        
        # Tab 3: Sync Demo
        self.sync_lbl = ctk.CTkLabel(t3, text="Ready to run threading demo.", text_color="#A78BFA")
        self.sync_lbl.pack(side="left", padx=20)
        ctk.CTkButton(t3, text="Start Sync Demo", fg_color="#8B5CF6", command=self.run_sync_demo).pack(side="right", padx=10)

    # --- MODULAR PRIORITY DIALOG ---
    def open_priority_dialog(self):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes first.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Change Priority")
        dialog.geometry("300x200")
        dialog.attributes("-topmost", True) 

        ctk.CTkLabel(dialog, text=f"Set Priority for {len(self.selected)} process(es)", font=("Segoe UI", 14, "bold")).pack(pady=20)

        priority_map = {"High Priority (-10)": -10, "Normal (0)": 0, "Low Priority (10)": 10}
        priority_var = ctk.StringVar(value="Normal (0)")

        dropdown = ctk.CTkOptionMenu(dialog, variable=priority_var, values=list(priority_map.keys()))
        dropdown.pack(pady=10)

        def apply_priority():
            val = priority_map[priority_var.get()]
            self.batch_os_action("nice", nice_value=val)
            dialog.destroy()

        ctk.CTkButton(dialog, text="Apply Changes", fg_color="#10B981", command=apply_priority).pack(pady=15)

    # --- UPGRADED BAR CHART ANALYTICS ---
    def show_resource_analytics(self):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes first to analyze.")
            return

        selected_cpu = sum(info['cpu'] for info in self.selected.values())
        selected_mem = sum(info['memory'] for info in self.selected.values())

        total_cpu = psutil.cpu_percent()
        total_mem = psutil.virtual_memory().percent

        other_cpu = max(0, total_cpu - selected_cpu)
        idle_cpu = max(0, 100 - total_cpu)
        other_mem = max(0, total_mem - selected_mem)
        free_mem = max(0, 100 - total_mem)

        win = ctk.CTkToplevel(self)
        win.title("Resource Analysis (Bar Charts)")
        win.geometry("800x450")
        win.attributes("-topmost", True)

        # Create subplots for Bar Charts
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), facecolor='#2b2b2b')
        fig.subplots_adjust(bottom=0.2, wspace=0.3)

        categories = ['Selected', 'Other Apps', 'Idle/Free']
        colors = ['#FF6B6B', '#4ECDC4', '#4b5563']

        # CPU Bar Chart
        cpu_vals = [selected_cpu, other_cpu, idle_cpu]
        ax1.bar(categories, cpu_vals, color=colors)
        ax1.set_title("CPU Utilization (%)", color="white", pad=10)
        ax1.set_ylim(0, 100)
        ax1.tick_params(colors='white')
        ax1.set_facecolor('#2b2b2b')

        # Memory Bar Chart
        mem_vals = [selected_mem, other_mem, free_mem]
        ax2.bar(categories, mem_vals, color=colors)
        ax2.set_title("Memory Utilization (%)", color="white", pad=10)
        ax2.set_ylim(0, 100)
        ax2.tick_params(colors='white')
        ax2.set_facecolor('#2b2b2b')

        # Add data labels on top of the bars for crisp readability
        for ax, vals in zip([ax1, ax2], [cpu_vals, mem_vals]):
            for i, v in enumerate(vals):
                ax.text(i, v + 2, f"{v:.1f}%", ha='center', color='white', fontweight='bold')

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    # --- OS AND SIMULATION EXECUTION ---
    def batch_os_action(self, action, **kwargs):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes first.")
            return
        results = []
        for pid in list(self.selected.keys()):
            success, msg = ProcessController.execute_action(pid, action, **kwargs)
            results.append(msg)
        messagebox.showinfo("Batch Results", "\n".join(results[:10]) + ("\n..." if len(results) > 10 else ""))
        self.refresh_processes() 

    def run_sim(self, algo):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes to simulate.")
            return
            
        sim_data = {}
        for pid, info in self.selected.items():
            sim_data[f"{info['name']}({pid})"] = {'at': random.randint(0, 5), 'bt': random.randint(2, 8)}
            
        if algo == "fcfs":
            timeline, df, tat, wt = run_fcfs(sim_data)
        else:
            timeline, df, tat, wt = run_rr(sim_data, quantum=2)
            
        self.show_results(timeline, df, tat, wt, algo.upper())

    # --- DYNAMICALLY SCALED GANTT CHART VISUALIZER ---
    def show_results(self, timeline, df, avg_tat, avg_wt, algo_name):
        win = ctk.CTkToplevel(self)
        win.title(f"Simulation Results - {algo_name}")
        win.geometry("1000x650")
        win.attributes("-topmost", True)

        scroll_frame = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll_frame, text=f"{algo_name} Scheduling Results", font=("Impact", 28)).pack(pady=10)

        gantt_frame = ctk.CTkFrame(scroll_frame)
        gantt_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(gantt_frame, text="Gantt Chart Timeline", font=("Segoe UI", 16, "bold")).pack(pady=5)

        # Frame to hold canvas + horizontal scrollbar
        gantt_container = ctk.CTkFrame(gantt_frame, fg_color="transparent")
        gantt_container.pack(fill="x", padx=10, pady=5)

        max_time = max(end for _, _, _, end in timeline) if timeline else 1
        
        # Fixed scale per time unit prevents squishing!
        scale = 35 
        total_canvas_width = max(800, max_time * scale + 100)

        canvas_gantt = tk.Canvas(gantt_container, bg="#1e1e1e", height=120, highlightthickness=0, 
                                 scrollregion=(0, 0, total_canvas_width, 120))
        
        h_scroll = ttk.Scrollbar(gantt_container, orient="horizontal", command=canvas_gantt.xview)
        canvas_gantt.configure(xscrollcommand=h_scroll.set)

        canvas_gantt.pack(side="top", fill="x", expand=True)
        h_scroll.pack(side="bottom", fill="x")

        colors = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7', '#A8E6CF', '#FF8B94', '#A3C4F3']
        x = 50

        for i, (proc_id, proc_name, start, end) in enumerate(timeline):
            w = (end - start) * scale
            if w > 0:
                color = colors[i % len(colors)]
                canvas_gantt.create_rectangle(x, 20, x + w, 70, fill=color, outline="#2b2b2b", width=2)
                
                # Only draw text if the block is wide enough
                if w > 25:
                    canvas_gantt.create_text(x + w/2, 45, text=proc_id, font=("Segoe UI", 11, "bold"), fill="black")
                    canvas_gantt.create_text(x + w/2, 65, text=f"BT:{end-start}", font=("Segoe UI", 8), fill="black")
                
                canvas_gantt.create_text(x, 95, text=str(int(start)), font=("Segoe UI", 8), fill="#A1A1AA")
                x += w

        canvas_gantt.create_text(x, 95, text=str(int(max_time)), font=("Segoe UI", 8), fill="#A1A1AA")

        # The Table
        table_frame = ctk.CTkFrame(scroll_frame)
        table_frame.pack(fill="both", expand=True, pady=10, padx=10)
        ctk.CTkLabel(table_frame, text="Process Statistics", font=("Segoe UI", 16, "bold")).pack(pady=5)

        columns = ['Process', 'PID', 'AT', 'BT', 'CT', 'TAT', 'WT']
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=8)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor='center')

        for proc_id in df.index:
            row = df.loc[proc_id]
            values = [row[col] for col in columns]
            tree.insert('', 'end', values=values)

        tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Averages
        avg_frame = ctk.CTkFrame(scroll_frame, fg_color="#1f538d")
        avg_frame.pack(fill="x", pady=10, padx=10)
        
        ctk.CTkLabel(avg_frame, text=f"📊 Average Turnaround Time: {avg_tat:.2f} units", font=("Segoe UI", 14, "bold"), text_color="white").pack(pady=5)
        ctk.CTkLabel(avg_frame, text=f"⏱️ Average Waiting Time: {avg_wt:.2f} units", font=("Segoe UI", 14, "bold"), text_color="white").pack(pady=5)

    def run_sync_demo(self):
        self.sync_lbl.configure(text="Demo Running... Check Terminal/Logs")
        self.sync_mgr.start_demo(num_threads=4)
        self.monitor_sync_demo()

    def monitor_sync_demo(self):
        if self.sync_mgr.logs:
            self.sync_lbl.configure(text=self.sync_mgr.logs[-1])
        if any(t.is_alive() for t in self.sync_mgr.active_threads):
            self.after(200, self.monitor_sync_demo)
        else:
            self.sync_lbl.configure(text="Demo Complete.")