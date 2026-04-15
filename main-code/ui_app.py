import os
import tkinter as tk
import customtkinter as ctk
import tkinter.ttk as ttk
from tkinter import messagebox
import random
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import psutil
import colorsys

from backend_core import ProcessMonitor, ProcessController, ContextManager, LiveScheduler, ActiveGuard

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ProcessDashboard(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.monitor = ProcessMonitor()
        self.selected = {}  
        self.search_var = ctk.StringVar(value="") 
        
        self.setup_graph()
        self.setup_middle_panel()
        self.setup_tabs()
        
        self.refresh_processes()
        
        
        # --- NEW: Start the auto-refresh loop for the AI ---
        # n seconds matches the 6 data points needed for the AI!
        
        self.auto_train_loop(seconds_left=ProcessMonitor.REQUIRED_SAMPLES)


    def auto_train_loop(self, seconds_left):
        """Automatically refreshes the table to feed the AI Predictor on startup."""
        if seconds_left > 0:
            self.refresh_processes()
            # Schedule this function to run again in 1000ms (1 second)
            self.after(1000, self.auto_train_loop, seconds_left - 1)
            
            
# --- 1. LIVE GRAPH (Toggleable Overview / Per-Core) ---
    def setup_graph(self):
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill="x", pady=5)
        
        # Add a header frame for the title and checkbox
        header = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(5, 0))
        
        ctk.CTkLabel(header, text="System Resource Monitor", font=("Segoe UI", 14, "bold")).pack(side="left")
        
        self.show_cores_var = ctk.BooleanVar(value=False)
        self.cores_checkbox = ctk.CTkCheckBox(header, text="Show Individual CPU Cores", 
                                              variable=self.show_cores_var, 
                                              command=self.toggle_graph_legend)
        self.cores_checkbox.pack(side="right")
        
        # Data structures for overall system usage
        self.x_data = list(range(60))
        self.cpu_data = [0] * 60
        self.mem_data = [0] * 60

        # Data structures for per-core usage
        self.num_cores = psutil.cpu_count()
        self.core_data = [[0] * 60 for _ in range(self.num_cores)]

        self.fig, self.ax = plt.subplots(figsize=(10, 2), facecolor='#2b2b2b')
        self.fig.subplots_adjust(left=0.05, right=0.95, top=0.85, bottom=0.2)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.tick_params(colors='white')
        self.ax.set_ylim(0, 100)
        self.ax.set_xlim(0, 59)
        self.ax.grid(True, color='#404040', linestyle='--', alpha=0.5)
        
        # 1. Create the Overall System Lines
        self.cpu_line, = self.ax.plot(self.x_data, self.cpu_data, color='#10B981', label='System CPU %', linewidth=2)
        self.mem_line, = self.ax.plot(self.x_data, self.mem_data, color='#8B5CF6', label='System RAM %', linewidth=2)
        self.sys_legend = self.ax.legend(loc='upper right', facecolor='#2b2b2b', labelcolor='white')
            
        # 2. Create the Per-Core Lines (Hidden by default)
        self.core_lines = []
        for i in range(self.num_cores):
            # Generate a unique color for each core
            hue = i / self.num_cores
            rgb = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
            hex_color = '#%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
            
            line, = self.ax.plot(self.x_data, self.core_data[i], color=hex_color, linewidth=1.5, alpha=0.7)
            line.set_visible(False)
            self.core_lines.append(line)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.top_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.ani = animation.FuncAnimation(self.fig, self.update_graph, interval=1000, cache_frame_data=False)

    def toggle_graph_legend(self):
        """Hides the legend when showing cores to prevent clutter."""
        if self.show_cores_var.get():
            self.sys_legend.set_visible(False)
        else:
            self.sys_legend.set_visible(True)

    def update_graph(self, frame):
        show_cores = self.show_cores_var.get()

        if show_cores:
            # --- Per-Core Mode ---
            core_percents = psutil.cpu_percent(percpu=True)
            for i in range(self.num_cores):
                self.core_data[i].pop(0)
                self.core_data[i].append(core_percents[i])
                self.core_lines[i].set_ydata(self.core_data[i])
                self.core_lines[i].set_visible(True)
            
            # Hide system lines
            self.cpu_line.set_visible(False)
            self.mem_line.set_visible(False)
            
            return self.core_lines
            
        else:
            # --- Overall System Mode ---
            self.cpu_data.pop(0)
            self.cpu_data.append(psutil.cpu_percent())
            self.mem_data.pop(0)
            self.mem_data.append(psutil.virtual_memory().percent)

            self.cpu_line.set_ydata(self.cpu_data)
            self.mem_line.set_ydata(self.mem_data)
            
            # Show system lines
            self.cpu_line.set_visible(True)
            self.mem_line.set_visible(True)
            
            # Hide core lines
            for line in self.core_lines:
                line.set_visible(False)
                
            return [self.cpu_line, self.mem_line]

    # --- 2. STABLE PROCESS TABLE ---
    def setup_middle_panel(self):
        self.mid_frame = ctk.CTkFrame(self)
        self.mid_frame.pack(fill="both", expand=True, pady=5)
        
        columns = ("Select", "PID", "Name", "CPU %", "Mem %", "Nice", "AI Prediction")
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
        # 2. Add a width definition for the new column
        self.tree.column("AI Prediction", width=100, anchor="center")
        
        
        scrollbar = ttk.Scrollbar(self.mid_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        self.tree.bind('<ButtonRelease-1>', self.on_select)
        
        ctrl_frame = ctk.CTkFrame(self.mid_frame, fg_color="transparent")
        ctrl_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(ctrl_frame, text="◀ Prev", width=60, command=self.prev_page).pack(side="left", padx=5)
        self.page_label = ctk.CTkLabel(ctrl_frame, text="Page 1")
        self.page_label.pack(side="left", padx=10)
        ctk.CTkButton(ctrl_frame, text="Next ▶", width=60, command=self.next_page).pack(side="left", padx=5)
        ctk.CTkButton(ctrl_frame, text="🔄 Refresh", fg_color="#10B981", width=80, command=self.refresh_processes).pack(side="left", padx=10)
        
        # --- NEW: Retrain AI Button ---
        ctk.CTkButton(ctrl_frame, text="🧠 Retrain AI", fg_color="#8B5CF6", width=90, command=self.trigger_retrain).pack(side="left", padx=2)
        
        self.search_entry = ctk.CTkEntry(ctrl_frame, textvariable=self.search_var, placeholder_text="Search Name/PID...", width=140)
        
        
        
        self.search_entry = ctk.CTkEntry(ctrl_frame, textvariable=self.search_var, placeholder_text="Search Name/PID...", width=140)
        self.search_entry.pack(side="left", padx=(10, 0))
        self.search_entry.bind("<Return>", lambda e: self.refresh_processes())
        ctk.CTkButton(ctrl_frame, text="🔍", width=30, command=self.refresh_processes).pack(side="left", padx=5)
        
        # === NEW: SELECT ALL & CLEAR BUTTONS ===
        ctk.CTkButton(ctrl_frame, text="✓ All", width=50, fg_color="#3B82F6", command=self.select_all).pack(side="left", padx=(5,2))
        ctk.CTkButton(ctrl_frame, text="✗ Clear", width=50, fg_color="#6B7280", command=self.clear_selection).pack(side="left", padx=2)
        
        ctk.CTkLabel(ctrl_frame, text="Select Random:").pack(side="left", padx=(15,5))
        self.rand_entry = ctk.CTkEntry(ctrl_frame, width=40)
        self.rand_entry.insert(0, "5")
        self.rand_entry.pack(side="left")
        ctk.CTkButton(ctrl_frame, text="Go", width=40, fg_color="#F59E0B", command=self.select_random_n).pack(side="left", padx=5)
        
        self.selection_label = ctk.CTkLabel(ctrl_frame, text="Selected: 0 processes", text_color="#3B82F6")
        self.selection_label.pack(side="right", padx=10)

    # NEW METHODS
    def select_all(self):
        # Selects everything currently filtered/visible in the list
        for pid, info in self.monitor.process_list:
            self.selected[pid] = info
        self.update_display()
        
    def clear_selection(self):
        self.selected.clear()
        self.update_display()

    def refresh_processes(self):
        self.monitor.refresh()
        
        query = self.search_var.get().lower().strip()
        if query:
            self.monitor.process_list = [
                (pid, info) for pid, info in self.monitor.process_list
                if query in info['name'].lower() or query in str(pid)
            ]
        
        active_pids = self.monitor.all_processes.keys()
        self.selected = {pid: self.monitor.all_processes[pid] for pid in self.selected.keys() if pid in active_pids}
        
        self.monitor.current_page = 0 
        self.update_display()
        
    def update_display(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        page_data = self.monitor.get_page(self.monitor.current_page)
        for pid, info in page_data.items():
            checkbox = "✓" if pid in self.selected else "□"
            
            # --- FETCH AI PREDICTION ---
            prediction = self.monitor.predict_cpu_ai(pid)
            
            # Insert the prediction into the values tuple
            self.tree.insert("", "end", values=(checkbox, pid, info['name'][:40], f"{info['cpu']:.1f}", f"{info['memory']:.1f}", info['nice'], prediction))
            
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
            # Add values[6] to keep the prediction text when unchecked
            self.tree.item(item, values=("□", values[1], values[2], values[3], values[4], values[5], values[6]))
        else:
            page_data = self.monitor.get_page(self.monitor.current_page)
            if pid in page_data:
                self.selected[pid] = page_data[pid]
                # Add values[6] to keep the prediction text when checked
                self.tree.item(item, values=("✓", values[1], values[2], values[3], values[4], values[5], values[6]))
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
        self.tabview = ctk.CTkTabview(self, height=220)
        self.tabview.pack(fill="x", pady=5)
        
        t1 = self.tabview.add("Real OS Controls")
        t2 = self.tabview.add("Live OS Scheduler") 
        t3 = self.tabview.add("Context Switcher") 
        t4 = self.tabview.add("Active OS Guard")
        
        # Tab 1: OS Control 
        ctk.CTkButton(t1, text="Kill", fg_color="#EF4444", width=70, command=lambda: self.batch_os_action("kill")).pack(side="left", padx=5)
        ctk.CTkButton(t1, text="Suspend", fg_color="#F59E0B", width=70, command=lambda: self.batch_os_action("suspend")).pack(side="left", padx=5)
        ctk.CTkButton(t1, text="Resume", fg_color="#10B981", width=70, command=lambda: self.batch_os_action("resume")).pack(side="left", padx=5)
        
        ctk.CTkButton(t1, text="⚙️ Change Priority", fg_color="#3B82F6", command=self.open_priority_dialog).pack(side="left", padx=15)
        ctk.CTkButton(t1, text="📊 Analyze Resources", fg_color="#8B5CF6", command=self.show_resource_analytics).pack(side="left", padx=5)
        # --- NEW: Core Affinity Button ---
        ctk.CTkButton(t1, text="💻 Set Core Affinity", fg_color="#F43F5E", command=self.open_affinity_dialog).pack(side="left", padx=5)
        
        
        
        
        # Tab 2: Live OS Scheduler
        ctrl_frame2 = ctk.CTkFrame(t2, fg_color="transparent")
        ctrl_frame2.pack(fill="x", pady=5)
        
        ctk.CTkLabel(ctrl_frame2, text="Mode:").pack(side="left", padx=(5, 2))
        self.mode_var = ctk.StringVar(value="Manual (Table)")
        ctk.CTkOptionMenu(ctrl_frame2, variable=self.mode_var, values=["Manual (Table)", "Auto (Hungry Apps)"], width=130).pack(side="left", padx=2)

        ctk.CTkLabel(ctrl_frame2, text="Algo:").pack(side="left", padx=(10, 2))
        self.algo_var = ctk.StringVar(value="Round Robin")
        self.algo_menu = ctk.CTkOptionMenu(ctrl_frame2, variable=self.algo_var, values=["Round Robin", "FCFS", "SJF", "Priority"], width=110, command=self.on_algo_change)
        self.algo_menu.pack(side="left", padx=2)

        self.q_frame = ctk.CTkFrame(ctrl_frame2, fg_color="transparent")
        self.q_frame.pack(side="left", padx=2)
        ctk.CTkLabel(self.q_frame, text="Q(s):").pack(side="left", padx=(2, 2))
        self.quantum_entry = ctk.CTkEntry(self.q_frame, width=40)
        self.quantum_entry.insert(0, "2.0")
        self.quantum_entry.pack(side="left")
        
        self.btn_start_live = ctk.CTkButton(ctrl_frame2, text="▶ Start Scheduling", fg_color="#10B981", width=120, command=self.start_live_scheduler)
        self.btn_start_live.pack(side="left", padx=(15, 5))
        
        self.btn_stop_live = ctk.CTkButton(ctrl_frame2, text="⏹ Stop & Resume All", fg_color="#EF4444", width=120, state="disabled", command=self.stop_live_scheduler)
        self.btn_stop_live.pack(side="left", padx=5)

        gantt_container = ctk.CTkFrame(t2)
        gantt_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.live_canvas = tk.Canvas(gantt_container, bg="#1e1e1e", highlightthickness=0, height=80)
        self.live_scroll = ttk.Scrollbar(gantt_container, orient="horizontal", command=self.live_canvas.xview)
        self.live_canvas.configure(xscrollcommand=self.live_scroll.set)

        self.live_canvas.pack(side="top", fill="both", expand=True)
        self.live_scroll.pack(side="bottom", fill="x")

        self.live_scheduler = None
        self.live_colors = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7', '#A8E6CF', '#FF8B94', '#A3C4F3']
        
        # Tab 3: Context Switcher (REFINED UI for Start/Terminate)
        top_ctx = ctk.CTkFrame(t3, fg_color="transparent")
        top_ctx.pack(fill="x", padx=10, pady=5)
        
        self.profile_var = ctk.StringVar(value="Gaming Mode")
        profiles = ContextManager.load_profiles()
        self.profile_dropdown = ctk.CTkOptionMenu(top_ctx, variable=self.profile_var, values=list(profiles.keys()), command=self.update_profile_view)
        self.profile_dropdown.pack(side="left", padx=5)
        
        # Unified dropdown for adding actions to the profile
        self.ctx_action_var = ctk.StringVar(value="Suspend")
        ctx_action_menu = ctk.CTkOptionMenu(top_ctx, variable=self.ctx_action_var, values=["Suspend", "Terminate", "Start (Launch)", "Set Priority"], width=130)
        ctx_action_menu.pack(side="left", padx=15)
        
        ctk.CTkButton(top_ctx, text="➕ Add to Profile", fg_color="#3B82F6", command=self.add_to_profile_action).pack(side="left", padx=5)
        ctk.CTkButton(top_ctx, text="🗑️ Clear Profile", fg_color="#EF4444", command=self.clear_profile).pack(side="right", padx=5)
        
        self.throttle_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(t3, text="Aggressive Mode: Auto-Throttle all other background apps to Low Priority", variable=self.throttle_var, text_color="#FCD34D").pack(pady=(0, 5))

        split_frame = ctk.CTkFrame(t3, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=10, pady=0)
        
        left_pane = ctk.CTkFrame(split_frame, fg_color="transparent")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0,5))
        
        self.profile_view = ctk.CTkTextbox(left_pane, height=70, fg_color="#2b2b2b", text_color="white")
        self.profile_view.pack(fill="both", expand=True)
        
        right_pane = ctk.CTkFrame(split_frame, fg_color="transparent")
        right_pane.pack(side="right", fill="both", expand=True, padx=(5,0))
        
        self.context_log = ctk.CTkTextbox(right_pane, height=70, fg_color="#1e1e1e", text_color="#A1A1AA")
        self.context_log.pack(fill="both", expand=True)
        
        exec_frame = ctk.CTkFrame(t3, fg_color="transparent")
        exec_frame.pack(fill="x", pady=5)
        
        self.btn_apply_ctx = ctk.CTkButton(exec_frame, text="🚀 START MODE", fg_color="#8B5CF6", hover_color="#7C3AED", command=self.run_context)
        self.btn_apply_ctx.pack(side="left", expand=True, padx=10)

        self.btn_revert_ctx = ctk.CTkButton(exec_frame, text="🛑 STOP & REVERT", fg_color="#EF4444", hover_color="#B91C1C", state="disabled", command=self.revert_context)
        self.btn_revert_ctx.pack(side="left", expand=True, padx=10)
        
        self.update_profile_view()
        self.context_log.insert("1.0", "Ready. Apply a profile to see execution logs here.\n")

        # Tab 4: Active OS Guard
        self.guard_backend = ActiveGuard()
        self.safe_zone_list = []
        
        guard_top = ctk.CTkFrame(t4, fg_color="transparent")
        guard_top.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(guard_top, text="🛡️ Add Selected to Safe Zone", fg_color="#3B82F6", command=self.add_to_safe_zone).pack(side="left", padx=5)
        self.safe_zone_label = ctk.CTkLabel(guard_top, text="Safe Apps: None", text_color="#10B981")
        self.safe_zone_label.pack(side="left", padx=10)
        
        guard_mid = ctk.CTkFrame(t4, fg_color="transparent")
        guard_mid.pack(fill="x", padx=5, pady=10)
        
        ctk.CTkLabel(guard_mid, text="Check Every (sec):").pack(side="left", padx=2)
        self.guard_interval = ctk.CTkEntry(guard_mid, width=40)
        self.guard_interval.insert(0, "2.0")
        self.guard_interval.pack(side="left", padx=2)
        
        ctk.CTkLabel(guard_mid, text="Max CPU Limit (%):").pack(side="left", padx=(15, 2))
        self.guard_cpu = ctk.CTkEntry(guard_mid, width=40)
        self.guard_cpu.insert(0, "15.0")
        self.guard_cpu.pack(side="left", padx=2)
        
        ctk.CTkLabel(guard_mid, text="Action:").pack(side="left", padx=(15, 2))
        self.guard_action = ctk.StringVar(value="Lower Priority")
        self.guard_action_menu = ctk.CTkOptionMenu(guard_mid, variable=self.guard_action, values=["Lower Priority", "Suspend"], width=130, command=self.on_guard_action_change)
        self.guard_action_menu.pack(side="left", padx=2)
        
        self.guard_nice_frame = ctk.CTkFrame(guard_mid, fg_color="transparent")
        self.guard_nice_frame.pack(side="left", padx=2)
        ctk.CTkLabel(self.guard_nice_frame, text="Target Nice:").pack(side="left", padx=2)
        self.guard_nice = ctk.CTkEntry(self.guard_nice_frame, width=40)
        self.guard_nice.insert(0, "15") 
        self.guard_nice.pack(side="left", padx=2)
        
        guard_bot = ctk.CTkFrame(t4, fg_color="transparent")
        guard_bot.pack(fill="x", padx=5, pady=5)
        
        self.btn_start_guard = ctk.CTkButton(guard_bot, text="🟢 Start Active Guard", fg_color="#10B981", command=self.start_guard)
        self.btn_start_guard.pack(side="left", padx=5)
        
        self.btn_stop_guard = ctk.CTkButton(guard_bot, text="🔴 Stop Guard", fg_color="#EF4444", state="disabled", command=self.stop_guard)
        self.btn_stop_guard.pack(side="left", padx=5)




    def trigger_retrain(self):
        """Wipes the AI's memory and restarts the auto-training countdown."""
        # 1. Tell the backend to clear the history dictionary
        self.monitor.reset_ai_training()
        
        # 2. Start the rapid-fire auto-refresh loop again
        self.auto_train_loop(seconds_left=self.monitor.REQUIRED_SAMPLES)
        
        
        
    # ==========================================
    # CONFIRMATION DIALOG 
    # ==========================================
    def confirm_auto_selection(self, pids, action_type, algo=None):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Review {action_type} Targets")
        dialog.geometry("450x350")
        dialog.attributes("-topmost", True)
        
        ctk.CTkLabel(dialog, text=f"Review automatically selected processes:", font=("Segoe UI", 14, "bold")).pack(pady=10)
        ctk.CTkLabel(dialog, text="Uncheck any processes you want to skip.", text_color="#A1A1AA").pack()
        
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        check_vars = {}
        for pid in pids:
            name = self.monitor.all_processes.get(pid, {}).get('name', str(pid))
            cpu = self.monitor.all_processes.get(pid, {}).get('cpu', 0.0)
            var = ctk.BooleanVar(value=True)
            
            cb_text = f"{name[:25]} (PID: {pid}) - CPU: {cpu:.1f}%"
            cb = ctk.CTkCheckBox(scroll, text=cb_text, variable=var)
            cb.pack(anchor="w", pady=5, padx=5)
            check_vars[pid] = var
            
        def on_confirm():
            final_pids = [p for p, v in check_vars.items() if v.get()]
            dialog.destroy()
            
            if not final_pids:
                messagebox.showinfo("Cancelled", "No processes were left selected.")
                return
                
            if action_type == "Scheduler":
                if algo == "Round Robin":
                    self.execute_scheduler(final_pids, algo, custom_params={})
                else:
                    auto_params = {}
                    for pid in final_pids:
                        cpu_usage = self.monitor.all_processes[pid]['cpu']
                        auto_params[pid] = {
                            'burst': max(5.0, min(cpu_usage, 20.0)),
                            'priority': random.randint(1, 5)
                        }
                    self.execute_scheduler(final_pids, algo, custom_params=auto_params)
                    
        ctk.CTkButton(dialog, text="Confirm Execution ▶", fg_color="#10B981", command=on_confirm).pack(pady=10)


    # --- DYNAMIC CONTEXT SWITCHER UI METHODS ---
    def update_profile_view(self, *_):
        profile_name = self.profile_var.get()
        profiles = ContextManager.load_profiles()
        data = profiles.get(profile_name, {"suspend": [], "terminate": [], "start": [], "priority": {}})
        
        self.profile_view.delete("1.0", "end")
        self.profile_view.insert("end", f"--- {profile_name} Saved Config ---\n")
        
        starts = [os.path.basename(p) for p in data.get('start', [])]
        self.profile_view.insert("end", f"🚀 Will Launch: {', '.join(starts) or 'None'}\n")
        self.profile_view.insert("end", f"💀 Will Terminate: {', '.join(data.get('terminate', [])) or 'None'}\n")
        self.profile_view.insert("end", f"⏸ Will Suspend: {', '.join(data.get('suspend', [])) or 'None'}\n")
        
        pri_data = data.get("priority", {})
        pri_str = ", ".join([f"{k} ({'High' if v < 0 or v > 30 else 'Low'})" for k, v in pri_data.items()])
        self.profile_view.insert("end", f"⚙️ Priorities: {pri_str if pri_str else 'None'}\n")

    def add_to_profile_action(self):
        action = self.ctx_action_var.get()
        if action == "Set Priority":
            self.add_priority_to_profile()
        elif action == "Suspend":
            self.add_to_profile("suspend")
        elif action == "Terminate":
            self.add_to_profile("terminate")
        elif action == "Start (Launch)":
            self.add_to_profile("start")

    def add_to_profile(self, category):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes from the table first!")
            return
            
        profile_name = self.profile_var.get()
        profiles = ContextManager.load_profiles()
        
        if profile_name not in profiles:
            profiles[profile_name] = {"suspend": [], "terminate": [], "start": [], "priority": {}}
            
        if category == "start":
            # For starting, we need to save the actual file paths (.exe / .app)
            new_items = set(info.get('exe', '') for info in self.selected.values() if info.get('exe'))
            if not new_items:
                messagebox.showwarning("Access Denied", "Could not retrieve file paths for selected processes. Run as Administrator.")
                return
        else:
            # For Suspend/Terminate, we just save the process names
            new_items = set(info['name'].lower() for info in self.selected.values())
            if category in ["suspend", "terminate"]:
                new_items = {name for name in new_items if "python" not in name and "main.py" not in name}

        current_list = set(profiles[profile_name].get(category, []))
        current_list.update(new_items)
        
        profiles[profile_name][category] = list(current_list)
        ContextManager.save_profiles(profiles)
        
        self.update_profile_view()
        self.clear_selection()
        
    def add_priority_to_profile(self):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes from the table first!")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Assign Profile Priority")
        dialog.geometry("300x200")
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text="Set Priority level for Profile:", font=("Segoe UI", 14, "bold")).pack(pady=20)

        if os.name == 'nt':
            priority_map = {"High Priority (Gaming)": psutil.HIGH_PRIORITY_CLASS, "Low Priority (Background)": psutil.IDLE_PRIORITY_CLASS}
        else:
            priority_map = {"High Priority (-10)": -10, "Low Priority (10)": 10}

        priority_var = ctk.StringVar(value=list(priority_map.keys())[0])
        dropdown = ctk.CTkOptionMenu(dialog, variable=priority_var, values=list(priority_map.keys()))
        dropdown.pack(pady=10)

        def save_priority():
            val = priority_map[priority_var.get()]
            profile_name = self.profile_var.get()
            profiles = ContextManager.load_profiles()

            if profile_name not in profiles:
                profiles[profile_name] = {"suspend": [], "terminate": [], "start": [], "priority": {}}
            if "priority" not in profiles[profile_name]:
                profiles[profile_name]["priority"] = {}

            new_names = set(info['name'].lower() for info in self.selected.values())
            for name in new_names:
                if "python" not in name and "main.py" not in name:
                    profiles[profile_name]["priority"][name] = val

            ContextManager.save_profiles(profiles)
            self.update_profile_view()
            self.clear_selection()
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save to Profile", fg_color="#10B981", command=save_priority).pack(pady=15)

    def clear_profile(self):
        profile_name = self.profile_var.get()
        if messagebox.askyesno("Confirm", f"Are you sure you want to clear all saved apps for {profile_name}?"):
            profiles = ContextManager.load_profiles()
            profiles[profile_name] = {"suspend": [], "terminate": [], "start": [], "priority": {}}
            ContextManager.save_profiles(profiles)
            self.update_profile_view()

    def run_context(self):
        profile_name = self.profile_var.get()
        do_throttle = self.throttle_var.get()
        
        self.context_log.delete("1.0", "end")
        self.context_log.insert("end", f"Applying {profile_name}...\n\n")
        
        logs = ContextManager.apply_profile(profile_name, auto_throttle=do_throttle)
        self.context_log.insert("end", "\n".join(logs) + "\n")
        
        self.btn_apply_ctx.configure(state="disabled")
        self.btn_revert_ctx.configure(state="normal")
        self.refresh_processes()

    def revert_context(self):
        self.context_log.delete("1.0", "end")
        self.context_log.insert("end", "Reverting to normal state...\n\n")
        
        logs = ContextManager.revert_context()
        self.context_log.insert("end", "\n".join(logs) + "\n")
        
        self.btn_apply_ctx.configure(state="normal")
        self.btn_revert_ctx.configure(state="disabled")
        self.refresh_processes()

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

        if os.name == 'nt':
            priority_map = {"High Priority": psutil.HIGH_PRIORITY_CLASS, "Normal": psutil.NORMAL_PRIORITY_CLASS, "Low Priority": psutil.IDLE_PRIORITY_CLASS}
        else:
            priority_map = {"High Priority (-10)": -10, "Normal (0)": 0, "Low Priority (10)": 10}
            
        priority_var = ctk.StringVar(value=list(priority_map.keys())[1])

        dropdown = ctk.CTkOptionMenu(dialog, variable=priority_var, values=list(priority_map.keys()))
        dropdown.pack(pady=10)

        def apply_priority():
            val = priority_map[priority_var.get()]
            self.batch_os_action("nice", nice_value=val)
            dialog.destroy()

        ctk.CTkButton(dialog, text="Apply Changes", fg_color="#10B981", command=apply_priority).pack(pady=15)

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

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), facecolor='#2b2b2b')
        fig.subplots_adjust(bottom=0.2, wspace=0.3)

        categories = ['Selected', 'Other Apps', 'Idle/Free']
        colors = ['#FF6B6B', '#4ECDC4', '#4b5563']

        cpu_vals = [selected_cpu, other_cpu, idle_cpu]
        ax1.bar(categories, cpu_vals, color=colors)
        ax1.set_title("CPU Utilization (%)", color="white", pad=10)
        ax1.set_ylim(0, 100)
        ax1.tick_params(colors='white')
        ax1.set_facecolor('#2b2b2b')

        mem_vals = [selected_mem, other_mem, free_mem]
        ax2.bar(categories, mem_vals, color=colors)
        ax2.set_title("Memory Utilization (%)", color="white", pad=10)
        ax2.set_ylim(0, 100)
        ax2.tick_params(colors='white')
        ax2.set_facecolor('#2b2b2b')

        for ax, vals in zip([ax1, ax2], [cpu_vals, mem_vals]):
            for i, v in enumerate(vals):
                ax.text(i, v + 2, f"{v:.1f}%", ha='center', color='white', fontweight='bold')

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    # to change CPU_Affinity
    def open_affinity_dialog(self):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes first.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Set CPU Core Affinity")
        dialog.geometry("350x400")
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text=f"Assign Cores for {len(self.selected)} process(es)", font=("Segoe UI", 14, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(dialog, text="Select the logical cores to allow usage:", text_color="#A1A1AA").pack(pady=(0, 10))

        # Dynamically find out how many logical cores the system has
        num_cores = psutil.cpu_count()
        
        # Use a scrollable frame in case the user has a 16+ core CPU!
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=20, pady=5)

        self.core_vars = {}
        for i in range(num_cores):
            var = ctk.BooleanVar(value=True) # Default all cores checked
            cb = ctk.CTkCheckBox(scroll, text=f"CPU Core {i}", variable=var)
            cb.pack(anchor="w", pady=5, padx=10)
            self.core_vars[i] = var

        def apply_affinity():
            selected_cores = [core for core, var in self.core_vars.items() if var.get()]
            
            if not selected_cores:
                messagebox.showwarning("Warning", "You must select at least one core to run the process!")
                return
            
            results = []
            for pid in list(self.selected.keys()):
                # Call your existing backend function!
                success, msg = ProcessController.set_affinity(pid, selected_cores)
                results.append(msg)
            
            messagebox.showinfo("Affinity Results", "\n".join(results[:10]) + ("\n..." if len(results) > 10 else ""))
            dialog.destroy()

        ctk.CTkButton(dialog, text="Apply Affinity Restrictions", fg_color="#10B981", command=apply_affinity).pack(pady=15)








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

    # --- LIVE OS SCHEDULING UI ---
    def on_algo_change(self, choice):
        if choice == "Round Robin":
            self.q_frame.pack(side="left", padx=2, before=self.btn_start_live)
        else:
            self.q_frame.pack_forget()

    def start_live_scheduler(self):
        mode = self.mode_var.get()
        algo = self.algo_var.get()
        
        if mode == "Manual (Table)":
            if not self.selected:
                messagebox.showwarning("Warning", "Select processes from the table first.")
                return
            pids_to_schedule = list(self.selected.keys())
            
            if algo == "Round Robin":
                self.execute_scheduler(pids_to_schedule, algo, custom_params={})
            else:
                self.prompt_for_params(pids_to_schedule, algo)
                
        else:
            pids_to_schedule = self.auto_select_hungry_processes()
            if not pids_to_schedule:
                messagebox.showerror("Error", "Could not find safe, active background processes.")
                return
                
            self.confirm_auto_selection(pids_to_schedule, action_type="Scheduler", algo=algo)

    def auto_select_hungry_processes(self):
        self.monitor.refresh()
        safe_procs = []
        
        # ADDED 'xwayland' to the list below!
        critical_names = ['systemd', 'kthreadd', 'kworker', 'rcu_sched', 'svchost.exe', 'csrss.exe', 
                          'smss.exe', 'wininit.exe', 'services.exe', 'lsass.exe', 'explorer.exe', 
                          'gnome-shell', 'xorg', 'xwayland', 'system', 'registry', 'python']
        
        my_pid = os.getpid() 
        
        for pid, info in self.monitor.all_processes.items():
            if pid <= 100 or pid == my_pid: continue 
            
            name = info['name'].lower()
            if any(crit in name for crit in critical_names): continue
            
            try:
                p = psutil.Process(pid)
                if p.username() in ['root', 'SYSTEM', 'Network Service', 'Local Service']:
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue
                
            safe_procs.append((pid, info['cpu']))
            
        safe_procs.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in safe_procs[:4]]

    def prompt_for_params(self, pids, algo):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"{algo} Parameters")
        dialog.geometry("400x350")
        dialog.attributes("-topmost", True)
        
        ctk.CTkLabel(dialog, text=f"Configure Simulated Jobs for {algo}", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.param_inputs = {}
        for pid in pids:
            name = self.monitor.all_processes.get(pid, {}).get('name', str(pid))
            frame = ctk.CTkFrame(scroll)
            frame.pack(fill="x", pady=2, padx=5)
            
            ctk.CTkLabel(frame, text=f"{name[:12]} (P:{pid})", width=120, anchor="w").pack(side="left", padx=5)
            
            burst_var = ctk.StringVar(value=str(random.randint(5, 12)))
            ctk.CTkLabel(frame, text="Burst(s):").pack(side="left")
            ctk.CTkEntry(frame, textvariable=burst_var, width=40).pack(side="left", padx=5)
            
            pri_var = None
            if algo == "Priority":
                pri_var = ctk.StringVar(value="1")
                ctk.CTkLabel(frame, text="Pri:").pack(side="left")
                ctk.CTkEntry(frame, textvariable=pri_var, width=30).pack(side="left", padx=5)
                
            self.param_inputs[pid] = (burst_var, pri_var)
            
        def on_confirm():
            custom_params = {}
            for p, (b_var, p_var) in self.param_inputs.items():
                try: b = float(b_var.get())
                except ValueError: b = 10.0
                
                pr = 1
                if p_var:
                    try: pr = int(p_var.get())
                    except ValueError: pr = 1
                    
                custom_params[p] = {'burst': b, 'priority': pr}
            
            dialog.destroy()
            self.execute_scheduler(pids, algo, custom_params=custom_params)
            
        ctk.CTkButton(dialog, text="Start Execution ▶", fg_color="#10B981", command=on_confirm).pack(pady=10)

    def execute_scheduler(self, pids, algo, custom_params=None):
        try:
            quantum = float(self.quantum_entry.get())
        except ValueError:
            quantum = 2.0

        self.live_scheduler = LiveScheduler(pids, algorithm=algo, quantum=quantum, custom_params=custom_params)
        
        if self.live_scheduler.start():
            self.btn_start_live.configure(state="disabled")
            self.btn_stop_live.configure(state="normal")
            self.live_canvas.delete("all")
            self.update_live_gantt()

    def stop_live_scheduler(self):
        if self.live_scheduler:
            self.live_scheduler.stop()
            
        self.btn_start_live.configure(state="normal")
        self.btn_stop_live.configure(state="disabled")
        messagebox.showinfo("Scheduler Stopped", "Scheduler stopped. All affected processes have been resumed.")

    def update_live_gantt(self):
        if not self.live_scheduler: return

        self.live_canvas.delete("all")

        with self.live_scheduler.lock:
            timeline = list(self.live_scheduler.timeline)

        scale = 35  
        max_x = 0
        y_top = 20
        y_bottom = 60

        pid_colors = {}
        color_idx = 0

        for pid, name, start, end in timeline:
            if pid not in pid_colors:
                pid_colors[pid] = self.live_colors[color_idx % len(self.live_colors)]
                color_idx += 1

            x1 = start * scale + 10
            x2 = end * scale + 10
            max_x = max(max_x, x2)

            color = pid_colors[pid]
            self.live_canvas.create_rectangle(x1, y_top, x2, y_bottom, fill=color, outline="#2b2b2b", width=2)

            if (x2 - x1) > 25:
                self.live_canvas.create_text((x1 + x2)/2, (y_top + y_bottom)/2, text=f"P:{pid}", fill="black", font=("Segoe UI", 9, "bold"))

        max_secs = int(max_x / scale) + 2
        for s in range(max_secs):
            tx = s * scale + 10
            self.live_canvas.create_line(tx, y_bottom, tx, y_bottom + 5, fill="#A1A1AA")
            self.live_canvas.create_text(tx, y_bottom + 15, text=f"{s}s", fill="#A1A1AA", font=("Segoe UI", 8))

        total_width = max(self.live_canvas.winfo_width(), max_x + 50)
        self.live_canvas.configure(scrollregion=(0, 0, total_width, 80))

        if self.live_scheduler.running:
            self.live_canvas.xview_moveto(1.0) 
            self.after(500, self.update_live_gantt) 
        else:
            self.btn_start_live.configure(state="normal")
            self.btn_stop_live.configure(state="disabled")
            
    # --- 4. ACTIVE OS GUARD METHODS ---
    def add_to_safe_zone(self):
        if not self.selected:
            messagebox.showwarning("Warning", "Select processes from the table first!")
            return
            
        new_names = {info['name'].lower() for info in self.selected.values()}
        self.safe_zone_list.extend(list(new_names))
        self.safe_zone_list = list(set(self.safe_zone_list)) 
        
        display_text = ", ".join(self.safe_zone_list)
        if len(display_text) > 50:
            display_text = display_text[:47] + "..."
            
        self.safe_zone_label.configure(text=f"Safe Apps: {display_text}")
        self.clear_selection()
        
    def on_guard_action_change(self, choice):
        if choice == "Lower Priority":
            self.guard_nice_frame.pack(side="left", padx=2)
        else:
            self.guard_nice_frame.pack_forget()

    def start_guard(self):
        try:
            interval = float(self.guard_interval.get())
            cpu_thresh = float(self.guard_cpu.get())
            target_nice = int(self.guard_nice.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for Interval, CPU limit, and Nice value.")
            return

        if os.name == 'nt' and target_nice > 5:
            target_nice = psutil.IDLE_PRIORITY_CLASS

        action = self.guard_action.get()
        
        if self.guard_backend.start(self.safe_zone_list, interval, cpu_thresh, action, target_nice):
            self.btn_start_guard.configure(state="disabled", text="🛡️ Guard is Active...")
            self.btn_stop_guard.configure(state="normal")
            
            self.guard_interval.configure(state="disabled")
            self.guard_cpu.configure(state="disabled")
            self.guard_action_menu.configure(state="disabled")
            self.guard_nice.configure(state="disabled")

    def stop_guard(self):
        self.guard_backend.stop()
        
        self.btn_start_guard.configure(state="normal", text="🟢 Start Active Guard")
        self.btn_stop_guard.configure(state="disabled")
        
        self.guard_interval.configure(state="normal")
        self.guard_cpu.configure(state="normal")
        self.guard_action_menu.configure(state="normal")
        self.guard_nice.configure(state="normal")
