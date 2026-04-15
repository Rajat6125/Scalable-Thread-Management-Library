import customtkinter as ctk
import threading
from ui_app import ProcessDashboard
from api_server import start_api_server

def main():
    # Start the API server in a background thread
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    root = ctk.CTk()
    root.title("Hybrid OS Manager & Simulator")
    # ... rest of your main.py code ...
    root.geometry("1100x750")
    
    app = ProcessDashboard(master=root)
    
    def on_closing():
        root.quit()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
