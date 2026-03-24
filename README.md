# CPU Scheduler with Real-Time Process Monitor
## Project Concept Overview
*What Problem Does This Solve?*
When learning operating systems, students often struggle to connect theoretical scheduling algorithms with real-world process management. They understand the math behind FCFS, SJF, and Round Robin, but have no idea how these concepts apply to actual running programs like Chrome, Python, or system processes.

This project bridges that gap by:
Monitoring real processes running on your computer
Simulating scheduling algorithms on those actual processes
Visualizing execution timelines to see how different algorithms would behave

*The Core Idea*
Think of this as a "what-if" simulator. You select real processes running on your system (like your browser, code editor, etc.), and the application shows you:

How a First-Come-First-Serve scheduler would execute them
How Shortest Job First would reorder them for better efficiency
How Round Robin would share CPU time fairly among them
The key insight: Real processes become the data for theoretical algorithms, making abstract concepts tangible.
