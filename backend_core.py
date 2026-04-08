import os
import psutil
import threading
import time
import random
import queue
import pandas as pd
from collections import deque
import subprocess

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
        """Fetches a static snapshot of processes so they don't jump around."""
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
        # Sort alphabetically by name to keep it stable
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
        self.timeline = []  # Stores tuples: (pid, name, start_time_offset, end_time_offset)
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
        # Ensure all processes are safely resumed when we stop the scheduler!
        for pid in list(self.pids):
            ProcessController.execute_action(pid, "resume")

    def _scheduler_loop(self):
        # Step 1: Initially suspend all selected processes
        for pid in list(self.pids):
            if psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

        while self.running and self.pids:
            pid = self.pids.popleft()

            # If process was killed externally or died naturally, skip it
            if not psutil.pid_exists(pid):
                continue

            try:
                p = psutil.Process(pid)
                name = p.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            # Step 2: Resume the process to give it CPU time
            ProcessController.execute_action(pid, "resume")
            start_slice = time.time() - self.start_time

            # Wait for the time quantum (broken into tiny chunks so 'stop' is highly responsive)
            elapsed = 0
            while elapsed < self.quantum and self.running:
                time.sleep(0.1)
                elapsed += 0.1

            end_slice = time.time() - self.start_time

            # Step 3: Suspend the process again
            if self.running and psutil.pid_exists(pid):
                ProcessController.execute_action(pid, "suspend")

            with self.lock:
                self.timeline.append((pid, name, start_slice, end_slice))

            # Step 4: If process is still alive, push back to queue for next round
            if self.running and psutil.pid_exists(pid):
                self.pids.append(pid)
                
        self.running = False # Clean exit if queue empties

# ==========================================
# 4. SYNC DEMO
# ==========================================
class SynchronizationManager:
    def __init__(self):
        self.shared_resource = 0
        self.mutex = threading.Lock()
        self.semaphore = threading.Semaphore(2)
        self.logs = []
        self.active_threads = []

    def log(self, msg):
        self.logs.append(msg)
        if len(self.logs) > 10: self.logs.pop(0)

    def worker_task(self, thread_id):
        self.log(f"T{thread_id} waiting for Semaphore...")
        with self.semaphore:
            self.log(f"T{thread_id} working (Simulated I/O)...")
            time.sleep(random.uniform(0.5, 1.5))
            with self.mutex:
                local_copy = self.shared_resource
                local_copy += 1
                time.sleep(0.1)
                self.shared_resource = local_copy
                self.log(f"T{thread_id} updated resource to {self.shared_resource}")

    def start_demo(self, num_threads=5):
        self.shared_resource = 0
        self.logs.clear()
        for i in range(num_threads):
            t = threading.Thread(target=self.worker_task, args=(i,))
            self.active_threads.append(t)
            t.start()
