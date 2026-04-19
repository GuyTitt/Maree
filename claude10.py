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
# Constantes globales — toutes les valeurs modifiables sont ici
# (couleurs, typographie, épaisseurs, tailles, textes multilingues)
# ---------------------------------------------------------------------------

# --- API ---
API_BASE = "https://api-maree.fr"
API_KEY  = "0000000000000000000000000000000"

# --- Fuseau horaire ---
PARIS = ZoneInfo("Europe/Paris")

# ── Palette de couleurs (thème sombre) ──────────────────────────────────────
BG      = "#0f172a"   # fond principal (bleu nuit très foncé)
SURFACE = "#1e293b"   # fond des cartes (bleu ardoise foncé)
BORDER  = "#334155"   # bordures et séparateurs
TEXT    = "#e2e8f0"   # texte principal (blanc doux)
MUTED   = "#94a3b8"   # texte secondaire (gris bleuté)
ACCENT  = "#38bdf8"   # couleur d'accentuation (bleu ciel)
ACCENT2 = "#0284c7"   # variante plus sombre de l'accent (boutons actifs)
PM_COL  = "#22d3ee"   # Pleine Mer  – cyan   (marée montante)
BM_COL  = "#f97316"   # Basse Mer   – orange (marée descendante)
ERROR   = "#f87171"   # messages d'erreur – rouge doux
NOW_COL = "#f472b6"   # repère « Maintenant » – rose
HAND_COL = "#dde6f0"  # couleur de l'aiguille (blanc cassé)
SHADOW_COL = "#0a1020" # couleur de l'ombre de l'aiguille

# ── Typographie ─────────────────────────────────────────────────────────────
# Police système : Segoe UI sur Windows, SF Pro sur macOS, DejaVu/Ubuntu sur Linux.
FONT           = "Segoe UI"
FONT_SZ_TITLE  = 16   # titre principal de l'en-tête
FONT_SZ_CARD   = 8    # titre des cartes (COURBE DE MARÉE, etc.)
FONT_SZ_MONTH  = 10   # nom du mois dans le calendrier
FONT_SZ_WDAY   = 9    # initiales des jours de la semaine
FONT_SZ_DAY    = 10   # chiffre du jour
FONT_SZ_EVENT  = 10   # heure de l'événement dans le panneau
FONT_SZ_CLOCK_H = 14  # hauteur dans l'horloge
FONT_SZ_CLOCK_T = 11  # heure dans l'horloge
FONT_SZ_CLOCK_D = 9   # direction dans l'horloge
FONT_SZ_BUBBLE  = 7   # texte des bulles de l'horloge
FONT_SZ_CLOCK_GRAD = 8  # graduation 00h/06h/12h/18h

# ── Calendrier — taille des cellules ────────────────────────────────────────
CAL_CELL  = 36   # largeur = hauteur d'une cellule en pixels
CAL_PAD   = 1    # espace entre cellules
CAL_RADIUS = 7   # rayon des coins arrondis des cellules

# ── Horloge ─────────────────────────────────────────────────────────────────
CLK_MARGIN        = 52   # marge entre le bord du canvas et le cercle (espace bulles)
CLK_ARC_RADIUS_IN = 10   # distance entre l'arc et le bord du cercle (r - CLK_ARC_RADIUS_IN)
CLK_ARC_WIDTH     = 6    # épaisseur normale des arcs PM/BM
CLK_ARC_WIDTH_THIN = 3   # épaisseur en cas de chevauchement (< 30 min)
CLK_OVERLAP_MIN   = 30   # seuil de chevauchement en minutes
CLK_TICK_MAJOR_LEN = 12  # longueur des grandes graduations (toutes les 3h)
CLK_TICK_MINOR_LEN = 6   # longueur des petites graduations (toutes les heures)
CLK_TICK_TINY_LEN  = 4   # longueur des micro-graduations (quarts d'heure)
CLK_TICK_MAJOR_W   = 2   # épaisseur grande graduation
CLK_TICK_MINOR_W   = 1   # épaisseur petite graduation
CLK_TICK_COLOR     = "#64748b"  # couleur des graduations principales
CLK_TICK_TINY_COL  = "#3d4f65"  # couleur des micro-graduations
CLK_HAND_WIDTH     = 3   # épaisseur de l'aiguille
CLK_HAND_SHADOW_W  = 5   # épaisseur de l'ombre de l'aiguille
CLK_FACE_RING_W    = 2   # épaisseur du cercle extérieur du cadran
CLK_BUBBLE_BH      = 14  # hauteur des bulles d'événement
CLK_BUBBLE_PX      = 4   # padding horizontal des bulles
CLK_BUBBLE_CHAR_W  = 5.5 # largeur estimée d'un caractère en pixels (font 7)

# ── Graphique Matplotlib ─────────────────────────────────────────────────────
CHART_LINE_W       = 2.4  # épaisseur de la courbe (partie active)
CHART_LINE_W_PAST  = 1.6  # épaisseur de la courbe (partie passée)
CHART_ALPHA_FILL   = 0.18  # transparence du remplissage (partie active)
CHART_ALPHA_FILL_PAST = 0.06  # transparence du remplissage (partie passée)
CHART_ALPHA_LINE_PAST = 0.40  # opacité de la ligne (partie passée)
CHART_NOW_LW       = 1.4  # épaisseur de la ligne « Maintenant »
CHART_MARKER_SIZE  = 80   # taille des marqueurs PM/BM (scatter, unités pts²)
CHART_NOW_PT_SIZE  = 60   # taille du point « Maintenant »
CHART_HOVER_PT_SIZE = 55  # taille du point de survol
CHART_GRID_ALPHA   = 0.4  # transparence de la grille horizontale
CHART_H_INTERVAL   = 2    # intervalle en heures entre deux graduations X

# ── Textes — français (i18n : remplacer ce bloc pour changer de langue) ──────
# Jours de la semaine (abréviation 3 lettres, lundi en premier)
I18N_WEEKDAYS_SHORT = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
# Noms des mois (janvier = index 0)
I18N_MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
I18N_TODAY        = "Aujourd'hui"
I18N_TOMORROW     = "Demain"
I18N_HIGH_WATER   = "Pleine Mer"   # PM
I18N_LOW_WATER    = "Basse Mer"    # BM
I18N_RISING       = "▲ Montante"
I18N_FALLING      = "▼ Descendante"
I18N_NEXT_TIDES   = "Prochaines marées"
I18N_TIDES_J_J1   = "Marées J + J+1"
I18N_TIDE_CLOCK   = "Horloge de marée"
I18N_LOADING      = "Chargement…"
I18N_NO_DATA      = "Aucune donnée"
I18N_NO_TIDES     = "Aucune marée détectée."
I18N_ERROR_PORTS  = "Erreur chargement ports"
I18N_ERROR_NET    = "Erreur réseau"
I18N_CHART_TODAY  = "MARÉES — Aujourd'hui + Demain"
I18N_CHART_OTHER  = "MARÉES"       # suivi de la date dans le code
I18N_MIDNIGHT     = " Minuit"
I18N_NOW_LABEL    = "Maintenant"
I18N_RISING_LEGEND   = "Montant"
I18N_FALLING_LEGEND  = "Descendant"

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
        self.data_all: list[dict] = []       # J + J+1 pour la courbe complète
        self.events_all: list[dict] = []     # PM/BM sur les 2 journées

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

        self.show_status(I18N_LOADING)

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
        self.show_status(I18N_LOADING)
        if self._live_job:
            self.root.after_cancel(self._live_job)
            self._live_job = None
        self.root.after(80, self.fetch_and_render)

    def fetch_and_render(self) -> None:
        """Charge J et J+1 pour la courbe complète sur deux journées.

        ``self.data_all`` contient tous les points des deux journées
        (utilisé pour la courbe).
        ``self.data`` est filtré selon le mode :
          - aujourd'hui → fenêtre glissante [now, now+24h] (horloge, events).
          - autre jour  → journée calendaire J uniquement.
        """
        site_id = self.get_site_id()
        today   = datetime.now(PARIS).date()

        def _load_day(date_obj):
            """Charge (ou met en cache) une journée complète."""
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
            pts = requests.get(url, timeout=15).json().get("data", [])
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"url": url, "data": pts}, f,
                          ensure_ascii=False, indent=2)
            return pts

        try:
            day_data      = _load_day(self.current_date)
            next_day_data = _load_day(self.current_date + timedelta(days=1))
            # Courbe complète J + J+1 (pour le graphique)
            self.data_all = day_data + next_day_data

            if self.current_date == today:
                # Fenêtre glissante [now-10min, now+24h] pour horloge + events
                now_ts = datetime.now(PARIS).timestamp()
                end_ts = now_ts + 86400
                self.data = [
                    pt for pt in self.data_all
                    if now_ts - 600 <= parse_local(pt["time"]).timestamp() <= end_ts
                ]
            else:
                self.data = day_data

        except Exception as exc:  # noqa: BLE001
            self.show_status(f"Erreur réseau : {exc}", ERROR)
            return

        self.events     = self._find_events()      # sur self.data (fenêtre active)
        self.events_all = self._find_events_from(self.data_all)  # sur 2 jours
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

    def _find_events_from(self, data: list[dict]) -> list[dict]:
        """Variante de ``_find_events`` travaillant sur une liste arbitraire.

        Args:
            data: Liste de points ``{"time": str, "height": float}``.

        Returns:
            Liste d'événements PM/BM triée chronologiquement.
        """
        saved = self.data
        self.data = data
        result = self._find_events()
        self.data = saved
        return result

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
            self.show_status(I18N_NO_DATA, ERROR)
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

        month_names = I18N_MONTHS

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

        # ── En-têtes + grille dans le même conteneur grid ────────────
        # Un seul Frame avec grid assure l'alignement parfait
        # entre les titres Lun/Mar/… et les cellules en dessous.
        CELL = 36
        PAD  = 1

        cal_grid = tk.Frame(parent, bg=SURFACE)
        cal_grid.pack(pady=(4, 2))

        # Titres des jours (ligne 0)
        for col, day_abbr in enumerate(I18N_WEEKDAYS_SHORT):
            tk.Label(
                cal_grid, text=day_abbr,
                fg=MUTED, bg=SURFACE,
                font=(FONT, 9, "bold"),
                width=3, anchor="center",
            ).grid(row=0, column=col, padx=PAD, pady=(0, 3), ipadx=2)

        # ── Grille des jours (lignes 1+) ────────────────────────────
        first_weekday    = datetime(year, month, 1).weekday()
        next_month_first = datetime(year + (month == 12), (month % 12) + 1, 1)
        days_in_month    = (next_month_first - timedelta(days=1)).day

        grid_col = first_weekday
        grid_row = 1   # ligne 0 = titres

        for day_num in range(1, days_in_month + 1):
            cell_date = datetime(year, month, day_num).date()
            self._make_day_cell(
                cal_grid,
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
            parent, text=I18N_TIDE_CLOCK,
            fg=MUTED, bg=SURFACE, font=(FONT, FONT_SZ_CARD, "bold"),
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
        W = c.winfo_width()  or 260
        H = c.winfo_height() or 260
        c.delete("all")

        # ── Géométrie : réservation de place pour les bulles latérales ─
        # Le cadran est centré mais décalé pour laisser de la place aux bulles.
        margin = CLK_MARGIN          # pixels réservés de chaque côté pour les bulles
        diam   = min(W - 2 * margin, H - 40)   # diamètre utilisable
        r      = diam // 2
        cx     = W // 2
        cy     = H // 2 - 10

        now   = datetime.now(PARIS)
        state = self._get_clock_state()

        # ── Fond du cadran ─────────────────────────────────────────────
        c.create_oval(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5,
                      fill=BORDER, outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=SURFACE, outline="#475569", width=CLK_FACE_RING_W)

        # ── Graduations 24 h ───────────────────────────────────────────
        # Dessinées AVANT les arcs pour être sous eux.
        # Convention : 0h = haut (−90° en trigonométrie standard).
        for h in range(24):
            frac    = h / 24
            ang_rad = math.radians(frac * 360 - 90)
            is_3h   = (h % 3 == 0)
            is_6h   = (h % 6 == 0)
            t_len   = (CLK_TICK_MAJOR_LEN if is_3h else CLK_TICK_MINOR_LEN)
            t_wid   = (CLK_TICK_MAJOR_W   if is_3h else CLK_TICK_MINOR_W)
            r_out   = r - 2
            r_in    = r_out - t_len
            c.create_line(
                cx + math.cos(ang_rad) * r_in,  cy + math.sin(ang_rad) * r_in,
                cx + math.cos(ang_rad) * r_out, cy + math.sin(ang_rad) * r_out,
                fill=CLK_TICK_COLOR, width=t_wid,
            )
            if is_6h:
                lx = cx + math.cos(ang_rad) * (r - CLK_TICK_MAJOR_LEN - 10)
                ly = cy + math.sin(ang_rad) * (r - CLK_TICK_MAJOR_LEN - 10)
                c.create_text(lx, ly, text=f"{h:02d}h",
                              fill=MUTED, font=(FONT, FONT_SZ_CLOCK_GRAD, "bold"))

        # Quarts d'heure
        for h in range(24):
            for m in (15, 30, 45):
                frac    = (h * 60 + m) / 1440
                ang_rad = math.radians(frac * 360 - 90)
                r_out   = r - 2
                r_in    = r_out - CLK_TICK_TINY_LEN
                c.create_line(
                    cx + math.cos(ang_rad) * r_in,  cy + math.sin(ang_rad) * r_in,
                    cx + math.cos(ang_rad) * r_out, cy + math.sin(ang_rad) * r_out,
                    fill=CLK_TICK_TINY_COL, width=1,
                )

        # ── Arcs PM/BM : 4 prochains événements, chevauchement géré ───
        now_ts     = now.timestamp()
        all_ev_src = getattr(self, "events_all", self.events)
        future_evs = [
            ev for ev in all_ev_src
            if parse_local(ev["time"]).timestamp() >= now_ts - 3600
        ][:4]

        def _mins_to_tk_angle(dt: datetime) -> float:
            """Convertit une heure en angle Tkinter.

            Tkinter ``create_arc`` mesure les angles en degrés **antihoraires**
            depuis l'est (3h = 0°).  L'horloge 24h place minuit en haut
            (= 12h en trigonométrie standard = 90° Tkinter).

            Args:
                dt: Datetime dont on veut l'angle.

            Returns:
                Angle en degrés dans le système Tkinter.
            """
            frac = (dt.hour * 60 + dt.minute) / 1440  # 0..1
            # Angle trigonométrique (antihoraire depuis est) : minuit = 90°
            return 90 - frac * 360   # minuit=90, 6h=0, 12h=−90, 18h=180

        def _mins_to_trig_rad(dt: datetime) -> float:
            """Angle en radians (convention trigonométrique) pour cos/sin."""
            frac = (dt.hour * 60 + dt.minute) / 1440
            return math.radians(frac * 360 - 90)  # minuit=−90° → haut

        OVERLAP_THRESH_S = CLK_OVERLAP_MIN * 60
        ar = r - CLK_ARC_RADIUS_IN   # rayon de l'arc

        # Détection de chevauchement
        arcs: list[dict] = []
        for i in range(len(future_evs) - 1):
            ev_a  = future_evs[i]
            ev_b  = future_evs[i + 1]
            dt_a  = parse_local(ev_a["time"])
            dt_b  = parse_local(ev_b["time"])
            ts_a  = dt_a.timestamp()
            ts_b  = dt_b.timestamp()

            overlap_prev = (i > 0 and
                abs(ts_a - parse_local(future_evs[i-1]["time"]).timestamp())
                < OVERLAP_THRESH_S)
            overlap_next = (i < len(future_evs) - 2 and
                abs(ts_b - ts_a) < OVERLAP_THRESH_S)

            arcs.append({
                "dt_a":  dt_a,  "dt_b":  dt_b,
                "tk_a":  _mins_to_tk_angle(dt_a),
                "tk_b":  _mins_to_tk_angle(dt_b),
                "col":   BM_COL if ev_a["type"] == "PM" else PM_COL,
                "thin":  overlap_prev or overlap_next,
                "ev_a":  ev_a,  "ev_b":  ev_b,
            })

        for arc in arcs:
            w      = CLK_ARC_WIDTH_THIN if arc["thin"] else CLK_ARC_WIDTH
            start  = arc["tk_a"]
            # extent négatif = sens horaire dans Tkinter
            extent = arc["tk_b"] - arc["tk_a"]
            # Normaliser : on veut toujours aller dans le sens horaire (extent < 0)
            if extent > 0:
                extent -= 360
            c.create_arc(cx - ar, cy - ar, cx + ar, cy + ar,
                         start=start, extent=extent,
                         style="arc", outline=arc["col"], width=w)

        # ── Bulles d'événements ancrées sur le bord de l'arc ──────────
        for ev in future_evs:
            dt       = parse_local(ev["time"])
            trig_rad = _mins_to_trig_rad(dt)
            col      = PM_COL if ev["type"] == "PM" else BM_COL

            # Point d'ancrage = bord EXTÉRIEUR de l'arc (rayon ar + w/2)
            anchor_r = ar + CLK_ARC_WIDTH // 2 + 3
            ax_pt    = cx + math.cos(trig_rad) * anchor_r
            ay_pt    = cy + math.sin(trig_rad) * anchor_r

            # La bulle va à droite si cos > 0 (côté droit), sinon à gauche
            right = math.cos(trig_rad) >= 0
            # Extrémité du trait horizontal (bord du canvas)
            bx = cx + r + margin - 4 if right else cx - r - margin + 4
            by = ay_pt

            # Trait de rappel pointillé
            c.create_line(ax_pt, ay_pt, bx, by, fill=col,
                          width=1, dash=(3, 2))

            # Bulle arrondie
            label_txt = f"{ev['type']} {dt.strftime('%H:%M')}"
            bw = len(label_txt) * CLK_BUBBLE_CHAR_W + CLK_BUBBLE_PX * 2
            bh = CLK_BUBBLE_BH
            if right:
                bx0, bx1 = bx, bx + bw
            else:
                bx0, bx1 = bx - bw, bx
            by0  = by - bh / 2
            by1  = by + bh / 2
            rr   = 3
            pts  = [
                bx0 + rr, by0,   bx1 - rr, by0,
                bx1,      by0 + rr, bx1,   by1 - rr,
                bx1 - rr, by1,   bx0 + rr, by1,
                bx0,      by1 - rr, bx0,   by0 + rr,
            ]
            c.create_polygon(pts, fill=SURFACE, outline=col, width=1, smooth=True)
            c.create_text((bx0 + bx1) / 2, (by0 + by1) / 2,
                          text=label_txt, fill=col,
                          font=(FONT, FONT_SZ_BUBBLE, "bold"))

        # ── Aiguille de l'heure actuelle ──────────────────────────────
        now_frac = (now.hour * 60 + now.minute) / 1440
        hand_rad = math.radians(now_frac * 360 - 90)
        hand_len = r - CLK_TICK_MAJOR_LEN - 14

        hx = cx + math.cos(hand_rad) * hand_len
        hy = cy + math.sin(hand_rad) * hand_len

        c.create_line(cx + 1, cy + 1, hx + 2, hy + 2,
                      fill=SHADOW_COL, width=CLK_HAND_SHADOW_W, capstyle="round")
        c.create_line(cx, cy, hx, hy,
                      fill=HAND_COL, width=CLK_HAND_WIDTH, capstyle="round")
        c.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill=HAND_COL, outline="")
        c.create_oval(cx - 7, cy - 7, cx + 7, cy + 7,
                      fill=SURFACE, outline=HAND_COL, width=2)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=HAND_COL, outline="")

        # ── Centre du cadran : hauteur, heure, direction ───────────────
        if state["is_today"] and state["current_height"] is not None:
            direction = state["direction"]
            h_color   = (PM_COL  if direction == "falling"
                         else BM_COL if direction == "rising" else ACCENT)
            dir_lbl   = (I18N_RISING   if direction == "rising"
                         else I18N_FALLING if direction == "falling" else "")
            dir_col   = (PM_COL if direction == "rising"
                         else BM_COL if direction == "falling" else MUTED)

            c.create_text(cx, cy - 16,
                          text=f"{state['current_height']:.2f} m",
                          fill=h_color, font=(FONT, FONT_SZ_CLOCK_H, "bold"))
            c.create_text(cx, cy + 8,
                          text=now.strftime("%H:%M"),
                          fill=TEXT, font=(FONT, FONT_SZ_CLOCK_T, "bold"))
            c.create_text(cx, cy + 26,
                          text=dir_lbl, fill=dir_col,
                          font=(FONT, FONT_SZ_CLOCK_D))
        else:
            c.create_text(cx, cy, text=I18N_TIDE_CLOCK,
                          fill=MUTED, font=(FONT, 8))

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
        """Affiche les événements PM/BM sur J et J+1, une ligne par marée.

        Format compact : [barre] [badge] [heure]  [hauteur]
        Les journées sont séparées par un petit titre coloré.

        Args:
            parent: Frame carte des marées.
        """
        today = datetime.now(PARIS).date()
        title = I18N_NEXT_TIDES if self.current_date == today else I18N_TIDES_J_J1
        tk.Label(parent, text=title, fg=MUTED, bg=SURFACE,
                 font=(FONT, FONT_SZ_CARD, "bold")).pack(anchor="w", padx=12, pady=(8, 2))

        all_evs = getattr(self, "events_all", self.events)
        if not all_evs:
            tk.Label(parent, text=I18N_NO_TIDES,
                     fg=MUTED, bg=SURFACE, font=(FONT, 9)).pack(padx=12)
            return

        days_seen: set = set()

        for ev in all_evs:
            dt      = parse_local(ev["time"])
            ev_date = dt.date()

            # ── Séparateur de jour ──────────────────────────────────────
            if ev_date not in days_seen:
                days_seen.add(ev_date)
                if ev_date == today:
                    day_lbl = I18N_TODAY
                elif ev_date == today + timedelta(days=1):
                    day_lbl = I18N_TOMORROW
                else:
                    day_lbl = (f"{I18N_WEEKDAYS_SHORT[ev_date.weekday()]}"
                               f" {ev_date.strftime('%d/%m')}")
                tk.Label(parent, text=day_lbl, fg=ACCENT, bg=SURFACE,
                         font=(FONT, 8, "bold")).pack(anchor="w", padx=12, pady=(4, 1))

            # ── Ligne compacte : barre | badge | heure  hauteur ─────────
            is_pm = ev["type"] == "PM"
            color = PM_COL if is_pm else BM_COL
            t_str = dt.strftime("%H:%M")
            h_str = f"{ev['height']:.2f} m"

            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", padx=10, pady=1, ipady=3)

            # Barre colorée
            tk.Frame(row, bg=color, width=3).pack(side="left", fill="y")

            # Badge PM/BM
            tk.Label(row, text=ev["type"], bg=SURFACE, fg=color,
                     font=(FONT, 7, "bold"), padx=4, pady=0,
                     relief="solid", bd=1).pack(side="left", padx=(4, 6))

            # Heure en blanc
            tk.Label(row, text=t_str, fg=TEXT, bg=BG,
                     font=(FONT, FONT_SZ_EVENT, "bold")).pack(side="left")

            # Hauteur colorée à droite
            tk.Label(row, text=h_str, fg=color, bg=BG,
                     font=(FONT, 8)).pack(side="right", padx=6)

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
        today = datetime.now(PARIS).date()
        chart_title = (
            I18N_CHART_TODAY
            if self.current_date == today
            else (f"{I18N_CHART_OTHER} — {self.current_date.strftime('%d/%m/%Y')}"
                  f"  +  {(self.current_date + timedelta(days=1)).strftime('%d/%m/%Y')}")
        )
        tk.Label(card, text=chart_title, fg=MUTED, bg=SURFACE,
                 font=(FONT, 8, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        # Données complètes J + J+1 pour la courbe
        all_data = getattr(self, "data_all", self.data)
        self._times_plain = [parse_local(d["time"]).replace(tzinfo=None) for d in all_data]
        self._heights     = [d["height"] for d in all_data]
        times, heights    = self._times_plain, self._heights
        now_plain         = datetime.now(PARIS).replace(tzinfo=None)

        self._fig, self._ax = plt.subplots(figsize=(12, 4.5), facecolor=SURFACE)
        ax = self._ax
        ax.set_facecolor(SURFACE)

        all_evs = getattr(self, "events_all", self.events)

        def _seg_color(ev_before, ev_after) -> str:
            """Couleur du segment : cyan=montant, orange=descendant."""
            if ev_before is None:
                return PM_COL if (ev_after and ev_after["type"] == "PM") else BM_COL
            return BM_COL if ev_before["type"] == "PM" else PM_COL

        # Bornes temporelles des segments [debut_data, ev0, ev1, …, fin_data]
        boundaries = (
            [times[0]]
            + [parse_local(e["time"]).replace(tzinfo=None) for e in all_evs]
            + [times[-1]]
        )
        ev_before_list = [None] + list(all_evs)
        ev_after_list  = list(all_evs) + [None]

        for seg_i in range(len(boundaries) - 1):
            t0  = boundaries[seg_i]
            t1  = boundaries[seg_i + 1]
            col = _seg_color(ev_before_list[seg_i], ev_after_list[seg_i])
            idx = [j for j, t in enumerate(times) if t0 <= t <= t1]
            if len(idx) < 2:
                continue
            st = [times[j]   for j in idx]
            sh = [heights[j] for j in idx]
            # Passé : assombri
            past = t1 <= now_plain
            ax.fill_between(st, sh, alpha=0.06 if past else 0.18, color=col)
            ax.plot(st, sh, color=col,
                    linewidth=1.5 if past else 2.4,
                    alpha=0.4 if past else 0.95)

        # Marqueurs PM/BM
        for ev in all_evs:
            t   = parse_local(ev["time"]).replace(tzinfo=None)
            col = PM_COL if ev["type"] == "PM" else BM_COL
            ax.scatter([t], [ev["height"]], color=col, s=80, zorder=5,
                       marker="^" if ev["type"] == "PM" else "v")

        # Séparateur minuit
        mid = self.current_date + timedelta(days=1)
        mid_dt = datetime(mid.year, mid.month, mid.day, 0, 0)
        ax.axvline(mid_dt, color=BORDER, linewidth=1, linestyle="-", alpha=0.7)

        # Ligne Maintenant
        ax.axvline(now_plain, color="#f472b6", linewidth=1.4,
                   linestyle="--", alpha=0.9, gid="nowline")
        for i in range(len(times) - 1):
            if times[i] <= now_plain <= times[i + 1]:
                ratio = (now_plain - times[i]) / (times[i + 1] - times[i])
                h_now = heights[i] + ratio * (heights[i + 1] - heights[i])
                sc = ax.scatter([now_plain], [h_now], s=60, color="#f472b6",
                                edgecolors="white", linewidths=1, zorder=7)
                sc.set_gid("nowline")
                break

        # Axes
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.set_xlim(times[0].replace(minute=0), times[-1])
        h_min = int(min(heights))
        h_max = int(max(heights)) + 1
        ax.set_yticks(range(h_min, h_max + 1))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v)} m"))
        for sp in ax.spines.values():
            sp.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED, labelsize=9)
        ax.set_ylabel("Hauteur (m)", color=MUTED, fontsize=9)
        ax.grid(True, color=BORDER, alpha=0.4, linewidth=0.5)

        legend_patches = [
            mpatches.Patch(color=PM_COL,   label=I18N_RISING_LEGEND),
            mpatches.Patch(color=BM_COL,   label=I18N_FALLING_LEGEND),
            mpatches.Patch(color=NOW_COL, label=I18N_NOW_LABEL),
        ]
        ax.legend(handles=legend_patches, facecolor=SURFACE, edgecolor=BORDER,
                  labelcolor=MUTED, fontsize=8, loc="upper right")
        self._fig.tight_layout(pad=1.0)

        # Ligne et point de survol (invisibles)
        self._vline    = ax.axvline(times[0], color=TEXT, linewidth=1,
                                    linestyle=":", alpha=0, zorder=10)
        self._hover_pt = ax.scatter([], [], s=55, color="white",
                                    edgecolors="white", linewidths=1.5, zorder=11)

        # Bulle d'info
        self._tooltip_win = tk.Toplevel(self.root)
        self._tooltip_win.withdraw()
        self._tooltip_win.overrideredirect(True)
        self._tooltip_win.configure(bg=BORDER)
        tip_inner = tk.Frame(self._tooltip_win, bg=SURFACE, padx=10, pady=6)
        tip_inner.pack(padx=1, pady=1)
        self._tip_time_lbl = tk.Label(tip_inner, text="",
                                      fg=TEXT, bg=SURFACE, font=(FONT, 9, "bold"))
        self._tip_time_lbl.pack(anchor="w")
        self._tip_height_lbl = tk.Label(tip_inner, text="",
                                        fg=PM_COL, bg=SURFACE, font=(FONT, 9, "bold"))
        self._tip_height_lbl.pack(anchor="w")

        mpl_canvas = FigureCanvasTkAgg(self._fig, card)
        mpl_canvas.draw()
        mpl_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 10))
        plt.close(self._fig)
        self._mpl_canvas  = mpl_canvas
        self._all_evs_cache = all_evs

        mpl_canvas.mpl_connect("motion_notify_event", self._on_chart_hover)
        mpl_canvas.mpl_connect("axes_leave_event",    self._on_chart_leave)


    def _on_chart_hover(self, event) -> None:
        """Survol du graphique : ligne guide, bulle enrichie et point sur la courbe.

        La bulle affiche :
        * Jour + heure en blanc (TEXT).
        * Hauteur colorée : cyan si marée montante, orange si descendante.
        Un petit cercle blanc est placé sur la courbe à la position du curseur.

        Args:
            event: Événement Matplotlib ``motion_notify_event``.
        """
        if event.inaxes != self._ax:
            self._hide_tooltip()
            return

        x_dt = mdates.num2date(event.xdata).replace(tzinfo=None)
        times, heights = self._times_plain, self._heights
        if not times:
            return

        # Interpolation linéaire de la hauteur
        h_val = None
        best_i = min(range(len(times)), key=lambda i: abs((times[i] - x_dt).total_seconds()))
        for i in range(len(times) - 1):
            if times[i] <= x_dt <= times[i + 1]:
                ratio = (x_dt - times[i]) / (times[i + 1] - times[i])
                h_val = heights[i] + ratio * (heights[i + 1] - heights[i])
                break
        if h_val is None:
            h_val = heights[best_i]

        # Couleur de la hauteur selon la phase de marée
        all_evs = getattr(self, "_all_evs_cache", [])
        h_color = ACCENT
        prev_ev = None
        for ev in all_evs:
            if parse_local(ev["time"]).replace(tzinfo=None) <= x_dt:
                prev_ev = ev
        if prev_ev:
            h_color = BM_COL if prev_ev["type"] == "PM" else PM_COL

        # Déplacement ligne verticale
        self._vline.set_xdata([x_dt, x_dt])
        self._vline.set_alpha(0.5)

        # Point sur la courbe
        self._hover_pt.set_offsets([[mdates.date2num(x_dt), h_val]])
        self._hover_pt.set_alpha(0.9)

        self._mpl_canvas.draw_idle()

        # Texte de la bulle
        day_str = x_dt.strftime("%a %d/%m")   # ex. "Mar 13/05"
        self._tip_time_lbl.config(text=f"📅 {day_str}  🕐 {x_dt.strftime('%H:%M')}")
        self._tip_height_lbl.config(text=f"📏  {h_val:.2f} m", fg=h_color)

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
        """Cache la bulle, la ligne de survol et le point sur la courbe."""
        if self._tooltip_win:
            self._tooltip_win.withdraw()
        if hasattr(self, "_vline"):
            self._vline.set_alpha(0)
        if hasattr(self, "_hover_pt"):
            self._hover_pt.set_alpha(0)
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
