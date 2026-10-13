# USB-Floss Magic

🇬🇧 **[English version](README.en.md)**

Nettoie une clé USB des fichiers inutiles que macOS, Windows ou Linux y laissent :
`.DS_Store`, `._fichier`, `Thumbs.db`, `Desktop.ini`, `.Spotlight-V100`…

Pensé pour les clés qui font des allers-retours entre un Mac et un PC : en un
clic la clé redevient propre, et **ces fichiers se recréent tout seuls si le
système en a besoin — aucune donnée n'est perdue**.

![USB-Floss Magic : quatre fichiers parasites détectés sur la clé DRIVE64](screenshot.png)

## Téléchargement

La version prête à l'emploi (application macOS pour **Apple Silicon**,
M1 et suivants) se trouve dans
[**Releases**](https://github.com/ritchy-lab/USB-Floss-Magic/releases/latest) :
télécharge le fichier `.zip`, décompresse-le, puis glisse l'application dans
`Applications`.

⚠️ L'application n'est pas signée par un certificat Apple payant, donc macOS
affiche un avertissement au premier lancement. Pour l'ouvrir quand même :
**clic droit sur l'application → Ouvrir**, puis confirme. Si macOS refuse
toujours (macOS 15 et suivants) : **Réglages Système → Confidentialité et
sécurité**, puis « Ouvrir quand même » en bas de la fenêtre.

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
./build.sh
```

Le script compile, retire les attributs `com.apple.FinderInfo` que le Finder
pose sur le paquet, signe en ad-hoc, vérifie la signature, puis fabrique le zip
de publication. Sans ce nettoyage et cette signature, le paquet part avec une
signature incomplète — et macOS affiche alors une icône de secours à la place de
la vraie.

Équivalent manuel :

```bash
pyinstaller --noconfirm --clean "USB-Floss Magic.spec"
xattr -cr "dist/USB-Floss Magic.app"
codesign --force --deep --sign - "dist/USB-Floss Magic.app"
ditto -c -k --norsrc --noextattr --noacl --keepParent \
  "dist/USB-Floss Magic.app" "dist/USB-Floss-Magic-0.7-macOS-arm64.zip"
```

Le résultat est dans `dist/USB-Floss Magic.app`. Les images (`background.png`,
`logo.png`, `button_*.png`, `popup_*.png`) doivent rester à côté du script.

> **Note sur l'architecture** : la construction en version *universelle*
> (Intel + Apple Silicon) est bloquée par Pillow, qui n'est pas distribué en
> binaire universel sur PyPI. Le spec compile donc pour l'architecture de la
> machine. Pour un Mac Intel, il faut un environnement Python x86_64 (sous
> Rosetta) et y relancer la construction.

> **Note sur l'icône et macOS 26** : macOS 26 (Tahoe) peut redessiner les icônes
> des applications qui ne suivent pas son nouveau gabarit « squircle ». Le projet
> utilise volontairement son icône ronde détourée (`icon.icns` + `icon.png`) :
> elle couvre toutes les tailles de 16 à 512 px avec des coins transparents. Pour
> adopter l'icône « Liquid Glass » de macOS 26, il faudrait fournir un fichier
> *Icon Composer* (`.icon`) compilé avec Xcode 26.

En cas de souci avec la version `.app`, les messages d'erreur sont écrits dans
`~/Library/Logs/USB-Floss Magic.log`.

## Tests

```bash
python3 test_usbfloss.py
```

## Soutenir le projet

USB-Floss Magic est gratuit, sans publicité et sans traqueur. Si l'app t'a
rendu service, tu peux m'offrir un café ☕ :

[**ko-fi.com/ritchy_lab**](https://ko-fi.com/ritchy_lab)

## Licence

MIT — © 2026 ritchy-lab
