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

        En mode « fenêtre glissante » (aujourd'hui), on charge les données
        du jour J **et** du jour J+1 pour couvrir la fenêtre de 24 h à
        partir de l'instant présent (qui peut chevaucher minuit).
        Pour les jours passés ou futurs, on charge uniquement le jour J.

        Stratégie de cache :
            1. Si un fichier JSON existe pour ce port/date → lecture locale.
            2. Sinon → requête API + sauvegarde du résultat.
        """
        site_id = self.get_site_id()
        today   = datetime.now(PARIS).date()

        def _load_day(date_obj):
            """Charge (ou met en cache) les données d'une journée.

            Args:
                date_obj: Objet ``date`` de la journée à charger.

            Returns:
                Liste de dicts ``{"time": str, "height": float}``.
            """
            cache_file = f"data/{site_id}_{date_obj.isoformat()}.json"
            if os.path.exists(cache_file):
                with open(cache_file, encoding="utf-8") as f:
                    return json.load(f).get("data", [])
            ds  = date_obj.isoformat()
            url = (
                f"{API_BASE}/water-levels?site={site_id}"
                f"&from={ds}T00:00&to={ds}T23:59"
                f"&step=10&tz=Europe/Paris&key={API_KEY}"
            )
            data = requests.get(url, timeout=15).json().get("data", [])
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"url": url, "data": data}, f,
                          ensure_ascii=False, indent=2)
            return data

        try:
            if self.current_date == today:
                # ── Mode fenêtre glissante : J + J+1 ─────────────────
                day_data      = _load_day(today)
                next_day_data = _load_day(today + timedelta(days=1))
                raw_data      = day_data + next_day_data

                # Filtre : garder uniquement les points dans [now, now+24h]
                now_ts      = datetime.now(PARIS).timestamp()
                end_ts      = now_ts + 86400   # 24 × 3600 secondes
                self.data   = [
                    pt for pt in raw_data
                    if now_ts - 600 <= parse_local(pt["time"]).timestamp() <= end_ts
                ]
            else:
                # ── Mode calendaire classique : jour J uniquement ─────
                self.data = _load_day(self.current_date)

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

        # ── En-têtes des jours de la semaine (grid pour alignement parfait) ──
        CELL = 36   # taille d'une cellule en pixels (largeur = hauteur)
        PAD  = 1    # espace entre cellules

        wk_frame = tk.Frame(parent, bg=SURFACE)
        wk_frame.pack()
        for col, day_abbr in enumerate(["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]):
            tk.Label(
                wk_frame, text=day_abbr,
                fg=MUTED, bg=SURFACE,
                font=(FONT, 9, "bold"),
                width=3, anchor="center",
            ).grid(row=0, column=col, padx=PAD, pady=(0, 2), ipadx=2)

        # ── Grille des jours (tk.grid, row/col explicites → alignement garanti) ─
        grid_frame = tk.Frame(parent, bg=SURFACE)
        grid_frame.pack(pady=2)

        first_weekday    = datetime(year, month, 1).weekday()   # 0=Lun … 6=Dim
        next_month_first = datetime(year + (month == 12), (month % 12) + 1, 1)
        days_in_month    = (next_month_first - timedelta(days=1)).day

        grid_col = first_weekday
        grid_row = 0
        for day_num in range(1, days_in_month + 1):
            cell_date = datetime(year, month, day_num).date()
            self._make_day_cell(
                grid_frame,
                text=str(day_num),
                cell_date=cell_date,
                is_sel=(cell_date == sel),
                is_today=(cell_date == today),
                grid_row=grid_row,
                grid_col=grid_col,
            )
            grid_col += 1
            if grid_col == 7:
                grid_col = 0
                grid_row += 1

    def _make_day_cell(
        self,
        parent: tk.Frame,
        text: str,
        cell_date,
        is_sel: bool,
        is_today: bool,
        grid_row: int = 0,
        grid_col: int = 0,
    ) -> None:
        """Crée une cellule de jour dans le calendrier avec canvas arrondi.

        Le rectangle arrondi est tracé via ``create_polygon`` avec 8 points
        de contrôle calculés analytiquement — cette méthode évite les
        artefacts (segments parasites aux coins) que produisent les
        combinaisons ``create_arc`` + ``create_line``.

        La cellule est placée dans le ``parent`` via ``grid`` avec les
        coordonnées ``grid_row`` / ``grid_col`` passées en argument, ce qui
        garantit l'alignement vertical et horizontal avec les en-têtes.

        Args:
            parent: Frame ``grid_frame`` de la grille du calendrier.
            text: Numéro du jour (chaîne vide → cellule invisible).
            cell_date: Objet ``date`` Python (None pour les cellules vides).
            is_sel: True si cette date est la date sélectionnée.
            is_today: True si cette date est aujourd'hui.
            grid_row: Ligne dans la grille Tkinter (0 = première semaine).
            grid_col: Colonne dans la grille Tkinter (0 = Lundi).
        """
        CELL = 36   # taille de la cellule en pixels
        PAD  = 1    # espace entre cellules

        # Cellule vide : canvas transparent pour maintenir l'espacement de la grille
        if not text:
            cv = tk.Canvas(parent, width=CELL, height=CELL,
                           bg=SURFACE, highlightthickness=0)
            cv.grid(row=grid_row, column=grid_col, padx=PAD, pady=PAD)
            return

        # ── Couleurs selon l'état ─────────────────────────────────────
        if is_sel:
            bg_fill  = ACCENT2
            fg_text  = "white"
            border_c = ACCENT
        elif is_today:
            bg_fill  = "#1e3a5f"
            fg_text  = ACCENT
            border_c = ACCENT
        else:
            bg_fill  = "#243044"
            fg_text  = MUTED
            border_c = "#3d5070"   # bordure discrète

        cv = tk.Canvas(
            parent, width=CELL, height=CELL,
            bg=SURFACE, highlightthickness=0, cursor="hand2",
        )
        cv.grid(row=grid_row, column=grid_col, padx=PAD, pady=PAD)

        # ── Rectangle arrondi via create_polygon (sans artefacts) ────
        # On calcule les 8 points du contour d'un rectangle à coins arrondis.
        # r = rayon des coins ; x0/y0/x1/y1 = boîte englobante avec 1 px de marge.
        r  = 7
        x0, y0, x1, y1 = 2, 2, CELL - 2, CELL - 2

        # Points dans le sens horaire, coins en paires (angle + tangente)
        pts = [
            x0 + r, y0,        # haut-gauche → droite
            x1 - r, y0,        # haut → coin droit
            x1,     y0 + r,    # coin haut-droit
            x1,     y1 - r,    # droite → bas
            x1 - r, y1,        # coin bas-droit
            x0 + r, y1,        # bas → coin gauche
            x0,     y1 - r,    # coin bas-gauche
            x0,     y0 + r,    # gauche → haut
        ]
        # ``smooth=True`` avec ces 8 points produit des coins parfaitement arrondis
        cv.create_polygon(
            pts,
            fill=bg_fill, outline=border_c, width=1,
            smooth=True,
        )

        # ── Numéro du jour centré ─────────────────────────────────────
        cv.create_text(
            CELL // 2, CELL // 2,
            text=text,
            fill=fg_text,
            font=(FONT, 10, "bold" if is_sel or is_today else "normal"),
            anchor="center",
        )

        # ── Interaction : clic pour sélectionner la date ──────────────
        if cell_date is not None:
            cv.bind("<Button-1>", lambda e, cd=cell_date: self._pick_date(cd))

        # Survol : légère surbrillance sur les cellules non sélectionnées
        def _hover_in(e):
            if not is_sel and not is_today:
                cv.delete("all")
                hover_pts = pts   # même contour
                cv.create_polygon(hover_pts, fill="#2d3f5c", outline=ACCENT,
                                  width=1, smooth=True)
                cv.create_text(CELL // 2, CELL // 2, text=text,
                               fill=TEXT, font=(FONT, 10), anchor="center")

        def _hover_out(e):
            if not is_sel and not is_today:
                cv.delete("all")
                cv.create_polygon(pts, fill=bg_fill, outline=border_c,
                                  width=1, smooth=True)
                cv.create_text(CELL // 2, CELL // 2, text=text,
                               fill=fg_text, font=(FONT, 10), anchor="center")

        cv.bind("<Enter>", _hover_in)
        cv.bind("<Leave>", _hover_out)

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
        """Redessine l'horloge de marée sur 24 heures (minuit en haut).

        Contrairement à une horloge classique (12h), cette horloge affiche
        un cycle de 24 heures : minuit (00:00) est au sommet, midi (12:00)
        en bas.  L'aiguille indique l'heure actuelle dans ce cycle.
        Les arcs colorés PM (cyan) et BM (orange) sont positionnés selon
        les heures réelles des événements de la journée.

        Cette méthode est appelée au démarrage puis toutes les 60 s.
        """
        if not hasattr(self, "clock_canvas") or not self.clock_canvas.winfo_exists():
            return

        c = self.clock_canvas
        c.update_idletasks()
        W = c.winfo_width()  or 280
        H = c.winfo_height() or 280
        c.delete("all")

        cx, cy = W // 2, H // 2 - 14
        r = min(W, H) // 2 - 18

        now   = datetime.now(PARIS)
        state = self._get_clock_state()

        # ── Fond du cadran ────────────────────────────────────────────
        c.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
                      fill=BORDER, outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=SURFACE, outline="#475569", width=2)

        # ── Arcs PM / BM positionnés selon les heures réelles ─────────
        # Sur une horloge 24h : 0° = minuit (haut), 1h = 15°, 12h = 180°, etc.
        # Pour chaque événement on calcule son angle à partir de son heure.
        def hour_to_angle(dt: datetime) -> float:
            """Convertit une heure en angle (0° = 00:00, sens horaire)."""
            minutes_since_midnight = dt.hour * 60 + dt.minute
            return (minutes_since_midnight / 1440) * 360 - 90  # -90 : minuit en haut

        ar    = r - 8
        arc_w = 6

        # Tracé des arcs entre événements consécutifs
        all_ev = self.events  # liste chronologique PM/BM
        for i in range(len(all_ev) - 1):
            ev_a = all_ev[i]
            ev_b = all_ev[i + 1]
            dt_a = parse_local(ev_a["time"])
            dt_b = parse_local(ev_b["time"])
            ang_a = hour_to_angle(dt_a)
            ang_b = hour_to_angle(dt_b)
            extent = ang_b - ang_a   # toujours positif (chronologique)
            # Couleur : orange si on descend (PM→BM), cyan si on monte (BM→PM)
            col = BM_COL if ev_a["type"] == "PM" else PM_COL
            c.create_arc(cx - ar, cy - ar, cx + ar, cy + ar,
                         start=-ang_a, extent=-extent, style="arc",
                         outline=col, width=arc_w)

        # ── Graduations 24 h et étiquettes ────────────────────────────
        for h in range(24):
            ang_deg = (h / 24) * 360 - 90   # 0h=haut, 12h=bas
            ang_rad = math.radians(ang_deg)
            is_major = (h % 3 == 0)          # graduation épaisse toutes les 3h
            is_label = (h % 6 == 0)          # étiquette toutes les 6h

            tick_out = r - 12
            tick_in  = tick_out - (12 if is_major else (7 if h % 1 == 0 else 4))
            c.create_line(
                cx + math.cos(ang_rad) * tick_in,  cy + math.sin(ang_rad) * tick_in,
                cx + math.cos(ang_rad) * tick_out, cy + math.sin(ang_rad) * tick_out,
                fill="#64748b", width=2 if is_major else 1,
            )

            # Étiquette horaire toutes les 6h : 00, 06, 12, 18
            if is_label:
                lx = cx + math.cos(ang_rad) * (r - 30)
                ly = cy + math.sin(ang_rad) * (r - 30)
                c.create_text(lx, ly, text=f"{h:02d}h",
                              fill=MUTED, font=(FONT, 8, "bold"))

        # ── Petites graduations intermédiaires (toutes les heure) ──────
        for h in range(24):
            for m in [15, 30, 45]:   # quarts d'heure
                frac    = (h * 60 + m) / 1440
                ang_rad = math.radians(frac * 360 - 90)
                tick_out = r - 12
                tick_in  = tick_out - 4
                c.create_line(
                    cx + math.cos(ang_rad) * tick_in,  cy + math.sin(ang_rad) * tick_in,
                    cx + math.cos(ang_rad) * tick_out, cy + math.sin(ang_rad) * tick_out,
                    fill="#3d4f65", width=1,
                )

        # ── Étiquettes PM / BM sur le cadran ──────────────────────────
        for ev in self.events:
            dt      = parse_local(ev["time"])
            ang_deg = (dt.hour * 60 + dt.minute) / 1440 * 360 - 90
            ang_rad = math.radians(ang_deg)
            col     = PM_COL if ev["type"] == "PM" else BM_COL
            lx = cx + math.cos(ang_rad) * (r - 42)
            ly = cy + math.sin(ang_rad) * (r - 42)
            c.create_text(lx, ly, text=ev["type"],
                          fill=col, font=(FONT, 8, "bold"))

        # ── Aiguille de l'heure actuelle ──────────────────────────────
        # Angle de l'aiguille = heure actuelle sur le cycle 24h
        now_frac    = (now.hour * 60 + now.minute) / 1440
        hand_ang    = math.radians(now_frac * 360 - 90)
        hand_len    = r - 28

        hx = cx + math.cos(hand_ang) * hand_len
        hy = cy + math.sin(hand_ang) * hand_len

        # Ombre
        c.create_line(cx + 1, cy + 1, hx + 2, hy + 2,
                      fill="#0a1020", width=5, capstyle="round")
        # Corps de l'aiguille (blanc/gris clair)
        c.create_line(cx, cy, hx, hy,
                      fill="#dde6f0", width=3, capstyle="round")
        c.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill="#dde6f0", outline="")
        c.create_oval(cx - 7, cy - 7, cx + 7, cy + 7,
                      fill=SURFACE, outline="#dde6f0", width=2)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#dde6f0", outline="")

        # ── Informations au centre du cadran ──────────────────────────
        if state["is_today"] and state["current_height"] is not None:
            direction = state["direction"]
            height_color = (
                PM_COL  if direction == "falling"   # descente PM→BM : cyan
                else BM_COL if direction == "rising"    # montée BM→PM  : orange
                else ACCENT
            )
            dir_label = (
                "▲ Montante"   if direction == "rising"
                else "▼ Descendante" if direction == "falling"
                else ""
            )
            dir_color = PM_COL if direction == "rising" else BM_COL if direction == "falling" else MUTED

            # Hauteur (grande, colorée)
            c.create_text(cx, cy - 16, text=f"{state['current_height']:.2f} m",
                          fill=height_color, font=(FONT, 15, "bold"))
            # Heure actuelle
            c.create_text(cx, cy + 8,  text=now.strftime("%H:%M"),
                          fill=TEXT, font=(FONT, 12, "bold"))
            # Direction
            c.create_text(cx, cy + 28, text=dir_label,
                          fill=dir_color, font=(FONT, 9))
        else:
            c.create_text(cx, cy, text="Horloge 24h", fill=MUTED, font=(FONT, 8))

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
        today  = datetime.now(PARIS).date()
        title  = ("Prochaines marées (24 h)" if self.current_date == today
                  else "Marées du jour")
        tk.Label(
            parent, text=title,
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
        today      = datetime.now(PARIS).date()
        chart_title = ("MARÉES — 24 HEURES GLISSANTES" if self.current_date == today
                       else f"COURBE DE MARÉE — {self.current_date.strftime('%d/%m/%Y')}")
        tk.Label(card, text=chart_title, fg=MUTED, bg=SURFACE,
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
