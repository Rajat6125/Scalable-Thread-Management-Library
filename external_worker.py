import os
import sys
import time
import requests
import psutil
import multiprocessing

def heavy_math_worker(name, boost_priority=False):
    pid = os.getpid()
    
    # Force this process to only use CPU Core 0 to guarantee a bottleneck
    psutil.Process(pid).cpu_affinity([0])
    
    if boost_priority:
        print(f"[{name}] (PID: {pid}) Calling Manager API to boost priority to High (-10)...")
        try:
            # THIS IS THE EXTERNAL APP TALKING TO YOUR MANAGER
            resp = requests.post('http://127.0.0.1:5000/api/set_priority', 
                                 json={'pid': pid, 'nice_value': -10})
            if resp.json().get('success'):
                print(f"[{name}] ✅ API confirmed priority boost!")
        except Exception as e:
            print(f"[{name}] API call failed. Is the manager running?")
    else:
        print(f"[{name}] (PID: {pid}) Running at Normal priority (0).")

    print(f"[{name}] Starting heavy computation...")
    start_time = time.time()
    
    # Do completely useless, heavy math to max out the CPU
    count = 0
    while count < 300_000_000:
        _ = 12345 ** 2
        count += 1
        
    duration = time.time() - start_time
    print(f"🏁 [{name}] FINISHED in {duration:.2f} seconds!")

if __name__ == '__main__':
    print("--- STARTING THE BOTTLENECK RACE ---")
    
    # Process A will run normally
    p1 = multiprocessing.Process(target=heavy_math_worker, args=("Process A (Normal)", False))
    
    # Process B will call your API to get VIP treatment
    p2 = multiprocessing.Process(target=heavy_math_worker, args=("Process B (VIP)", True))

    p1.start()
    p2.start()

    p1.join()
    p2.join()
