#!/usr/bin/env python3
"""
USBFloss — Nettoyer les fichiers macOS inutiles sur une clé USB.

Version 0.6 : mode interactif, filtre des volumes Time Machine
et limite de taille pour ne proposer que les petites clés USB.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

JUNK_FILES = {
    # Fichiers macOS
    ".DS_Store",
    ".apdisk",
    ".VolumeIcon.icns",
    ".localized",
    ".AppleDouble",
    ".AppleDB",
    ".AppleShare PDS",
    ".com.apple.timemachine.donotpresent",
    # Fichiers Windows (Windows crée ces fichiers sur une clé)
    "Thumbs.db",
    "Desktop.ini",
    # Fichiers Linux / autres
    ".Trash",
}

JUNK_DIRS = {
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    ".TemporaryItems",
    ".DocumentRevisions-V100",
    ".AppleDB",
}

JUNK_PREFIXES = (
    "._",
)

# Sur macOS, les volumes externes sont montés dans /Volumes.
VOLUMES_DIR = Path("/Volumes")

# Taille maximale d'un volume proposé au nettoyage (en Go).
# Au-delà, on considère que c'est un disque de stockage, pas une clé.
MAX_VOLUME_SIZE_GB = 256

# Volumes système à ne jamais proposer
EXCLUDED_NAMES = {
    "com.apple.TimeMachine.localsnapshots",
}


def _is_junk_name(name: str, is_dir: bool) -> bool:
    """Test interne : le nom et le type suffisent, sans toucher au disque."""
    if name in JUNK_FILES:
        return True
    if is_dir and name in JUNK_DIRS:
        return True
    return name.startswith(JUNK_PREFIXES)


def is_junk(path: Path) -> bool:
    """Renvoie True si le chemin correspond à un fichier parasite macOS."""
    return _is_junk_name(path.name, path.is_dir())


def scan(root: Path) -> list[Path]:
    """Parcourt récursivement `root` et renvoie la liste des fichiers parasites.

    On utilise os.walk plutôt que Path.rglob, pour deux raisons :
      - on ne fabrique un objet Path que pour les candidats (rglob en crée un
        pour chaque fichier du disque, ce qui est lent sur une grosse clé) ;
      - on refuse de descendre dans les dossiers protégés (.Spotlight-V100,
        .Trashes...), qui ne contiennent rien à nettoyer. Ces dossiers sont
        quand même signalés, pour que l'interface les affiche « ignorés ».
    """
    junk: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)

        for name in dirnames:
            if _is_junk_name(name, True):
                junk.append(base / name)

        # On retire les dossiers protégés du parcours : on n'y entre jamais.
        dirnames[:] = [d for d in dirnames if d not in JUNK_DIRS]

        for name in filenames:
            if _is_junk_name(name, False):
                junk.append(base / name)

    return junk


def is_dangerous_root(root: Path) -> bool:
    """True si la racine est trop large pour un nettoyage de clé USB.

    Refuse le disque entier ("/" ou "C:\\") et le dossier personnel, ainsi
    que n'importe quel dossier qui le contient (comme "/Users").
    """
    return root == Path(root.anchor) or Path.home().is_relative_to(root)


def delete(paths: list[Path], root: Path) -> tuple[int, int]:
    """Supprime les chemins donnés. Renvoie (succès, échecs)."""
    if is_dangerous_root(root):
        print(f"  Nettoyage impossible ici : {root}")
        return 0, len(paths)

    ok = 0
    ko = 0
    for path in paths:
        # Un fichier ne se supprime que s'il est DANS la racine, et jamais
        # la racine elle-même (sinon rmtree effacerait tout son contenu).
        if path == root:
            print(f"  IGNORÉ   : {path} (c'est la racine elle-même)")
            ko += 1
            continue
        if not path.is_relative_to(root):
            print(f"  IGNORÉ   : {path} (hors de {root})")
            ko += 1
            continue

        rel = path.relative_to(root)
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"  supprimé : {rel}")
            ok += 1
        except FileNotFoundError:
            # Le fichier a déjà été supprimé (entre le scan et maintenant)
            print(f"  déjà absent : {rel}")
            ok += 1
        except OSError as e:
            print(f"  ÉCHEC    : {rel} ({e})")
            ko += 1
    return ok, ko


def is_time_machine(volume: Path) -> bool:
    """Détecte si un volume sert à Time Machine."""
    # Time Machine HFS+ : dossier Backups.backupdb à la racine
    if (volume / "Backups.backupdb").exists():
        return True
    # Time Machine APFS : fichier marqueur à la racine
    if (volume / ".com.apple.timemachine.donotpresent").exists():
        return True
    return False


def volume_size_gb(volume: Path) -> float | None:
    """Renvoie la taille totale du volume en Go, ou None si indisponible."""
    try:
        total, _used, _free = shutil.disk_usage(volume)
        return total / (1024 ** 3)
    except OSError:
        return None


def list_volumes() -> list[tuple[Path, float]]:
    """Renvoie la liste des volumes éligibles : (chemin, taille en Go).

    Exclut : disques système, Time Machine, volumes > MAX_VOLUME_SIZE_GB.
    """
    if not VOLUMES_DIR.is_dir():
        return []

    volumes = []
    for entry in sorted(VOLUMES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        # Disque de démarrage (lien symbolique)
        if os.path.islink(entry):
            continue
        # Volumes système connus
        if entry.name in EXCLUDED_NAMES:
            continue
        # Time Machine
        if is_time_machine(entry):
            continue
        # Taille
        size = volume_size_gb(entry)
        if size is None:
            continue
        if size > MAX_VOLUME_SIZE_GB:
            continue

        volumes.append((entry, size))

    return volumes


def format_size(size_gb: float) -> str:
    """Formate une taille en Go ou To pour l'affichage."""
    if size_gb >= 1000:
        return f"{size_gb / 1000:.1f} To"
    return f"{size_gb:.0f} Go"


def choose_volume() -> Path | None:
    """Propose à l'utilisateur de choisir un volume. Renvoie None si annulé."""
    volumes = list_volumes()

    if not volumes:
        print("Aucun volume éligible détecté.")
        print("Branche une clé USB ou un petit disque externe, puis relance.")
        print(f"(Seuls les volumes de moins de {MAX_VOLUME_SIZE_GB} Go sont proposés.)")
        return None

    print("Volumes détectés :")
    for i, (vol, size) in enumerate(volumes, start=1):
        print(f"  {i}. {vol.name:<20} ({format_size(size)})")
    print()

    while True:
        answer = input(f"Quel volume nettoyer ? [1-{len(volumes)}] ").strip()

        if not answer:
            print("Annulé.")
            return None

        try:
            choice = int(answer)
        except ValueError:
            print("Réponse invalide. Tape un numéro.")
            continue

        if 1 <= choice <= len(volumes):
            return volumes[choice - 1][0]

        print(f"Numéro hors plage. Choisis entre 1 et {len(volumes)}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nettoie les fichiers macOS inutiles sur une clé USB.",
    )
    parser.add_argument(
        "chemin",
        type=Path,
        nargs="?",
        help="Dossier à nettoyer (ex : /Volumes/DRIVE64). "
             "Si omis, mode interactif.",
    )
    parser.add_argument("--delete", action="store_true",
                        help="Supprime réellement les fichiers (sinon : aperçu).")
    parser.add_argument("--yes", action="store_true",
                        help="Ne pas demander de confirmation.")
    return parser.parse_args()


def main():
    args = parse_args()

    # Choix du volume : direct ou interactif
    if args.chemin is None:
        root = choose_volume()
        if root is None:
            sys.exit(0)
    else:
        root = args.chemin.resolve()

    if not root.is_dir():
        print(f"Erreur : {root} n'est pas un dossier valide.")
        sys.exit(1)

    if is_dangerous_root(root):
        print(f"Erreur : {root} est trop large. Indique le dossier d'une clé USB.")
        sys.exit(1)

    print()
    print(f"Analyse de : {root}")
    print()

    junk = scan(root)

    if not junk:
        print("Aucun fichier parasite trouvé. La clé est propre.")
        return

    print(f"{len(junk)} élément(s) parasite(s) trouvé(s) :\n")
    for path in junk:
        kind = "dossier" if path.is_dir() else "fichier"
        print(f"  [{kind}] {path.relative_to(root)}")

    print()

    if not args.delete:
        print("Mode aperçu — rien n'a été supprimé.")
        print("Pour supprimer, relance avec --delete")
        return

    if not args.yes:
        answer = input(f"Nettoyer {root.name} ? [o/N] ").strip().lower()
        if answer not in ("o", "oui", "y", "yes"):
            print("Annulé.")
            return

    print()
    ok, ko = delete(junk, root)
    print()
    print(f"Terminé : {ok} supprimé(s), {ko} échec(s).")


if __name__ == "__main__":
    main()
