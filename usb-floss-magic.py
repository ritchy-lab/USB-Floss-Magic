# ============================================================
# USB-Floss Magic — Interface graphique
# © 2026 Richard Cogne — Tous droits réservés
# made by ritchy
# ============================================================

import logging
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from usbfloss import (
    JUNK_DIRS,
    MAX_VOLUME_SIZE_GB,
    delete,
    format_size,
    list_volumes,
    scan,
)

log = logging.getLogger("usbfloss.gui")

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

if sys.platform == "darwin":
    FONT_MAIN = "SF Pro Display"
    FONT_MONO = "Menlo"
elif sys.platform == "win32":
    FONT_MAIN = "Segoe UI"
    FONT_MONO = "Consolas"
else:
    FONT_MAIN = "DejaVu Sans"
    FONT_MONO = "DejaVu Sans Mono"

# Palette
BG_MAIN = "#000000"
CYAN = "#00F0FF"
CYAN_BRIGHT = "#3BFCFF"
CYAN_HOVER = "#23A7C8"
RED = "#D22D2D"
RED_BRIGHT = "#FF0000"
TEXT_WHITE = "#FFFFFF"
TEXT_GREY = "#8A9AA9"
TEXT_DIM = "#5A6A78"
LINK_COLOR = "#7FE0E8"

BORDER_BLUE = "#5B8FB8"

# Fenêtre
WIN_W = 480
WIN_H = 620

BORDER_MARGIN = 8
BORDER_WIDTH = 1
LOGO_WIDTH_OFFSET = 50

INNER_X0 = BORDER_MARGIN + 8
INNER_Y0 = BORDER_MARGIN + 8
INNER_W = WIN_W - 2 * INNER_X0
INNER_H = WIN_H - 2 * INNER_Y0

SHADOW_COLOR = "#001018"
EJECT_BOX_GAP = 4
VOL_BRACKET_GAP = 10
CURSOR_HAND = "pointinghand" if sys.platform == "darwin" else "hand2"

BOTTOM_LINE_1_OFFSET = 85
BOTTOM_LINE_2_OFFSET = 50
HELP_LINE_OFFSET = 469
SIGNATURE_OFFSET = 28

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _res(name):
    return os.path.join(SCRIPT_DIR, name)


BACKGROUND_PATH = _res("background.png")
LOGO_PATH = _res("logo.png")
BTN_IDLE_PATH = _res("button_idle.png")
BTN_ACTIVE_PATH = _res("button_active.png")
BTN_PROCESSING_PATH = _res("button_processing.png")

POPUP_SUCCESS_PATH = _res("popup_success.png")
POPUP_WARNING_PATH = _res("popup_warning.png")
POPUP_ERROR_PATH = _res("popup_error.png")

BTN_SIZE = 340
BTN_INNER_RADIUS = 90

# Icône affichée à droite du titre dans la fenêtre d'aide :
# sa taille, puis l'espace autour d'elle (à gauche, à droite).
HELP_ICON_SIZE = 55
HELP_ICON_PADX = (10, 40)

VOLUME_CHECK_INTERVAL = 2000
# Re-scan complet de la clé (junk apparu ou disparu tout seul).
# Inutile d'être plus pressé : brancher une clé ou la nettoyer déclenche déjà
# un scan immédiat, et parcourir une clé coûte cher en accès disque.
# Re-scan : le délai s'adapte à la vitesse du dernier scan. Une petite clé est
# relue toutes les 2 s (on voit tout de suite un fichier qu'on vient d'y copier),
# une grosse clé beaucoup moins souvent, pour ne pas user le disque pour rien.
RESCAN_INTERVAL = 15000        # délai maximal
RESCAN_INTERVAL_MIN = 2000     # délai minimal
RESCAN_FACTEUR = 25            # marge : 25 x la durée du dernier scan
QUEUE_POLL_INTERVAL = 100
EJECT_TIMEOUT = 30
MAX_POPUP_ROWS = 2000

# Dossiers gérés par macOS : signalés dans la liste, jamais supprimés.
# La liste vient du cœur (usbfloss.JUNK_DIRS) pour ne pas la recopier.
PROTECTED_NAMES = set(JUNK_DIRS)

APP_VERSION = "0.7"


# ------------------------------------------------------------------
# Langue de l'interface : celle du Mac (français, sinon anglais)
# ------------------------------------------------------------------
def _langue_systeme():
    """« fr » si le Mac est en français, « en » dans tous les autres cas."""
    brut = ""
    if sys.platform == "darwin":
        try:
            brut = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            brut = ""
    if not brut:
        brut = os.environ.get("LANG") or os.environ.get("LC_ALL") or ""
    trouve = re.search(r'"([^"]+)"', brut)
    code = trouve.group(1) if trouve else brut
    return "fr" if code[:2].lower() == "fr" else "en"


LANGUE = _langue_systeme()

TEXTES = {
    "fr": {
        "aucun_fichier": "> Aucun fichier",
        "trouves": "> {n} élément(s) trouvé(s)",
        "nettoyer_ejecter": "Nettoyer et Éjecter",
        "aucun": "Aucun",
        "erreur_suppression": "Erreur pendant la suppression :\n{err}",
        "titre_erreur": "Erreur",
        "supprimes": "{ok} élément(s) supprimé(s).",
        "titre_bravo": "Bravo !",
        "echecs": "{ok} supprimé(s), {ko} échec(s).\n\nCertains fichiers n'ont pas pu être supprimés.",
        "titre_attention": "Attention",
        "eject_titre": "Éjection impossible :\n{err}",
        "eject_non_pris_en_charge": "Éjection non prise en charge sur ce système.",
        "eject_delai": "La clé ne répond pas (délai de {n} s dépassé).",
        "erreur_inattendue": "Erreur inattendue : {err}",
        "eject_bloquee": "Une application bloque la clé 🛑\n\nFerme l'application pour la libérer 🔓",
        "eject_deja_retiree": "La clé a déjà été retirée.",
        "eject_plus_montee": "La clé n'est plus montée.",
        "eject_sans_reponse": "La clé ne répond pas.",
        "eject_detail": "Éjection impossible.\n\nDétail technique :\n{extrait}",
        "eject_inconnue": "Éjection impossible (raison inconnue).",
        "plus_tard": "Plus tard",
        "fermer": "Fermer",
        "don_bientot": "\n\n(Le lien de don arrive très bientôt !)",
        "aide_titre": "Aide — USB-Floss Magic",
        "liste_titre": "Fichiers trouvés",
        "liste_compte": "{n} élément(s) trouvé(s)",
        "ignore_decale": "    (ignoré)",
        "donate_titre": "le labo tourne au café,",
        "donate_bouton": "Offrir un café ☕",
        "donate_message": (
            "J'ai passé des soirées à traquer les .DS_Store, les ._cache, et tous "
            "ces fichiers fantômes que macOS laisse derrière lui. Ta clé USB ne te "
            "remerciera jamais.\n\n"
            "Moi, si.\n\n"
            "☕ ko-fi.com/ritchy_lab"
        ),
    },
    "en": {
        "aucun_fichier": "> No file",
        "trouves": "> {n} item(s) found",
        "nettoyer_ejecter": "Clean and Eject",
        "aucun": "None",
        "erreur_suppression": "Error while deleting:\n{err}",
        "titre_erreur": "Error",
        "supprimes": "{ok} item(s) removed.",
        "titre_bravo": "Well done!",
        "echecs": "{ok} removed, {ko} failed.\n\nSome files could not be deleted.",
        "titre_attention": "Warning",
        "eject_titre": "Could not eject:\n{err}",
        "eject_non_pris_en_charge": "Ejecting is not supported on this system.",
        "eject_delai": "The drive is not responding ({n} s timeout).",
        "erreur_inattendue": "Unexpected error: {err}",
        "eject_bloquee": "An application is using the drive 🛑\n\nClose it to release the drive 🔓",
        "eject_deja_retiree": "The drive has already been removed.",
        "eject_plus_montee": "The drive is no longer mounted.",
        "eject_sans_reponse": "The drive is not responding.",
        "eject_detail": "Could not eject.\n\nTechnical detail:\n{extrait}",
        "eject_inconnue": "Could not eject (unknown reason).",
        "plus_tard": "Later",
        "fermer": "Close",
        "don_bientot": "\n\n(The donation link is coming very soon!)",
        "aide_titre": "Help — USB-Floss Magic",
        "liste_titre": "Files found",
        "liste_compte": "{n} item(s) found",
        "ignore_decale": "    (ignored)",
        "donate_titre": "this lab runs on coffee,",
        "donate_bouton": "Buy me a coffee ☕",
        "donate_message": (
            "I spent evenings chasing .DS_Store, ._cache and all those ghost "
            "files macOS leaves behind. Your USB drive will never thank you.\n\n"
            "I will.\n\n"
            "☕ ko-fi.com/ritchy_lab"
        ),
    },
}


def TR(cle, **valeurs):
    """Texte dans la langue du système (l'anglais sert de secours)."""
    texte = TEXTES[LANGUE].get(cle) or TEXTES["en"].get(cle) or cle
    return texte.format(**valeurs) if valeurs else texte


GITHUB_URL = "https://github.com/ritchy-lab/USB-Floss-Magic"

# ------------------------------------------------------------------
# Soutien / dons (fenêtre ouverte par la signature en bas à gauche)
# ------------------------------------------------------------------
# Lien de la page de don. Vide = la fenêtre s'ouvre sans bouton de don.
DONATE_URL = "https://ko-fi.com/ritchy_lab"

# Lues au moment de l'affichage, pour suivre la langue courante.
DONATE_TITRE_CLE = "donate_titre"
DONATE_BOUTON_CLE = "donate_bouton"
DONATE_MESSAGE_CLE = "donate_message"

HELP_CONTENT = {
    "fr": [
        ("title", "USB-Floss Magic"),
        ("space", ""),
        ("text", "Nettoie une clé USB des fichiers inutiles"),
        ("text", "créés par macOS, Windows ou Linux."),
        ("space", ""),
        ("title2", "Utilisation"),
        ("bullet", "1. Branche une clé USB."),
        ("bullet", "2. Elle apparaît automatiquement en bas à droite."),
        ("bullet", "3. Le nombre de fichiers trouvés s'affiche."),
        ("bullet", "4. Clique sur le rond central pour nettoyer."),
        ("space", ""),
        ("title2", "Éjecter la clé"),
        ("text", "Coche « Nettoyer et Éjecter » pour que la clé"),
        ("text", "soit éjectée automatiquement après le nettoyage."),
        ("space", ""),
        ("title2", "Fichiers ignorés"),
        ("text", "Certains dossiers protégés par le système (comme"),
        ("text", ".Spotlight-V100 et .Trashes) sont laissés en place."),
        ("text", "Ils ne gênent pas et sont recréés automatiquement."),
        ("space", ""),
        ("title2", "Limite de taille"),
        ("text", "Seules les clés USB et disques externes de moins"),
        ("text", f"de {MAX_VOLUME_SIZE_GB} Go sont proposés automatiquement."),
        ("text", "Au-delà, la clé n'apparaît pas : utilisez la ligne"),
        ("text", "de commande usbfloss.py en mode direct si besoin."),
        ("space", ""),
        ("title2", "Voir le détail"),
        ("text", "Clique sur « X élément(s) trouvé(s) » pour voir"),
        ("text", "la liste complète des fichiers détectés."),
        ("space", ""),
        ("sep", ""),
        ("donate", "☕  Soutenir le projet"),
        ("credit", f"© 2026 — ritchy-lab — version {APP_VERSION}"),
        ("link", GITHUB_URL.replace("https://", "")),
    ],
    "en": [
        ("title", "USB-Floss Magic"),
        ("space", ""),
        ("text", "Cleans a USB drive of the useless files left"),
        ("text", "behind by macOS, Windows or Linux."),
        ("space", ""),
        ("title2", "How to use it"),
        ("bullet", "1. Plug in a USB drive."),
        ("bullet", "2. It shows up automatically at the bottom right."),
        ("bullet", "3. The number of files found is displayed."),
        ("bullet", "4. Click the central disc to clean."),
        ("space", ""),
        ("title2", "Ejecting the drive"),
        ("text", "Tick \u201cClean and Eject\u201d so the drive is"),
        ("text", "ejected automatically after cleaning."),
        ("space", ""),
        ("title2", "Ignored files"),
        ("text", "Some folders protected by the system (such as"),
        ("text", ".Spotlight-V100 and .Trashes) are left in place."),
        ("text", "They are harmless and recreated automatically."),
        ("space", ""),
        ("title2", "Size limit"),
        ("text", "Only USB drives and external disks under"),
        ("text", f"{MAX_VOLUME_SIZE_GB} GB are offered automatically."),
        ("text", "Beyond that the drive does not appear: use the"),
        ("text", "usbfloss.py command line in direct mode if needed."),
        ("space", ""),
        ("title2", "See the details"),
        ("text", "Click \u201cX item(s) found\u201d to see the full list"),
        ("text", "of the detected files."),
        ("space", ""),
        ("sep", ""),
        ("donate", "☕  Support the project"),
        ("credit", f"© 2026 — ritchy-lab — version {APP_VERSION}"),
        ("link", GITHUB_URL.replace("https://", "")),
    ],
}


class _CanvasLabel:
    def __init__(self, canvas, x, y, text, font, fill,
                 anchor="w", tags=(), on_change=None, shadow=True):
        self.canvas = canvas
        self._on_change = on_change
        self._shadow = None
        if shadow:
            self._shadow = canvas.create_text(
                x + 1, y + 1, text=text, font=font, fill=SHADOW_COLOR,
                anchor=anchor, tags=tags,
            )
        self._id = canvas.create_text(
            x, y, text=text, font=font, fill=fill,
            anchor=anchor, tags=tags,
        )

    def configure(self, text=None, fg=None):
        if text is not None:
            if self._shadow is not None:
                self.canvas.itemconfigure(self._shadow, text=text)
            self.canvas.itemconfigure(self._id, text=text)
        if fg is not None:
            self.canvas.itemconfigure(self._id, fill=fg)
        if text is not None and self._on_change:
            self._on_change()

    def move_to(self, x, y):
        self.canvas.coords(self._id, x, y)
        if self._shadow is not None:
            self.canvas.coords(self._shadow, x + 1, y + 1)

    def bbox(self):
        return self.canvas.bbox(self._id)


class USBFlossMagicApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"USB-Floss Magic {APP_VERSION}")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - WIN_W) // 2
        y = (screen_h - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        self.volumes = []
        self.current_volume = None
        self.all_junk = []
        self.current_junk = []
        self.protected_junk = []
        self._last_volumes_state = None
        self._last_junk_signature = None
        self._images = {}
        self._eject = False
        self._hovering_button = False

        self._results = queue.Queue()
        self._scan_running = False
        self._scan_pending = False
        self._busy = False
        self._closing = False
        self._help_popup = None
        self._help_canvas = None
        self._list_popup = None
        self._list_box = None
        self._list_title = None
        self._last_scan_duration = None
        self._help_scroll_acc = 0.0
        self.bind_all("<TouchpadScroll>", self._on_help_scroll, add="+")

        self._drag_x = 0
        self._drag_y = 0

        self._build_canvas()
        self._load_images()
        self._build_header()
        self._build_quit_button()
        self._build_central_button()
        self._build_clean_it_label()
        self._build_bottom_bar()

        self._bind_drag()

        self.update_idletasks()
        self.overrideredirect(True)
        self.deiconify()
        self.lift()
        self.focus_force()

        self.after(100, self._poll_results)
        self.after(100, self._tick_volumes)
        self.after(100, self._tick_rescan)

    def destroy(self):
        self._closing = True

        # 1) Fermer d'abord les fenêtres secondaires (aide, liste, dialogues).
        #    Sinon l'annulation globale des "after" ci-dessous supprime des
        #    commandes Tcl qui leur appartiennent, et leur destruction en
        #    cascade échoue alors avec : "can't delete Tcl command".
        for child in list(self.winfo_children()):
            if isinstance(child, tk.Toplevel):
                try:
                    child.destroy()
                except Exception:
                    pass

        # 2) Annuler les callbacks en attente (polling, rescan, popups).
        for after_id in self.tk.call('after', 'info'):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        try:
            self.canvas.delete("all")
            self._images.clear()
            self._btn_photos.clear()
        except Exception:
            pass

        super().destroy()

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self,
            width=WIN_W,
            height=WIN_H,
            bd=0,
            highlightthickness=0,
            bg=BG_MAIN,
        )
        self.canvas.pack(fill="both", expand=True)

    def _bind_tag(self, tag, on_click=None, on_enter=None, on_leave=None, hand=True):
        def enter(e):
            if hand:
                self.canvas.configure(cursor=CURSOR_HAND)
            if on_enter:
                on_enter(e)

        def leave(e):
            if hand:
                self.canvas.configure(cursor="")
            if on_leave:
                on_leave(e)

        self.canvas.tag_bind(tag, "<Enter>", enter)
        self.canvas.tag_bind(tag, "<Leave>", leave)
        if on_click:
            self.canvas.tag_bind(tag, "<Button-1>", lambda e: on_click())

    def _hover_link(self, widget):
        """Éclaircit un lien au survol.

        C'est le seul retour visuel fiable : l'option -cursor de Tk comme un
        appel direct à AppKit (NSCursor.set) se font reprendre par le système
        au mouvement de souris suivant.
        """
        widget.bind("<Enter>", lambda e: widget.configure(fg=TEXT_WHITE), add="+")
        widget.bind("<Leave>", lambda e: widget.configure(fg=LINK_COLOR), add="+")

    def _load_photo(self, path, width):
        if not os.path.exists(path):
            log.warning("Image manquante : %s", path)
            return None
        try:
            img = Image.open(path).convert("RGBA")
            height = round(width * img.height / img.width)
            img = img.resize((width, height), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            log.warning("Erreur chargement %s : %s", path, e)
            return None

    def _make_background(self):
        bg = None
        if os.path.exists(BACKGROUND_PATH):
            try:
                bg = Image.open(BACKGROUND_PATH).convert("RGBA")
                if bg.size != (WIN_W, WIN_H):
                    bg = bg.resize((WIN_W, WIN_H), Image.LANCZOS)
            except Exception as e:
                log.warning("Erreur chargement fond : %s", e)
                bg = None
        else:
            log.warning("Image manquante : %s", BACKGROUND_PATH)
        if bg is None:
            bg = Image.new("RGBA", (WIN_W, WIN_H), BG_MAIN)

        k = 4
        overlay = Image.new("RGBA", (WIN_W * k, WIN_H * k), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for inset, radius in ((BORDER_MARGIN, 12), (INNER_X0, 10)):
            draw.rounded_rectangle(
                [inset * k, inset * k, (WIN_W - inset) * k - 1, (WIN_H - inset) * k - 1],
                radius=radius * k,
                outline=BORDER_BLUE,
                width=BORDER_WIDTH * k,
            )
        overlay = overlay.resize((WIN_W, WIN_H), Image.LANCZOS)
        return ImageTk.PhotoImage(Image.alpha_composite(bg, overlay))

    def _load_images(self):
        def load_ctk(path, size):
            if not os.path.exists(path):
                log.warning("Image manquante : %s", path)
                return None
            try:
                img = Image.open(path)
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
            except Exception as e:
                log.warning("Erreur chargement %s : %s", path, e)
                return None

        self._images["popup_success"] = load_ctk(POPUP_SUCCESS_PATH, (64, 64))
        self._images["popup_warning"] = load_ctk(POPUP_WARNING_PATH, (64, 64))
        self._images["popup_error"] = load_ctk(POPUP_ERROR_PATH, (64, 64))
        self._images["help_icon"] = load_ctk(
            POPUP_SUCCESS_PATH, (HELP_ICON_SIZE, HELP_ICON_SIZE)
        )

        self._images["bg"] = self._make_background()
        self._images["logo"] = self._load_photo(LOGO_PATH, WIN_W - LOGO_WIDTH_OFFSET)
        self._btn_photos = {
            "idle": self._load_photo(BTN_IDLE_PATH, BTN_SIZE),
            "active": self._load_photo(BTN_ACTIVE_PATH, BTN_SIZE),
            "processing": self._load_photo(BTN_PROCESSING_PATH, BTN_SIZE),
        }

        self.canvas.create_image(0, 0, image=self._images["bg"], anchor="nw")

    def _build_header(self):
        if self._images.get("logo"):
            self.canvas.create_image(
                WIN_W // 2,
                INNER_Y0 + 8,
                image=self._images["logo"],
                anchor="n",
                tags=("logo",),
            )

    def _build_quit_button(self):
        self.quit_btn = _CanvasLabel(
            self.canvas,
            INNER_X0 + INNER_W - 20,
            INNER_Y0 + 118,
            "✗",
            (FONT_MAIN, 14),
            TEXT_GREY,
            anchor="ne",
            tags=("quit",),
        )
        self._bind_tag(
            "quit",
            on_click=self.destroy,
            on_enter=lambda e: self.quit_btn.configure(fg=RED_BRIGHT),
            on_leave=lambda e: self.quit_btn.configure(fg=TEXT_GREY),
        )

    def _build_central_button(self):
        photo = self._btn_photos.get("idle")
        cx = WIN_W // 2
        cy = INNER_Y0 + INNER_H // 2 + 20
        self._btn_item = self.canvas.create_image(
            cx,
            cy,
            image=photo,
            anchor="center",
            tags=("btn",),
        )

        r = BTN_INNER_RADIUS
        self.canvas.create_oval(
            cx - r, cy - r,
            cx + r, cy + r,
            outline="",
            fill="",
            tags=("btn_zone",),
        )

    def _build_clean_it_label(self):
        self.clean_it_label = _CanvasLabel(
            self.canvas,
            WIN_W // 2,
            INNER_Y0 + 130,
            "Clean it",
            (FONT_MAIN, 14, "normal"),
            CYAN,
            anchor="center",
            tags=("clean_it",),
            shadow=True,
        )

        self._bind_tag(
            "btn_zone",
            on_click=self._on_central_click,
            on_enter=self._on_btn_enter,
            on_leave=self._on_btn_leave,
        )

    def _on_btn_enter(self, event):
        self._hovering_button = True
        self._refresh_visual()

    def _on_btn_leave(self, event):
        self._hovering_button = False
        self._refresh_visual()

    def _build_bottom_bar(self):
        left = INNER_X0 + 30
        right = INNER_X0 + INNER_W - 30

        y1 = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - BOTTOM_LINE_1_OFFSET

        self.counter_label = _CanvasLabel(
            self.canvas, left, y1, TR("aucun_fichier"),
            (FONT_MAIN, 10), TEXT_DIM, anchor="w", tags=("counter",),
        )
        self._bind_tag(
            "counter",
            on_click=lambda: self._on_counter_click(None),
        )

        self.eject_text = _CanvasLabel(
            self.canvas, right, y1, TR("nettoyer_ejecter"),
            (FONT_MAIN, 10), TEXT_GREY, anchor="e", tags=("eject",),
        )
        text_x0 = self.eject_text.bbox()[0]
        self.eject_box = _CanvasLabel(
            self.canvas, text_x0 - EJECT_BOX_GAP, y1, "✗",
            (FONT_MAIN, 12, "bold"), TEXT_GREY, anchor="e", tags=("eject",),
        )
        self._bind_tag("eject", on_click=self._toggle_eject)

        self._vol_y = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - BOTTOM_LINE_2_OFFSET
        self._vol_right_x = right

        self.vol_left = _CanvasLabel(
            self.canvas, 0, self._vol_y, ">",
            (FONT_MAIN, 14, "normal"), CYAN, anchor="e", tags=("vol",),
        )
        self.vol_name = _CanvasLabel(
            self.canvas, 0, self._vol_y, TR("aucun"),
            (FONT_MAIN, 14, "normal"), CYAN, anchor="e", tags=("vol",),
            on_change=self._layout_volume_line,
        )
        self.vol_right = _CanvasLabel(
            self.canvas, 0, self._vol_y, "<",
            (FONT_MAIN, 14), CYAN, anchor="e", tags=("vol",),
        )
        self._bind_tag("vol", on_click=self._open_volume_menu)
        self._layout_volume_line()

        y3 = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - HELP_LINE_OFFSET

        self.help_btn = _CanvasLabel(
            self.canvas, 40, y3, "?",
            (FONT_MAIN, 14, "bold"), TEXT_GREY, anchor="w", tags=("help",),
        )
        self._bind_tag(
            "help",
            on_click=self._open_help,
            on_enter=lambda e: self.help_btn.configure(fg=CYAN),
            on_leave=lambda e: self.help_btn.configure(fg=TEXT_GREY),
        )

        y4 = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - SIGNATURE_OFFSET

        self.signature = _CanvasLabel(
            self.canvas, left, y4, "ritchy-lab",
            (FONT_MAIN, 9), TEXT_DIM, anchor="w", tags=("signature",),
        )
        self._bind_tag(
            "signature",
            on_click=self._open_donate,
            on_enter=lambda e: self.signature.configure(fg=CYAN),
            on_leave=lambda e: self.signature.configure(fg=TEXT_DIM),
        )

    def _layout_volume_line(self):
        self.vol_right.move_to(self._vol_right_x, self._vol_y)
        x = self.vol_right.bbox()[0] - VOL_BRACKET_GAP
        self.vol_name.move_to(x, self._vol_y)
        x = self.vol_name.bbox()[0] - VOL_BRACKET_GAP
        self.vol_left.move_to(x, self._vol_y)

    def _toggle_eject(self):
        self._eject = not self._eject
        if self._eject:
            self.eject_box.configure(text="✓", fg=CYAN)
            self.eject_text.configure(fg=CYAN)
        else:
            self.eject_box.configure(text="✗", fg=TEXT_GREY)
            self.eject_text.configure(fg=TEXT_GREY)

    def _bind_drag(self):
        self.canvas.tag_bind("logo", "<Button-1>", self._start_drag)
        self.canvas.tag_bind("logo", "<B1-Motion>", self._do_drag)

    def _start_drag(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _open_volume_menu(self):
        if not self.volumes:
            return

        menu = tk.Menu(self, tearoff=0)
        for vol, size in self.volumes:
            label = f"{vol.name}  ({format_size(size)})"
            menu.add_command(
                label=label,
                command=lambda v=vol: self._select_volume(v),
            )

        x0, _, _, y1 = self.vol_name.bbox()
        menu.post(self.winfo_rootx() + x0, self.winfo_rooty() + y1 + 4)

    def _select_volume(self, vol_path):
        self.current_volume = vol_path
        self.vol_name.configure(text=vol_path.name)
        self._last_junk_signature = None
        # Ne jamais garder la liste de la clé précédente à l'écran.
        self._set_junk([])
        self._request_scan()

    def _tick_volumes(self):
        if self._closing:
            return
        try:
            self._check_volumes()
        except Exception:
            log.exception("Erreur pendant la détection des volumes")
        finally:
            self.after(VOLUME_CHECK_INTERVAL, self._tick_volumes)

    def _tick_rescan(self):
        if self._closing:
            return
        delai = RESCAN_INTERVAL
        try:
            self._request_scan()
            duree = self._last_scan_duration
            if duree is not None:
                # Délai proportionnel au coût du dernier scan, encadré.
                delai = int(min(RESCAN_INTERVAL, max(
                    RESCAN_INTERVAL_MIN, duree * 1000 * RESCAN_FACTEUR)))
        except Exception:
            log.exception("Erreur pendant le rescan")
        finally:
            self.after(delai, self._tick_rescan)

    def _poll_results(self):
        if self._closing:
            return
        try:
            while True:
                try:
                    msg = self._results.get_nowait()
                except queue.Empty:
                    break
                kind, args = msg[0], msg[1:]
                if kind == "scan":
                    self._on_scan_done(*args)
                elif kind == "clean":
                    self._on_clean_done(*args)
        except Exception:
            log.exception("Erreur pendant le traitement d'un résultat")
        finally:
            self.after(QUEUE_POLL_INTERVAL, self._poll_results)

    def _check_volumes(self):
        new_volumes = list_volumes()
        new_state = tuple((str(v), s) for v, s in new_volumes)

        if new_state == self._last_volumes_state:
            return

        self._last_volumes_state = new_state
        self.volumes = new_volumes
        self._last_junk_signature = None

        paths = [v for v, _ in new_volumes]

        if not paths:
            self.current_volume = None
            self.vol_name.configure(text=TR("aucun"))
            self._set_junk([])
            return

        if self.current_volume not in paths:
            self.current_volume = paths[0]
            # La clé a changé : on efface tout de suite la liste précédente.
            self._last_junk_signature = None
            self._set_junk([])

        self.vol_name.configure(text=self.current_volume.name)
        self._request_scan()

    def _request_scan(self):
        if self.current_volume is None or self._busy:
            return
        if self._scan_running:
            self._scan_pending = True
            return

        self._scan_running = True
        self._scan_pending = False
        threading.Thread(
            target=self._scan_worker,
            args=(self.current_volume,),
            daemon=True,
        ).start()

    def _scan_worker(self, volume):
        debut = time.perf_counter()
        try:
            junk = scan(volume)
            duree = time.perf_counter() - debut
            self._results.put(("scan", volume, junk, None, duree))
        except Exception as e:
            self._results.put(("scan", volume, None, e, time.perf_counter() - debut))

    def _on_scan_done(self, volume, junk, error, duree=None):
        self._scan_running = False
        if duree is not None:
            self._last_scan_duration = duree

        if error is not None:
            log.warning("Scan impossible sur %s : %s", volume, error)
        elif volume == self.current_volume and not self._busy:
            signature = tuple(sorted(str(p.relative_to(volume)) for p in junk))
            if signature != self._last_junk_signature:
                self._last_junk_signature = signature
                self._set_junk(junk)

        if self._scan_pending:
            self._request_scan()

    def _is_protected(self, path):
        return path.name in PROTECTED_NAMES

    def _set_junk(self, junk):
        self.all_junk = list(junk)
        self.current_junk = [p for p in self.all_junk if not self._is_protected(p)]
        self.protected_junk = [p for p in self.all_junk if self._is_protected(p)]
        self._refresh_status()
        self._fill_list_content()      # si la fenêtre de liste est ouverte

    def _refresh_status(self):
        n = len(self.current_junk)

        if n:
            text = TR("trouves", n=n)
            color = CYAN
        else:
            text = TR("aucun_fichier")
            color = TEXT_DIM

        self.counter_label.configure(text=text, fg=color)
        self._refresh_visual()

    def _refresh_visual(self):
        if self._busy:
            state, color = "processing", RED_BRIGHT
        elif self.current_junk:
            if self._hovering_button:
                state, color = "processing", RED_BRIGHT
            else:
                state, color = "active", RED
        else:
            state, color = "idle", CYAN

        img = self._btn_photos.get(state)
        if img:
            self.canvas.itemconfigure(self._btn_item, image=img)
        self.clean_it_label.configure(fg=color)

    def _on_central_click(self):
        if self._busy or not self.current_junk or self.current_volume is None:
            return

        volume = self.current_volume
        junk = list(self.current_junk)

        self._busy = True
        self._refresh_visual()
        threading.Thread(
            target=self._clean_worker,
            args=(volume, junk, self._eject),
            daemon=True,
        ).start()

    def _clean_worker(self, volume, junk, eject):
        try:
            ok, ko = delete(junk, volume)
        except Exception as e:
            self._results.put(("clean", volume, 0, 0, e, None))
            return

        eject_error = self._eject_volume(volume) if eject else None
        self._results.put(("clean", volume, ok, ko, None, eject_error))

    def _on_clean_done(self, volume, ok, ko, error, eject_error):
        self._busy = False

        self._last_volumes_state = None
        self._last_junk_signature = None
        # Les fichiers listés viennent d'être traités : on vide tout de suite
        # le compteur pour ne pas laisser un bouton rouge mensonger.
        self._set_junk([])
        try:
            self._check_volumes()
        except Exception:
            log.exception("Erreur pendant la détection des volumes")
        self._request_scan()
        self._refresh_visual()

        popups = []

        if error is not None:
            popups.append({
                "message": TR("erreur_suppression", err=error),
                "title": TR("titre_erreur"),
                "icon": "error",
            })
        elif ko == 0:
            popups.append({
                "message": TR("supprimes", ok=ok),
                "title": TR("titre_bravo"),
                "icon": "success",
            })
        else:
            popups.append({
                "message": TR("echecs", ok=ok, ko=ko),
                "title": TR("titre_attention"),
                "icon": "warning",
            })

        if eject_error:
            popups.append({
                "message": TR("eject_titre", err=eject_error),
                "title": TR("titre_attention"),
                "icon": "warning",
            })

        self._show_dialogs_sequentially(popups)

    def _show_dialogs_sequentially(self, popups):
        if not popups:
            return

        popup_data = popups[0]
        rest = popups[1:]

        def on_close():
            if rest:
                self.after(100, lambda: self._show_dialogs_sequentially(rest))

        self._custom_dialog(
            message=popup_data["message"],
            buttons=[("OK", on_close)],
            title=popup_data["title"],
            icon=popup_data["icon"],
        )

    def _on_help_scroll(self, event):
        pop = self._help_popup
        cv = self._help_canvas
        if pop is None or cv is None or not pop.winfo_exists():
            return
        # Seulement quand le pointeur est sur la fenêtre d'aide
        if not str(event.widget).startswith(str(pop)):
            return
        try:
            dx, dy = (int(str(v)) for v in self.tk.splitlist(
                self.tk.call("tk::PreciseScrollDeltas", event.delta)))
        except Exception:
            # Repli si cette commande interne à Tk n'existe pas (Tk 8.6)
            try:
                dy = int(event.delta)
            except (TypeError, ValueError):
                return
        if dy == 0:
            return
        # On cumule les petits gestes : le canvas avance par pas de plusieurs pixels
        step = int(str(cv.cget("yscrollincrement"))) or 1
        self._help_scroll_acc += -dy
        units = int(self._help_scroll_acc / step)
        if units:
            cv.yview_scroll(units, "units")
            self._help_scroll_acc -= units * step
            
    def _open_help(self):
        # Une seule fenêtre d'aide à la fois
        if self._help_popup is not None and self._help_popup.winfo_exists():
            self._help_popup.lift()
            self._help_popup.focus_force()
            return

        popup = ctk.CTkToplevel(self)
        self._help_popup = popup
        popup.title(TR("aide_titre"))
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color=BG_MAIN)
        popup.withdraw()                       # ← cache la fenêtre tout de suite
        popup.overrideredirect(True)
        popup.bind("<Escape>", lambda e: popup.destroy())

        outer = ctk.CTkFrame(
            popup,
            fg_color=BG_MAIN,
            corner_radius=12,
            border_color=BORDER_BLUE,
            border_width=1,
        )
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        inner = ctk.CTkFrame(
            outer,
            fg_color=BG_MAIN,
            corner_radius=10,
            border_color=BORDER_BLUE,
            border_width=1,
        )
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        content = ctk.CTkScrollableFrame(
            inner,
            fg_color=BG_MAIN,
            scrollbar_button_color="#00A8B8",
            scrollbar_button_hover_color=CYAN,
            width=440,
            height=420,
        )
        content.pack(fill="both", expand=True, padx=15, pady=(15, 10))
        self._help_canvas = content._parent_canvas

        for kind, txt in HELP_CONTENT[LANGUE]:
            if kind == "space":
                tk.Label(content, text="", bg=BG_MAIN, height=1).pack()
            elif kind == "title":
                # Titre à gauche, icône à droite, sur la même ligne.
                row = tk.Frame(content, bg=BG_MAIN)
                row.pack(fill="x", pady=(4, 4))
                tk.Label(
                    row, text=txt,
                    font=(FONT_MAIN, 16, "normal"),
                    fg=CYAN, bg=BG_MAIN, anchor="w",
                ).pack(side="left")
                icon_img = self._images.get("help_icon")
                if icon_img is not None:
                    # CTkLabel obligatoire : un tk.Label ne sait pas afficher
                    # un CTkImage (TclError "image ... doesn't exist").
                    # fg_color=BG_MAIN : le fond de l'icône est transparent.
                    ctk.CTkLabel(
                        row, image=icon_img, text="",
                        fg_color=BG_MAIN, bg_color=BG_MAIN,
                    ).pack(side="right", padx=HELP_ICON_PADX)
            elif kind == "title2":
                tk.Label(
                    content, text=txt,
                    font=(FONT_MAIN, 13, "bold"),
                    fg="#3DDFA0", bg=BG_MAIN, anchor="w",
                ).pack(fill="x", pady=(10, 4))
            elif kind == "bullet":
                tk.Label(
                    content, text=txt,
                    font=(FONT_MAIN, 11),
                    fg=TEXT_WHITE, bg=BG_MAIN, anchor="w", justify="left",
                ).pack(fill="x")
            elif kind == "credit":
                tk.Label(
                    content, text=txt,
                    font=(FONT_MAIN, 10),
                    fg=TEXT_GREY, bg=BG_MAIN, anchor="center",
                ).pack(fill="x", pady=(4, 2))
            elif kind == "link":
                lbl = tk.Label(
                    content, text=txt,
                    font=(FONT_MONO, 9),
                    fg=LINK_COLOR, bg=BG_MAIN, anchor="center",
                    cursor=CURSOR_HAND,
                )
                lbl.pack(fill="x")
                lbl.bind("<Button-1>", lambda e: self._open_link(GITHUB_URL))
                self._hover_link(lbl)
            elif kind == "donate":
                # Comme le lien GitHub, mais ouvre la fenêtre de don.
                lbl = tk.Label(
                    content, text=txt,
                    font=(FONT_MAIN, 12),
                    fg=LINK_COLOR, bg=BG_MAIN, anchor="center",
                    cursor=CURSOR_HAND,
                )
                lbl.pack(fill="x", pady=(0, 4))
                lbl.bind("<Button-1>", lambda e: self._open_donate())
                self._hover_link(lbl)
            elif kind == "sep":
                tk.Frame(content, height=1, bg="#2A3A48").pack(fill="x", pady=8)
            else:
                tk.Label(
                    content, text=txt,
                    font=(FONT_MAIN, 11),
                    fg=TEXT_WHITE, bg=BG_MAIN, anchor="w", justify="left",
                ).pack(fill="x")

        ctk.CTkButton(
            inner,
            text="Fermer",
            font=(FONT_MAIN, 12, "normal"),
            width=120,
            height=32,
            corner_radius=16,
            fg_color="transparent",
            border_color=CYAN_BRIGHT,
            border_width=1,
            text_color=TEXT_WHITE,
            hover_color=CYAN_HOVER,
            command=popup.destroy,
        ).pack(pady=(0, 15))

        popup.update_idletasks()
        w = 500
        h = 600
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        popup.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        # Affiche la fenêtre une fois positionnée
        popup.deiconify()
        popup.lift()
        popup.focus_force()

        def _grab():
            try:
                popup.grab_set()
            except tk.TclError:
                pass
        popup.after(150, _grab)

    def _open_link(self, url):
        webbrowser.open(url)

    def _open_donate(self):
        """Fenêtre « offre-moi un café », ouverte par la signature."""
        message = TR(DONATE_MESSAGE_CLE)
        if DONATE_URL:
            buttons = [
                (TR(DONATE_BOUTON_CLE), lambda: self._open_link(DONATE_URL)),
                (TR("plus_tard"), None),
            ]
        else:
            # Lien pas encore renseigné : on n'affiche rien de cassé.
            buttons = [(TR("fermer"), None)]
            message += TR("don_bientot")

        self._custom_dialog(
            message=message,
            buttons=buttons,
            title=TR(DONATE_TITRE_CLE),
            icon="success",
        )

    def _eject_volume(self, volume_path):
        if sys.platform != "darwin":
            return TR("eject_non_pris_en_charge")
        try:
            res = subprocess.run(
                ["diskutil", "eject", str(volume_path)],
                capture_output=True,
                text=True,
                timeout=EJECT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return TR("eject_delai", n=EJECT_TIMEOUT)
        except Exception as e:
            return TR("erreur_inattendue", err=e)

        if res.returncode != 0:
            return self._translate_eject_error(res.stderr or res.stdout or "")
        return None

    def _translate_eject_error(self, raw):
        low = raw.lower()

        if "could not be unmounted" in low or "dissent" in low:
            return TR("eject_bloquee")
        if "was not found" in low or "no such file" in low:
            return TR("eject_deja_retiree")
        if "not mounted" in low:
            return TR("eject_plus_montee")
        if "timeout" in low:
            return TR("eject_sans_reponse")

        excerpt = raw.strip()[:200]
        if excerpt:
            return TR("eject_detail", extrait=excerpt)
        return TR("eject_inconnue")

    def _custom_dialog(self, message, buttons, title=None, subtitle=None, icon=None):
        popup = ctk.CTkToplevel(self)
        popup.title("USB-Floss")
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color=BG_MAIN)
        popup.overrideredirect(True)
        popup.bind("<Escape>", lambda e: popup.destroy())

        outer = ctk.CTkFrame(
            popup,
            fg_color=BG_MAIN,
            corner_radius=12,
            border_color=BORDER_BLUE,
            border_width=1,
        )
        outer.pack(fill="both", expand=True, padx=8, pady=8)

        inner = ctk.CTkFrame(
            outer,
            fg_color=BG_MAIN,
            corner_radius=10,
            border_color=BORDER_BLUE,
            border_width=1,
        )
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        icon_key = f"popup_{icon}" if icon else None
        icon_img = self._images.get(icon_key) if icon_key else None
        if icon_img:
            lbl_icon = ctk.CTkLabel(inner, image=icon_img, text="")
            lbl_icon.pack(pady=(20, 5))
        else:
            tk.Frame(inner, bg=BG_MAIN, height=15).pack()

        if title:
            if icon == "warning":
                title_color = "#FFA500"
            elif icon == "error":
                title_color = RED
            else:
                title_color = CYAN
            tk.Label(
                inner,
                text=title,
                font=(FONT_MAIN, 14, "normal"),
                fg=title_color,
                bg=BG_MAIN,
                bd=0,
                highlightthickness=0,
            ).pack(pady=(5, 5))

        if subtitle:
            tk.Label(
                inner,
                text=subtitle,
                font=(FONT_MAIN, 11),
                fg=TEXT_GREY,
                bg=BG_MAIN,
                bd=0,
                highlightthickness=0,
            ).pack(pady=(0, 10))

        tk.Label(
            inner,
            text=message,
            font=(FONT_MAIN, 12),
            fg=TEXT_WHITE,
            bg=BG_MAIN,
            bd=0,
            highlightthickness=0,
            justify="center",
            wraplength=420,
        ).pack(padx=20, pady=(10, 20))

        btn_frame = tk.Frame(inner, bg=BG_MAIN, bd=0, highlightthickness=0)
        btn_frame.pack(pady=(0, 20))

        def make_action(action, popup_ref):
            def handler():
                popup_ref.destroy()
                if action:
                    action()
            return handler

        for label, action in buttons:
            # Boutons « secondaires » (contour gris). « Fermer » n'en est pas
            # un : tout seul dans une fenêtre, c'est l'action principale.
            is_cancel = label.lower() in (
                "annuler", "non", "cancel", "no", "plus tard", "later",
            )
            btn = ctk.CTkButton(
                btn_frame,
                text=label,
                font=(FONT_MAIN, 12, "normal"),
                width=120,
                height=32,
                corner_radius=16,
                fg_color="transparent",
                border_color=CYAN_BRIGHT if not is_cancel else TEXT_GREY,
                border_width=1,
                text_color=TEXT_WHITE if not is_cancel else TEXT_GREY,
                hover_color=CYAN_HOVER if not is_cancel else "#2A2A2A",
                command=make_action(action, popup),
            )
            btn.pack(side="left", padx=8)

        popup.update_idletasks()
        w = 500
        h = popup.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        popup.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        def _grab():
            try:
                popup.grab_set()
                popup.focus_set()
            except tk.TclError:
                pass
        popup.after(150, _grab)

        return popup

    # ------------------------------------------------------------------
    # Fenêtre liste
    # ------------------------------------------------------------------
    def _on_counter_click(self, event):
        if not self.current_junk:
            return
        self._open_list_popup()

    def _open_list_popup(self):
        # Une seule fenêtre de liste à la fois (comme pour l'aide).
        if self._list_popup is not None and self._list_popup.winfo_exists():
            self._list_popup.lift()
            self._list_popup.focus_force()
            return

        if not self.all_junk or self.current_volume is None:
            return

        popup = ctk.CTkToplevel(self)
        self._list_popup = popup
        popup.title(TR("liste_titre"))
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color="#0A0F14")
        popup.overrideredirect(True)
        popup.bind("<Escape>", lambda e: popup.destroy())

        self.update_idletasks()
        w, h = 500, 500
        x = self.winfo_x() + (WIN_W - w) // 2
        y = self.winfo_y() + (WIN_H - h) // 2
        popup.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        self._list_title = ctk.CTkLabel(
            popup,
            text="",
            font=(FONT_MAIN, 14, "normal"),
            text_color=CYAN,
        )
        self._list_title.pack(pady=(15, 10))

        box = ctk.CTkTextbox(
            popup,
            fg_color="#0F161C",
            text_color=TEXT_WHITE,
            corner_radius=10,
            font=(FONT_MONO, 11),
            wrap="none",
            scrollbar_button_color="#00A8B8",
            scrollbar_button_hover_color=CYAN,
        )
        box.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        box.tag_config("ignored", foreground=TEXT_DIM)
        self._list_box = box
        self._fill_list_content()

        ctk.CTkButton(
            popup,
            text="Fermer",
            font=(FONT_MAIN, 13, "normal"),
            width=140,
            height=34,
            corner_radius=17,
            fg_color="transparent",
            border_color=CYAN_BRIGHT,
            border_width=1,
            text_color=TEXT_WHITE,
            hover_color=CYAN_HOVER,
            command=popup.destroy,
        ).pack(pady=(0, 15))

        def _grab():
            try:
                popup.grab_set()
                popup.focus_set()
            except tk.TclError:
                pass

        popup.after(150, _grab)

    def _fill_list_content(self):
        """(Re)remplit la fenêtre de liste — rappelée à chaque changement."""
        box = getattr(self, "_list_box", None)
        if box is None or not box.winfo_exists():
            self._list_box = None
            return

        items = list(self.all_junk)
        volume = self.current_volume
        titre = getattr(self, "_list_title", None)
        if titre is not None and titre.winfo_exists():
            titre.configure(text=TR("liste_compte", n=len(items)))

        position = box.yview()[0]          # on garde la position de lecture

        # Tout le texte en un seul insert : beaucoup plus rapide qu'une
        # insertion ligne par ligne sur des milliers d'entrées.
        lines = []
        ignored_lines = []
        for path in items[:MAX_POPUP_ROWS]:
            rel = (str(path.relative_to(volume))
                   if volume and path.is_relative_to(volume) else str(path))
            if self._is_protected(path):
                lines.append(f"{rel}" + TR("ignore_decale"))
                ignored_lines.append(len(lines))
            else:
                lines.append(rel)
        if len(items) > MAX_POPUP_ROWS:
            lines.append(f"… et {len(items) - MAX_POPUP_ROWS} autre(s)")
            ignored_lines.append(len(lines))

        box.configure(state="normal")
        box.delete("1.0", "end")
        if lines:
            box.insert("end", "\n".join(lines) + "\n")
        for num in ignored_lines:
            box.tag_add("ignored", f"{num}.0", f"{num}.end")
        box.configure(state="disabled")
        box.yview_moveto(position)


def _setup_logging():
    """En développement : logs sur la console. Dans l'app .app : dans un fichier."""
    if not getattr(sys, "frozen", False):
        logging.basicConfig(level=logging.INFO)
        return

    log_dir = os.path.join(os.path.expanduser("~"), "Library", "Logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = logging.FileHandler(
            os.path.join(log_dir, "USB-Floss Magic.log"),
            mode="w", encoding="utf-8",
        )
    except OSError:
        return
    logging.basicConfig(level=logging.INFO, handlers=[handler])


if __name__ == "__main__":
    _setup_logging()
    app = USBFlossMagicApp()
    app.mainloop()
