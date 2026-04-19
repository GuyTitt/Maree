import tkinter as tk
from tkinter import ttk
import requests
import math
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API_BASE = "https://api-maree.fr"
API_KEY = "0000000000000000000000000000000"
PARIS = ZoneInfo("Europe/Paris")

os.makedirs("data", exist_ok=True)

class TideApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Marées - Hauteurs d'eau")
        self.root.configure(bg="#0f172a")
        self.current_date = datetime.now(PARIS).date()
        self.data = []
        self.events = []
        self.create_ui()
        self.load_sites()

    def create_ui(self):
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

        # Zone scrollable
        self.canvas_main = tk.Canvas(self.root, bg="#0f172a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas_main.yview)
        self.scrollable_frame = tk.Frame(self.canvas_main, bg="#0f172a")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas_main.configure(scrollregion=self.canvas_main.bbox("all")))
        self.canvas_main.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_main.configure(yscrollcommand=scrollbar.set)

        self.canvas_main.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scrollbar.pack(side="right", fill="y")

        self.show_status("Chargement...")

    def show_status(self, text, color="#94a3b8"):
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        tk.Label(self.scrollable_frame, text=text, fg=color, bg="#0f172a", font=("", 12)).pack(expand=True, pady=100)

    def load_sites(self):
        try:
            r = requests.get(f"{API_BASE}/sites?key={API_KEY}")
            sites = sorted(r.json().get("sites", []), key=lambda x: x["name"])
            self.port_combo["values"] = [f"{s['site_id']} - {s['name']}" for s in sites]
            self.port_combo.set(self.port_combo["values"][0])
            self.load_data()
        except:
            self.show_status("Erreur chargement ports", "#f87171")

    def get_cache_path(self, site_id):
        return f"data/{site_id}_{self.current_date.strftime('%Y-%m-%d')}.json"

    def load_data(self):
        self.show_status("Chargement...")
        self.root.after(100, self.fetch_and_render)

    def fetch_and_render(self):
        site_id = self.port_combo.get().split(" - ")[0]
        cache_file = self.get_cache_path(site_id)

        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                self.data = json.load(f).get("data", [])
        else:
            try:
                date_str = self.current_date.isoformat()
                url = f"{API_BASE}/water-levels?site={site_id}&from={date_str}T00:00&to={date_str}T23:59&step=10&tz=Europe/Paris&key={API_KEY}"
                self.data = requests.get(url).json().get("data", [])

                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "data": self.data}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.show_status(f"Erreur: {e}", "#f87171")
                return

        self.events = self.find_tide_events()
        self.render_all()

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
        for w in self.scrollable_frame.winfo_children():
            w.destroy()

        if not self.data:
            self.show_status("Aucune donnée", "#f87171")
            return

        # Top row : 3 cadres
        top = tk.Frame(self.scrollable_frame, bg="#0f172a")
        top.pack(fill="x", pady=10)

        w = 315
        # Calendrier
        cal = tk.Frame(top, bg="#1e293b", relief="solid", bd=1, width=w)
        cal.pack(side="left", padx=8, fill="y")
        cal.pack_propagate(False)
        self.draw_calendar(cal)

        # Horloge
        clock = tk.Frame(top, bg="#1e293b", relief="solid", bd=1, width=w)
        clock.pack(side="left", padx=8, fill="y")
        clock.pack_propagate(False)
        self.draw_clock(clock)

        # Marées du jour
        events = tk.Frame(top, bg="#1e293b", relief="solid", bd=1, width=w)
        events.pack(side="left", padx=8, fill="y")
        events.pack_propagate(False)
        self.draw_events(events)

        # Graphique en dessous (dans son propre frame)
        graph_frame = tk.Frame(self.scrollable_frame, bg="#0f172a")
        graph_frame.pack(fill="both", expand=True, pady=15)

        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.dates as mdates

        self.fig, self.ax = plt.subplots(figsize=(11.8, 5.4), facecolor="#0f172a")
        self.ax.set_facecolor("#1e293b")
        self.draw_chart()
        canvas = FigureCanvasTkAgg(self.fig, graph_frame)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(self.fig)

    def draw_calendar(self, parent):
        year = self.current_date.year
        month = self.current_date.month
        tk.Label(parent, text=self.current_date.strftime("%B %Y"), bg="#1e293b", fg="#e2e8f0", font=("Segoe UI", 10, "bold")).pack(pady=8)

        days = ["L","M","M","J","V","S","D"]
        h = tk.Frame(parent, bg="#1e293b")
        h.pack()
        for d in days:
            tk.Label(h, text=d, width=4, bg="#1e293b", fg="#64748b").pack(side="left")

        cal = tk.Frame(parent, bg="#1e293b")
        cal.pack(pady=5)
        first = datetime(year, month, 1).weekday()
        days_in_month = (datetime(year, month+1, 1) - timedelta(days=1)).day

        row = tk.Frame(cal, bg="#1e293b")
        row.pack()
        for _ in range(first):
            tk.Label(row, text="", width=4, height=2, bg="#1e293b").pack(side="left")

        for d in range(1, days_in_month + 1):
            if len(row.winfo_children()) == 7:
                row = tk.Frame(cal, bg="#1e293b")
                row.pack()
            date_str = f"{year}-{month:02d}-{d:02d}"
            bg = "#0284c7" if datetime(year, month, d).date() == self.current_date else "#1e293b"
            fg = "white" if datetime(year, month, d).date() == self.current_date else "#e2e8f0"
            lbl = tk.Label(row, text=str(d), width=4, height=2, bg=bg, fg=fg, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, ds=date_str: self.pick_date(ds))

    def draw_clock(self, parent):
        tk.Label(parent, text="Horloge de marée", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=8)
        self.clock_canvas = tk.Canvas(parent, width=280, height=355, bg="#1e293b", highlightthickness=0)
        self.clock_canvas.pack(pady=5)
        self.draw_tide_clock()

    def draw_events(self, parent):
        tk.Label(parent, text="Marées du jour", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=15, pady=8)
        for ev in self.events:
            color = "#22d3ee" if ev["type"] == "PM" else "#f97316"
            f = tk.Frame(parent, bg="#0f172a", pady=8, padx=12)
            f.pack(fill="x", padx=10, pady=3)
            tk.Label(f, text=ev["type"], bg=color, fg="black", font=("Segoe UI", 8, "bold"), width=3).pack(side="left")
            t = datetime.fromisoformat(ev["time"].replace("Z","")).strftime("%H:%M")
            tk.Label(f, text=t, bg="#0f172a", fg="white", font=("Segoe UI", 11)).pack(side="left", padx=15)
            tk.Label(f, text=f"{ev['height']:.2f} m", bg="#0f172a", fg="#94a3b8").pack(side="right")

    def draw_tide_clock(self):
        c = self.clock_canvas
        c.delete("all")
        cx, cy, r = 140, 170, 118
        c.create_oval(cx-r-8, cy-r-8, cx+r+8, cy+r+8, fill="#334155")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#1e293b", outline="#475569", width=4)

        c.create_arc(cx-r+20, cy-r+20, cx+r-20, cy+r-20, start=0, extent=180, style="arc", outline="#f97316", width=20)
        c.create_arc(cx-r+20, cy-r+20, cx+r-20, cy+r-20, start=180, extent=180, style="arc", outline="#22d3ee", width=20)

        for i in range(24):
            ang = math.radians(i * 15 - 90)
            len_ = 12 if i % 2 == 0 else 8
            x1 = cx + math.cos(ang) * (r - len_)
            y1 = cy + math.sin(ang) * (r - len_)
            x2 = cx + math.cos(ang) * (r - 4)
            y2 = cy + math.sin(ang) * (r - 4)
            c.create_line(x1, y1, x2, y2, fill="#64748b", width=2)

        c.create_text(cx, cy - r + 32, text="PM", fill="#22d3ee", font=("Segoe UI", 12, "bold"))
        c.create_text(cx, cy + r - 32, text="BM", fill="#f97316", font=("Segoe UI", 12, "bold"))

        rad = math.radians(45 - 90)
        hx = cx + math.cos(rad) * 90
        hy = cy + math.sin(rad) * 90
        c.create_line(cx, cy, hx, hy, fill="#38bdf8", width=6, capstyle="round")
        c.create_oval(cx-8, cy-8, cx+8, cy+8, fill="#1e293b", outline="#38bdf8", width=3)

        h = self.data[len(self.data)//2]["height"] if self.data else 0.0
        now = datetime.now(PARIS).strftime("%H:%M")
        c.create_text(cx, cy + 165, text=f"{now}   {h:.2f} m", fill="#38bdf8", font=("Segoe UI", 13, "bold"))

    def draw_chart(self):
        import matplotlib.dates as mdates
        times = [datetime.fromisoformat(d["time"].replace("Z","")).replace(tzinfo=PARIS) for d in self.data]
        heights = [d["height"] for d in self.data]

        self.ax.clear()
        self.ax.plot(times, heights, color="#38bdf8", linewidth=2.8)
        self.ax.set_ylabel("Hauteur (m)", color="#94a3b8")
        self.ax.grid(True, alpha=0.3, color="#334155")
        self.ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        self.ax.set_xlim(times[0].replace(hour=0, minute=0), times[-1].replace(hour=23, minute=59))
        self.ax.tick_params(colors="#94a3b8")

    def pick_date(self, ds):
        self.current_date = datetime.fromisoformat(ds).date()
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def prev_day(self):
        self.current_date -= timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def next_day(self):
        self.current_date += timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def today(self):
        self.current_date = datetime.now(PARIS).date()
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1430x960")
    app = TideApp(root)
    root.mainloop()