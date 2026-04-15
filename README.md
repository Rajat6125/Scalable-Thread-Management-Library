# Hybrid OS Manager & Simulator

A comprehensive, Python-based task manager and Operating System concept simulator designed specifically for Linux (Ubuntu).

This project goes beyond a standard task manager by integrating AI to predict CPU usage, a local API for inter-process communication, an automated resource guard, and a live OS scheduler simulator that actually suspends and resumes real processes.

## 🚀 What Can This App Do? (Core Modules)
The application is divided into four main operational tabs, each serving a distinct purpose for both practical system management and educational demonstration.

### 1. Real OS Controls
This is your standard, but highly upgraded, task manager. Select one or multiple processes from the live table to perform batch operations:

Standard Controls: Instantly Kill, Suspend, or Resume selected processes.

CPU Priority (Nice): Adjust how much CPU time the Linux kernel gives to an app by changing its nice value (e.g., boosting a heavy task to High Priority).

Core Affinity: Force specific applications to only run on designated CPU cores (e.g., pinning a game to Cores 0-3 to prevent background apps from interfering).

Resource Analytics: View dynamic bar charts comparing the CPU and Memory usage of your selected apps versus the rest of the system.

### 2. Live OS Scheduler (Simulator)
An interactive, educational tool that demonstrates how Operating Systems schedule tasks, but uses real system processes instead of theoretical numbers.

Choose an algorithm: Round Robin (with adjustable time quantums), FCFS, SJF, or Priority.

Select processes manually or use the "Auto (Hungry Apps)" mode to grab background tasks.

Once started, the app actively suspends and resumes the selected processes according to the algorithm's rules, visualizing the execution timeline on a live Gantt Chart.

### 3. Context Switcher (Profiles)
Create custom "Modes" (like Gaming Mode, Focus Mode, or Relax Mode) to instantly optimize your system for specific workflows. The app stores these configurations in a persistent profiles.json file.

Build a Profile: Tell the app exactly what to do when a mode starts:
```
🚀 Start: Automatically launch specific applications (e.g., open Steam and Discord).
💀 Terminate: Kill distracting or heavy apps.
⏸️ Suspend: Temporarily freeze background apps to free up resources without losing their state.
⚙️ Set Priority: Shift specific background tasks to Low Priority.
Aggressive Auto-Throttle: A toggleable feature that automatically drops the priority of all non-essential background apps when the mode is engaged.
Revert: Click "Stop & Revert" to instantly wake up suspended apps and restore normal priorities.
```
### 4. Active OS Guard (OS Shield)
An automated background watchdog that protects your system from suddenly greedy applications.

How it works: Set a CPU threshold (e.g., 15%) and an interval (e.g., check every 2 seconds).

Action: Tell the guard to either automatically Lower Priority or completely Suspend any app that crosses the threshold.

Safe Zone: Add essential apps (like your browser or system services) to a whitelist so they are never throttled, no matter how much CPU they use.

## 📂 Project Structure

```text
process_manager/
├── main-code/                 # Core application files
│   ├── main.py                # App entry point & UI initialization
│   ├── ui_app.py              # CustomTkinter frontend & interactive dashboards
│   ├── backend_core.py        # OS logic, psutil wrappers, AI models, and schedulers
│   └── api_server.py          # Flask API for external process communication
├── helper-processes/          # Demo scripts for classroom/presentation showcases
│   ├── dummy_process.py       # Infinite loop tied to CPU Core 0
│   ├── heavy_process.py       # Computationally expensive math loop
│   └── external_worker.py     # Demo of inter-process API priority boosting
├── App-shortcuts.desktop/     # Linux .desktop entries for quick launching
├── myvenv/                    # Python virtual environment (ignored in git)
├── profiles.json              # Auto-generated saved states for Context Switcher
├── requirements.txt           # Python package dependencies
└── setup.html                 # Terminal logs of the initial environment setup
```
🛠️ Prerequisites
This application is highly coupled with Linux concepts (like nice values). It is designed and tested on Ubuntu.
- Python 3.12+
- python3-tk (For the Matplotlib backend and UI elements)
- python3-venv (For the virtual environment)

### ⚙️ Installation & Setup
Follow these exact steps to replicate the environment and run the application on an Ubuntu system:


> [!Note]
> You actually don't need to setup anything else except for the ones provided in setup.html , make sure you type the code written in yellow in the terminal and name the directory as process_manager to make it work , the virtual environment should also be named as myvenv and the folder should be saved on Home in ubuntu . 

Update system packages:

```Bash
sudo apt update
Install required system dependencies:
```
```Bash
sudo apt install python3-tk python3-venv
Create and activate a virtual environment:
```
```Bash
python3 -m venv myvenv
source myvenv/bin/activate
Install Python dependencies:
```
```Bash
pip install -r requirements.txt
```
💻 Usage
To run the application, navigate to the root directory, activate your virtual environment, and launch main.py.

Note: Because this app modifies CPU affinity, changes nice values, and suspends processes, running it with sudo is recommended for full functionality.

Bash
```source myvenv/bin/activate
sudo myvenv/bin/python main-code/main.py
```
## (Alternatively, use the .desktop shortcuts provided in the App-shortcuts.desktop folder for quick access)
 

🧪 Helper Processes (Classroom Demos)
The helper-processes folder contains scripts specifically designed to bottleneck the system so you can demonstrate the manager's capabilities:

dummy_process.py: Hardcodes itself to CPU Core 0 and runs a continuous loop. Great for demonstrating the Set Core Affinity feature and the Active OS Guard.

heavy_process.py: Maxes out CPU usage with heavy calculations. Use this to demonstrate the Live OS Scheduler (e.g., watch it pause and resume during Round Robin).

external_worker.py: Spawns two mathematical workers. One runs normally, while the other communicates with the manager's Flask API (http://127.0.0.1:5000/api/set_priority) to request VIP priority. Great for demonstrating local inter-process communication.



> [!CAUTION]
> **This tool allows you to actively suspend, terminate, and throttle system-level processes. Use caution when modifying critical Linux background services, as terminating the wrong process may require a system reboot. Safe-guards are built into the code, but admin privileges (sudo) grant complete control.

