import os
import psutil
import threading
import time
import random
import queue
import pandas as pd
from collections import deque
import subprocess
import json
from sklearn.linear_model import LinearRegression
import numpy as np
# ==========================================
# 1. PROCESS MONITOR (Stable, Paginated + AI Prediction)
# ==========================================
class ProcessMonitor:
    REQUIRED_SAMPLES = 15
    def __init__(self):
        self.all_processes = {}
        self.process_list = []
        self.page_size = 20
        self.current_page = 0
        self.history = {}  # pid -> cpu history (From process_predictor)
                
    def refresh(self):
        processes = {}
        
        # 1. Get the PID of this exact Python script
        my_pid = os.getpid() 

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'nice', 'exe']):
            try:
                info = proc.info
                if info['name'] and info['pid']:
                    pid = info['pid']
                    
                    # 2. If the process is US, skip it immediately!
                    if pid == my_pid:
                        continue
                        
                    cpu = info['cpu_percent'] or 0

                    # --- Friend's History Logic ---
                    if pid not in self.history:
                        self.history[pid] = []

                    self.history[pid].append(cpu)

                    # Dynamically limit history size based on your required samples
                    max_history = max(15, self.REQUIRED_SAMPLES + 5)
                    if len(self.history[pid]) > max_history:
                        self.history[pid].pop(0)

                    processes[pid] = {
                        'name': info['name'],
                        'cpu': cpu,
                        'memory': info['memory_percent'] or 0,
                        'nice': info['nice'] or 0,
                        'exe': info['exe'] or "",
                        'pid': pid
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        self.all_processes = processes
        self.process_list = sorted(processes.items(), key=lambda x: x[1]['name'].lower())
        self.current_page = 0

    def get_page(self, page_num):
        start = page_num * self.page_size
        end = start + self.page_size
        return dict(self.process_list[start:end])

    def total_pages(self):
        if not self.process_list: return 0
        return (len(self.process_list) + self.page_size - 1) // self.page_size

    # --- Friend's Predictor Logic ---
    def predict_cpu_ai(self, pid):

        values = self.history.get(pid, [])

        
        if len(values) < self.REQUIRED_SAMPLES:
            steps_left = self.REQUIRED_SAMPLES - len(values)
            return f"Training... ({steps_left} left)"

        try:
            X = []
            y = []

            for i in range(len(values) - 3):
                X.append(values[i:i+3])
                y.append(values[i+3])

            X = np.array(X)
            y = np.array(y)

            model = LinearRegression()
            model.fit(X, y)

            last_input = np.array(values[-3:]).reshape(1, -1)
            prediction = model.predict(last_input)[0]

            if prediction > 60:
                return f"High ({prediction:.1f}%)"
            elif prediction > 25:
                return f"Med ({prediction:.1f}%)"
            else:
                return f"Low ({prediction:.1f}%)"

        except Exception as e:
            return "Error"
            
    def reset_ai_training(self):
        """Clears the historical data, forcing the AI to retrain."""
        self.history = {}
        
# ==========================================
# 2. OS CONTROLLER (Real Actions)
# ==========================================
class ProcessController:
    @staticmethod
    def execute_action(pid, action, **kwargs):
        try:
            p = psutil.Process(pid)
            if action == "kill":
                p.terminate()
                return True, f"PID {pid} terminated."
            elif action == "suspend":
                p.suspend()
                return True, f"PID {pid} suspended."
            elif action == "resume":
                p.resume()
                return True, f"PID {pid} resumed."
            elif action == "nice":
                p.nice(kwargs.get('nice_value', 0))
                return True, f"PID {pid} nice set to {kwargs.get('nice_value')}."
            return False, "Unknown action."
        except Exception as e:
            return False, f"PID {pid} Error: {str(e)}"

    @staticmethod
    def set_affinity(pid, cores):
        try:
            p = psutil.Process(pid)
            p.cpu_affinity(cores)
            return True, f"PID {pid} pinned to cores {cores}."
        except Exception as e:
            return False, f"Affinity Error: {str(e)}"

# ==========================================
# 3. LIVE OS SCHEDULER (Infinite Looping & Dynamic Algos)
# ==========================================
class LiveScheduler:
    def __init__(self, pids, algorithm="Round Robin", quantum=2.0, custom_params=None):
        self.base_pids = list(pids) 
        self.pids = deque(self.base_pids)
        self.algorithm = algorithm
        self.quantum = quantum
        self.running = False
        self.timeline = []  
        self.start_time = 0
        self.lock = threading.Lock()
        self.thread = None

        self.proc_info = {}
        custom = custom_params or {}
        
        for pid in self.base_pids:
            try:
                p = psutil.Process(pid)
                burst = custom.get(pid, {}).get('burst', random.randint(5, 15))
                priority = custom.get(pid, {}).get('priority', 1)
                
                self.proc_info[pid] = {
                    'name': p.name(),
                    'priority': priority,
                    'burst': burst,
                    'remaining': burst
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                if pid in self.pids:
                    self.pids.remove(pid)

    def start(self):
        if not self.pids: return False
        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=self.quantum + 1)
            
        for pid in self.base_pids:
            if psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "resume")

    def _scheduler_loop(self):
        for pid in list(self.pids):
            if psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

        while self.running:
            if not self.pids:
                self.pids = deque([p for p in self.base_pids if psutil.pid_exists(p)])
                if not self.pids:
                    time.sleep(1) 
                    continue
                for pid in self.pids:
                    self.proc_info[pid]['remaining'] = self.proc_info[pid]['burst']

            if self.algorithm == "SJF":
                self.pids = deque(sorted(self.pids, key=lambda p: self.proc_info[p]['remaining']))
            elif self.algorithm == "Priority":
                self.pids = deque(sorted(self.pids, key=lambda p: self.proc_info[p]['priority']))
                
            pid = self.pids.popleft()

            if not psutil.pid_exists(pid):
                continue

            requeue = False
            if self.algorithm == "Round Robin":
                run_time = self.quantum
                requeue = True
            else:
                run_time = self.proc_info[pid]['remaining']

            name = self.proc_info[pid]['name']

            ProcessController.execute_action(pid, "resume")
            start_slice = time.time() - self.start_time

            elapsed = 0
            while elapsed < run_time and self.running:
                time.sleep(0.1)
                elapsed += 0.1

            end_slice = time.time() - self.start_time

            if self.running and psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

            with self.lock:
                self.timeline.append((pid, name, start_slice, end_slice))

            if self.algorithm != "Round Robin":
                self.proc_info[pid]['remaining'] -= elapsed
                if self.proc_info[pid]['remaining'] > 0.1:
                    requeue = True

            if self.running and psutil.pid_exists(pid) and requeue:
                self.pids.append(pid)
                
        self.running = False

# ==========================================
# 4. CONTEXT SWITCHER (Profiles & Reversions)
# ==========================================
class ContextManager:
    PROFILE_FILE = "profiles.json"
    
    _active_state = {
        "suspended_pids": [],
        "changed_priorities": {}  
    }
    _is_active = False

    @classmethod
    def load_profiles(cls):
        profiles = {}
        if os.path.exists(cls.PROFILE_FILE):
            try:
                with open(cls.PROFILE_FILE, "r") as f:
                    profiles = json.load(f)
            except json.JSONDecodeError:
                pass
        
        default_profiles = {
            "Gaming Mode": {"suspend": [], "terminate": [], "start": [], "priority": {}},
            "Focus Mode": {"suspend": [], "terminate": [], "start": [], "priority": {}},
            "Relax Mode": {"suspend": [], "terminate": [], "start": [], "priority": {}}
        }
        
        if not profiles:
            profiles = default_profiles
            cls.save_profiles(profiles)
            
        # Migrate old configs if necessary
        for p_name, p_data in profiles.items():
            if "priority" not in p_data: p_data["priority"] = {}
            if "terminate" not in p_data: p_data["terminate"] = []
            if "start" not in p_data: p_data["start"] = []
                
        return profiles

    @classmethod
    def save_profiles(cls, profiles_data):
        with open(cls.PROFILE_FILE, "w") as f:
            json.dump(profiles_data, f, indent=4)

    @classmethod
    def apply_profile(cls, profile_name, auto_throttle=False):
        if cls._is_active:
            cls.revert_context()

        profiles = cls.load_profiles()
        if profile_name not in profiles:
            return ["Error: Profile not found."]

        profile = profiles[profile_name]
        to_suspend = profile.get("suspend", [])
        to_terminate = profile.get("terminate", [])
        to_start = profile.get("start", [])
        to_prioritize = profile.get("priority", {}) 

        logs = []
        cls._active_state["suspended_pids"].clear()
        cls._active_state["changed_priorities"].clear()

        my_pid = os.getpid() 

        # 1. Modify active background processes
        for proc in psutil.process_iter(['pid', 'name', 'nice']):
            try:
                p_name = proc.info['name'].lower()
                pid = proc.info['pid']
                nice_val = proc.info['nice']

                if pid == my_pid or pid == 0:
                    continue 

                if any(target.lower() == p_name for target in to_terminate):
                    proc.terminate()
                    logs.append(f"💀 Terminated: {proc.info['name']} (PID: {pid})")

                elif any(target.lower() == p_name for target in to_suspend):
                    proc.suspend()
                    cls._active_state["suspended_pids"].append(pid)
                    logs.append(f"⏸ Suspended: {proc.info['name']} (PID: {pid})")

                elif p_name in to_prioritize:
                    target_nice = to_prioritize[p_name]
                    if nice_val is not None:
                        cls._active_state["changed_priorities"][pid] = nice_val
                        proc.nice(target_nice)
                        p_label = "High" if (target_nice < 0 or target_nice > 30) else "Low"
                        logs.append(f"⚙️ Priority Shifted: {proc.info['name']} -> {p_label}")
                    
                elif auto_throttle and nice_val is not None:
                    if os.name == 'nt':
                        is_normal_or_lower = nice_val in [psutil.NORMAL_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS]
                        target_low_priority = psutil.IDLE_PRIORITY_CLASS 
                    else:
                        is_normal_or_lower = nice_val >= 0
                        target_low_priority = 15 

                    if is_normal_or_lower:
                        cls._active_state["changed_priorities"][pid] = nice_val
                        proc.nice(target_low_priority)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 2. Launch requested applications natively
        for exe_path in to_start:
            if exe_path and os.path.exists(exe_path):
                try:
                    subprocess.Popen([exe_path])
                    logs.append(f"🚀 Launched: {os.path.basename(exe_path)}")
                except Exception as e:
                    logs.append(f"⚠️ Failed to launch {os.path.basename(exe_path)}: {e}")

        if auto_throttle:
            logs.insert(0, f"📉 MASS THROTTLE: Reduced CPU priority of {len(cls._active_state['changed_priorities'])} background apps!")

        if not logs:
            logs.append("Profile applied, but no actions were taken.")
            
        cls._is_active = True
        return logs

    @classmethod
    def revert_context(cls):
        if not cls._is_active:
            return ["⚠️ No active mode to revert."]

        logs = []
        resumed_count = 0
        restored_count = 0

        for pid in cls._active_state["suspended_pids"]:
            try:
                psutil.Process(pid).resume()
                resumed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        for pid, orig_nice in cls._active_state["changed_priorities"].items():
            try:
                psutil.Process(pid).nice(orig_nice)
                restored_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if resumed_count > 0:
            logs.append(f"▶ Woke up {resumed_count} suspended apps.")
        if restored_count > 0:
            logs.append(f"⚙️ Restored original CPU priority for {restored_count} background apps.")

        cls._active_state["suspended_pids"].clear()
        cls._active_state["changed_priorities"].clear()
        cls._is_active = False

        if not logs:
            logs.append("Reverted, but all affected processes had already closed naturally.")

        return logs
        
# ==========================================
# 5. ACTIVE OS GUARD (Automated Throttler)
# ==========================================
class ActiveGuard:
    def __init__(self):
        self.running = False
        self.thread = None
        self.safe_names = set()
        self.interval = 2.0
        self.cpu_threshold = 10.0
        self.action = "Priority"
        self.target_nice = 15 
        self.my_pid = os.getpid() # Store our manager's exact PID

    def start(self, safe_apps, interval, cpu_threshold, action, target_nice):
        if self.running:
            return False
            
        self.safe_names = {name.lower() for name in safe_apps}
        
        # REMOVED 'python' from here so we can actually throttle dummy test scripts!
        # Notice we are using partial base names now (e.g., 'xwayland' instead of 'xwayland.bin')
        critical_sys = ['systemd', 'svchost', 'explorer', 'csrss', 
                        'smss', 'wininit', 'services', 'lsass', 'xwayland', 'xorg']
        self.safe_names.update(critical_sys)
        
        self.interval = interval
        self.cpu_threshold = cpu_threshold
        self.action = action
        self.target_nice = target_nice
        
        self.running = True
        self.thread = threading.Thread(target=self._guard_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _guard_loop(self):
        for proc in psutil.process_iter(['cpu_percent']): pass
        
        while self.running:
            time.sleep(self.interval)
            
            # Dynamically grab any background threads/children our manager spawned (like the Flask API)
            try:
                my_children = [p.pid for p in psutil.Process(self.my_pid).children(recursive=True)]
            except:
                my_children = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                if not self.running: break
                try:
                    name = proc.info['name'].lower()
                    pid = proc.info['pid']
                    cpu_usage = proc.info['cpu_percent'] or 0.0
                    
                    # 1. BULLETPROOF PROTECTION: Skip OS Roots, our App, and our Child Threads
                    if pid <= 100 or pid == self.my_pid or pid in my_children:
                        continue
                        
                    # 2. Check if the app name contains any of our safe keywords (Partial Matching)
                    if any(safe in name for safe in self.safe_names):
                        continue
                        
                    # 3. Execute the Guard Action on the greedy process!
                    if cpu_usage >= self.cpu_threshold:
                        if self.action == "Suspend":
                            proc.suspend()
                            print(f"[GUARD] Suspended greedy app: {name} (PID: {pid}) - {cpu_usage}%")
                        elif self.action == "Lower Priority":
                            proc.nice(self.target_nice)
                            print(f"[GUARD] Throttled greedy app: {name} (PID: {pid}) - {cpu_usage}%")
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    pass
