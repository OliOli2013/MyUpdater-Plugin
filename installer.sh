#!/bin/sh
# MyUpdater-Mod installer V4 – naprawiony URL
PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
GITHUB="https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
PKGS="wget curl tar unzip bash"
FILES="plugin.py logo.png myupdater.png __init__.py install_archive_script.sh"

echo ">>> MyUpdater-Mod installer"
mkdir -p "$PLUGIN_DIR"

# --- zależności ---
for p in $PKGS; do
  command -v $p >/dev/null || opkg install $p
done

# --- pobieranie ---
for f in $FILES; do
  echo "  > $f"
  wget -q "$GITHUB/$f" -O "$PLUGIN_DIR/$f" || {
    echo "!!! błąd pobierania $f"; exit 1
  }
done

# --- uprawnienia ---
chmod 644 "$PLUGIN_DIR"/*.py "$PLUGIN_DIR"/*.png
chmod +x "$PLUGIN_DIR/install_archive_script.sh"

echo ">>> zakończono – zalecany restart GUI"
exit 0
