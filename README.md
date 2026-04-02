# Hybrid OS Manager & Scheduler Simulator
A powerful Operating System simulation and management tool that combines real process control, CPU scheduling visualization, thread synchronization, and API-based external interaction — all in one interactive dashboard.

## Features
### 1. Real-Time Process Monitoring
View all active system processes
CPU & Memory usage tracking
Stable paginated process table (no flickering)
Search and filter by PID or process name

### 2. OS-Level Process Control
Perform real system operations:
❌ Kill processes
⏸ Suspend processes
▶ Resume processes
⚙️ Change process priority (Nice values)

### 3. Live CPU Visualization
Real-time multi-core CPU usage graph
Built using matplotlib
Updates dynamically every second

### 4. Round Robin Scheduler (Live Simulation)
Select processes and apply Round Robin Scheduling
Configurable time quantum (default: 2 seconds)

### 5. Synchronization Demo (Multithreading)
Demonstrates core OS concepts:
🔐 Mutex (Lock)
🚦 Semaphore
🧵 Multiple threads accessing shared resource

✔ Prevents race conditions
✔ Controls concurrent access

### 6. External API Integration
Built-in Flask API server
External programs can interact with OS manager
Uses real OS processes (not dummy simulation)
Displays execution using a live Gantt chart
