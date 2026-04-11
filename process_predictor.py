from sklearn.linear_model import LinearRegression
import psutil
import numpy as np

class ProcessMonitor:
    def __init__(self):
        self.all_processes = {}
        self.process_list = []
        self.page_size = 20
        self.current_page = 0
        self.history = {}  # pid → cpu history

    def refresh(self):
        processes = {}

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'nice']):
            try:
                info = proc.info
                if info['name'] and info['pid']:

                    pid = info['pid']
                    cpu = info['cpu_percent'] or 0

                    if pid not in self.history:
                        self.history[pid] = []

                    self.history[pid].append(cpu)

                    if len(self.history[pid]) > 15:
                        self.history[pid].pop(0)

                    processes[pid] = {
                        'name': info['name'],
                        'cpu': cpu,
                        'memory': info['memory_percent'] or 0,
                        'nice': info['nice'] or 0,
                        'pid': pid
                    }

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        self.all_processes = processes
        self.process_list = sorted(processes.items(), key=lambda x: x[1]['name'].lower())
        self.current_page = 0

    def predict_cpu_ai(self, pid):
        values = self.history.get(pid, [])

        if len(values) < 6:
            return "Training..."

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
                return f"High  ({prediction:.1f})"
            elif prediction > 25:
                return f"Medium  ({prediction:.1f})"
            else:
                return f"Low ({prediction:.1f})"

        except Exception as e:
            return "Error"