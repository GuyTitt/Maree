"""Application pédagogique d'affichage des marées.

Ce module constitue un exemple complet d'application Python/Tkinter
utilisant une API REST externe, un cache JSON local, Matplotlib pour
les graphiques et le module ``zoneinfo`` pour la gestion des fuseaux
horaires.  Il est conçu pour illustrer les bonnes pratiques PEP 8 et
le style de documentation Google (Google Python Style Guide).

Dépendances::

    pip install requests matplotlib

Données :
    Les hauteurs d'eau sont fournies par l'API https://api-maree.fr,
    calculées à partir de composantes harmoniques IFREMER diffusées
    sous licence Creative Commons Attribution (BY).

Example::

    python claude07.py
"""

# ---------------------------------------------------------------------------
# Imports — bibliothèques standard d'abord, puis tierces, puis locales
# (règle PEP 8 §  Imports)
# ---------------------------------------------------------------------------
import json          # lecture/écriture du cache local
import math          # calculs trigonométriques pour l'horloge
import os            # création du répertoire de cache
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # gestion des fuseaux horaires (Python ≥ 3.9)

import matplotlib                                   # moteur de rendu à fixer AVANT pyplot
matplotlib.use("TkAgg")                             # intégration dans Tkinter
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import requests                                     # appels HTTP vers l'API
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

# --- API ---
API_BASE = "https://api-maree.fr"
API_KEY  = "0000000000000000000000000000000"

# --- Fuseau horaire ---
PARIS = ZoneInfo("Europe/Paris")

# --- Palette de couleurs (thème sombre) ---
BG      = "#0f172a"   # fond principal (bleu nuit très foncé)
SURFACE = "#1e293b"   # fond des cartes (bleu ardoise foncé)
BORDER  = "#334155"   # bordures et séparateurs
TEXT    = "#e2e8f0"   # texte principal (blanc doux)
MUTED   = "#94a3b8"   # texte secondaire (gris bleuté)
ACCENT  = "#38bdf8"   # couleur d'accentuation (bleu ciel)
ACCENT2 = "#0284c7"   # variante plus sombre de l'accent
PM_COL  = "#22d3ee"   # Pleine Mer  – cyan (montée)
BM_COL  = "#f97316"   # Basse Mer   – orange (descente)
ERROR   = "#f87171"   # messages d'erreur – rouge doux

# --- Typographie ---
FONT = "Segoe UI"     # police système Windows ; remplacée par le système sur macOS/Linux

# --- Mise en cache ---
os.makedirs("data", exist_ok=True)   # crée le dossier data/ si absent


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def parse_local(iso_str: str) -> datetime:
    """Convertit une chaîne ISO-8601 en ``datetime`` conservant l'offset local.

    L'API renvoie des timestamps avec offset explicite, par ex.
    ``2026-04-12T00:00:00+02:00``.  ``fromisoformat`` lit cet offset et
    retourne un ``datetime`` *aware* sans jamais convertir en UTC.
    Ainsi ``00:00+02:00`` reste affiché ``00:00`` en heure locale.

    Args:
        iso_str: Chaîne au format ISO-8601, avec ou sans offset.

    Returns:
        Un objet ``datetime`` aware si l'offset est présent, naïf sinon.
    """
    return datetime.fromisoformat(iso_str)


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class TideApp:
    """Application Tkinter d'affichage des marées.

    Cette classe orchestre l'ensemble de l'interface : en-tête de navigation,
    calendrier mini, horloge de marée animée, panneau des événements PM/BM et
    graphique Matplotlib interactif.

    Attributes:
        root (tk.Tk): Fenêtre Tkinter principale.
        current_date (date): Date actuellement affichée.
        data (list[dict]): Points de hauteur d'eau chargés depuis l'API ou le cache.
        events (list[dict]): Événements PM/BM détectés pour la journée.
        _live_job (str | None): Identifiant du callback ``after`` pour la mise à
            jour toutes les 60 secondes (``None`` si pas planifié).
        _cal_year (int): Année affichée dans le mini-calendrier.
        _cal_month (int): Mois affiché dans le mini-calendrier.
        _tooltip_win (tk.Toplevel | None): Fenêtre flottante de la bulle d'info
            sur le graphique.
        _times_plain (list[datetime]): Timestamps naïfs (sans tz) pour Matplotlib.
        _heights (list[float]): Hauteurs d'eau correspondantes.
        _fig (Figure | None): Figure Matplotlib du graphique.
        _ax (Axes | None): Axes Matplotlib du graphique.
        _mpl_canvas (FigureCanvasTkAgg | None): Canevas d'intégration Matplotlib/Tk.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialise l'application et lance le chargement des ports.

        Args:
            root: Fenêtre Tkinter racine créée par le bloc ``__main__``.
        """
        self.root = root
        self.root.title("Marées – Hauteurs d'eau")
        self.root.configure(bg=BG)

        # Date de travail : aujourd'hui en heure de Paris
        self.current_date = datetime.now(PARIS).date()

        # Données de la journée (chargées depuis l'API ou le cache)
        self.data: list[dict] = []
        self.events: list[dict] = []

        # Gestion de la mise à jour automatique (horloge + graphique)
        self._live_job: str | None = None

        # Navigation mensuelle du mini-calendrier
        self._cal_year: int | None = None
        self._cal_month: int | None = None

        # État de la bulle d'info du graphique
        self._tooltip_win: tk.Toplevel | None = None
        self._times_plain: list[datetime] = []
        self._heights: list[float] = []

        # Références Matplotlib (créées dans draw_chart)
        self._fig = None
        self._ax = None
        self._mpl_canvas = None

        # Construction de l'interface puis chargement des ports
        self.create_ui()
        self.load_sites()

    # ------------------------------------------------------------------
    # Construction de l'interface principale
    # ------------------------------------------------------------------

    def create_ui(self) -> None:
        """Crée le squelette de l'interface : en-tête + zone scrollable.

        L'en-tête contient le titre, le sélecteur de port et les boutons
        de navigation par date.  La zone scrollable accueille les trois
        cartes (calendrier, horloge, marées) et le graphique.
        """
        # ── En-tête ────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=SURFACE)
        header.pack(fill="x")

        tk.Label(
            header, text="🌊  Marées",
            font=(FONT, 16, "bold"), fg=ACCENT, bg=SURFACE
        ).pack(side="left", padx=20, pady=10)

        ctrl = tk.Frame(header, bg=SURFACE)
        ctrl.pack(side="right", padx=16)

        # Combobox de sélection du port
        self.port_combo = ttk.Combobox(ctrl, width=32, state="readonly", font=(FONT, 9))
        self.port_combo.pack(side="left", padx=4)
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        # Navigation par date (◀ date ▶ Aujourd'hui)
        nav = tk.Frame(ctrl, bg=SURFACE)
        nav.pack(side="left", padx=6)
        btn_style = dict(
            bg=BORDER, fg=TEXT, relief="flat",
            activebackground=ACCENT2, activeforeground="white",
            bd=0, padx=8, pady=4, cursor="hand2",
        )
        tk.Button(nav, text="◀", **btn_style, command=self.prev_day).pack(side="left", padx=2)
        self.date_label = tk.Label(
            nav, text=self.current_date.strftime("%Y-%m-%d"),
            fg=TEXT, bg=SURFACE, font=(FONT, 9), width=12,
        )
        self.date_label.pack(side="left", padx=6)
        tk.Button(nav, text="▶", **btn_style, command=self.next_day).pack(side="left", padx=2)
        tk.Button(
            nav, text="Aujourd'hui",
            bg=ACCENT2, fg="white", relief="flat",
            activebackground=ACCENT, activeforeground="white",
            bd=0, padx=10, pady=4, cursor="hand2",
            command=self.today,
        ).pack(side="left", padx=(8, 0))

        # ── Zone scrollable ────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        # Canvas principal + scrollbar verticale
        self.canvas_main = tk.Canvas(body, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas_main.yview)
        self.scrollable_frame = tk.Frame(self.canvas_main, bg=BG)

        # Mise à jour de la scrollregion quand le contenu change de taille
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas_main.configure(
                scrollregion=self.canvas_main.bbox("all")
            ),
        )
        self._win = self.canvas_main.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas_main.configure(yscrollcommand=vbar.set)

        # Le frame interne suit la largeur du canvas (pour les grids responsive)
        self.canvas_main.bind(
            "<Configure>",
            lambda e: self.canvas_main.itemconfig(self._win, width=e.width),
        )

        # Support de la molette souris (Windows)
        self.canvas_main.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas_main.yview_scroll(int(-e.delta / 120), "units"),
        )

        self.canvas_main.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        self.show_status("Chargement…")

    # ------------------------------------------------------------------
    # Helpers génériques
    # ------------------------------------------------------------------

    def show_status(self, text: str, color: str = MUTED) -> None:
        """Remplace le contenu de la zone scrollable par un message centré.

        Args:
            text: Message à afficher.
            color: Couleur du texte (code hexadécimal Tkinter).
        """
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        tk.Label(
            self.scrollable_frame, text=text,
            fg=color, bg=BG, font=(FONT, 12),
        ).pack(expand=True, pady=120)

    def _card(self, parent: tk.Widget, **kwargs) -> tk.Frame:
        """Crée un ``Frame`` avec le style « carte » (fond sombre + bordure).

        Args:
            parent: Widget Tkinter parent.
            **kwargs: Arguments supplémentaires transmis à ``tk.Frame``.

        Returns:
            Le ``Frame`` créé, non encore placé dans la grille/pack.
        """
        return tk.Frame(parent, bg=SURFACE, bd=1, relief="solid", **kwargs)

    # ------------------------------------------------------------------
    # Chargement des ports (API)
    # ------------------------------------------------------------------

    def load_sites(self) -> None:
        """Récupère la liste des ports depuis l'API et peuple le combobox.

        En cas d'erreur réseau, affiche un message d'erreur à l'écran.
        Le port « boulogne-sur-mer » est sélectionné par défaut s'il est
        disponible.
        """
        try:
            response = requests.get(f"{API_BASE}/sites?key={API_KEY}", timeout=10)
            sites = sorted(response.json().get("sites", []), key=lambda s: s["name"])
            self.port_combo["values"] = [f"{s['site_id']} | {s['name']}" for s in sites]

            # Sélection du port par défaut
            default = next(
                (s for s in sites if s["site_id"] == "boulogne-sur-mer"),
                sites[0],
            )
            self.port_combo.set(f"{default['site_id']} | {default['name']}")
            self.load_data()
        except Exception as exc:  # noqa: BLE001
            self.show_status(f"Erreur chargement ports : {exc}", ERROR)

    def get_site_id(self) -> str:
        """Extrait l'identifiant du port sélectionné depuis le combobox.

        Returns:
            Chaîne ``site_id`` de l'API (ex : ``"boulogne-sur-mer"``).
        """
        return self.port_combo.get().split(" | ")[0]

    # ------------------------------------------------------------------
    # Chargement et traitement des données
    # ------------------------------------------------------------------

    def get_cache_path(self, site_id: str) -> str:
        """Retourne le chemin du fichier cache JSON pour un port et une date.

        Args:
            site_id: Identifiant du port.

        Returns:
            Chemin relatif du fichier cache, ex ``data/boulogne_2026-04-12.json``.
        """
        return f"data/{site_id}_{self.current_date.isoformat()}.json"

    def load_data(self) -> None:
        """Déclenche le chargement des données avec un délai de 80 ms.

        Le délai permet à Tkinter de redessiner l'écran (afficher « Chargement… »)
        avant le blocage réseau éventuel.
        """
        self.show_status("Chargement…")
        if self._live_job:
            self.root.after_cancel(self._live_job)
            self._live_job = None
        self.root.after(80, self.fetch_and_render)

    def fetch_and_render(self) -> None:
        """Charge les hauteurs d'eau (cache ou API) puis déclenche le rendu.

        Stratégie de cache :
            1. Si un fichier JSON existe pour ce port/date → lecture locale.
            2. Sinon → requête API + sauvegarde du résultat.

        En cas d'erreur réseau, un message est affiché sans planter l'app.
        """
        site_id    = self.get_site_id()
        cache_file = self.get_cache_path(site_id)

        if os.path.exists(cache_file):
            # Lecture depuis le cache local (pas de requête réseau)
            with open(cache_file, encoding="utf-8") as f:
                self.data = json.load(f).get("data", [])
        else:
            # Requête vers l'API et mise en cache
            try:
                ds  = self.current_date.isoformat()
                url = (
                    f"{API_BASE}/water-levels?site={site_id}"
                    f"&from={ds}T00:00&to={ds}T23:59"
                    f"&step=10&tz=Europe/Paris&key={API_KEY}"
                )
                self.data = requests.get(url, timeout=15).json().get("data", [])
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "data": self.data}, f,
                              ensure_ascii=False, indent=2)
            except Exception as exc:  # noqa: BLE001
                self.show_status(f"Erreur réseau : {exc}", ERROR)
                return

        self.events = self._find_events()
        self.render_all()

    def _find_events(self) -> list[dict]:
        """Détecte les événements de Pleine Mer et Basse Mer dans la série.

        L'algorithme recherche les extrema locaux (maximum → PM, minimum → BM).
        Un mécanisme de déduplication élimine les plateaux (plusieurs points
        consécutifs du même type espacés de moins de 30 min).

        Returns:
            Liste de dicts ``{"type": "PM"|"BM", "time": str, "height": float}``
            triée chronologiquement.
        """
        data = self.data
        raw: list[dict] = []

        for i in range(1, len(data) - 1):
            prev_h = data[i - 1]["height"]
            curr_h = data[i]["height"]
            next_h = data[i + 1]["height"]

            # Maximum local → Pleine Mer
            if curr_h >= prev_h and curr_h >= next_h and (curr_h > prev_h or curr_h > next_h):
                raw.append({"type": "PM", "time": data[i]["time"], "height": curr_h})
            # Minimum local → Basse Mer
            elif curr_h <= prev_h and curr_h <= next_h and (curr_h < prev_h or curr_h < next_h):
                raw.append({"type": "BM", "time": data[i]["time"], "height": curr_h})

        # Déduplication des plateaux (deux événements du même type < 30 min d'écart)
        deduped: list[dict] = []
        for ev in raw:
            last = deduped[-1] if deduped else None
            if last and last["type"] == ev["type"]:
                diff_min = (
                    (parse_local(ev["time"]) - parse_local(last["time"])).total_seconds() / 60
                )
                if diff_min <= 30:
                    # On garde l'événement le plus extrême du plateau
                    if (ev["type"] == "PM" and ev["height"] > last["height"]) or (
                        ev["type"] == "BM" and ev["height"] < last["height"]
                    ):
                        deduped[-1] = ev
                    continue
            deduped.append(ev)

        return deduped

    # ------------------------------------------------------------------
    # Rendu principal
    # ------------------------------------------------------------------

    def render_all(self) -> None:
        """Reconstruit l'intégralité de la zone scrollable.

        Dispose trois cartes en grille (calendrier | horloge | marées)
        puis ajoute le graphique en dessous.  Lance le timer de mise à
        jour automatique si la date affichée est aujourd'hui.
        """
        # Nettoyage des widgets précédents
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self._mpl_canvas = None

        if not self.data:
            self.show_status("Aucune donnée", ERROR)
            return

        # ── Ligne supérieure : 3 cartes en grille responsive ───────────
        top = tk.Frame(self.scrollable_frame, bg=BG)
        top.pack(fill="x", padx=16, pady=(16, 0))
        top.columnconfigure(0, weight=1)   # les 3 colonnes se partagent l'espace
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

        # ── Graphique ───────────────────────────────────────────────────
        chart_wrap = tk.Frame(self.scrollable_frame, bg=BG)
        chart_wrap.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self.draw_chart(chart_wrap)

        # Démarrage du timer de rafraîchissement (horloge + trait « Maintenant »)
        if self.current_date == datetime.now(PARIS).date():
            self._schedule_live()

    # ------------------------------------------------------------------
    # Mini-calendrier
    # ------------------------------------------------------------------

    def draw_calendar(self, parent: tk.Frame) -> None:
        """Initialise le mini-calendrier sur le mois de la date courante.

        Args:
            parent: Frame carte qui accueille le calendrier.
        """
        self._cal_year  = self.current_date.year
        self._cal_month = self.current_date.month
        self._render_calendar(parent)

    def _render_calendar(self, parent: tk.Frame) -> None:
        """(Re)dessine le contenu du calendrier (appelé aussi lors du changement de mois).

        Utilise un ``tk.Canvas`` par cellule pour simuler des coins arrondis
        sur les boutons de jour, ce qui n'est pas nativement supporté par Tkinter.
        Chaque cellule est un canvas cliquable avec un rectangle à coins arrondis.

        Args:
            parent: Frame carte contenant le calendrier.
        """
        # Suppression des widgets existants avant de reconstruire
        for widget in parent.winfo_children():
            widget.destroy()

        year, month = self._cal_year, self._cal_month
        today = datetime.now(PARIS).date()
        sel   = self.current_date

        month_names = [
            "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
        ]

        # ── Ligne de navigation du mois ──────────────────────────────
        hdr = tk.Frame(parent, bg=SURFACE)
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        nav_btn_style = dict(
            bg=BORDER, fg=TEXT, relief="flat", bd=0,
            padx=6, pady=2, cursor="hand2",
            activebackground=ACCENT2, activeforeground="white",
        )
        tk.Button(
            hdr, text="◀", **nav_btn_style,
            command=lambda: self._cal_shift(parent, -1),
        ).pack(side="left")
        tk.Label(
            hdr, text=f"{month_names[month - 1]} {year}",
            fg=TEXT, bg=SURFACE, font=(FONT, 10, "bold"),  # police agrandie
        ).pack(side="left", expand=True)
        tk.Button(
            hdr, text="▶", **nav_btn_style,
            command=lambda: self._cal_shift(parent, 1),
        ).pack(side="right")

        # ── En-têtes des jours de la semaine ─────────────────────────
        wk_frame = tk.Frame(parent, bg=SURFACE)
        wk_frame.pack()
        cell_w = 36   # largeur d'une cellule en pixels
        for day_abbr in ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]:
            tk.Label(
                wk_frame, text=day_abbr,
                fg=MUTED, bg=SURFACE,
                font=(FONT, 8),   # police agrandie vs. ancienne (7)
                width=4, anchor="center",
            ).pack(side="left")

        # ── Grille des jours ─────────────────────────────────────────
        grid_frame = tk.Frame(parent, bg=SURFACE)
        grid_frame.pack(pady=2)

        # Calcul du premier jour de la semaine (0=Lundi … 6=Dimanche)
        first_weekday = datetime(year, month, 1).weekday()

        # Nombre de jours dans le mois (calcul générique gérant décembre)
        next_month_first = datetime(
            year + (month == 12), (month % 12) + 1, 1
        )
        days_in_month = (next_month_first - timedelta(days=1)).day

        # La grille est construite ligne par ligne (7 colonnes = 7 jours)
        row_frame = tk.Frame(grid_frame, bg=SURFACE)
        row_frame.pack(anchor="center")

        # Cellules vides pour aligner le premier jour sur le bon jour de semaine
        for _ in range(first_weekday):
            self._make_day_cell(row_frame, text="", cell_date=None,
                                is_sel=False, is_today=False)

        for day_num in range(1, days_in_month + 1):
            # Passage à la ligne suivante tous les 7 jours
            if len(row_frame.winfo_children()) == 7:
                row_frame = tk.Frame(grid_frame, bg=SURFACE)
                row_frame.pack(anchor="center")

            cell_date = datetime(year, month, day_num).date()
            self._make_day_cell(
                row_frame,
                text=str(day_num),
                cell_date=cell_date,
                is_sel=(cell_date == sel),
                is_today=(cell_date == today),
            )

    def _make_day_cell(
        self,
        parent: tk.Frame,
        text: str,
        cell_date,
        is_sel: bool,
        is_today: bool,
    ) -> None:
        """Crée une cellule de jour dans le calendrier avec canvas arrondi.

        Chaque cellule est un ``tk.Canvas`` de taille fixe.  Un rectangle
        à coins arrondis (simulé par ``create_arc`` + ``create_rectangle``)
        sert de fond, coloré selon l'état du jour.

        Args:
            parent: Ligne (Frame) de la grille qui accueille la cellule.
            text: Numéro du jour à afficher (chaîne vide pour les cases vides).
            cell_date: Objet ``date`` correspondant (None pour les cases vides).
            is_sel: True si ce jour est la date sélectionnée.
            is_today: True si ce jour est aujourd'hui.
        """
        cell_size = 36   # hauteur et largeur en pixels

        # Couleurs selon l'état de la cellule
        if is_sel:
            bg_fill   = ACCENT2        # fond bleu sélectionné
            fg_text   = "white"
            border_c  = ACCENT         # bordure claire
            cell_bg   = ACCENT2        # fond du canvas
        elif is_today:
            bg_fill   = "#1e3a5f"      # fond légèrement bleuté
            fg_text   = ACCENT
            border_c  = ACCENT
            cell_bg   = "#1e3a5f"
        elif text == "":
            # Cellule vide (avant le 1er jour du mois)
            cv = tk.Canvas(parent, width=cell_size, height=cell_size,
                           bg=SURFACE, highlightthickness=0)
            cv.pack(side="left", padx=1, pady=1)
            return
        else:
            bg_fill   = "#243044"      # fond discret légèrement différent de SURFACE
            fg_text   = MUTED
            border_c  = MUTED
            cell_bg   = "#243044"

        # Canvas servant de bouton (pas de relief natif → simulation)
        cv = tk.Canvas(
            parent, width=cell_size, height=cell_size,
            bg=SURFACE, highlightthickness=0, cursor="hand2",
        )
        cv.pack(side="left", padx=1, pady=1)

        # Rayon des coins arrondis
        r = 6
        x0, y0, x1, y1 = 1, 1, cell_size - 1, cell_size - 1

        # Dessin du rectangle arrondi (8 segments : 4 arcs + 4 lignes droites)
        cv.create_arc(x0,       y0,       x0+2*r, y0+2*r, start=90,  extent=90,  fill=bg_fill, outline=border_c, width=1)
        cv.create_arc(x1-2*r,   y0,       x1,     y0+2*r, start=0,   extent=90,  fill=bg_fill, outline=border_c, width=1)
        cv.create_arc(x0,       y1-2*r,   x0+2*r, y1,     start=180, extent=90,  fill=bg_fill, outline=border_c, width=1)
        cv.create_arc(x1-2*r,   y1-2*r,   x1,     y1,     start=270, extent=90,  fill=bg_fill, outline=border_c, width=1)
        cv.create_rectangle(x0+r, y0,   x1-r, y1,   fill=bg_fill, outline="")
        cv.create_rectangle(x0,   y0+r, x1,   y1-r, fill=bg_fill, outline="")
        cv.create_line(x0+r, y0,   x1-r, y0,   fill=border_c, width=1)
        cv.create_line(x0+r, y1,   x1-r, y1,   fill=border_c, width=1)
        cv.create_line(x0,   y0+r, x0,   y1-r, fill=border_c, width=1)
        cv.create_line(x1,   y0+r, x1,   y1-r, fill=border_c, width=1)

        # Numéro du jour, centré
        cv.create_text(
            cell_size // 2, cell_size // 2,
            text=text, fill=fg_text,
            font=(FONT, 9, "bold" if is_sel or is_today else ""),
            anchor="center",
        )

        # Gestion du clic
        if cell_date is not None:
            cv.bind("<Button-1>", lambda e, cd=cell_date: self._pick_date(cd))

        # Effet de survol : bordure plus lumineuse
        def _on_enter(e):
            if not is_sel:
                cv.itemconfig("all", fill=ACCENT if not is_today else ACCENT)

        def _on_leave(e):
            pass   # le canvas est reconstruit à chaque navigation, pas besoin de restaurer

    def _cal_shift(self, parent: tk.Frame, offset: int) -> None:
        """Fait avancer ou reculer le mini-calendrier d'un mois.

        Args:
            parent: Frame carte du calendrier (pour le re-rendu).
            offset: +1 pour le mois suivant, -1 pour le mois précédent.
        """
        month = self._cal_month + offset
        year  = self._cal_year
        if month > 12:
            month, year = 1, year + 1
        if month < 1:
            month, year = 12, year - 1
        self._cal_year, self._cal_month = year, month
        self._render_calendar(parent)

    def _pick_date(self, date_obj) -> None:
        """Sélectionne une nouvelle date et recharge les données.

        Args:
            date_obj: Objet ``date`` de la cellule cliquée.
        """
        self.current_date = date_obj
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    # ------------------------------------------------------------------
    # Horloge de marée
    # ------------------------------------------------------------------

    def draw_clock(self, parent: tk.Frame) -> None:
        """Crée le canevas de l'horloge et planifie le premier dessin.

        Le dessin est différé de 50 ms via ``after`` afin que Tkinter ait
        le temps de calculer les dimensions réelles du canvas avant qu'on
        l'utilise.

        Args:
            parent: Frame carte de l'horloge.
        """
        tk.Label(
            parent, text="Horloge de marée",
            fg=MUTED, bg=SURFACE, font=(FONT, 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 2))

        self.clock_canvas = tk.Canvas(parent, bg=SURFACE, highlightthickness=0)
        self.clock_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # On force la mise à jour des dimensions avant le premier dessin
        self.root.update()
        self.root.after(50, self.redraw_clock)

    def redraw_clock(self) -> None:
        """Redessine entièrement l'horloge de marée sur son canevas.

        L'horloge est un cadran circulaire dont l'aiguille indique la
        position dans le cycle semi-lunaire (PM en haut, BM en bas).
        Les graduations sont étiquetées avec l'heure réelle ancrée sur
        la première PM de la journée.

        Cette méthode est appelée au démarrage puis toutes les 60 s
        par ``_live_tick``.
        """
        if not hasattr(self, "clock_canvas") or not self.clock_canvas.winfo_exists():
            return

        c = self.clock_canvas
        c.update_idletasks()
        W = c.winfo_width()  or 280
        H = c.winfo_height() or 280
        c.delete("all")   # effacement complet avant de redessiner

        # Géométrie du cadran
        cx, cy = W // 2, H // 2 - 14
        r = min(W, H) // 2 - 18

        # État courant (angle de l'aiguille, hauteur, direction…)
        state = self._get_clock_state()

        # ── Fond du cadran ────────────────────────────────────────────
        c.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
                      fill=BORDER, outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=SURFACE, outline="#475569", width=2)

        # ── Arcs colorés (fins pour laisser la place aux étiquettes) ──
        # Demi-cercle droit : descente PM → BM (orange)
        ar    = r - 8
        arc_w = 5
        c.create_arc(cx - ar, cy - ar, cx + ar, cy + ar,
                     start=-90, extent=-180, style="arc",
                     outline=BM_COL, width=arc_w)
        # Demi-cercle gauche : montée BM → PM (cyan)
        c.create_arc(cx - ar, cy - ar, cx + ar, cy + ar,
                     start=90, extent=-180, style="arc",
                     outline=PM_COL, width=arc_w)

        # ── Graduations et étiquettes horaires ────────────────────────
        # On ancre les heures sur la première PM de la journée.
        pm_events   = [e for e in self.events if e["type"] == "PM"]
        first_pm_dt = parse_local(pm_events[0]["time"]) if pm_events else None

        for i in range(24):
            # angle_deg : 0° = sommet (PM), sens horaire
            ang_deg  = i * 15 - 90
            ang_rad  = math.radians(ang_deg)
            is_major = (i % 2 == 0)   # graduation majeure toutes les 30° (≈ 1 h)

            # Trait de graduation
            tick_out = r - 12
            tick_in  = tick_out - (10 if is_major else 6)
            c.create_line(
                cx + math.cos(ang_rad) * tick_in,
                cy + math.sin(ang_rad) * tick_in,
                cx + math.cos(ang_rad) * tick_out,
                cy + math.sin(ang_rad) * tick_out,
                fill="#64748b", width=2 if is_major else 1,
            )

            # Étiquette horaire (ex. "11:30") aux graduations majeures
            if is_major and first_pm_dt:
                tide_hour = i // 2   # 0 = PM, 6 = +6h ≈ BM, 12 = PM suivante
                label_dt  = first_pm_dt + timedelta(hours=tide_hour)
                if tide_hour <= 12:
                    label_x = cx + math.cos(ang_rad) * (r - 28)
                    label_y = cy + math.sin(ang_rad) * (r - 28)
                    c.create_text(
                        label_x, label_y,
                        text=label_dt.strftime("%H:%M"),
                        fill="#64748b", font=(FONT, 6),
                    )

        # ── Étiquettes PM / BM fixées au sommet et au bas ─────────────
        c.create_text(cx, cy - r + 10, text="PM", fill=PM_COL, font=(FONT, 8, "bold"))
        c.create_text(cx, cy + r - 10, text="BM", fill=BM_COL, font=(FONT, 8, "bold"))

        # ── Hauteur instantanée à l'intérieur du cadran ───────────────
        # Couleur : cyan pendant la descente (PM → BM), orange pendant la montée (BM → PM)
        if state["is_today"] and state["current_height"] is not None:
            height_color = (
                PM_COL if state["direction"] == "falling"
                else BM_COL if state["direction"] == "rising"
                else ACCENT
            )
            c.create_text(
                cx, cy - 14,
                text=f"{state['current_height']:.2f} m",
                fill=height_color, font=(FONT, 14, "bold"),
            )

        # ── Aiguille — blanche/gris clair ────────────────────────────
        hand_rad = math.radians(state["angle"] - 90)
        hand_len = r - 30
        hx = cx + math.cos(hand_rad) * hand_len
        hy = cy + math.sin(hand_rad) * hand_len

        c.create_line(cx + 1, cy + 1, hx + 2, hy + 2,
                      fill="#0a1020", width=5, capstyle="round")    # ombre
        c.create_line(cx, cy, hx, hy,
                      fill="#dde6f0", width=3, capstyle="round")    # aiguille blanche
        c.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill="#dde6f0", outline="")
        c.create_oval(cx - 7, cy - 7, cx + 7, cy + 7,
                      fill=SURFACE, outline="#dde6f0", width=2)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#dde6f0", outline="")

        # ── Heure et direction sous le centre ─────────────────────────
        if state["is_today"] and state["current_height"] is not None:
            direction = state["direction"]
            dir_label = (
                "▲ Montante"   if direction == "rising"
                else "▼ Descendante" if direction == "falling"
                else ""
            )
            dir_color = (
                PM_COL  if direction == "rising"
                else BM_COL if direction == "falling"
                else MUTED
            )
            # Heure actuelle (actualisée à chaque appel de redraw_clock)
            c.create_text(cx, cy + 14,
                          text=datetime.now(PARIS).strftime("%H:%M"),
                          fill=TEXT, font=(FONT, 11, "bold"))
            c.create_text(cx, cy + 32,
                          text=dir_label, fill=dir_color, font=(FONT, 8))
        else:
            c.create_text(cx, cy + 18,
                          text="Première marée du jour",
                          fill=MUTED, font=(FONT, 7))

    def _get_clock_state(self) -> dict:
        """Calcule l'état courant de l'horloge de marée.

        Détermine :

        * l'angle de l'aiguille (0° = PM en haut, 180° = BM en bas) ;
        * la hauteur d'eau interpolée à l'instant présent ;
        * la direction (montante / descendante).

        Returns:
            Dictionnaire avec les clés :
            ``angle`` (float), ``is_today`` (bool),
            ``current_height`` (float | None), ``direction`` (str | None).
        """
        data, events = self.data, self.events
        now = datetime.now(PARIS)

        # Valeur par défaut si pas de données
        if not data:
            return {"angle": 0, "is_today": False,
                    "current_height": None, "direction": None}

        day_start = parse_local(data[0]["time"])
        is_today  = day_start.date() == now.date()
        ref_time  = now if is_today else day_start

        # ── Interpolation de la hauteur à l'instant ``now`` ──────────
        current_height = None
        if is_today:
            ref_ts = now.timestamp()
            for i in range(len(data) - 1):
                t0 = parse_local(data[i]["time"]).timestamp()
                t1 = parse_local(data[i + 1]["time"]).timestamp()
                if t0 <= ref_ts <= t1:
                    ratio = (ref_ts - t0) / (t1 - t0)
                    current_height = (
                        data[i]["height"] + ratio * (data[i + 1]["height"] - data[i]["height"])
                    )
                    break

        # ── Événements encadrant l'heure de référence ─────────────────
        ref_ts   = ref_time.timestamp()
        prev_ev  = next_ev = None
        for ev in events:
            ev_ts = parse_local(ev["time"]).timestamp()
            if ev_ts <= ref_ts:
                prev_ev = ev
            elif next_ev is None:
                next_ev = ev

        # ── Direction de la marée ──────────────────────────────────────
        direction = None
        if prev_ev and next_ev:
            direction = "rising"  if next_ev["type"] == "PM" else "falling"
        elif prev_ev:
            direction = "falling" if prev_ev["type"] == "PM" else "rising"
        elif next_ev:
            direction = "rising"  if next_ev["type"] == "PM" else "falling"

        # ── Angle de l'aiguille ───────────────────────────────────────
        # PM → BM : 0° → 180° (demi-tour droit, sens horaire)
        # BM → PM : 180° → 360° (demi-tour gauche, sens horaire)
        angle = 0.0
        if prev_ev and next_ev:
            pms  = parse_local(prev_ev["time"]).timestamp()
            nms  = parse_local(next_ev["time"]).timestamp()
            prog = max(0.0, min(1.0, (ref_ts - pms) / (nms - pms)))
            angle = prog * 180 if prev_ev["type"] == "PM" else 180 + prog * 180
        elif prev_ev:
            angle = 30  if prev_ev["type"] == "PM" else 210
        elif next_ev:
            angle = 330 if next_ev["type"] == "PM" else 150

        return {
            "angle": angle,
            "is_today": is_today,
            "current_height": current_height,
            "direction": direction,
        }

    # ------------------------------------------------------------------
    # Panneau des événements PM / BM
    # ------------------------------------------------------------------

    def draw_events(self, parent: tk.Frame) -> None:
        """Affiche la liste des événements PM/BM de la journée.

        Chaque événement est représenté par une ligne colorée avec :
        une barre verticale indiquant le type, un badge PM/BM,
        l'heure en grand et la hauteur en mètres.

        Args:
            parent: Frame carte des marées du jour.
        """
        tk.Label(
            parent, text="Marées du jour",
            fg=MUTED, bg=SURFACE, font=(FONT, 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 4))

        if not self.events:
            tk.Label(parent, text="Aucune marée détectée.",
                     fg=MUTED, bg=SURFACE, font=(FONT, 9)).pack(padx=12)
            return

        for ev in self.events:
            is_pm = ev["type"] == "PM"
            color = PM_COL if is_pm else BM_COL
            label = "Pleine Mer" if is_pm else "Basse Mer"
            t_str = parse_local(ev["time"]).strftime("%H:%M")

            # Ligne d'événement
            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", padx=10, pady=3, ipady=6)

            # Barre colorée à gauche (indicateur visuel PM vs BM)
            tk.Frame(row, bg=color, width=4).pack(side="left", fill="y")

            inner = tk.Frame(row, bg=BG)
            inner.pack(side="left", fill="both", expand=True, padx=10)

            # Badge « PM » ou « BM »
            tk.Label(
                inner, text=ev["type"],
                bg=SURFACE, fg=color,
                font=(FONT, 7, "bold"), padx=5, pady=2,
                relief="solid", bd=1,
            ).pack(side="left", padx=(0, 10))

            # Heure et hauteur
            info = tk.Frame(inner, bg=BG)
            info.pack(side="left")
            tk.Label(info, text=t_str, fg=TEXT, bg=BG,
                     font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(info, text=f"{ev['height']:.2f} m – {label}",
                     fg=MUTED, bg=BG, font=(FONT, 8)).pack(anchor="w")

    # ------------------------------------------------------------------
    # Graphique Matplotlib avec bulle d'info au survol
    # ------------------------------------------------------------------

    def draw_chart(self, parent: tk.Widget) -> None:
        """Construit et affiche le graphique de la courbe de marée.

        Fonctionnalités :
        * Courbe lissée avec remplissage semi-transparent.
        * Marqueurs ▲ (PM) et ◆ (BM) positionnés sur les extrema.
        * Ligne verticale rose « Maintenant » (aujourd'hui uniquement).
        * Ligne verticale de survol + bulle d'info (heure, hauteur).

        Args:
            parent: Widget parent dans lequel placer la carte du graphique.
        """
        card = self._card(parent)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="COURBE DE MARÉE", fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        # Timestamps naïfs (sans offset) pour éviter les conflits tz avec Matplotlib
        self._times_plain = [parse_local(d["time"]).replace(tzinfo=None) for d in self.data]
        self._heights     = [d["height"] for d in self.data]
        times, heights    = self._times_plain, self._heights

        # ── Figure Matplotlib ─────────────────────────────────────────
        self._fig, self._ax = plt.subplots(figsize=(12, 4.2), facecolor=SURFACE)
        ax = self._ax
        ax.set_facecolor(SURFACE)

        # Remplissage semi-transparent sous la courbe
        ax.fill_between(times, heights, alpha=0.15, color=ACCENT)
        ax.plot(times, heights, color=ACCENT, linewidth=2.4)

        # ── Marqueurs PM / BM ─────────────────────────────────────────
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

        # ── Repère « Maintenant » (aujourd'hui seulement) ─────────────
        today = datetime.now(PARIS).date()
        if self.current_date == today:
            now_plain = datetime.now(PARIS).replace(tzinfo=None)
            ax.axvline(now_plain, color="#f472b6", linewidth=1.4,
                       linestyle="--", alpha=0.9, gid="nowline")
            # Point sur la courbe à l'heure actuelle (interpolation linéaire)
            for i in range(len(times) - 1):
                if times[i] <= now_plain <= times[i + 1]:
                    ratio = (now_plain - times[i]) / (times[i + 1] - times[i])
                    h_now = heights[i] + ratio * (heights[i + 1] - heights[i])
                    sc = ax.scatter([now_plain], [h_now], color="#f472b6", s=55, zorder=6)
                    sc.set_gid("nowline")
                    break

        # ── Axes et style ─────────────────────────────────────────────
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlim(
            times[0].replace(hour=0, minute=0),
            times[-1].replace(hour=23, minute=59),
        )
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylabel("Hauteur (m)", color=MUTED, fontsize=9)
        ax.grid(True, color=BORDER, alpha=0.5, linewidth=0.6)

        # ── Légende ───────────────────────────────────────────────────
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

        # ── Ligne de survol (invisible par défaut) ────────────────────
        self._vline = ax.axvline(times[0], color=ACCENT, linewidth=1,
                                 linestyle=":", alpha=0, zorder=10)

        # ── Bulle d'info (fenêtre Toplevel sans décoration) ───────────
        self._tooltip_win = tk.Toplevel(self.root)
        self._tooltip_win.withdraw()                   # cachée au départ
        self._tooltip_win.overrideredirect(True)       # pas de barre de titre
        self._tooltip_win.configure(bg=BORDER)
        tip_inner = tk.Frame(self._tooltip_win, bg=SURFACE, padx=10, pady=6)
        tip_inner.pack(padx=1, pady=1)
        self._tip_time_lbl = tk.Label(tip_inner, text="",
                                      fg=ACCENT, bg=SURFACE, font=(FONT, 9, "bold"))
        self._tip_time_lbl.pack(anchor="w")
        self._tip_height_lbl = tk.Label(tip_inner, text="",
                                        fg=TEXT, bg=SURFACE, font=(FONT, 9))
        self._tip_height_lbl.pack(anchor="w")

        # ── Intégration Matplotlib → Tkinter ──────────────────────────
        mpl_canvas = FigureCanvasTkAgg(self._fig, card)
        mpl_canvas.draw()
        mpl_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 10))
        plt.close(self._fig)   # libère la mémoire Matplotlib (le canvas Tk reste valide)
        self._mpl_canvas = mpl_canvas

        # Événements souris pour la bulle d'info
        mpl_canvas.mpl_connect("motion_notify_event", self._on_chart_hover)
        mpl_canvas.mpl_connect("axes_leave_event",    self._on_chart_leave)

    def _on_chart_hover(self, event) -> None:
        """Gère le survol du graphique : déplace la ligne et met à jour la bulle.

        Args:
            event: Événement Matplotlib ``motion_notify_event``.
        """
        if event.inaxes != self._ax:
            self._hide_tooltip()
            return

        # Conversion coordonnée x (numérique Matplotlib) → datetime Python
        x_dt = mdates.num2date(event.xdata).replace(tzinfo=None)

        times, heights = self._times_plain, self._heights
        if not times:
            return

        # Interpolation linéaire de la hauteur à la position du curseur
        h_val = None
        best_i = min(range(len(times)), key=lambda i: abs((times[i] - x_dt).total_seconds()))
        for i in range(len(times) - 1):
            if times[i] <= x_dt <= times[i + 1]:
                ratio = (x_dt - times[i]) / (times[i + 1] - times[i])
                h_val = heights[i] + ratio * (heights[i + 1] - heights[i])
                break
        if h_val is None:
            h_val = heights[best_i]

        # Déplacement de la ligne verticale de survol
        self._vline.set_xdata([x_dt, x_dt])
        self._vline.set_alpha(0.6)
        self._mpl_canvas.draw_idle()

        # Mise à jour du texte de la bulle
        self._tip_time_lbl.config(text=f"🕐  {x_dt.strftime('%H:%M')}")
        self._tip_height_lbl.config(text=f"📏  {h_val:.2f} m")

        # Positionnement de la bulle près du curseur (coordonnées écran)
        widget = self._mpl_canvas.get_tk_widget()
        root_x = widget.winfo_rootx() + int(event.x) + 14
        root_y = widget.winfo_rooty() + int(widget.winfo_height() - event.y) - 10
        self._tooltip_win.geometry(f"+{root_x}+{root_y}")
        self._tooltip_win.deiconify()
        self._tooltip_win.lift()

    def _on_chart_leave(self, event) -> None:
        """Cache la bulle et la ligne de survol quand la souris quitte le graphique.

        Args:
            event: Événement Matplotlib ``axes_leave_event``.
        """
        self._hide_tooltip()

    def _hide_tooltip(self) -> None:
        """Cache la bulle d'info et rend la ligne de survol transparente."""
        if self._tooltip_win:
            self._tooltip_win.withdraw()
        if hasattr(self, "_vline"):
            self._vline.set_alpha(0)
            if self._mpl_canvas:
                self._mpl_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Mise à jour automatique (toutes les 60 secondes)
    # ------------------------------------------------------------------

    def _schedule_live(self) -> None:
        """Planifie le prochain appel de ``_live_tick`` dans 60 secondes."""
        self._live_job = self.root.after(60_000, self._live_tick)

    def _live_tick(self) -> None:
        """Callback exécuté toutes les 60 s pour rafraîchir horloge et graphique.

        Met à jour :
        1. L'horloge de marée (angle de l'aiguille, heure, hauteur).
        2. Le repère « Maintenant » sur le graphique (ligne + point).
        """
        if hasattr(self, "clock_canvas") and self.clock_canvas.winfo_exists():
            self.redraw_clock()
        self._update_now_line()
        self._schedule_live()

    def _update_now_line(self) -> None:
        """Déplace le repère « Maintenant » sur le graphique à l'heure actuelle.

        Supprime les artistes Matplotlib précédemment taggés ``gid="nowline"``
        (ligne verticale + point) et les redessine à la position courante.
        Cela évite de reconstruire entièrement le graphique.

        Ne fait rien si on ne visualise pas la date d'aujourd'hui.
        """
        if not self._mpl_canvas or not self._ax:
            return
        if self.current_date != datetime.now(PARIS).date():
            return

        now_plain = datetime.now(PARIS).replace(tzinfo=None)

        # Suppression des anciens artistes « nowline » (ligne + scatter)
        for artist in list(self._ax.lines) + list(self._ax.collections):
            if getattr(artist, "get_gid", lambda: None)() == "nowline":
                artist.remove()

        # Nouvelle ligne verticale rose
        self._ax.axvline(
            now_plain, color="#f472b6", linewidth=1.4,
            linestyle="--", alpha=0.9, gid="nowline",
        )

        # Nouveau point sur la courbe (interpolation)
        times, heights = self._times_plain, self._heights
        for i in range(len(times) - 1):
            if times[i] <= now_plain <= times[i + 1]:
                ratio = (now_plain - times[i]) / (times[i + 1] - times[i])
                h_now = heights[i] + ratio * (heights[i + 1] - heights[i])
                sc = self._ax.scatter([now_plain], [h_now],
                                      color="#f472b6", s=55, zorder=6)
                sc.set_gid("nowline")
                break

        self._mpl_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Navigation par date
    # ------------------------------------------------------------------

    def prev_day(self) -> None:
        """Recule d'un jour et recharge les données."""
        self.current_date -= timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def next_day(self) -> None:
        """Avance d'un jour et recharge les données."""
        self.current_date += timedelta(days=1)
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()

    def today(self) -> None:
        """Revient à la date d'aujourd'hui et recharge les données."""
        self.current_date = datetime.now(PARIS).date()
        self.date_label.config(text=self.current_date.strftime("%Y-%m-%d"))
        self.load_data()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1280x860")
    root.minsize(900, 600)
    app = TideApp(root)
    root.mainloop()
