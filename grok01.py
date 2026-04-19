import tkinter as tk
from tkinter import ttk
import requests
import math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates

API_BASE = "https://api-maree.fr"
API_KEY = "0000000000000000000000000000000"

class TideApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Marées - Hauteurs d'eau")
        self.root.configure(bg="#0f172a")
        self.current_date = datetime.now().date()
        self.data = []
        self.events = []
        self.canvas_widget = None
        self.status = None
        self.create_ui()
        self.load_sites()

    def create_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1e293b")
        header.pack(fill="x")
        tk.Label(header, text="🌊 Marées", font=("Segoe UI", 18, "bold"), fg="#38bdf8", bg="#1e293b").pack(side="left", padx=20, pady=12)

        ctrl = tk.Frame(header, bg="#1e293b")
        ctrl.pack(side="right", padx=20)

        self.port_combo = ttk.Combobox(ctrl, width=40, state="readonly")
        self.port_combo.pack(side="left", padx=5)
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        nav = tk.Frame(ctrl, bg="#1e293b")
        nav.pack(side="left", padx=10)
        tk.Button(nav, text="◀", width=3, bg="#334155", fg="white", command=self.prev_day).pack(side="left")
        self.date_label = tk.Label(nav, text=self.current_date.strftime("%Y-%m-%d"), fg="#e2e8f0", bg="#1e293b", width=12)
        self.date_label.pack(side="left", padx=8)
        tk.Button(nav, text="▶", width=3, bg="#334155", fg="white", command=self.next_day).pack(side="left")
        tk.Button(nav, text="Aujourd'hui", bg="#0284c7", fg="white", command=self.today).pack(side="left", padx=5)

        self.main = tk.Frame(self.root, bg="#0f172a")
        self.main.pack(fill="both", expand=True, padx=20, pady=10)

        # Status label (on le recrée à chaque fois)
        self.show_status("Chargement des ports...")

    def show_status(self, text, color="#94a3b8"):
        if self.status:
            self.status.destroy()
        self.status = tk.Label(self.main, text=text, fg=color, bg="#0f172a", font=("", 12))
        self.status.pack(expand=True)

    def load_sites(self):
        try:
            r = requests.get(f"{API_BASE}/sites?key={API_KEY}")
            sites = sorted(r.json().get("sites", []), key=lambda x: x["name"])
            self.port_combo["values"] = [f"{s['site_id']} - {s['name']}" for s in sites]
            if self.port_combo["values"]:
                self.port_combo.set(self.port_combo["values"][0])
                self.load_data()
        except:
            self.show_status("Erreur chargement ports", "#f87171")

    def load_data(self):
        self.show_status("Chargement des données...")
        self.root.after(100, self.fetch_and_render)

    def fetch_and_render(self):
        site_id = self.port_combo.get().split(" - ")[0]
        date_str = self.current_date.isoformat()

        try:
            url = f"{API_BASE}/water-levels?site={site_id}&from={date_str}T00:00&to={date_str}T23:59&step=10&tz=Europe/Paris&key={API_KEY}"
            self.data = requests.get(url).json().get("data", [])
            self.events = self.find_tide_events()
            self.render_all()
        except Exception as e:
            self.show_status(f"Erreur: {e}", "#f87171")

    def find_tide_events(self):
        events = []
        for i in range(1, len(self.data)-1):
            p = self.data[i-1]["height"]
            c = self.data[i]["height"]
            n = self.data[i+1]["height"]
            if c >= max(p, n):
                events.append({"type":"PM", "time":self.data[i]["time"], "height":c})
            elif c <= min(p, n):
                events.append({"type":"BM", "time":self.data[i]["time"], "height":c})
        return events[:4]

    def render_all(self):
        # Nettoyage complet
        for widget in self.main.winfo_children():
            widget.destroy()

        if not self.data:
            self.show_status("Aucune donnée pour cette date", "#f87171")
            return

        top = tk.Frame(self.main, bg="#0f172a")
        top.pack(fill="x", pady=5)

        # Calendrier placeholder
        cal = tk.Frame(top, bg="#1e293b", relief="solid", bd=1)
        cal.pack(side="left", padx=8, fill="y")
        tk.Label(cal, text=self.current_date.strftime("%B %Y"), bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 10, "bold")).pack(pady=15)

        # Horloge
        clock_f = tk.Frame(top, bg="#1e293b", relief="solid", bd=1)
        clock_f.pack(side="left", padx=8, fill="y")
        tk.Label(clock_f, text="Horloge de marée", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=8)
        self.clock_canvas = tk.Canvas(clock_f, width=270, height=310, bg="#1e293b", highlightthickness=0)
        self.clock_canvas.pack(pady=5)
        self.draw_tide_clock()

        # Événements
        ev_f = tk.Frame(top, bg="#1e293b", relief="solid", bd=1, width=320)
        ev_f.pack(side="left", padx=8, fill="y")
        ev_f.pack_propagate(False)
        tk.Label(ev_f, text="Marées du jour", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=8)
        for ev in self.events:
            color = "#22d3ee" if ev["type"] == "PM" else "#f97316"
            f = tk.Frame(ev_f, bg="#0f172a", pady=8, padx=12)
            f.pack(fill="x", padx=10, pady=3)
            tk.Label(f, text=ev["type"], bg=color, fg="black", font=("Segoe UI", 8, "bold"), width=3).pack(side="left")
            t = datetime.fromisoformat(ev["time"].replace("Z", "")).strftime("%H:%M")
            tk.Label(f, text=t, bg="#0f172a", fg="white", font=("Segoe UI", 11)).pack(side="left", padx=15)
            tk.Label(f, text=f"{ev['height']:.2f} m", bg="#0f172a", fg="#94a3b8").pack(side="right")

        # Graphique
        self.fig, self.ax = plt.subplots(figsize=(11.5, 4.8))
        self.draw_chart()
        self.canvas_widget = FigureCanvasTkAgg(self.fig, self.main)
        self.canvas_widget.get_tk_widget().pack(fill="both", expand=True, pady=10)
        plt.close(self.fig)

    def draw_tide_clock(self):
        c = self.clock_canvas
        c.delete("all")
        cx, cy, r = 135, 145, 110
        c.create_oval(cx-r-5, cy-r-5, cx+r+5, cy+r+5, fill="#334155")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#1e293b", outline="#475569", width=3)

        angle = 45
        rad = math.radians(angle - 90)
        hx = cx + math.cos(rad) * 82
        hy = cy + math.sin(rad) * 82
        c.create_line(cx, cy, hx, hy, fill="#22d3ee", width=5, capstyle="round")
        c.create_oval(cx-7, cy-7, cx+7, cy+7, fill="#1e293b", outline="#38bdf8", width=3)

        h = self.data[len(self.data)//2]["height"] if self.data else 0.0
        c.create_text(cx, cy+160, text=f"{h:.2f} m", fill="#38bdf8", font=("Segoe UI", 14, "bold"))

    def draw_chart(self):
        times = [datetime.fromisoformat(d["time"].replace("Z","")) for d in self.data]
        heights = [d["height"] for d in self.data]

        self.ax.clear()
        self.ax.plot(times, heights, color="#38bdf8", linewidth=2.5)
        self.ax.set_ylabel("Hauteur (m)", color="#94a3b8")
        self.ax.grid(True, alpha=0.3, color="#334155")
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.tick_params(colors="#94a3b8")

        for ev in self.events:
            t = datetime.fromisoformat(ev["time"].replace("Z",""))
            color = "#22d3ee" if ev["type"] == "PM" else "#f97316"
            marker = "^" if ev["type"] == "PM" else "v"
            self.ax.plot(t, ev["height"], marker=marker, color=color, markersize=10, linestyle="")

    def prev_day(self):
        self.current_date -= timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def next_day(self):
        self.current_date += timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def today(self):
        self.current_date = datetime.now().date()
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1320x880")
    app = TideApp(root)
    root.mainloop()