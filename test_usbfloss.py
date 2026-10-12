#!/usr/bin/env python3
"""Tests de usbfloss.py (aucune dépendance à installer).

Lance-les avec :   python3 test_usbfloss.py
"""

import tempfile
from pathlib import Path

from usbfloss import delete, is_dangerous_root, is_junk, scan


def test_is_junk_reconnait_les_fichiers_parasites():
    assert is_junk(Path("/Volumes/CLE/.DS_Store"))
    assert is_junk(Path("/Volumes/CLE/Thumbs.db"))
    assert is_junk(Path("/Volumes/CLE/Desktop.ini"))
    assert is_junk(Path("/Volumes/CLE/Photos/._vacances.jpg"))
    assert not is_junk(Path("/Volumes/CLE/Photos/vacances.jpg"))
    assert not is_junk(Path("/Volumes/CLE/rapport.pdf"))


def test_racines_refusees():
    assert is_dangerous_root(Path("/"))
    assert is_dangerous_root(Path.home())
    assert is_dangerous_root(Path("/Users"))
    assert not is_dangerous_root(Path("/Volumes/MA_CLE"))


def test_scan_trouve_le_junk_et_ignore_les_dossiers_proteges():
    with tempfile.TemporaryDirectory() as tmp:
        cle = Path(tmp)
        (cle / "Photos").mkdir()
        (cle / "Photos" / "vacances.jpg").write_text("photo")
        (cle / "Photos" / "._vacances.jpg").write_text("junk")
        (cle / ".DS_Store").write_text("junk")
        (cle / ".Spotlight-V100").mkdir()
        (cle / ".Spotlight-V100" / ".DS_Store").write_text("interne")

        noms = sorted(p.name for p in scan(cle))
        # Le dossier protégé est signalé, mais on n'entre pas dedans :
        # son .DS_Store interne n'est donc pas listé.
        assert noms == [".DS_Store", ".Spotlight-V100", "._vacances.jpg"], noms


def test_delete_ne_touche_jamais_la_cle_elle_meme():
    with tempfile.TemporaryDirectory() as tmp:
        cle = Path(tmp)
        (cle / "vacances.jpg").write_text("photo")

        ok, ko = delete([cle], cle)          # piège volontaire

        assert (ok, ko) == (0, 1)
        assert (cle / "vacances.jpg").exists()


def test_delete_ignore_un_chemin_hors_perimetre():
    with tempfile.TemporaryDirectory() as tmp:
        cle = Path(tmp) / "cle"
        cle.mkdir()
        dehors = Path(tmp) / "._ailleurs"
        dehors.write_text("à garder")

        ok, ko = delete([dehors], cle)

        assert (ok, ko) == (0, 1)
        assert dehors.exists()


def test_delete_supprime_le_junk_et_garde_le_reste():
    with tempfile.TemporaryDirectory() as tmp:
        cle = Path(tmp)
        (cle / ".DS_Store").write_text("junk")
        (cle / "vacances.jpg").write_text("photo")

        ok, ko = delete(scan(cle), cle)

        assert (ok, ko) == (1, 0)
        assert not (cle / ".DS_Store").exists()
        assert (cle / "vacances.jpg").exists()


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\n{len(tests)} test(s) réussi(s).")
