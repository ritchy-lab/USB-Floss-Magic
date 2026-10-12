# USB-Floss Magic

Nettoie une clé USB des fichiers inutiles que macOS, Windows ou Linux y laissent :
`.DS_Store`, `._fichier`, `Thumbs.db`, `Desktop.ini`, `.Spotlight-V100`…

Pensé pour les clés qui font des allers-retours entre un Mac et un PC : en un
clic la clé redevient propre, et **ces fichiers se recréent tout seuls si le
système en a besoin — aucune donnée n'est perdue**.

## Ce que fait l'application

- détecte automatiquement les clés USB et petits disques externes branchés
  (moins de 256 Go, hors disques Time Machine) ;
- affiche le nombre de fichiers parasites trouvés ;
- les supprime d'un clic sur le bouton central ;
- peut éjecter la clé juste après le nettoyage (case « Nettoyer et Éjecter ») ;
- clique sur « X élément(s) trouvé(s) » pour voir la liste complète.

## Installation (pour lancer depuis le code)

Il faut **Python 3.10 ou plus récent** et **macOS** (les volumes sont lus dans
`/Volumes`).

```bash
pip install -r requirements.txt
python3 usb-floss-magic.py
```

## Version ligne de commande

```bash
python3 usbfloss.py                                  # menu : choisir la clé
python3 usbfloss.py /Volumes/MA_CLE                  # aperçu, ne supprime rien
python3 usbfloss.py /Volumes/MA_CLE --delete         # supprime (demande confirmation)
python3 usbfloss.py /Volumes/MA_CLE --delete --yes   # supprime sans confirmation
```

## Sécurité

- l'application refuse de nettoyer la racine du disque (`/`) ou tout dossier qui
  contient ton dossier personnel : elle ne travaille que sur une clé ou un petit
  disque externe ;
- chaque suppression vérifie que le fichier est bien **dans** la clé choisie,
  et jamais la clé elle-même ;
- les dossiers gérés par macOS (`.Spotlight-V100`, `.Trashes`, `.fseventsd`…)
  sont signalés dans la liste mais jamais supprimés ;
- les fichiers nettoyés (`.DS_Store`, `._*`…) sont recréés automatiquement par
  le système quand c'est utile : les supprimer ne casse rien.

## Construire l'application macOS (.app)

```bash
pyinstaller "USB-Floss Magic.spec"
```

Le résultat est dans `dist/USB-Floss Magic.app`. Les images (`background.png`,
`logo.png`, `button_*.png`, `popup_*.png`) doivent rester à côté du script.

En cas de souci avec la version `.app`, les messages d'erreur sont écrits dans
`~/Library/Logs/USB-Floss Magic.log`.

## Tests

```bash
python3 test_usbfloss.py
```

## Licence

MIT — © 2026 ritchy-lab
