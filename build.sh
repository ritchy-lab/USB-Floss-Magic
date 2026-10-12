#!/bin/bash
# Construit USB-Floss Magic.app et son zip de publication.
#   ./build.sh
#
# Deux choses que PyInstaller ne fait pas seul :
#  1. il n'arrive pas à signer le paquet : le Finder y pose un attribut
#     com.apple.FinderInfo, et codesign refuse alors de signer. D'où le
#     nettoyage suivi d'une signature explicite.
#  2. sans signature valide, macOS affiche une icône de secours à la place de la
#     vraie icône — et une copie téléchargée peut être signalée « endommagée ».
#
# La compilation se fait dans un dossier temporaire, puis l'app et le zip sont
# recopiés dans dist/ : ça évite que le Finder ou un service de synchronisation
# ne vienne salir le paquet pendant la signature.
set -e

cd "$(dirname "$0")"
VERSION=0.6
NOM="USB-Floss Magic"
TMP="$(mktemp -d)"
DIST="$TMP/dist"
APP="$DIST/$NOM.app"
ZIP="USB-Floss-Magic-${VERSION}-macOS-arm64.zip"

echo "1/5  compilation dans un dossier temporaire…"
pyinstaller --noconfirm --clean --distpath "$DIST" --workpath "$TMP/build" \
    "$NOM.spec" > /dev/null

echo "2/5  nettoyage des attributs et signature…"
xattr -cr "$APP" 2>/dev/null || true
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "3/5  fabrication du zip…"
ditto -c -k --norsrc --noextattr --noacl --keepParent "$APP" "$DIST/$ZIP"

echo "4/5  vérification du zip (comme le fera l'utilisateur)…"
mkdir -p "$TMP/verif"
ditto -x -k "$DIST/$ZIP" "$TMP/verif"
codesign --verify --deep --strict "$TMP/verif/$NOM.app"
rm -rf "$TMP/verif"

echo "5/5  copie des résultats dans dist/…"
mkdir -p dist
rm -rf "dist/$NOM.app"
ditto "$APP" "dist/$NOM.app"
cp "$DIST/$ZIP" "dist/$ZIP"
rm -rf "$TMP"

echo
echo "Terminé : dist/$ZIP"
lipo -info "dist/$NOM.app/Contents/MacOS/$NOM" | sed 's/.*: /architecture : /'
/usr/libexec/PlistBuddy -c "Print :CFBundleIconFile" "dist/$NOM.app/Contents/Info.plist" | sed 's/^/icône : /'
du -sh "dist/$NOM.app" "dist/$ZIP"
