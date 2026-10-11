# ============================================================
# USB-Floss Magic — Interface graphique
# © 2026 Richard Cogne — Tous droits réservés
# made by ritchy
# ============================================================

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk


from usbfloss import list_volumes, format_size, scan, delete

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
RED = "#B51A1A"
RED_BRIGHT = "#FF0000"
TEXT_WHITE = "#FFFFFF"
TEXT_GREY = "#8A9AA9"
TEXT_DIM = "#5A6A78"

BORDER_BLUE = "#5B8FB8"

# Fenêtre
WIN_W = 480
WIN_H = 620

BORDER_MARGIN = 8
BORDER_WIDTH = 1
LOGO_WIDTH_OFFSET = 50   # marge horizontale du bandeau (px retirés)

# Zone intérieure (à l'intérieur du double liseré)
INNER_X0 = BORDER_MARGIN + 8
INNER_Y0 = BORDER_MARGIN + 8
INNER_W = WIN_W - 2 * INNER_X0
INNER_H = WIN_H - 2 * INNER_Y0

SHADOW_COLOR = "#001018"   # ombre des textes (lisibilité sur le fond)
EJECT_BOX_GAP = 4          # px entre la case ✗/✓ et le texte « Nettoyer et Éjecter »
VOL_BRACKET_GAP = 10       # px entre « > », le nom du volume et « < »
CURSOR_HAND = "pointinghand" if sys.platform == "darwin" else "hand2"

BOTTOM_LINE_1_OFFSET = 85   # distance du bas de la fenêtre pour élément et éjecter
BOTTOM_LINE_2_OFFSET = 55   # distance du bas de la fenêtre pour la ligne nom du disque

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
BTN_INNER_RADIUS = 90   # rayon de la zone cliquable (le rond rouge central)

VOLUME_CHECK_INTERVAL = 2000   # ms : détection branchement / débranchement
RESCAN_INTERVAL = 5000         # ms : rescan du contenu du volume courant
QUEUE_POLL_INTERVAL = 100      # ms : lecture des résultats des threads
EJECT_TIMEOUT = 30             # s  : délai max de diskutil eject
MAX_POPUP_ROWS = 2000          # lignes max affichées dans la fenêtre liste

PROTECTED_NAMES = {
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".DocumentRevisions-V100",
}

APP_VERSION = "0.5-magic"


# ------------------------------------------------------------------
# Texte dessiné sur le Canvas (avec une ombre pour rester lisible
# sur le fond image)
# ------------------------------------------------------------------
class _CanvasLabel:
    def __init__(self, canvas, x, y, text, font, fill,
                 anchor="w", tags=(), on_change=None):
        self.canvas = canvas
        self._on_change = on_change
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
            self.canvas.itemconfigure(self._shadow, text=text)
            self.canvas.itemconfigure(self._id, text=text)
        if fg is not None:
            self.canvas.itemconfigure(self._id, fill=fg)
        if text is not None and self._on_change:
            self._on_change()

    def move_to(self, x, y):
        self.canvas.coords(self._id, x, y)
        self.canvas.coords(self._shadow, x + 1, y + 1)

    def bbox(self):
        return self.canvas.bbox(self._id)


# ------------------------------------------------------------------
# Application
# ------------------------------------------------------------------
class USBFlossMagicApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("USB-Floss")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        # Centre la fenêtre sur l'écran (nécessaire car
        # overrideredirect empêche macOS de la placer)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - WIN_W) // 2
        y = (screen_h - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        self.volumes = []
        self.current_volume = None
        self.all_junk = []          # tout ce que scan() a trouvé
        self.current_junk = []      # supprimable (hors protégés)
        self.protected_junk = []    # ignoré
        self._last_volumes_state = None
        self._last_junk_signature = None
        self._images = {}
        self._eject = False
        self._hovering_button = False

        # Threads : scan / suppression ne bloquent plus l'interface
        self._results = queue.Queue()
        self._scan_running = False
        self._scan_pending = False
        self._busy = False          # suppression / éjection en cours
        self._closing = False

        self._drag_x = 0
        self._drag_y = 0

        self._build_canvas()
        self._load_images()
        self._build_header()
        self._build_quit_button()
        self._build_central_button()
        self._build_clean_it_label()
        self._build_bottom_bar()

        # Déplacement de la fenêtre
        self._bind_drag()

        # Retire la barre macOS pendant que la fenêtre est cachée,
        # puis l'affiche : plus de flash de la barre au lancement
        self.update_idletasks()
        self.overrideredirect(True)
        self.deiconify()
        self.lift()
        self.focus_force()

        # Les boucles démarrent après l'affichage de la fenêtre
        self.after(100, self._poll_results)
        self.after(100, self._tick_volumes)
        self.after(100, self._tick_rescan)

    def destroy(self):
        self._closing = True

        # Annule tous les callbacks programmés avant de détruire
        # (sinon Tkinter plante à la sortie sur macOS)
        for after_id in self.tk.call('after', 'info'):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

            # Vide les images avant destruction
        try:
            self.canvas.delete("all")
            self._images.clear()
            self._btn_photos.clear()
        except Exception:
            pass

        super().destroy()

    # ------------------------------------------------------------------
    # Canvas (fond image + liserés) : tout le visuel est dessiné dessus
    # ------------------------------------------------------------------
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
        """Branche clic / survol sur tous les éléments portant ce tag."""
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

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------
    def _load_photo(self, path, width):
        """Charge un PNG (alpha conservé) redimensionné à `width`, ratio gardé."""
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
        """Fond + double liseré, assemblés en une seule image."""
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

        # Liserés dessinés en 4x puis réduits (bords lissés)
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

        # Icônes des popups (widgets CTk)
        self._images["popup_success"] = load_ctk(POPUP_SUCCESS_PATH, (64, 64))
        self._images["popup_warning"] = load_ctk(POPUP_WARNING_PATH, (64, 64))
        self._images["popup_error"] = load_ctk(POPUP_ERROR_PATH, (64, 64))

        # Images dessinées sur le canvas (références à conserver)
        self._images["bg"] = self._make_background()
        self._images["logo"] = self._load_photo(LOGO_PATH, WIN_W - LOGO_WIDTH_OFFSET)
        self._btn_photos = {
            "idle": self._load_photo(BTN_IDLE_PATH, BTN_SIZE),
            "active": self._load_photo(BTN_ACTIVE_PATH, BTN_SIZE),
            "processing": self._load_photo(BTN_PROCESSING_PATH, BTN_SIZE),
        }

        self.canvas.create_image(0, 0, image=self._images["bg"], anchor="nw")

    # ------------------------------------------------------------------
    # Bandeau
    # ------------------------------------------------------------------
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
            INNER_X0 + INNER_W - 10,
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

    # ------------------------------------------------------------------
    # Bouton central + « Clean it »
    # ------------------------------------------------------------------
    def _build_central_button(self):
        photo = self._btn_photos.get("idle")
        cx = WIN_W // 2
        cy = INNER_Y0 + INNER_H // 2 + 30
        self._btn_item = self.canvas.create_image(
            cx,
            cy,
            image=photo,
            anchor="center",
            tags=("btn",),
        )

        # Zone cliquable : cercle invisible au centre du bouton
        # (représente le rond rouge intérieur)
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
            INNER_X0 + 30,
            INNER_Y0 + 140,
            "Clean it",
            (FONT_MAIN, 14, "normal"),
            CYAN,
            anchor="w",
            tags=("clean_it",),
        )

        # Zone cliquable centrale du bouton (rond rouge)
        self._bind_tag(
            "btn_zone",
            on_click=self._on_central_click,
            on_enter=self._on_btn_enter,
            on_leave=self._on_btn_leave,
        )

        # Clean it : aucune interaction (ni clic ni survol propre)
        # La couleur change uniquement au survol du bouton (tag "btn_zone")

    def _on_btn_enter(self, event):
        self._hovering_button = True
        self._refresh_visual()

    def _on_btn_leave(self, event):
        self._hovering_button = False
        self._refresh_visual()

    # ------------------------------------------------------------------
    # Barre du bas
    # ------------------------------------------------------------------
    def _build_bottom_bar(self):
        left = INNER_X0 + 30
        right = INNER_X0 + INNER_W - 30

        # ----- Ligne 1 : compteur (gauche) + éjecter (droite) -----
        y1 = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - BOTTOM_LINE_1_OFFSET

        self.counter_label = _CanvasLabel(
            self.canvas, left, y1, "> Aucun fichier",
            (FONT_MAIN, 10), TEXT_DIM, anchor="w", tags=("counter",),
        )
        self._bind_tag(
            "counter",
            on_click=lambda: self._on_counter_click(None),
        )

        # Éjecter : texte aligné à droite, case juste à gauche du texte
        self.eject_text = _CanvasLabel(
            self.canvas, right, y1, "Nettoyer et Éjecter",
            (FONT_MAIN, 10), TEXT_GREY, anchor="e", tags=("eject",),
        )
        text_x0 = self.eject_text.bbox()[0]
        self.eject_box = _CanvasLabel(
            self.canvas, text_x0 - EJECT_BOX_GAP, y1, "✗",
            (FONT_MAIN, 12, "bold"), TEXT_GREY, anchor="e", tags=("eject",),
        )
        self._bind_tag("eject", on_click=self._toggle_eject)

        # ----- Ligne 2 : > DRIVE64 < (à droite) -----
        self._vol_y = INNER_Y0 + WIN_H - 2 * BORDER_MARGIN - 6 - BOTTOM_LINE_2_OFFSET
        self._vol_right_x = right

        self.vol_left = _CanvasLabel(
            self.canvas, 0, self._vol_y, ">",
            (FONT_MAIN, 14, "normal"), CYAN, anchor="e", tags=("vol",),
        )
        self.vol_name = _CanvasLabel(
            self.canvas, 0, self._vol_y, "Aucun",
            (FONT_MAIN, 14, "normal"), CYAN, anchor="e", tags=("vol",),
            on_change=self._layout_volume_line,
        )
        self.vol_right = _CanvasLabel(
            self.canvas, 0, self._vol_y, "<",
            (FONT_MAIN, 14), CYAN, anchor="e", tags=("vol",),
        )
        self._bind_tag("vol", on_click=self._open_volume_menu)
        self._layout_volume_line()

    def _layout_volume_line(self):
        """Recale « > nom < » depuis la droite : le nom change de largeur."""
        self.vol_right.move_to(self._vol_right_x, self._vol_y)
        x = self.vol_right.bbox()[0] - VOL_BRACKET_GAP
        self.vol_name.move_to(x, self._vol_y)
        x = self.vol_name.bbox()[0] - VOL_BRACKET_GAP
        self.vol_left.move_to(x, self._vol_y)

    # ------------------------------------------------------------------
    # Toggle éjecter
    # ------------------------------------------------------------------
    def _toggle_eject(self):
        self._eject = not self._eject
        if self._eject:
            self.eject_box.configure(text="✓", fg=CYAN)
            self.eject_text.configure(fg=CYAN)
        else:
            self.eject_box.configure(text="✗", fg=TEXT_GREY)
            self.eject_text.configure(fg=TEXT_GREY)

    # ------------------------------------------------------------------
    # Déplacement de la fenêtre (clic-glisser sur le bandeau)
    # ------------------------------------------------------------------
    def _bind_drag(self):
        """Attache les événements de drag uniquement au bandeau logo."""
        self.canvas.tag_bind("logo", "<Button-1>", self._start_drag)
        self.canvas.tag_bind("logo", "<B1-Motion>", self._do_drag)

    def _start_drag(self, event):
        # Décalage entre le curseur (écran) et le coin de la fenêtre
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _do_drag(self, event):
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Menu des volumes
    # ------------------------------------------------------------------
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
        self._request_scan()

    # ------------------------------------------------------------------
    # Boucles périodiques (jamais interrompues par une exception)
    # ------------------------------------------------------------------
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
        try:
            self._request_scan()
        except Exception:
            log.exception("Erreur pendant le rescan")
        finally:
            self.after(RESCAN_INTERVAL, self._tick_rescan)

    def _poll_results(self):
        """Lit, dans le thread de l'interface, les résultats des threads."""
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

    # ------------------------------------------------------------------
    # Volumes
    # ------------------------------------------------------------------
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
            self.vol_name.configure(text="Aucun")
            self._set_junk([])
            return

        if self.current_volume not in paths:
            self.current_volume = paths[0]

        self.vol_name.configure(text=self.current_volume.name)
        self._request_scan()

    # ------------------------------------------------------------------
    # Scan (thread) — un seul scan à la fois
    # ------------------------------------------------------------------
    def _request_scan(self):
        if self.current_volume is None or self._busy:
            return
        if self._scan_running:
            self._scan_pending = True   # relancé dès la fin du scan en cours
            return

        self._scan_running = True
        self._scan_pending = False
        threading.Thread(
            target=self._scan_worker,
            args=(self.current_volume,),
            daemon=True,
        ).start()

    def _scan_worker(self, volume):
        try:
            junk = scan(volume)
            self._results.put(("scan", volume, junk, None))
        except Exception as e:
            self._results.put(("scan", volume, None, e))

    def _on_scan_done(self, volume, junk, error):
        self._scan_running = False

        if error is not None:
            # Volume probablement retiré pendant le scan : la détection
            # des volumes mettra l'affichage à jour.
            log.warning("Scan impossible sur %s : %s", volume, error)
        elif volume == self.current_volume and not self._busy:
            signature = tuple(sorted(str(p.relative_to(volume)) for p in junk))
            if signature != self._last_junk_signature:
                self._last_junk_signature = signature
                self._set_junk(junk)

        if self._scan_pending:
            self._request_scan()

    # ------------------------------------------------------------------
    # État et affichage
    # ------------------------------------------------------------------
    def _is_protected(self, path):
        return path.name in PROTECTED_NAMES

    def _set_junk(self, junk):
        self.all_junk = list(junk)
        self.current_junk = [p for p in self.all_junk if not self._is_protected(p)]
        self.protected_junk = [p for p in self.all_junk if self._is_protected(p)]
        self._refresh_status()

    def _refresh_status(self):
        n = len(self.current_junk)

        if n:
            text = f"> {n} élément(s) trouvé(s)"
            color = CYAN
        else:
            text = "> Aucun fichier"
            color = TEXT_DIM   # gris discret

        self.counter_label.configure(text=text, fg=color)
        self._refresh_visual()

    def _refresh_visual(self):
        """Image du bouton et couleur de « Clean it » selon l'état."""
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

    # ------------------------------------------------------------------
    # Clic bouton central
    # ------------------------------------------------------------------
    def _on_central_click(self):
        if self._busy or not self.current_junk or self.current_volume is None:
            return

        # Capturé avant la boîte de dialogue : le volume courant peut
        # changer pendant qu'elle est ouverte.
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

        # Resynchronise tout d'abord (volume éventuellement éjecté)
        self._last_volumes_state = None
        self._last_junk_signature = None
        try:
            self._check_volumes()
        except Exception:
            log.exception("Erreur pendant la détection des volumes")
        self._refresh_visual()

        # Prépare la liste des popups à afficher (une seule à la fois)
        popups = []

        if error is not None:
            popups.append({
                "message": f"Erreur pendant la suppression :\n{error}",
                "title": "Erreur",
                "icon": "error",
            })
        elif ko == 0:
            popups.append({
                "message": f"{ok} élément(s) supprimé(s).",
                "title": "Bravo !",
                "icon": "success",
            })
        else:
            popups.append({
                "message": f"{ok} supprimé(s), {ko} échec(s).\n\nCertains fichiers n'ont pas pu être supprimés.",
                "title": "Attention",
                "icon": "warning",
            })

        if eject_error:
            popups.append({
                "message": f"Éjection impossible :\n{eject_error}",
                "title": "Attention",
                "icon": "warning",
            })

        # Affiche les popups l'une après l'autre
        self._show_dialogs_sequentially(popups)

    def _show_dialogs_sequentially(self, popups):
        """Affiche une liste de popups l'une après l'autre.
        Chaque popup doit être fermée avant que la suivante apparaisse."""
        if not popups:
            return

        popup_data = popups[0]
        rest = popups[1:]

        def on_close():
            # Affiche la suivante après un court délai
            if rest:
                self.after(100, lambda: self._show_dialogs_sequentially(rest))

        # On passe un callback à _custom_dialog via le bouton OK
        self._custom_dialog(
            message=popup_data["message"],
            buttons=[("OK", on_close)],
            title=popup_data["title"],
            icon=popup_data["icon"],
        )

    # ------------------------------------------------------------------
    # Éjection (appelée dans un thread) — retourne un message d'erreur
    # ou None si tout s'est bien passé
    # ------------------------------------------------------------------
    def _eject_volume(self, volume_path):
        if sys.platform != "darwin":
            return "Éjection non prise en charge sur ce système."
        try:
            res = subprocess.run(
                ["diskutil", "eject", str(volume_path)],
                capture_output=True,
                text=True,
                timeout=EJECT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return f"La clé ne répond pas (délai de {EJECT_TIMEOUT} s dépassé)."
        except Exception as e:
            return f"Erreur inattendue : {e}"

        if res.returncode != 0:
            return self._translate_eject_error(res.stderr or res.stdout or "")
        return None

    def _translate_eject_error(self, raw):
        """Traduit l'erreur diskutil en message compréhensible."""
        low = raw.lower()

        if "could not be unmounted" in low or "dissent" in low:
            return (
                "Une application bloque la clé 🛑\n\n"
                "Ferme l'application pour la libérer 🔓"
            )
        if "was not found" in low or "no such file" in low:
            return "La clé a déjà été retirée."
        if "not mounted" in low:
            return "La clé n'est plus montée."
        if "timeout" in low:
            return "La clé ne répond pas."

        # Cas non reconnu : on affiche un message générique + un extrait
        # du texte original (les 200 premiers caractères)
        excerpt = raw.strip()[:200]
        if excerpt:
            return f"Éjection impossible.\n\nDétail technique :\n{excerpt}"
        return "Éjection impossible (raison inconnue)."

    # ------------------------------------------------------------------
    # Fenêtre de dialogue stylée (remplace messagebox)
    # ------------------------------------------------------------------
    def _custom_dialog(self, message, buttons, title=None, subtitle=None, icon=None):
        """Affiche une fenêtre de dialogue modale stylée.

        message   : str, texte principal (peut contenir des sauts de ligne)
        buttons   : liste de tuples (label, action) — action = callable ou None
        title     : str optionnel, titre affiché en haut
        subtitle  : str optionnel, sous-titre plus petit
        icon      : "success", "warning", "error" ou None
        """
        popup = ctk.CTkToplevel(self)
        popup.title("USB-Floss")
        popup.resizable(False, False)
        popup.transient(self)
        popup.configure(fg_color=BG_MAIN)
        popup.overrideredirect(True)
        popup.bind("<Escape>", lambda e: popup.destroy())

        # Cadre avec double liseré (cohérent avec la fenêtre principale)
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

        # Icône d'état (si fournie et chargée)
        icon_key = f"popup_{icon}" if icon else None
        icon_img = self._images.get(icon_key) if icon_key else None
        if icon_img:
            lbl_icon = ctk.CTkLabel(inner, image=icon_img, text="")
            lbl_icon.pack(pady=(20, 5))
        else:
            # Pas d'icône : on garde un peu d'espace en haut
            tk.Frame(inner, bg=BG_MAIN, height=15).pack()

        # Titre (couleur selon l'icône)
        if title:
            if icon == "warning":
                title_color = "#FFA500"   # orange
            elif icon == "error":
                title_color = RED             # rouge
            else:
                title_color = CYAN            # cyan par défaut
            tk.Label(
                inner,
                text=title,
                font=(FONT_MAIN, 14, "normal"),
                fg=title_color,
                bg=BG_MAIN,
                bd=0,
                highlightthickness=0,
            ).pack(pady=(5, 5))

        # Sous-titre
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

        # Message principal
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

        # Boutons
        btn_frame = tk.Frame(inner, bg=BG_MAIN, bd=0, highlightthickness=0)
        btn_frame.pack(pady=(0, 20))

        def make_action(action, popup_ref):
            def handler():
                popup_ref.destroy()
                if action:
                    action()
            return handler

        for label, action in buttons:
            # Style différent pour "Annuler" (plus discret)
            is_cancel = label.lower() in ("annuler", "non", "cancel")
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

        # Centrage sur la fenêtre principale
        popup.update_idletasks()
        w = 500
        h = popup.winfo_reqheight()
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        popup.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        # grab_set avec délai (sinon échoue)
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
        # Rien à afficher → on ne fait rien
        if not self.current_junk:
            return
        self._open_list_popup()

    
    def _open_list_popup(self):
        if not self.all_junk or self.current_volume is None:
            return

        items = list(self.all_junk)
        volume = self.current_volume

        popup = ctk.CTkToplevel(self)
        popup.title("Fichiers trouvés")
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

        ctk.CTkLabel(
            popup,
            text=f"{len(items)} élément(s) trouvé(s)",
            font=(FONT_MAIN, 14, "normal"),
            text_color=CYAN,
        ).pack(pady=(15, 10))

        # Une seule zone de texte : beaucoup plus légère qu'un widget par fichier
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

        for path in items[:MAX_POPUP_ROWS]:
            rel = str(path.relative_to(volume))
            if self._is_protected(path):
                box.insert("end", f"{rel}    (ignoré)\n", "ignored")
            else:
                box.insert("end", f"{rel}\n")
        if len(items) > MAX_POPUP_ROWS:
            box.insert(
                "end",
                f"… et {len(items) - MAX_POPUP_ROWS} autre(s)\n",
                "ignored",
            )
        box.configure(state="disabled")

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

        # grab_set échoue si la fenêtre n'est pas encore affichée
        def _grab():
            try:
                popup.grab_set()
                popup.focus_set()
            except tk.TclError:
                pass

        popup.after(150, _grab)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = USBFlossMagicApp()
    app.mainloop()
