#!/bin/bash
# Construit USB-Floss Magic.app et son zip de publication.
#   ./build.sh
#
# Pourquoi les étapes 2 et 3 : le Finder ajoute un attribut com.apple.FinderInfo
# au paquet dès qu'on le touche, et codesign refuse alors de signer. Résultat :
# signature incomplète, et macOS affiche une icône de secours à la place de la
# vraie. On nettoie donc, on signe, puis on zippe tout de suite — et le zip est
# fabriqué SANS transporter les attributs locaux (--noextattr).
set -e

cd "$(dirname "$0")"
VERSION=0.6
APP="dist/USB-Floss Magic.app"
ZIP="dist/USB-Floss-Magic-${VERSION}-macOS-arm64.zip"

echo "1/5  compilation…"
pyinstaller --noconfirm --clean "USB-Floss Magic.spec" > /dev/null

echo "2/5  nettoyage des attributs macOS…"
xattr -cr "$APP" 2>/dev/null || true
xattr -d com.apple.FinderInfo "$APP" 2>/dev/null || true

echo "3/5  signature ad-hoc…"
codesign --force --deep --sign - "$APP"

echo "4/5  vérification de la signature…"
codesign --verify --deep --strict "$APP"

echo "5/5  fabrication du zip…"
rm -f "$ZIP"
ditto -c -k --norsrc --noextattr --noacl --keepParent "$APP" "$ZIP"

echo
echo "Terminé : $ZIP"
lipo -info "$APP/Contents/MacOS/USB-Floss Magic" | sed 's/.*: //'
du -sh "$APP" "$ZIP"
