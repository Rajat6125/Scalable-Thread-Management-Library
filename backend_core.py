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
# 3. SCHEDULING ALGORITHMS (Simulations)
# ==========================================
def assign_process_ids(processes):
    return {name: f"P{i}" for i, (name, _) in enumerate(processes.items(), 1)}

def run_fcfs(processes):
    proc_list = [(name, data['at'], data['bt']) for name, data in processes.items()]
    proc_list.sort(key=lambda x: x[1])
    id_map = assign_process_ids(processes)
    
    timeline, results, current_time = [], {}, 0
    for name, at, bt in proc_list:
        if current_time < at: current_time = at
        start = current_time
        current_time += bt
        timeline.append((id_map[name], name, start, current_time))
        results[id_map[name]] = {'Process': name.split('(')[0], 'PID': name.split('(')[1].rstrip(')'), 
                                 'AT': at, 'BT': bt, 'CT': current_time, 'TAT': current_time - at, 'WT': (current_time - at) - bt}
    df = pd.DataFrame.from_dict(results, orient='index')
    return timeline, df, df['TAT'].mean(), df['WT'].mean()

def run_rr(processes, quantum):
    proc_list = sorted([(name, data['at'], data['bt']) for name, data in processes.items()], key=lambda x: x[1])
    id_map = assign_process_ids(processes)
    
    remaining_bt = {name: bt for name, at, bt in proc_list}
    completion_time = {}
    time, completed, n = 0, 0, len(processes)
    timeline, ready_queue = [], deque()
    index, last_process, start_time = 0, None, None
    
    while completed < n:
        while index < n and proc_list[index][1] <= time:
            ready_queue.append(proc_list[index][0])
            index += 1
        
        if not ready_queue:
            time += 1
            continue
            
        current = ready_queue.popleft()
        if current != last_process:
            if last_process is not None: timeline.append((id_map[last_process], last_process, start_time, time))
            last_process, start_time = current, time
            
        exec_time = min(quantum, remaining_bt[current])
        time += exec_time
        remaining_bt[current] -= exec_time
        
        while index < n and proc_list[index][1] <= time:
            ready_queue.append(proc_list[index][0])
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
        results[id_map[name]] = {'Process': name.split('(')[0], 'PID': name.split('(')[1].rstrip(')'), 
                                 'AT': at, 'BT': bt, 'CT': completion_time[name], 'TAT': completion_time[name] - at, 'WT': (completion_time[name] - at) - bt}
    df = pd.DataFrame.from_dict(results, orient='index')
    return timeline, df, df['TAT'].mean(), df['WT'].mean()

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