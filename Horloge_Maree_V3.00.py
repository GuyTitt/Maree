# Horloge-Marée_V3.0.py Version 3.0
"""Application pédagogique d'affichage des marées.

Ce module constitue un exemple complet d'application Python/Tkinter
utilisant une API REST externe, un cache JSON local, Matplotlib pour
les graphiques et le module ``zoneinfo`` pour la gestion des fuseaux
horaires.  Il est conçu pour illustrer les bonnes pratiques PEP 8 et
le style de documentation Google (Google Python Style Guide).

Dépendances::

    pip install requests matplotlib python-dotenv

Clé API :
    Créer un fichier ``.env`` à la racine du projet contenant::

        API-MAREE_KEY=votre_clé_ici

    La clé n'est jamais inscrite dans le code source (bonne pratique
    de sécurité, essentielle avant tout dépôt sur GitHub).

Données :
    Les hauteurs d'eau sont fournies par l'API https://api-maree.fr,
    calculées à partir de composantes harmoniques IFREMER diffusées
    sous licence Creative Commons Attribution (BY).

Example::

    python claude13.py
"""

version = ("","Horloge_Marée","py","3.0")
print(f"{version[0]}/{version[1]}.{version[2]} version [{version[3]}]")

# ---------------------------------------------------------------------------
# Imports — bibliothèques standard d'abord, puis tierces, puis locales
# (règle PEP 8 §  Imports)
# ---------------------------------------------------------------------------
import json          # lecture/écriture du cache local
import math          # calculs trigonométriques pour l'horloge
import os            # création du répertoire de cache, lecture variables d'env
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
from dotenv import load_dotenv                      # lecture du fichier .env
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ---------------------------------------------------------------------------
# Constantes globales — toutes les valeurs modifiables sont ici
# (couleurs, typographie, épaisseurs, tailles, textes multilingues)
# ---------------------------------------------------------------------------

# --- API ---
# La clé est lue depuis le fichier .env (jamais inscrite dans le code source).
# Créer un fichier .env contenant :  API-MAREE_KEY=votre_clé
load_dotenv()                                  # charge .env dans os.environ
API_BASE = "https://api-maree.fr"
API_KEY  = os.getenv("API-MAREE_KEY", "")     # "" si la variable est absente

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
CLK_BUBBLE_OFFSET  = 6   # distance entre le bord du cadran et la bulle (pixels)
                          # ↑ augmenter pour éloigner les bulles du cercle

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
# Titres des 4 cartes du haut
I18N_CARD_CAL     = "Sélection"
I18N_CARD_CLOCK   = "Horloge de Marée"
I18N_CARD_EVENTS  = "Inversion de marée"
I18N_CARD_CHART   = "Niveau des marées"   # suivi de « — J + J+1 » dans le code
# Format de date longue pour le panneau marées (ex. "Lundi 20 avril 2026")
I18N_WEEKDAYS_LONG = [
    "Lundi", "Mardi", "Mercredi", "Jeudi",
    "Vendredi", "Samedi", "Dimanche",
]
# Bouton calendrier
I18N_TODAY_BTN    = "Aujourd'hui"
I18N_PORT_LABEL   = "Port :"

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
        # Mémorisation pour détecter le passage à minuit dans _live_tick
        self._was_today: bool = True

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

        # Mémorisation de l'état "était-on sur aujourd'hui" pour détecter minuit
        self._was_today: bool = True

        # État pour la détection du passage à minuit
        self._was_today: bool = True   # on démarre toujours sur aujourd'hui

        # Construction de l'interface puis chargement des ports
        self.create_ui()
        self.load_sites()

    # ------------------------------------------------------------------
    # Construction de l'interface principale
    # ------------------------------------------------------------------

    def create_ui(self) -> None:
        """Crée le squelette de l'interface : en-tête + zone scrollable.

        ``self.port_combo`` est initialisé à ``None`` ici.  Il est créé
        (ou recréé) dans ``draw_calendar()`` à chaque appel de ``render_all()``.
        Pour que ``load_sites()`` puisse peupler le combobox avant le premier
        rendu, on crée un combobox **temporaire** invisible qui sera remplacé
        par le vrai à l'affichage.
        """
        # ── En-tête minimaliste ────────────────────────────────────────
        header = tk.Frame(self.root, bg=SURFACE)
        header.pack(fill="x")
        tk.Label(
            header, text="🌊  Marées – Hauteurs d'eau",
            font=(FONT, FONT_SZ_TITLE, "bold"), fg=ACCENT, bg=SURFACE
        ).pack(side="left", padx=20, pady=8)

        # ── Combobox temporaire (non affiché, pour load_sites) ─────────
        # Tkinter ne supporte pas le re-parenting natif.  On crée un widget
        # fantôme dans le header pour que load_sites() puisse le peupler.
        # draw_calendar() créera le vrai combobox visible et copiera les valeurs.
        self._port_values: list[str] = []   # valeurs disponibles
        self._port_selected: str    = ""    # port actuellement sélectionné
        # Combobox fantôme : parent = header mais jamais pack()é
        self.port_combo = ttk.Combobox(header, width=26, state="readonly",
                                       font=(FONT, 8))
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self._on_port_change())

        # ── Zone scrollable ────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        self.canvas_main = tk.Canvas(body, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas_main.yview)
        self.scrollable_frame = tk.Frame(self.canvas_main, bg=BG)

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
        self.canvas_main.bind(
            "<Configure>",
            lambda e: self.canvas_main.itemconfig(self._win, width=e.width),
        )
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

    def _on_port_change(self) -> None:
        """Callback déclenché quand l'utilisateur change de port dans n'importe quel combobox.

        Sauvegarde la sélection dans ``_port_selected`` (donnée canonique)
        puis recharge les données.
        """
        self._port_selected = self.port_combo.get()
        self.load_data()

    def load_sites(self) -> None:
        """Récupère la liste des ports depuis l'API et peuple les comboboxes.

        Les valeurs sont stockées dans ``_port_values`` et ``_port_selected``
        — des attributs simples qui survivent à la destruction/recréation
        des widgets Tkinter lors de chaque appel à ``render_all()``.
        """
        try:
            response = requests.get(f"{API_BASE}/sites?key={API_KEY}", timeout=10)
            sites = sorted(response.json().get("sites", []), key=lambda s: s["name"])
            self._port_values = [f"{s['site_id']} | {s['name']}" for s in sites]

            # Port par défaut : Boulogne-sur-Mer si disponible
            default = next(
                (s for s in sites if s["site_id"] == "boulogne-sur-mer"),
                sites[0],
            )
            self._port_selected = f"{default['site_id']} | {default['name']}"

            # Peupler le combobox fantôme (pour get_site_id avant render_all)
            self.port_combo["values"] = self._port_values
            self.port_combo.set(self._port_selected)

            self.load_data()
        except Exception as exc:  # noqa: BLE001
            self.show_status(f"{I18N_ERROR_PORTS} : {exc}", ERROR)

    def get_site_id(self) -> str:
        """Retourne l'identifiant du port sélectionné.

        Utilise ``_port_selected`` (attribut persistant) plutôt que
        ``self.port_combo.get()`` pour être robuste même si le combobox
        Tkinter vient d'être recréé et n'a pas encore reçu sa valeur.

        Returns:
            Chaîne ``site_id`` (ex : ``"boulogne-sur-mer"``).
        """
        return self._port_selected.split(" | ")[0] if self._port_selected else ""

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
        """Construit la carte « Sélection » : titre, port, navigation, calendrier.

        Cette carte regroupe toutes les commandes de l'application :
        * Sélecteur de port (Combobox).
        * Boutons ◀ / ▶ pour naviguer entre les jours.
        * Bouton « Aujourd'hui » pour revenir au jour courant.
        * Mini-calendrier mensuel avec cellules cliquables.

        Args:
            parent: Frame carte qui accueille l'ensemble.
        """
        # ── Titre de la carte ──────────────────────────────────────────
        tk.Label(parent, text=I18N_CARD_CAL, fg=MUTED, bg=SURFACE,
                 font=(FONT, FONT_SZ_CARD, "bold")).pack(anchor="w", padx=12, pady=(8, 4))

        # ── Sélecteur de port ──────────────────────────────────────────
        # À chaque render_all() le combobox est recréé dans cette carte.
        # Les valeurs et la sélection sont relues depuis _port_values et
        # _port_selected, qui survivent à la destruction des widgets Tkinter.
        port_frame = tk.Frame(parent, bg=SURFACE)
        port_frame.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(port_frame, text=I18N_PORT_LABEL, fg=MUTED, bg=SURFACE,
                 font=(FONT, 8)).pack(side="left", padx=(0, 4))
        self.port_combo = ttk.Combobox(port_frame, width=26, state="readonly",
                                       font=(FONT, 8))
        self.port_combo["values"] = self._port_values
        if self._port_selected:
            self.port_combo.set(self._port_selected)
        self.port_combo.bind("<<ComboboxSelected>>", lambda e: self._on_port_change())
        self.port_combo.pack(side="left", fill="x", expand=True)

        # ── Barre de navigation : ◀  date  ▶  Aujourd'hui ─────────────
        nav = tk.Frame(parent, bg=SURFACE)
        nav.pack(fill="x", padx=10, pady=(2, 4))
        btn_s = dict(bg=BORDER, fg=TEXT, relief="flat", bd=0,
                     padx=6, pady=3, cursor="hand2",
                     activebackground=ACCENT2, activeforeground="white")
        tk.Button(nav, text="◀", **btn_s, command=self.prev_day).pack(side="left")
        self.date_label = tk.Label(
            nav, text=self._fmt_date_long(self.current_date),
            fg=TEXT, bg=SURFACE, font=(FONT, 8), width=18)
        self.date_label.pack(side="left", padx=4)
        tk.Button(nav, text="▶", **btn_s, command=self.next_day).pack(side="left")
        tk.Button(nav, text=I18N_TODAY_BTN,
                  bg=ACCENT2, fg="white", relief="flat", bd=0,
                  padx=8, pady=3, cursor="hand2",
                  activebackground=ACCENT, activeforeground="white",
                  command=self.today).pack(side="right")

        # ── Calendrier mensuel ─────────────────────────────────────────
        self._cal_year  = self.current_date.year
        self._cal_month = self.current_date.month
        self._cal_parent = parent    # mémoriser pour _cal_shift
        self._render_calendar(parent)

    def _fmt_date_long(self, d) -> str:
        """Formate une date en chaîne courte lisible (ex. "Lun 20 Avril 2026")."""
        wd = I18N_WEEKDAYS_SHORT[d.weekday()]
        mo = I18N_MONTHS[d.month - 1]
        return f"{wd} {d.day:02d} {mo} {d.year}"

    def _fmt_date_long_full(self, d) -> str:
        """Formate avec jour complet (ex. "Lundi 20 avril 2026")."""
        wd = I18N_WEEKDAYS_LONG[d.weekday()]
        mo = I18N_MONTHS[d.month - 1].lower()
        return f"{wd} {d.day} {mo} {d.year}"

    def _render_calendar(self, parent: tk.Frame) -> None:
        """Reconstruit la grille calendrier (mois + jours).

        Ne détruit que les widgets marqués ``_is_cal_grid`` afin de
        préserver le port_combo et la barre de navigation du haut,
        construits une seule fois dans ``draw_calendar``.

        Args:
            parent: Frame carte du calendrier.
        """
        for widget in parent.winfo_children():
            if getattr(widget, "_is_cal_grid", False):
                widget.destroy()

        year, month = self._cal_year, self._cal_month
        today = datetime.now(PARIS).date()
        sel   = self.current_date

        # ── Navigation du mois ────────────────────────────────────────
        hdr = tk.Frame(parent, bg=SURFACE)
        hdr._is_cal_grid = True
        hdr.pack(fill="x", padx=8, pady=(2, 2))
        nb = dict(bg=BORDER, fg=TEXT, relief="flat", bd=0, padx=5, pady=1,
                  cursor="hand2", activebackground=ACCENT2, activeforeground="white")
        tk.Button(hdr, text="◀", **nb,
                  command=lambda: self._cal_shift(parent, -1)).pack(side="left")
        tk.Label(hdr, text=f"{I18N_MONTHS[month-1]} {year}",
                 fg=TEXT, bg=SURFACE,
                 font=(FONT, FONT_SZ_MONTH, "bold")).pack(side="left", expand=True)
        tk.Button(hdr, text="▶", **nb,
                  command=lambda: self._cal_shift(parent, 1)).pack(side="right")

        # ── Grille : titres + cellules dans le même Frame ─────────────
        cal_grid = tk.Frame(parent, bg=SURFACE)
        cal_grid._is_cal_grid = True
        cal_grid.pack(pady=(2, 4))

        for col, day_abbr in enumerate(I18N_WEEKDAYS_SHORT):
            tk.Label(cal_grid, text=day_abbr, fg=MUTED, bg=SURFACE,
                     font=(FONT, FONT_SZ_WDAY, "bold"),
                     width=3, anchor="center").grid(
                row=0, column=col, padx=CAL_PAD, pady=(0, 2), ipadx=2)

        first_wd  = datetime(year, month, 1).weekday()
        nxt       = datetime(year + (month == 12), (month % 12) + 1, 1)
        days_in   = (nxt - timedelta(days=1)).day
        g_col, g_row = first_wd, 1

        for day_num in range(1, days_in + 1):
            cell_date = datetime(year, month, day_num).date()
            self._make_day_cell(
                cal_grid, text=str(day_num), cell_date=cell_date,
                is_sel=(cell_date == sel), is_today=(cell_date == today),
                grid_row=g_row, grid_col=g_col,
            )
            g_col += 1
            if g_col == 7:
                g_col = 0
                g_row += 1

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
        """Fait avancer/reculer le calendrier d'un mois et le redessine."""
        month = self._cal_month + offset
        year  = self._cal_year
        if month > 12: month, year = 1,  year + 1
        if month < 1:  month, year = 12, year - 1
        self._cal_year, self._cal_month = year, month
        self._render_calendar(parent)

    def _pick_date(self, date_obj) -> None:
        """Sélectionne une date et recharge les données."""
        self.current_date = date_obj
        if hasattr(self, "date_label"):
            self.date_label.config(text=self._fmt_date_long(self.current_date))
        self.load_data()

    # ------------------------------------------------------------------
    # Horloge de marée
    # ------------------------------------------------------------------

    def draw_clock(self, parent: tk.Frame) -> None:
        """Crée la carte horloge.

        Si la date affichée n'est pas aujourd'hui, l'horloge est muette :
        pas d'aiguille, pas d'arcs, pas de bulles — un simple message
        indique que l'horloge n'est disponible que pour le jour courant.
        Cela évite d'afficher des informations incorrectes pour des dates
        passées ou futures.

        Args:
            parent: Frame carte de l'horloge.
        """
        tk.Label(
            parent, text=I18N_CARD_CLOCK,
            fg=MUTED, bg=SURFACE, font=(FONT, FONT_SZ_CARD, "bold"),
        ).pack(anchor="w", padx=12, pady=(8, 2))

        today = datetime.now(PARIS).date()
        if self.current_date != today:
            # Horloge muette : date non courante
            tk.Label(
                parent,
                text="⏸  Horloge disponible\nuniquement pour aujourd'hui",
                fg=MUTED, bg=SURFACE, font=(FONT, 9),
                justify="center",
            ).pack(expand=True, pady=20)
            return

        self.clock_canvas = tk.Canvas(parent, bg=SURFACE, highlightthickness=0)
        self.clock_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # On force la mise à jour des dimensions avant le premier dessin
        self.root.update()
        self.root.after(50, self.redraw_clock)

    def redraw_clock(self) -> None:
        """Redessine l'horloge de marée 24 h (minuit en haut).

        Logique des arcs :
        * L'horloge affiche une fenêtre de 24 h glissante, calée sur
          minuit du jour courant (00:00) jusqu'à minuit+24 h.
        * Les timestamps absolus sont convertis en fraction de cette
          fenêtre de 24 h pour obtenir les angles, évitant tout problème
          avec les événements du lendemain.
        * Arc PM→BM : couleur BM_COL (orange, descente).
        * Arc BM→PM : couleur PM_COL (cyan, montée).
        * Arc en cours : tronqué à l'heure actuelle (partie passée effacée).
        """
        if not hasattr(self, "clock_canvas") or not self.clock_canvas.winfo_exists():
            return
        c = self.clock_canvas
        c.update_idletasks()
        W = c.winfo_width()  or 280
        H = c.winfo_height() or 280
        c.delete("all")

        margin = CLK_MARGIN
        diam   = min(W - 2 * margin, H - 50)
        r      = max(diam // 2, 60)
        cx, cy = W // 2, H // 2 - 6

        now   = datetime.now(PARIS)
        state = self._get_clock_state()

        # ── Fenêtre 24 h : de minuit J à minuit J+1 ───────────────────
        # Tous les angles sont calculés par rapport à cette fenêtre.
        midnight_j = datetime(now.year, now.month, now.day,
                              0, 0, 0, tzinfo=PARIS)
        window_sec = 86400.0   # 24 h en secondes

        def _ts_to_tk(ts: float) -> float:
            """Timestamp → angle Tkinter (antihoraire depuis est).

            Minuit J = 90°, 6h = 0°, 12h = −90°, 18h = 180°.
            Les timestamps hors fenêtre sont extrapolés.
            """
            frac = (ts - midnight_j.timestamp()) / window_sec
            return 90.0 - frac * 360.0

        def _ts_to_trig(ts: float) -> float:
            """Timestamp → angle trigonométrique (radians, cos/sin)."""
            frac = (ts - midnight_j.timestamp()) / window_sec
            return math.radians(frac * 360.0 - 90.0)

        now_ts    = now.timestamp()
        now_tk    = _ts_to_tk(now_ts)
        now_trig  = _ts_to_trig(now_ts)

        # ── Fond du cadran ─────────────────────────────────────────────
        c.create_oval(cx-r-5, cy-r-5, cx+r+5, cy+r+5, fill=BORDER, outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r,
                      fill=SURFACE, outline="#475569", width=CLK_FACE_RING_W)

        # Si la date affichée n'est pas aujourd'hui, on ne dessine que
        # le cadran vide avec un message central (pas d'arcs ni d'aiguille).
        if not state["is_today"]:
            c.create_text(cx, cy - 10, text=I18N_CARD_CLOCK,
                          fill=MUTED, font=(FONT, 9, "bold"))
            c.create_text(cx, cy + 10,
                          text=self._fmt_date_long(self.current_date),
                          fill=MUTED, font=(FONT, 8))
            return   # sortie anticipée : pas de graduations, arcs ni aiguille

        # ── Graduations 24 h ───────────────────────────────────────────
        for h in range(24):
            frac    = h / 24.0
            ang_rad = math.radians(frac * 360.0 - 90.0)
            is_3h   = (h % 3 == 0)
            t_len   = CLK_TICK_MAJOR_LEN if is_3h else CLK_TICK_MINOR_LEN
            t_wid   = CLK_TICK_MAJOR_W   if is_3h else CLK_TICK_MINOR_W
            r_out   = r - 2
            r_in    = r_out - t_len
            c.create_line(
                cx + math.cos(ang_rad)*r_in,  cy + math.sin(ang_rad)*r_in,
                cx + math.cos(ang_rad)*r_out, cy + math.sin(ang_rad)*r_out,
                fill=CLK_TICK_COLOR, width=t_wid)
            label_r = r - t_len - 13
            if h in {0, 6, 12, 18}:
                lx = cx + math.cos(ang_rad) * label_r
                ly = cy + math.sin(ang_rad) * label_r
                c.create_text(lx, ly, text=f"{h:02d}",
                              fill=MUTED, font=(FONT, FONT_SZ_CLOCK_GRAD+2, "bold"))
            elif h in {3, 9, 15, 21}:
                lx = cx + math.cos(ang_rad) * label_r
                ly = cy + math.sin(ang_rad) * label_r
                c.create_text(lx, ly, text=f"{h:02d}",
                              fill="#6e8090", font=(FONT, FONT_SZ_CLOCK_GRAD, "bold"))

        # Quarts d'heure
        for h in range(24):
            for m in (15, 30, 45):
                frac    = (h*60 + m) / 1440.0
                ang_rad = math.radians(frac * 360.0 - 90.0)
                r_out   = r - 2
                r_in    = r_out - CLK_TICK_TINY_LEN
                c.create_line(
                    cx + math.cos(ang_rad)*r_in,  cy + math.sin(ang_rad)*r_in,
                    cx + math.cos(ang_rad)*r_out, cy + math.sin(ang_rad)*r_out,
                    fill=CLK_TICK_TINY_COL, width=1)

        # ── Horloge muette hors du jour courant ───────────────────────
        # L'horloge est un cadran temps réel : elle n'a de sens que pour
        # aujourd'hui.  Pour un autre jour, on affiche le cadran vide avec
        # le nom du jour sélectionné et on retourne sans dessiner les arcs.
        if not state["is_today"]:
            c.create_text(cx, cy - 10,
                          text=I18N_CARD_CLOCK, fill=MUTED,
                          font=(FONT, 10, "bold"))
            c.create_text(cx, cy + 14,
                          text=self._fmt_date_long(self.current_date),
                          fill="#475569", font=(FONT, 8))
            return

        # ── Arcs PM/BM ─────────────────────────────────────────────────
        # Principe : on prend les événements (passés récents + futurs)
        # et on trace un arc entre chaque paire consécutive.
        # Couleur : PM→BM = BM_COL (orange), BM→PM = PM_COL (cyan).
        # Arc en cours : start = now (partie passée effacée).
        all_ev_src = getattr(self, "events_all", self.events)

        # Tous les événements disponibles (J + J+1)
        # On ne garde que ceux qui ont une fin > maintenant
        # et un début < maintenant + 24h
        ev_pairs = []
        for i in range(len(all_ev_src) - 1):
            ev_a  = all_ev_src[i]
            ev_b  = all_ev_src[i + 1]
            ts_a  = parse_local(ev_a["time"]).timestamp()
            ts_b  = parse_local(ev_b["time"]).timestamp()
            # Ignorer les arcs entièrement passés ou entièrement hors fenêtre
            if ts_b < now_ts:
                continue
            if ts_a > now_ts + window_sec:
                break
            ev_pairs.append((ev_a, ev_b, ts_a, ts_b))

        # Limiter à 4 arcs
        ev_pairs = ev_pairs[:4]

        OVERLAP_S = CLK_OVERLAP_MIN * 60
        ar = r - CLK_ARC_RADIUS_IN

        for idx, (ev_a, ev_b, ts_a, ts_b) in enumerate(ev_pairs):
            in_progress = ts_a <= now_ts <= ts_b

            # Couleur : PM→BM = orange (descente), BM→PM = cyan (montée)
            col = BM_COL if ev_a["type"] == "PM" else PM_COL

            # Angles Tkinter
            start_tk = now_tk if in_progress else _ts_to_tk(ts_a)
            end_tk   = _ts_to_tk(ts_b)

            # extent : toujours négatif = sens horaire dans Tkinter
            extent = end_tk - start_tk
            while extent >= 0:
                extent -= 360.0
            # Sécurité : pas plus d'un tour complet
            if extent < -355:
                extent = -355

            # Chevauchement avec adjacent (arc mince)
            thin = False
            if idx > 0:
                _, _, _, prev_ts_b = ev_pairs[idx-1]
                thin = thin or abs(ts_a - prev_ts_b) < OVERLAP_S
            if idx < len(ev_pairs) - 1:
                _, _, next_ts_a, _ = ev_pairs[idx+1]
                thin = thin or abs(ts_b - next_ts_a) < OVERLAP_S

            w = CLK_ARC_WIDTH_THIN if thin else CLK_ARC_WIDTH
            c.create_arc(cx-ar, cy-ar, cx+ar, cy+ar,
                         start=start_tk, extent=extent,
                         style="arc", outline=col, width=w)

        # ── Bulles sur le bord de l'arc ───────────────────────────────
        shown_evs: set = set()
        for ev_a, ev_b, ts_a, ts_b in ev_pairs:
            for ev, ts_ev in ((ev_a, ts_a), (ev_b, ts_b)):
                ev_id = ev["time"]
                if ev_id in shown_evs:
                    continue
                if ts_ev < now_ts - 120:   # passé > 2 min → pas de bulle
                    continue
                shown_evs.add(ev_id)

                trig = _ts_to_trig(ts_ev)
                col  = PM_COL if ev["type"] == "PM" else BM_COL

                anchor_r = ar + CLK_ARC_WIDTH // 2 + 4
                ax_pt = cx + math.cos(trig) * anchor_r
                ay_pt = cy + math.sin(trig) * anchor_r

                right = math.cos(trig) >= 0
                bx    = cx + r + margin - CLK_BUBBLE_OFFSET if right else cx - r - margin + CLK_BUBBLE_OFFSET
                by    = ay_pt

                c.create_line(ax_pt, ay_pt, bx, by,
                              fill=col, width=1, dash=(3, 2))

                dt_ev     = parse_local(ev["time"])
                label_txt = f"{ev['type']} {dt_ev.strftime('%H:%M')}"
                bw   = len(label_txt) * CLK_BUBBLE_CHAR_W * 1.3 + CLK_BUBBLE_PX * 2 + 6
                bh   = CLK_BUBBLE_BH + 4
                bx0  = bx if right else bx - bw
                bx1  = bx0 + bw
                by0  = by - bh / 2
                by1  = by + bh / 2
                rr   = 4
                pts  = [bx0+rr, by0, bx1-rr, by0, bx1, by0+rr, bx1, by1-rr,
                        bx1-rr, by1, bx0+rr, by1, bx0, by1-rr, bx0, by0+rr]
                c.create_polygon(pts, fill=SURFACE, outline=col,
                                 width=1, smooth=True)
                c.create_text((bx0+bx1)/2, (by0+by1)/2,
                              text=label_txt, fill=col,
                              font=(FONT, FONT_SZ_BUBBLE+1, "bold"))

        # ── Aiguille ───────────────────────────────────────────────────
        hand_len = r - CLK_TICK_MAJOR_LEN - 10
        hx = cx + math.cos(now_trig) * hand_len
        hy = cy + math.sin(now_trig) * hand_len
        c.create_line(cx+1, cy+1, hx+2, hy+2,
                      fill=SHADOW_COL, width=CLK_HAND_SHADOW_W, capstyle="round")
        c.create_line(cx, cy, hx, hy,
                      fill=HAND_COL, width=CLK_HAND_WIDTH, capstyle="round")
        c.create_oval(hx-5, hy-5, hx+5, hy+5, fill=HAND_COL, outline="")
        c.create_oval(cx-7, cy-7, cx+7, cy+7,
                      fill=SURFACE, outline=HAND_COL, width=2)
        c.create_oval(cx-2, cy-2, cx+2, cy+2, fill=HAND_COL, outline="")

        # ── Aiguille et arcs seulement si date == aujourd'hui ────────
        # Si l'utilisateur consulte un jour passé ou futur, l'horloge
        # affiche uniquement le cadran vide (sans aiguille ni arcs),
        # car il n'y a pas de "maintenant" à pointer.
        if not state["is_today"]:
            c.create_text(cx, cy, text="—", fill=MUTED,
                          font=(FONT, 24, "bold"))
            c.create_text(cx, cy + 28,
                          text=self._fmt_date_long(self.current_date),
                          fill=MUTED, font=(FONT, 7))
            return   # on s'arrête ici : pas d'arcs, pas d'aiguille

        # ── Textes centraux (seulement si aujourd'hui) ────────────────
        if state["is_today"] and state["current_height"] is not None:
            direction = state["direction"]
            h_color = (PM_COL  if direction == "falling"
                       else BM_COL if direction == "rising" else ACCENT)
            dir_lbl = (I18N_RISING   if direction == "rising"
                       else I18N_FALLING if direction == "falling" else "")
            dir_col = (PM_COL if direction == "rising"
                       else BM_COL if direction == "falling" else MUTED)
            # Hauteur : au-dessus du centre
            c.create_text(cx, cy - 26,
                          text=f"{state['current_height']:.2f} m",
                          fill=h_color, font=(FONT, FONT_SZ_CLOCK_H+3, "bold"))
            # Heure : plus bas pour lisibilité
            c.create_text(cx, cy + 16,
                          text=now.strftime("%H:%M"),
                          fill=TEXT, font=(FONT, FONT_SZ_CLOCK_T+3, "bold"))
            # Direction
            c.create_text(cx, cy + 36,
                          text=dir_lbl, fill=dir_col,
                          font=(FONT, FONT_SZ_CLOCK_D+1))
        elif not state["is_today"]:
            # Horloge muette quand on consulte une date passée ou future :
            # aucune aiguille, aucun arc, message informatif au centre.
            c.create_text(cx, cy - 10, text=I18N_TIDE_CLOCK,
                          fill=MUTED, font=(FONT, 9, "bold"))
            c.create_text(cx, cy + 12,
                          text=self._fmt_date_long(self.current_date),
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
        title = I18N_CARD_EVENTS
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
                # Afficher la date complète : "Lundi 20 avril 2026"
                day_lbl = self._fmt_date_long_full(ev_date)
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
        d1 = self._fmt_date_long(self.current_date)
        d2 = self._fmt_date_long(self.current_date + timedelta(days=1))
        chart_title = f"{I18N_CARD_CHART} — {d1}  +  {d2}"
        # Titre de la carte + sous-titre avec les dates
        tk.Label(card, text=I18N_CARD_CHART, fg=MUTED, bg=SURFACE,
                 font=(FONT, FONT_SZ_CARD, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(card, text=chart_title, fg=ACCENT, bg=SURFACE,
                 font=(FONT, 7)).pack(anchor="w", padx=16, pady=(0, 4))

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

        # Texte de la bulle — jour en français via les constantes i18n
        # strftime("%a") renvoie la locale système (anglais sur Windows sans config)
        # On construit donc la chaîne manuellement depuis I18N_WEEKDAYS_SHORT.
        wd_fr  = I18N_WEEKDAYS_SHORT[x_dt.weekday()]   # ex. "Mar"
        day_str = f"{wd_fr} {x_dt.day:02d}/{x_dt.month:02d}"
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
        """Planifie le prochain appel de ``_live_tick`` dans 60 secondes.

        ``root.after(ms, func)`` est la méthode Tkinter pour planifier
        une fonction différée.  Elle retourne un identifiant (job_id) qui
        permet d'annuler le rappel via ``root.after_cancel(job_id)``.
        """
        self._live_job = self.root.after(60_000, self._live_tick)

    def _live_tick(self) -> None:
        """Callback exécuté toutes les 60 s pour rafraîchir horloge et graphique.

        Actions effectuées à chaque tick :
        1. Vérification du passage à minuit → rechargement complet si nécessaire.
        2. Redessinage de l'horloge (aiguille, hauteur, direction).
        3. Déplacement du repère « Maintenant » sur le graphique.

        Le passage à minuit est détecté en comparant la date courante
        affichée (``self.current_date``) avec ``datetime.now(PARIS).date()``.
        Si elles diffèrent alors que l'on était sur « aujourd'hui », cela
        signifie que minuit vient de passer : on recharge les données du
        nouveau jour et on met à jour le calendrier.
        """
        today = datetime.now(PARIS).date()

        # ── Détection du passage à minuit ─────────────────────────────
        # Si current_date était aujourd'hui et qu'il vient de changer,
        # on est passés à minuit : rechargement complet nécessaire.
        if hasattr(self, "_was_today") and self._was_today and self.current_date != today:
            # Mise à jour de la date courante vers le nouveau jour
            self.current_date = today
            # Rechargement des données (J nouveau + J+1)
            self.load_data()
            return   # load_data planifiera un nouveau live tick

        # Mémoriser si on était sur aujourd'hui (pour la prochaine vérification)
        self._was_today = (self.current_date == today)

        # ── Rafraîchissement de l'horloge ─────────────────────────────
        if hasattr(self, "clock_canvas") and self.clock_canvas.winfo_exists():
            self.redraw_clock()

        # ── Déplacement du trait « Maintenant » sur le graphique ───────
        self._update_now_line()

        # ── Replanification du prochain tick ──────────────────────────
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
        if hasattr(self, "date_label"):
            self.date_label.config(text=self._fmt_date_long(self.current_date))
        self.load_data()

    def next_day(self) -> None:
        """Avance d'un jour et recharge les données."""
        self.current_date += timedelta(days=1)
        if hasattr(self, "date_label"):
            self.date_label.config(text=self._fmt_date_long(self.current_date))
        self.load_data()

    def today(self) -> None:
        """Revient à la date d'aujourd'hui et recharge les données."""
        self.current_date = datetime.now(PARIS).date()
        if hasattr(self, "date_label"):
            self.date_label.config(text=self._fmt_date_long(self.current_date))
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
# Horloge-Marée_V3.0.py Version 3.0
