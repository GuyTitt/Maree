import tkinter as tk
from tkinter import ttk
import requests
import math
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as mpatches

API_BASE = "https://api-maree.fr"
API_KEY  = "0000000000000000000000000000000"
PARIS    = ZoneInfo("Europe/Paris")

os.makedirs("data", exist_ok=True)

# ── Palette ────────────────────────────────────────────────────────────────────
BG      = "#0f172a"
SURFACE = "#1e293b"
BORDER  = "#334155"
TEXT    = "#e2e8f0"
MUTED   = "#94a3b8"
ACCENT  = "#38bdf8"
ACCENT2 = "#0284c7"
PM_COL  = "#22d3ee"
BM_COL  = "#f97316"
ERROR   = "#f87171"
FONT    = "Segoe UI"


def parse_local(iso_str: str) -> datetime:
    """Parse an ISO-8601 string keeping the local offset (no UTC conversion)."""
    return datetime.fromisoformat(iso_str)


class TideApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Marées – Hauteurs d'eau")
        self.root.configure(bg=BG)
        self.current_date = datetime.now(PARIS).date()
        self.data   = []
        self.events = []
        self._chart_canvas = None
        self._live_job     = None
        self._cal_year  = None
        self._cal_month = None
        self.create_ui()
        self.load_sites()

    # ── UI skeleton ────────────────────────────────────────────────────────────
    def create_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=SURFACE, pady=0)
        header.pack(fill="x")

        tk.Label(header, text="🌊  Marées", font=(FONT, 16, "bold"),
                 fg=ACCENT, bg=SURFACE).pack(side="left", padx=20, pady=10)

        ctrl = tk.Frame(header, bg=SURFACE)
        ctrl.pack(side="right", padx=16)

        self.port_combo = ttk.Combobox(ctrl, width=32, state="readonly",
                                       font=(FONT, 9))
        self.port_combo.pack(side="left", padx=4)
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        # Navigation
        nav = tk.Frame(ctrl, bg=SURFACE)
        nav.pack(side="left", padx=6)
        btn_style = dict(bg="#334155", fg=TEXT, relief="flat",
                         activebackground=ACCENT2, activeforeground="white",
                         bd=0, padx=8, pady=4, cursor="hand2")
        tk.Button(nav, text="◀", **btn_style, command=self.prev_day).pack(side="left", padx=2)
        self.date_label = tk.Label(nav, text=self.current_date.strftime("%Y-%m-%d"),
                                   fg=TEXT, bg=SURFACE, font=(FONT, 9), width=12)
        self.date_label.pack(side="left", padx=6)
        tk.Button(nav, text="▶", **btn_style, command=self.next_day).pack(side="left", padx=2)
        tk.Button(nav, text="Aujourd'hui",
                  bg=ACCENT2, fg="white", relief="flat",
                  activebackground=ACCENT, activeforeground="white",
                  bd=0, padx=10, pady=4, cursor="hand2",
                  command=self.today).pack(side="left", padx=(8, 0))

        # ── Scrollable body ────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        self.canvas_main = tk.Canvas(body, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical",
                              command=self.canvas_main.yview)
        self.scrollable_frame = tk.Frame(self.canvas_main, bg=BG)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_main.configure(
                scrollregion=self.canvas_main.bbox("all")))
        self._win = self.canvas_main.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_main.configure(yscrollcommand=vbar.set)
        self.canvas_main.bind(
            "<Configure>",
            lambda e: self.canvas_main.itemconfig(self._win, width=e.width))

        # mouse-wheel support
        self.canvas_main.bind_all("<MouseWheel>",
            lambda e: self.canvas_main.yview_scroll(int(-e.delta / 120), "units"))

        self.canvas_main.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        self.show_status("Chargement…")

    # ── Helpers ────────────────────────────────────────────────────────────────
    def show_status(self, text, color=MUTED):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        tk.Label(self.scrollable_frame, text=text, fg=color, bg=BG,
                 font=(FONT, 12)).pack(expand=True, pady=120)

    def _card(self, parent, **kwargs):
        """Return a rounded-ish surface Frame."""
        f = tk.Frame(parent, bg=SURFACE, bd=1, relief="solid", **kwargs)
        return f

    # ── Sites ──────────────────────────────────────────────────────────────────
    def load_sites(self):
        try:
            r     = requests.get(f"{API_BASE}/sites?key={API_KEY}", timeout=10)
            sites = sorted(r.json().get("sites", []), key=lambda x: x["name"])
            self.port_combo["values"] = [f"{s['site_id']} | {s['name']}"
                                         for s in sites]
            # default: boulogne-sur-mer if available
            default = next((s for s in sites
                            if s["site_id"] == "boulogne-sur-mer"), sites[0])
            self.port_combo.set(f"{default['site_id']} | {default['name']}")
            self.load_data()
        except Exception as e:
            self.show_status(f"Erreur chargement ports : {e}", ERROR)

    def get_site_id(self):
        return self.port_combo.get().split(" | ")[0]

    # ── Data ──────────────────────────────────────────────────────────────────
    def get_cache_path(self, site_id):
        return f"data/{site_id}_{self.current_date.isoformat()}.json"

    def load_data(self):
        self.show_status("Chargement…")
        if self._live_job:
            self.root.after_cancel(self._live_job)
            self._live_job = None
        self.root.after(80, self.fetch_and_render)

    def fetch_and_render(self):
        site_id    = self.get_site_id()
        cache_file = self.get_cache_path(site_id)

        if os.path.exists(cache_file):
            with open(cache_file, encoding="utf-8") as f:
                self.data = json.load(f).get("data", [])
        else:
            try:
                ds  = self.current_date.isoformat()
                url = (f"{API_BASE}/water-levels?site={site_id}"
                       f"&from={ds}T00:00&to={ds}T23:59"
                       f"&step=10&tz=Europe/Paris&key={API_KEY}")
                self.data = requests.get(url, timeout=15).json().get("data", [])
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "data": self.data}, f,
                              ensure_ascii=False, indent=2)
            except Exception as e:
                self.show_status(f"Erreur : {e}", ERROR)
                return

        self.events = self._find_events()
        self.render_all()

    def _find_events(self):
        """Find PM / BM events with deduplication (plateaus)."""
        data = self.data
        raw  = []
        for i in range(1, len(data) - 1):
            p, c, n = data[i-1]["height"], data[i]["height"], data[i+1]["height"]
            if c >= p and c >= n and (c > p or c > n):
                raw.append({"type": "PM", "time": data[i]["time"], "height": c})
            elif c <= p and c <= n and (c < p or c < n):
                raw.append({"type": "BM", "time": data[i]["time"], "height": c})

        deduped = []
        for ev in raw:
            last = deduped[-1] if deduped else None
            if last and last["type"] == ev["type"]:
                diff = (parse_local(ev["time"]) - parse_local(last["time"])).total_seconds() / 60
                if diff <= 30:
                    if (ev["type"] == "PM" and ev["height"] > last["height"]) or \
                       (ev["type"] == "BM" and ev["height"] < last["height"]):
                        deduped[-1] = ev
                    continue
            deduped.append(ev)
        return deduped

    # ── Render all ────────────────────────────────────────────────────────────
    def render_all(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        if self._chart_canvas:
            self._chart_canvas = None

        if not self.data:
            self.show_status("Aucune donnée", ERROR)
            return

        # ── Top row: Calendar | Tide-clock | Events ──────────────────────────
        top = tk.Frame(self.scrollable_frame, bg=BG)
        top.pack(fill="x", padx=16, pady=(16, 0))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)

        cal_card = self._card(top, height=310)
        cal_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        cal_card.grid_propagate(False)
        self.draw_calendar(cal_card)

        clk_card = self._card(top, height=310)
        clk_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        clk_card.grid_propagate(False)
        self.draw_clock(clk_card)

        ev_card = self._card(top, height=310)
        ev_card.grid(row=0, column=2, sticky="nsew", padx=6, pady=4)
        ev_card.grid_propagate(False)
        self.draw_events(ev_card)

        # ── Chart ────────────────────────────────────────────────────────────
        chart_wrap = tk.Frame(self.scrollable_frame, bg=BG)
        chart_wrap.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self.draw_chart(chart_wrap)

        # Live refresh every 60 s (only for today)
        today = datetime.now(PARIS).date()
        if self.current_date == today:
            self._schedule_live()

    # ── Calendar ──────────────────────────────────────────────────────────────
    def draw_calendar(self, parent):
        self._cal_year  = self.current_date.year
        self._cal_month = self.current_date.month
        self._render_calendar(parent)

    def _render_calendar(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        year, month = self._cal_year, self._cal_month
        today  = datetime.now(PARIS).date()
        sel    = self.current_date
        month_names = ["Janvier","Février","Mars","Avril","Mai","Juin",
                       "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

        # Title row
        hdr = tk.Frame(parent, bg=SURFACE)
        hdr.pack(fill="x", padx=8, pady=(8, 2))
        nav_btn = dict(bg="#334155", fg=TEXT, relief="flat", bd=0,
                       padx=6, pady=2, cursor="hand2",
                       activebackground=ACCENT2, activeforeground="white")
        tk.Button(hdr, text="◀", **nav_btn,
                  command=lambda: self._cal_shift(parent, -1)).pack(side="left")
        tk.Label(hdr, text=f"{month_names[month-1]} {year}",
                 fg=TEXT, bg=SURFACE, font=(FONT, 9, "bold")).pack(side="left", expand=True)
        tk.Button(hdr, text="▶", **nav_btn,
                  command=lambda: self._cal_shift(parent, 1)).pack(side="right")

        # Weekday headers
        wk = tk.Frame(parent, bg=SURFACE)
        wk.pack(padx=4)
        for d in ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]:
            tk.Label(wk, text=d, fg=MUTED, bg=SURFACE,
                     font=(FONT, 7), width=4).pack(side="left")

        # Day grid
        grid = tk.Frame(parent, bg=SURFACE)
        grid.pack(padx=4, pady=2)

        first_wd = datetime(year, month, 1).weekday()  # 0=Mon
        if month == 12:
            days_in = (datetime(year+1, 1, 1) - timedelta(days=1)).day
        else:
            days_in = (datetime(year, month+1, 1) - timedelta(days=1)).day

        row = tk.Frame(grid, bg=SURFACE)
        row.pack(anchor="w")
        for _ in range(first_wd):
            tk.Label(row, text="", width=4, height=2, bg=SURFACE).pack(side="left")

        for d in range(1, days_in + 1):
            if len(row.winfo_children()) == 7:
                row = tk.Frame(grid, bg=SURFACE)
                row.pack(anchor="w")
            cell_date = datetime(year, month, d).date()
            is_sel   = (cell_date == sel)
            is_today = (cell_date == today)
            bg_ = ACCENT2 if is_sel else SURFACE
            fg_ = "white"  if is_sel else (ACCENT if is_today else MUTED)
            relief_ = "flat"
            lbl = tk.Label(row, text=str(d), width=4, height=2,
                           bg=bg_, fg=fg_, font=(FONT, 8), relief=relief_,
                           cursor="hand2")
            if is_today and not is_sel:
                lbl.config(bd=1, relief="solid")
            lbl.pack(side="left")
            lbl.bind("<Button-1>",
                     lambda e, cd=cell_date: self._pick_date(cd))
            lbl.bind("<Enter>",
                     lambda e, l=lbl, s=is_sel: l.config(fg=TEXT) if not s else None)
            lbl.bind("<Leave>",
                     lambda e, l=lbl, s=is_sel, fg=fg_: l.config(fg=fg_) if not s else None)

    def _cal_shift(self, parent, offset):
        m = self._cal_month + offset
        y = self._cal_year
        if m > 12: m, y = 1, y + 1
        if m < 1:  m, y = 12, y - 1
        self._cal_year, self._cal_month = y, m
        self._render_calendar(parent)

    def _pick_date(self, date_obj):
        self.current_date = date_obj
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    # ── Tide clock ────────────────────────────────────────────────────────────
    def draw_clock(self, parent):
        tk.Label(parent, text="Horloge de marée", fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
        self.clock_canvas = tk.Canvas(parent, bg=SURFACE, highlightthickness=0)
        self.clock_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        # Defer drawing until the canvas has real pixel dimensions
        self.root.update()
        self.root.after(50, self.redraw_clock)

    def redraw_clock(self):
        c = self.clock_canvas
        c.update_idletasks()
        W = c.winfo_width()  or 280
        H = c.winfo_height() or 270
        c.delete("all")

        cx, cy = W // 2, H // 2 - 10
        r = min(W, H) // 2 - 20

        # Clock state
        state = self._get_clock_state()

        # Background circles
        c.create_oval(cx-r-6, cy-r-6, cx+r+6, cy+r+6, fill="#334155", outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=SURFACE, outline="#475569", width=2)

        # Semi-arc zones
        ar = r - 18
        c.create_arc(cx-ar, cy-ar, cx+ar, cy+ar,
                     start=0, extent=180, style="arc",
                     outline=BM_COL, width=10)          # right half → descendante
        c.create_arc(cx-ar, cy-ar, cx+ar, cy+ar,
                     start=180, extent=180, style="arc",
                     outline=PM_COL, width=10)          # left half  → montante

        # Tick marks
        for i in range(24):
            ang = math.radians(i * 15 - 90)
            is_major = i % 2 == 0
            inner_r  = r - (14 if is_major else 8)
            x1 = cx + math.cos(ang) * inner_r
            y1 = cy + math.sin(ang) * inner_r
            x2 = cx + math.cos(ang) * (r - 3)
            y2 = cy + math.sin(ang) * (r - 3)
            c.create_line(x1, y1, x2, y2, fill="#64748b",
                          width=2 if is_major else 1)

        # PM / BM labels
        c.create_text(cx, cy - r + 28, text="PM", fill=PM_COL,
                      font=(FONT, 10, "bold"))
        c.create_text(cx, cy + r - 28, text="BM", fill=BM_COL,
                      font=(FONT, 10, "bold"))
        c.create_text(cx + r - 26, cy, text="+3h", fill="#64748b",
                      font=(FONT, 7))
        c.create_text(cx - r + 26, cy, text="+3h", fill="#64748b",
                      font=(FONT, 7))

        # Hand
        angle = state["angle"]
        hand_color = (PM_COL if state["direction"] == "rising"
                      else BM_COL if state["direction"] == "falling"
                      else ACCENT)
        hand_rad = math.radians(angle - 90)
        hand_len = r - 32
        hx = cx + math.cos(hand_rad) * hand_len
        hy = cy + math.sin(hand_rad) * hand_len
        c.create_line(cx, cy, hx+1, hy+1, fill="#00000055",
                      width=4, capstyle="round")
        c.create_line(cx, cy, hx, hy, fill=hand_color,
                      width=3, capstyle="round")
        c.create_oval(hx-5, hy-5, hx+5, hy+5, fill=hand_color, outline="")
        c.create_oval(cx-7, cy-7, cx+7, cy+7, fill=SURFACE,
                      outline=hand_color, width=2)
        c.create_oval(cx-2, cy-2, cx+2, cy+2, fill=hand_color, outline="")

        # Status text below
        if state["is_today"] and state["current_height"] is not None:
            h_val = state["current_height"]
            now_s = datetime.now(PARIS).strftime("%H:%M")
            dir_label = ("▲ Marée montante" if state["direction"] == "rising"
                         else "▼ Marée descendante" if state["direction"] == "falling"
                         else "")
            dir_col = (PM_COL if state["direction"] == "rising"
                       else BM_COL if state["direction"] == "falling"
                       else MUTED)
            c.create_text(cx, cy + r + 10, fill=ACCENT,
                          text=f"{h_val:.2f} m",
                          font=(FONT, 13, "bold"))
            c.create_text(cx, cy + r + 28, fill=dir_col,
                          text=dir_label, font=(FONT, 8))
            c.create_text(cx, cy + r + 44, fill=MUTED,
                          text=now_s, font=(FONT, 8))
        else:
            c.create_text(cx, cy + r + 18, fill=MUTED,
                          text="Horloge basée sur la première marée du jour",
                          font=(FONT, 7))

    def _get_clock_state(self):
        data   = self.data
        events = self.events
        now    = datetime.now(PARIS)

        if not data:
            return {"angle":0, "is_today":False, "current_height":None,
                    "direction":None}

        day_start = parse_local(data[0]["time"])
        day_end   = parse_local(data[-1]["time"])
        is_today  = (day_start.date() == now.date())
        ref_time  = now if is_today else day_start

        # Interpolate current height
        current_height = None
        if is_today:
            ref_ms = now.timestamp()
            for i in range(len(data)-1):
                t0 = parse_local(data[i]["time"]).timestamp()
                t1 = parse_local(data[i+1]["time"]).timestamp()
                if t0 <= ref_ms <= t1:
                    ratio = (ref_ms - t0) / (t1 - t0)
                    current_height = (data[i]["height"] +
                                      ratio * (data[i+1]["height"] - data[i]["height"]))
                    break

        ref_ms = ref_time.timestamp()
        prev_ev = next_ev = None
        for ev in events:
            evms = parse_local(ev["time"]).timestamp()
            if evms <= ref_ms:
                prev_ev = ev
            elif next_ev is None and evms > ref_ms:
                next_ev = ev

        direction = None
        if prev_ev and next_ev:
            direction = "rising"  if next_ev["type"] == "PM" else "falling"
        elif prev_ev:
            direction = "falling" if prev_ev["type"] == "PM" else "rising"
        elif next_ev:
            direction = "rising"  if next_ev["type"] == "PM" else "falling"

        angle = 0
        if prev_ev and next_ev:
            pms  = parse_local(prev_ev["time"]).timestamp()
            nms  = parse_local(next_ev["time"]).timestamp()
            prog = max(0, min(1, (ref_ms - pms) / (nms - pms)))
            angle = prog * 180 if prev_ev["type"] == "PM" else 180 + prog * 180
        elif prev_ev:
            angle = 30  if prev_ev["type"] == "PM" else 210
        elif next_ev:
            angle = 330 if next_ev["type"] == "PM" else 150

        return {"angle": angle, "is_today": is_today,
                "current_height": current_height, "direction": direction}

    # ── Events panel ──────────────────────────────────────────────────────────
    def draw_events(self, parent):
        tk.Label(parent, text="Marées du jour", fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=12, pady=(8, 4))

        if not self.events:
            tk.Label(parent, text="Aucune marée détectée.",
                     fg=MUTED, bg=SURFACE, font=(FONT, 9)).pack(padx=12)
            return

        for ev in self.events:
            is_pm  = ev["type"] == "PM"
            color  = PM_COL if is_pm else BM_COL
            label  = "Pleine Mer" if is_pm else "Basse Mer"
            t_str  = parse_local(ev["time"]).strftime("%H:%M")

            row = tk.Frame(parent, bg="#0f172a", bd=0)
            row.pack(fill="x", padx=10, pady=3, ipady=6)

            # colored left border simulation
            bar = tk.Frame(row, bg=color, width=4)
            bar.pack(side="left", fill="y")

            inner = tk.Frame(row, bg="#0f172a")
            inner.pack(side="left", fill="both", expand=True, padx=10)

            badge = tk.Label(inner, text=ev["type"],
                             bg=SURFACE, fg=color,
                             font=(FONT, 7, "bold"), padx=5, pady=2,
                             relief="solid", bd=1)
            badge.pack(side="left", padx=(0, 10))

            info = tk.Frame(inner, bg="#0f172a")
            info.pack(side="left")
            tk.Label(info, text=t_str, fg=TEXT, bg="#0f172a",
                     font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(info, text=f"{ev['height']:.2f} m – {label}",
                     fg=MUTED, bg="#0f172a",
                     font=(FONT, 8)).pack(anchor="w")

    # ── Chart ─────────────────────────────────────────────────────────────────
    def draw_chart(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)

        tk.Label(card, text="COURBE DE MARÉE", fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        # Build local datetime list — strip timezone offset for matplotlib (keeps HH:MM correct)
        times   = [parse_local(d["time"]).replace(tzinfo=None) for d in self.data]
        heights = [d["height"] for d in self.data]

        fig, ax = plt.subplots(figsize=(12, 4.2), facecolor=SURFACE)
        ax.set_facecolor("#1e293b")

        # Gradient fill via PolyCollection
        ax.fill_between(times, heights, alpha=0.18, color=ACCENT)
        line, = ax.plot(times, heights, color=ACCENT, linewidth=2.4)

        # PM / BM markers
        pm_x, pm_y, bm_x, bm_y = [], [], [], []
        for ev in self.events:
            t = parse_local(ev["time"]).replace(tzinfo=None)
            h = ev["height"]
            if ev["type"] == "PM":
                pm_x.append(t); pm_y.append(h)
            else:
                bm_x.append(t); bm_y.append(h)

        ax.scatter(pm_x, pm_y, color=PM_COL, s=70, zorder=5,
                   marker="^", label="PM")
        ax.scatter(bm_x, bm_y, color=BM_COL, s=70, zorder=5,
                   marker="D", label="BM")

        # "Now" vertical line (today only)
        today = datetime.now(PARIS).date()
        if self.current_date == today:
            now_local = datetime.now(PARIS).replace(tzinfo=None)
            ax.axvline(now_local, color="#f472b6", linewidth=1.4,
                       linestyle="--", alpha=0.9, label="Maintenant")
            # dot at current height
            for i in range(len(self.data)-1):
                t0 = times[i]
                t1 = times[i+1]
                if t0 <= now_local <= t1:
                    ratio = (now_local - t0) / (t1 - t0)
                    h_now = heights[i] + ratio * (heights[i+1] - heights[i])
                    ax.scatter([now_local], [h_now], color="#f472b6",
                               s=55, zorder=6)
                    break

        # X axis: hours in local time (already correct, just format HH:MM)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlim(times[0].replace(hour=0, minute=0),
                    times[-1].replace(hour=23, minute=59))

        # Styling
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylabel("Hauteur (m)", color=MUTED, fontsize=9)
        ax.yaxis.set_tick_params(colors=MUTED)
        ax.grid(True, color=BORDER, alpha=0.5, linewidth=0.6)
        ax.set_facecolor(SURFACE)

        # Legend
        legend_patches = [
            mpatches.Patch(color=ACCENT,  label="Hauteur (m)"),
            mpatches.Patch(color=PM_COL,  label="PM"),
            mpatches.Patch(color=BM_COL,  label="BM"),
        ]
        if self.current_date == today:
            legend_patches.append(mpatches.Patch(color="#f472b6", label="Maintenant"))
        ax.legend(handles=legend_patches, facecolor=SURFACE, edgecolor=BORDER,
                  labelcolor=MUTED, fontsize=8, loc="upper right")

        fig.tight_layout(pad=1.2)

        canvas = FigureCanvasTkAgg(fig, card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 10))
        plt.close(fig)
        self._chart_canvas = canvas

    # ── Live refresh ──────────────────────────────────────────────────────────
    def _schedule_live(self):
        self._live_job = self.root.after(60_000, self._live_tick)

    def _live_tick(self):
        """Refresh only the clock and chart now-line every minute."""
        if hasattr(self, "clock_canvas"):
            self.redraw_clock()
        self._schedule_live()

    # ── Navigation ────────────────────────────────────────────────────────────
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
    root.geometry("1280x860")
    root.minsize(900, 600)
    app = TideApp(root)
    root.mainloop()
