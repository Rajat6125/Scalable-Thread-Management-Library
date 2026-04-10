import os
import psutil
import threading
import time
import random
import queue
import pandas as pd
from collections import deque
import subprocess
import json # <-- NEW IMPORT

# ==========================================
# 1. PROCESS MONITOR (Stable, Paginated)
# ==========================================
class ProcessMonitor:
    def __init__(self):
        self.all_processes = {}
        self.process_list = []
        self.page_size = 20
        self.current_page = 0
        
    def refresh(self):
        processes = {}
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'nice']):
            try:
                info = proc.info
                if info['name'] and info['pid']:
                    processes[info['pid']] = {
                        'name': info['name'],
                        'cpu': info['cpu_percent'] or 0,
                        'memory': info['memory_percent'] or 0,
                        'nice': info['nice'] or 0,
                        'pid': info['pid']
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

# ==========================================
# 3. LIVE OS SCHEDULER (Real Process Round-Robin)
# ==========================================
class LiveScheduler:
    def __init__(self, pids, quantum=2.0):
        self.pids = deque(pids)
        self.quantum = quantum
        self.running = False
        self.timeline = []  
        self.start_time = 0
        self.lock = threading.Lock()
        self.thread = None

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
        for pid in list(self.pids):
            ProcessController.execute_action(pid, "resume")

    def _scheduler_loop(self):
        for pid in list(self.pids):
            if psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

        while self.running and self.pids:
            pid = self.pids.popleft()

            if not psutil.pid_exists(pid):
                continue

            try:
                p = psutil.Process(pid)
                name = p.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            ProcessController.execute_action(pid, "resume")
            start_slice = time.time() - self.start_time

            elapsed = 0
            while elapsed < self.quantum and self.running:
                time.sleep(0.1)
                elapsed += 0.1

            end_slice = time.time() - self.start_time

            if self.running and psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

            with self.lock:
                self.timeline.append((pid, name, start_slice, end_slice))

            if self.running and psutil.pid_exists(pid):
                self.pids.append(pid)
                
        self.running = False 

# ==========================================
# 4. CONTEXT SWITCHER (Profiles & Reversions)
# ==========================================
class ContextManager:
    PROFILE_FILE = "profiles.json"
    
    # We use this to remember the OS state before we wrecked it for gaming
    _active_state = {
        "suspended_pids": [],
        "changed_priorities": {}  # Format: {pid: original_nice_value}
    }
    _is_active = False

    @classmethod
    def load_profiles(cls):
        if os.path.exists(cls.PROFILE_FILE):
            try:
                with open(cls.PROFILE_FILE, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        default_profiles = {
            "Gaming Mode": {"suspend": [], "resume": []},
            "Focus Mode": {"suspend": [], "resume": []},
            "Relax Mode": {"suspend": [], "resume": []}
        }
        cls.save_profiles(default_profiles)
        return default_profiles

    @classmethod
    def save_profiles(cls, profiles_data):
        with open(cls.PROFILE_FILE, "w") as f:
            json.dump(profiles_data, f, indent=4)

    @classmethod
    def apply_profile(cls, profile_name, auto_throttle=False):
        # If a mode is already running, revert it first so we don't permanently lose our old settings!
        if cls._is_active:
            cls.revert_context()

        profiles = cls.load_profiles()
        if profile_name not in profiles:
            return ["Error: Profile not found."]

        profile = profiles[profile_name]
        to_suspend = profile.get("suspend", [])
        to_resume = profile.get("resume", [])

        logs = []
        cls._active_state["suspended_pids"].clear()
        cls._active_state["changed_priorities"].clear()

        my_pid = os.getpid() # Don't accidentally throttle our own app

        for proc in psutil.process_iter(['pid', 'name', 'nice']):
            try:
                p_name = proc.info['name'].lower()
                pid = proc.info['pid']
                nice_val = proc.info['nice']

                if pid == my_pid or pid == 0:
                    continue 

                # 1. Check for Explicit Suspend
                if any(target.lower() == p_name for target in to_suspend):
                    proc.suspend()
                    cls._active_state["suspended_pids"].append(pid)
                    logs.append(f"⏸ Suspended: {proc.info['name']} (PID: {pid})")
                
                # 2. Check for Explicit Resume
                elif any(target.lower() == p_name for target in to_resume):
                    proc.resume()
                    logs.append(f"▶ Resumed: {proc.info['name']} (PID: {pid})")
                    
                # 3. MASS THROTTLE: If it wasn't suspended/resumed, and auto_throttle is ON
                elif auto_throttle and nice_val is not None:
                    # Windows uses specific constants for normal/low priority
                    if os.name == 'nt':
                        is_normal_or_lower = nice_val in [psutil.NORMAL_PRIORITY_CLASS, psutil.BELOW_NORMAL_PRIORITY_CLASS]
                        target_low_priority = psutil.IDLE_PRIORITY_CLASS 
                    # Mac/Linux uses 0 (normal) to 20 (lowest)
                    else:
                        is_normal_or_lower = nice_val >= 0
                        target_low_priority = 15 

                    # If it's a normal task, drop its priority to the absolute floor
                    if is_normal_or_lower:
                        cls._active_state["changed_priorities"][pid] = nice_val
                        proc.nice(target_low_priority)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # AccessDenied naturally protects us from throttling critical Windows/System processes!
                continue
                
        if auto_throttle:
            logs.insert(0, f"📉 MASS THROTTLE: Reduced CPU priority of {len(cls._active_state['changed_priorities'])} background apps!")

        if not logs:
            logs.append("No actions taken. Ensure you have apps added to the profile.")
            
        cls._is_active = True
        return logs

    @classmethod
    def revert_context(cls):
        if not cls._is_active:
            return ["⚠️ No active mode to revert."]

        logs = []
        resumed_count = 0
        restored_count = 0

        # 1. Wake up the suspended apps
        for pid in cls._active_state["suspended_pids"]:
            try:
                psutil.Process(pid).resume()
                resumed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 2. Restore the original priorities of the throttled apps
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
