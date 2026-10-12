#!/bin/bash
# Construit USB-Floss Magic.app et son zip de publication.
#   ./build.sh
#
# La compilation se fait dans un dossier temporaire, PAS dans le dépôt :
# le dossier ~/Documents est géré par un service de synchronisation (iCloud,
# Google Drive…) qui repose un attribut com.apple.FinderInfo sur les fichiers.
# Avec cet attribut, codesign refuse de signer : le paquet part alors avec une
# signature incomplète, macOS affiche une icône de secours, et une copie
# téléchargée peut être signalée comme « endommagée ». À la fin, l'app et le zip
# sont recopiés dans dist/.
#
# PyInstaller ne fait pas non plus l'icône « Liquid Glass » de macOS 26 :
# AppIcon.icon est compilé par actool en Assets.car (macOS 26 l'utilise,
# macOS 11 à 15 continuent avec icon.icns).
set -e

cd "$(dirname "$0")"
VERSION=0.6
NOM="USB-Floss Magic"
TMP="$(mktemp -d)"
DIST="$TMP/dist"
APP="$DIST/$NOM.app"
ZIP="USB-Floss-Magic-${VERSION}-macOS-arm64.zip"

echo "1/6  compilation dans un dossier temporaire…"
pyinstaller --noconfirm --clean --distpath "$DIST" --workpath "$TMP/build" \
    "$NOM.spec" > /dev/null

echo "2/6  icône macOS 26 (Icon Composer)…"
mkdir -p "$TMP/icon"
if ! xcrun actool --compile "$TMP/icon" --app-icon AppIcon \
        --output-partial-info-plist "$TMP/icon/partial.plist" \
        --platform macosx --minimum-deployment-target 11.0 --target-device mac \
        --output-format human-readable-text "AppIcon.icon" > "$TMP/actool.log" 2>&1; then
    echo "   ÉCHEC d'actool :"
    sed -n '1,15p' "$TMP/actool.log"
    exit 1
fi
# actool signale un problème d'icône par un simple avertissement : on vérifie
# qu'il a bien produit le Assets.car (sinon l'icône serait silencieusement absente).
[ -s "$TMP/icon/Assets.car" ] || {
    echo "   actool n'a pas produit Assets.car :"; cat "$TMP/actool.log"; exit 1; }
cp "$TMP/icon/Assets.car" "$APP/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c "Set :CFBundleIconName AppIcon" "$APP/Contents/Info.plist" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleIconName string AppIcon" "$APP/Contents/Info.plist"

echo "3/6  nettoyage des attributs et signature…"
xattr -cr "$APP" 2>/dev/null || true
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "4/6  fabrication du zip…"
ditto -c -k --norsrc --noextattr --noacl --keepParent "$APP" "$DIST/$ZIP"

echo "5/6  vérification du zip (comme le fera l'utilisateur)…"
mkdir -p "$TMP/verif"
ditto -x -k "$DIST/$ZIP" "$TMP/verif"
codesign --verify --deep --strict "$TMP/verif/$NOM.app"
rm -rf "$TMP/verif"

echo "6/6  copie des résultats dans dist/…"
mkdir -p dist
rm -rf "dist/$NOM.app"
ditto "$APP" "dist/$NOM.app"
cp "$DIST/$ZIP" "dist/$ZIP"
rm -rf "$TMP"

echo
echo "Terminé : dist/$ZIP"
lipo -info "dist/$NOM.app/Contents/MacOS/$NOM" | sed 's/.*: /architecture : /'
/usr/libexec/PlistBuddy -c "Print :CFBundleIconName" "dist/$NOM.app/Contents/Info.plist" | sed 's/^/CFBundleIconName : /'
du -sh "dist/$NOM.app" "dist/$ZIP"
