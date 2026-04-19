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
PM_COL  = "#22d3ee"   # cyan  → pleine mer (montante)
BM_COL  = "#f97316"   # orange → basse mer (descendante)
ERROR   = "#f87171"
FONT    = "Segoe UI"


def parse_local(iso_str: str) -> datetime:
    """Parse ISO-8601 string, keeping the local offset (no UTC conversion)."""
    return datetime.fromisoformat(iso_str)


class TideApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Marées – Hauteurs d'eau")
        self.root.configure(bg=BG)
        self.current_date = datetime.now(PARIS).date()
        self.data         = []
        self.events       = []
        self._live_job    = None
        self._cal_year    = None
        self._cal_month   = None
        # chart tooltip state
        self._tooltip_win  = None
        self._times_plain  = []   # naive datetimes for chart
        self._heights      = []
        self._fig          = None
        self._ax           = None
        self._mpl_canvas   = None
        self.create_ui()
        self.load_sites()

    # ── UI skeleton ────────────────────────────────────────────────────────────
    def create_ui(self):
        header = tk.Frame(self.root, bg=SURFACE)
        header.pack(fill="x")
        tk.Label(header, text="🌊  Marées", font=(FONT, 16, "bold"),
                 fg=ACCENT, bg=SURFACE).pack(side="left", padx=20, pady=10)

        ctrl = tk.Frame(header, bg=SURFACE)
        ctrl.pack(side="right", padx=16)
        self.port_combo = ttk.Combobox(ctrl, width=32, state="readonly", font=(FONT, 9))
        self.port_combo.pack(side="left", padx=4)
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        nav = tk.Frame(ctrl, bg=SURFACE)
        nav.pack(side="left", padx=6)
        bs = dict(bg=BORDER, fg=TEXT, relief="flat", activebackground=ACCENT2,
                  activeforeground="white", bd=0, padx=8, pady=4, cursor="hand2")
        tk.Button(nav, text="◀", **bs, command=self.prev_day).pack(side="left", padx=2)
        self.date_label = tk.Label(nav, text=self.current_date.strftime("%Y-%m-%d"),
                                   fg=TEXT, bg=SURFACE, font=(FONT, 9), width=12)
        self.date_label.pack(side="left", padx=6)
        tk.Button(nav, text="▶", **bs, command=self.next_day).pack(side="left", padx=2)
        tk.Button(nav, text="Aujourd'hui", bg=ACCENT2, fg="white", relief="flat",
                  activebackground=ACCENT, activeforeground="white",
                  bd=0, padx=10, pady=4, cursor="hand2",
                  command=self.today).pack(side="left", padx=(8, 0))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        self.canvas_main = tk.Canvas(body, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas_main.yview)
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
        self.canvas_main.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas_main.yview_scroll(int(-e.delta / 120), "units"))
        self.canvas_main.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")
        self.show_status("Chargement…")

    def show_status(self, text, color=MUTED):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        tk.Label(self.scrollable_frame, text=text, fg=color, bg=BG,
                 font=(FONT, 12)).pack(expand=True, pady=120)

    def _card(self, parent, **kw):
        return tk.Frame(parent, bg=SURFACE, bd=1, relief="solid", **kw)

    # ── Sites ──────────────────────────────────────────────────────────────────
    def load_sites(self):
        try:
            r     = requests.get(f"{API_BASE}/sites?key={API_KEY}", timeout=10)
            sites = sorted(r.json().get("sites", []), key=lambda x: x["name"])
            self.port_combo["values"] = [f"{s['site_id']} | {s['name']}" for s in sites]
            default = next((s for s in sites if s["site_id"] == "boulogne-sur-mer"), sites[0])
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
        data, raw = self.data, []
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
                    if ((ev["type"] == "PM" and ev["height"] > last["height"]) or
                            (ev["type"] == "BM" and ev["height"] < last["height"])):
                        deduped[-1] = ev
                    continue
            deduped.append(ev)
        return deduped

    # ── Render all ────────────────────────────────────────────────────────────
    def render_all(self):
        for w in self.scrollable_frame.winfo_children():
            w.destroy()
        self._mpl_canvas = None
        if not self.data:
            self.show_status("Aucune donnée", ERROR)
            return

        top = tk.Frame(self.scrollable_frame, bg=BG)
        top.pack(fill="x", padx=16, pady=(16, 0))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.columnconfigure(2, weight=1)

        cal_card = self._card(top, height=320)
        cal_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=4)
        cal_card.grid_propagate(False)
        self.draw_calendar(cal_card)

        clk_card = self._card(top, height=320)
        clk_card.grid(row=0, column=1, sticky="nsew", padx=6, pady=4)
        clk_card.grid_propagate(False)
        self.draw_clock(clk_card)

        ev_card = self._card(top, height=320)
        ev_card.grid(row=0, column=2, sticky="nsew", padx=6, pady=4)
        ev_card.grid_propagate(False)
        self.draw_events(ev_card)

        chart_wrap = tk.Frame(self.scrollable_frame, bg=BG)
        chart_wrap.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self.draw_chart(chart_wrap)

        if self.current_date == datetime.now(PARIS).date():
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
        today = datetime.now(PARIS).date()
        sel   = self.current_date
        month_names = ["Janvier","Février","Mars","Avril","Mai","Juin",
                       "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

        hdr = tk.Frame(parent, bg=SURFACE)
        hdr.pack(fill="x", padx=8, pady=(8, 2))
        nb = dict(bg=BORDER, fg=TEXT, relief="flat", bd=0, padx=6, pady=2,
                  cursor="hand2", activebackground=ACCENT2, activeforeground="white")
        tk.Button(hdr, text="◀", **nb,
                  command=lambda: self._cal_shift(parent, -1)).pack(side="left")
        tk.Label(hdr, text=f"{month_names[month-1]} {year}",
                 fg=TEXT, bg=SURFACE, font=(FONT, 9, "bold")).pack(side="left", expand=True)
        tk.Button(hdr, text="▶", **nb,
                  command=lambda: self._cal_shift(parent, 1)).pack(side="right")

        wk = tk.Frame(parent, bg=SURFACE)
        wk.pack(padx=4)
        for d in ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]:
            tk.Label(wk, text=d, fg=MUTED, bg=SURFACE,
                     font=(FONT, 7), width=4).pack(side="left")

        grid = tk.Frame(parent, bg=SURFACE)
        grid.pack(padx=4, pady=2)
        first_wd = datetime(year, month, 1).weekday()
        days_in  = (datetime(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)).day

        row = tk.Frame(grid, bg=SURFACE)
        row.pack(anchor="w")
        for _ in range(first_wd):
            tk.Label(row, text="", width=4, height=2, bg=SURFACE).pack(side="left")

        for d in range(1, days_in + 1):
            if len(row.winfo_children()) == 7:
                row = tk.Frame(grid, bg=SURFACE)
                row.pack(anchor="w")
            cell_date = datetime(year, month, d).date()
            is_sel   = cell_date == sel
            is_today = cell_date == today
            bg_ = ACCENT2 if is_sel else SURFACE
            fg_ = "white"  if is_sel else (ACCENT if is_today else MUTED)
            lbl = tk.Label(row, text=str(d), width=4, height=2,
                           bg=bg_, fg=fg_, font=(FONT, 8),
                           relief="solid" if (is_today and not is_sel) else "flat",
                           bd=1 if (is_today and not is_sel) else 0,
                           cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, cd=cell_date: self._pick_date(cd))
            lbl.bind("<Enter>",    lambda e, l=lbl, s=is_sel: l.config(fg=TEXT) if not s else None)
            lbl.bind("<Leave>",    lambda e, l=lbl, s=is_sel, f=fg_: l.config(fg=f) if not s else None)

    def _cal_shift(self, parent, offset):
        m = self._cal_month + offset
        y = self._cal_year
        if m > 12: m, y = 1,  y + 1
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
        self.root.update()
        self.root.after(50, self.redraw_clock)

    def redraw_clock(self):
        if not hasattr(self, "clock_canvas") or not self.clock_canvas.winfo_exists():
            return
        c = self.clock_canvas
        c.update_idletasks()
        W = c.winfo_width()  or 280
        H = c.winfo_height() or 280
        c.delete("all")

        cx, cy = W // 2, H // 2 - 14
        r = min(W, H) // 2 - 18

        state = self._get_clock_state()

        # ── Outer ring + face ─────────────────────────────────────────────────
        c.create_oval(cx-r-6, cy-r-6, cx+r+6, cy+r+6, fill=BORDER, outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=SURFACE, outline="#475569", width=2)

        # ── Zone arcs — thinner so hour labels are visible ────────────────────
        ar = r - 8          # radius of arc track (closer to edge, thinner)
        arc_w = 5           # thinner width to leave room for labels
        # Right arc: descent PM→BM, orange
        c.create_arc(cx-ar, cy-ar, cx+ar, cy+ar,
                     start=-90, extent=-180, style="arc",
                     outline=BM_COL, width=arc_w)
        # Left arc: ascent BM→PM, cyan
        c.create_arc(cx-ar, cy-ar, cx+ar, cy+ar,
                     start=90, extent=-180, style="arc",
                     outline=PM_COL, width=arc_w)

        # ── Hour graduations with time labels ─────────────────────────────────
        pm_events   = [e for e in self.events if e["type"] == "PM"]
        first_pm_dt = parse_local(pm_events[0]["time"]) if pm_events else None

        for i in range(24):
            ang_deg  = i * 15 - 90
            ang      = math.radians(ang_deg)
            is_major = (i % 2 == 0)
            # ticks start just inside the arc
            tick_out = r - 12
            tick_in  = tick_out - (10 if is_major else 6)
            x1 = cx + math.cos(ang) * tick_in
            y1 = cy + math.sin(ang) * tick_in
            x2 = cx + math.cos(ang) * tick_out
            y2 = cy + math.sin(ang) * tick_out
            c.create_line(x1, y1, x2, y2, fill="#64748b",
                          width=2 if is_major else 1)

            # Hour label at each major tick
            if is_major and first_pm_dt:
                tide_hours = i // 2
                label_dt   = first_pm_dt + timedelta(hours=tide_hours)
                label_str  = label_dt.strftime("%H:%M") if tide_hours <= 12 else ""
                if label_str:
                    lx = cx + math.cos(ang) * (r - 28)
                    ly = cy + math.sin(ang) * (r - 28)
                    c.create_text(lx, ly, text=label_str, fill="#64748b",
                                  font=(FONT, 6))

        # ── PM / BM fixed labels ──────────────────────────────────────────────
        c.create_text(cx, cy - r + 10, text="PM", fill=PM_COL,
                      font=(FONT, 8, "bold"))
        c.create_text(cx, cy + r - 10, text="BM", fill=BM_COL,
                      font=(FONT, 8, "bold"))

        # ── Height inside the dial (colored by direction) ─────────────────────
        if state["is_today"] and state["current_height"] is not None:
            h_val    = state["current_height"]
            h_color  = (PM_COL if state["direction"] == "falling"   # PM→BM : bleu cyan
                        else BM_COL if state["direction"] == "rising"  # BM→PM : orange
                        else ACCENT)
            c.create_text(cx, cy - 14, text=f"{h_val:.2f} m",
                          fill=h_color, font=(FONT, 14, "bold"))

        # ── Hand — white/light grey ───────────────────────────────────────────
        angle    = state["angle"]
        hand_rad = math.radians(angle - 90)
        hand_len = r - 30
        hx = cx + math.cos(hand_rad) * hand_len
        hy = cy + math.sin(hand_rad) * hand_len

        c.create_line(cx+1, cy+1, hx+2, hy+2, fill="#0a1020",
                      width=5, capstyle="round")                    # shadow
        c.create_line(cx, cy, hx, hy, fill="#dde6f0",
                      width=3, capstyle="round")                    # white/grey hand
        c.create_oval(hx-5, hy-5, hx+5, hy+5, fill="#dde6f0", outline="")
        c.create_oval(cx-7, cy-7, cx+7, cy+7, fill=SURFACE,
                      outline="#dde6f0", width=2)
        c.create_oval(cx-2, cy-2, cx+2, cy+2, fill="#dde6f0", outline="")

        # ── Time + direction below center ─────────────────────────────────────
        if state["is_today"] and state["current_height"] is not None:
            now_s     = datetime.now(PARIS).strftime("%H:%M")
            dir_label = ("▲ Montante" if state["direction"] == "rising"
                         else "▼ Descendante" if state["direction"] == "falling"
                         else "")
            dir_col   = (PM_COL if state["direction"] == "rising"
                         else BM_COL if state["direction"] == "falling"
                         else MUTED)
            c.create_text(cx, cy + 14, text=now_s,
                          fill=TEXT, font=(FONT, 11, "bold"))
            c.create_text(cx, cy + 32, text=dir_label,
                          fill=dir_col, font=(FONT, 8))
        else:
            c.create_text(cx, cy + 18, fill=MUTED,
                          text="Première marée du jour",
                          font=(FONT, 7))

    def _get_clock_state(self):
        data, events = self.data, self.events
        now = datetime.now(PARIS)
        if not data:
            return {"angle": 0, "is_today": False,
                    "current_height": None, "direction": None}

        day_start = parse_local(data[0]["time"])
        is_today  = (day_start.date() == now.date())
        ref_time  = now if is_today else day_start

        # Interpolate current height
        current_height = None
        if is_today:
            ref_ms = now.timestamp()
            for i in range(len(data) - 1):
                t0 = parse_local(data[i]["time"]).timestamp()
                t1 = parse_local(data[i+1]["time"]).timestamp()
                if t0 <= ref_ms <= t1:
                    ratio = (ref_ms - t0) / (t1 - t0)
                    current_height = (data[i]["height"] +
                                      ratio * (data[i+1]["height"] - data[i]["height"]))
                    break

        ref_ms   = ref_time.timestamp()
        prev_ev  = next_ev = None
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
            prog = max(0.0, min(1.0, (ref_ms - pms) / (nms - pms)))
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
            is_pm = ev["type"] == "PM"
            color = PM_COL if is_pm else BM_COL
            label = "Pleine Mer" if is_pm else "Basse Mer"
            t_str = parse_local(ev["time"]).strftime("%H:%M")

            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", padx=10, pady=3, ipady=6)

            bar = tk.Frame(row, bg=color, width=4)
            bar.pack(side="left", fill="y")

            inner = tk.Frame(row, bg=BG)
            inner.pack(side="left", fill="both", expand=True, padx=10)

            badge = tk.Label(inner, text=ev["type"], bg=SURFACE, fg=color,
                             font=(FONT, 7, "bold"), padx=5, pady=2,
                             relief="solid", bd=1)
            badge.pack(side="left", padx=(0, 10))

            info = tk.Frame(inner, bg=BG)
            info.pack(side="left")
            tk.Label(info, text=t_str, fg=TEXT, bg=BG,
                     font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(info, text=f"{ev['height']:.2f} m – {label}",
                     fg=MUTED, bg=BG, font=(FONT, 8)).pack(anchor="w")

    # ── Chart with hover tooltip ───────────────────────────────────────────────
    def draw_chart(self, parent):
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="COURBE DE MARÉE", fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        # Naive datetimes for matplotlib (local time, no tz offset confusion)
        self._times_plain = [parse_local(d["time"]).replace(tzinfo=None) for d in self.data]
        self._heights     = [d["height"] for d in self.data]
        times, heights    = self._times_plain, self._heights

        self._fig, self._ax = plt.subplots(figsize=(12, 4.2), facecolor=SURFACE)
        ax = self._ax
        ax.set_facecolor(SURFACE)

        ax.fill_between(times, heights, alpha=0.15, color=ACCENT)
        ax.plot(times, heights, color=ACCENT, linewidth=2.4)

        # PM / BM markers
        pm_x, pm_y, bm_x, bm_y = [], [], [], []
        for ev in self.events:
            t = parse_local(ev["time"]).replace(tzinfo=None)
            h = ev["height"]
            if ev["type"] == "PM":
                pm_x.append(t); pm_y.append(h)
            else:
                bm_x.append(t); bm_y.append(h)
        ax.scatter(pm_x, pm_y, color=PM_COL, s=70, zorder=5, marker="^")
        ax.scatter(bm_x, bm_y, color=BM_COL, s=70, zorder=5, marker="D")

        # "Now" line (today only)
        today = datetime.now(PARIS).date()
        if self.current_date == today:
            now_plain = datetime.now(PARIS).replace(tzinfo=None)
            ax.axvline(now_plain, color="#f472b6", linewidth=1.4,
                       linestyle="--", alpha=0.9)
            for i in range(len(times) - 1):
                if times[i] <= now_plain <= times[i+1]:
                    ratio = (now_plain - times[i]) / (times[i+1] - times[i])
                    h_now = heights[i] + ratio * (heights[i+1] - heights[i])
                    ax.scatter([now_plain], [h_now], color="#f472b6", s=55, zorder=6)
                    break

        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlim(times[0].replace(hour=0, minute=0),
                    times[-1].replace(hour=23, minute=59))
        for sp in ax.spines.values():
            sp.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylabel("Hauteur (m)", color=MUTED, fontsize=9)
        ax.grid(True, color=BORDER, alpha=0.5, linewidth=0.6)

        legend_patches = [
            mpatches.Patch(color=ACCENT,  label="Hauteur (m)"),
            mpatches.Patch(color=PM_COL,  label="PM"),
            mpatches.Patch(color=BM_COL,  label="BM"),
        ]
        if self.current_date == today:
            legend_patches.append(mpatches.Patch(color="#f472b6", label="Maintenant"))
        ax.legend(handles=legend_patches, facecolor=SURFACE, edgecolor=BORDER,
                  labelcolor=MUTED, fontsize=8, loc="upper right")

        self._fig.tight_layout(pad=1.2)

        # ── Hover vertical line + tooltip ─────────────────────────────────────
        self._vline = ax.axvline(times[0], color=ACCENT, linewidth=1,
                                 linestyle=":", alpha=0, zorder=10)
        # Tooltip window (Toplevel, initially hidden)
        self._tooltip_win = tk.Toplevel(self.root)
        self._tooltip_win.withdraw()
        self._tooltip_win.overrideredirect(True)
        self._tooltip_win.configure(bg=BORDER)
        tip_inner = tk.Frame(self._tooltip_win, bg=SURFACE, padx=10, pady=6)
        tip_inner.pack(padx=1, pady=1)
        self._tip_time_lbl   = tk.Label(tip_inner, text="", fg=ACCENT,
                                        bg=SURFACE, font=(FONT, 9, "bold"))
        self._tip_time_lbl.pack(anchor="w")
        self._tip_height_lbl = tk.Label(tip_inner, text="", fg=TEXT,
                                        bg=SURFACE, font=(FONT, 9))
        self._tip_height_lbl.pack(anchor="w")

        mpl_canvas = FigureCanvasTkAgg(self._fig, card)
        mpl_canvas.draw()
        widget = mpl_canvas.get_tk_widget()
        widget.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        plt.close(self._fig)
        self._mpl_canvas = mpl_canvas

        # Bind mouse events on the matplotlib widget
        mpl_canvas.mpl_connect("motion_notify_event", self._on_chart_hover)
        mpl_canvas.mpl_connect("axes_leave_event",    self._on_chart_leave)

    def _on_chart_hover(self, event):
        if event.inaxes != self._ax:
            self._hide_tooltip()
            return
        # Convert mouse x (matplotlib date number) to datetime
        x_dt = mdates.num2date(event.xdata).replace(tzinfo=None)
        # Find nearest data point
        times, heights = self._times_plain, self._heights
        if not times:
            return
        # Interpolate height at cursor position
        best_i = min(range(len(times)), key=lambda i: abs((times[i] - x_dt).total_seconds()))
        # Linear interpolation for smoothness
        h_val = None
        for i in range(len(times) - 1):
            if times[i] <= x_dt <= times[i+1]:
                ratio = (x_dt - times[i]) / (times[i+1] - times[i])
                h_val = heights[i] + ratio * (heights[i+1] - heights[i])
                break
        if h_val is None:
            h_val = heights[best_i]

        # Move vertical guide line
        self._vline.set_xdata([x_dt, x_dt])
        self._vline.set_alpha(0.6)
        self._mpl_canvas.draw_idle()

        # Update tooltip labels
        self._tip_time_lbl.config(text=f"🕐  {x_dt.strftime('%H:%M')}")
        self._tip_height_lbl.config(text=f"📏  {h_val:.2f} m")

        # Position tooltip near cursor (screen coords)
        canvas_widget = self._mpl_canvas.get_tk_widget()
        root_x = canvas_widget.winfo_rootx() + int(event.x) + 14
        root_y = canvas_widget.winfo_rooty() + int(canvas_widget.winfo_height() - event.y) - 10
        self._tooltip_win.geometry(f"+{root_x}+{root_y}")
        self._tooltip_win.deiconify()
        self._tooltip_win.lift()

    def _on_chart_leave(self, event):
        self._hide_tooltip()

    def _hide_tooltip(self):
        if self._tooltip_win:
            self._tooltip_win.withdraw()
        if hasattr(self, "_vline"):
            self._vline.set_alpha(0)
            if self._mpl_canvas:
                self._mpl_canvas.draw_idle()

    # ── Live refresh (every 60 s, today only) ─────────────────────────────────
    def _schedule_live(self):
        self._live_job = self.root.after(60_000, self._live_tick)

    def _live_tick(self):
        # 1) Redraw clock hand
        if hasattr(self, "clock_canvas") and self.clock_canvas.winfo_exists():
            self.redraw_clock()
        # 2) Move the "Now" line + dot on the chart
        self._update_now_line()
        self._schedule_live()

    def _update_now_line(self):
        """Move the pink 'Maintenant' line and dot to the current time."""
        if not self._mpl_canvas or not self._ax:
            return
        if self.current_date != datetime.now(PARIS).date():
            return
        now_plain = datetime.now(PARIS).replace(tzinfo=None)

        # Remove previous now-line artists (tagged with gid="nowline")
        for art in list(self._ax.lines) + list(self._ax.collections):
            if getattr(art, "get_gid", lambda: None)() == "nowline":
                art.remove()

        self._ax.axvline(now_plain, color="#f472b6", linewidth=1.4,
                         linestyle="--", alpha=0.9, gid="nowline")

        times, heights = self._times_plain, self._heights
        for i in range(len(times) - 1):
            if times[i] <= now_plain <= times[i+1]:
                ratio = (now_plain - times[i]) / (times[i+1] - times[i])
                h_now = heights[i] + ratio * (heights[i+1] - heights[i])
                sc = self._ax.scatter([now_plain], [h_now],
                                      color="#f472b6", s=55, zorder=6)
                sc.set_gid("nowline")
                break

        self._mpl_canvas.draw_idle()

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
