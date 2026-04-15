import os
import time
import psutil 

def start():
    pid = os.getpid()
    
    # Force this process to only use CPU Core 0 to guarantee a bottleneck
    psutil.Process(pid).cpu_affinity([0])
    
    print(pid)
    t = 0
    while True:
        print("Time - ",t)
        t += 1
        
        time.sleep(1)
    

if __name__ == '__main__':

    start()
