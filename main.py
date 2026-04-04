import customtkinter as ctk
from ui_app import ProcessDashboard

def main():
    root = ctk.CTk()
    root.title("Hybrid OS Manager & Simulator")
    root.geometry("1100x750")
    
    app = ProcessDashboard(master=root)
    
    def on_closing():
        root.quit()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()