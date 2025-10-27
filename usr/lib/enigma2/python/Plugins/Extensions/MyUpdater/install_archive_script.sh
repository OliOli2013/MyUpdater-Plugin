#!/bin/sh
# Skrypt do instalacji list kanałów (zip lub tar.gz)
# Argument 1: Ścieżka do archiwum
# Argument 2: Typ (zip lub tar.gz)

ARCHIVE_PATH="$1"
ARCHIVE_TYPE="$2"
TARGET_DIR="/etc/enigma2/"
TMP_DIR="/tmp/MyUpdater_chlist" # Dedykowany katalog tymczasowy

echo ">>> [Skrypt] Rozpoczynam instalację: $ARCHIVE_PATH"

rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# Rozpakuj
if [ "$ARCHIVE_TYPE" = "zip" ]; then
    unzip -o -q "$ARCHIVE_PATH" -d "$TMP_DIR"
elif [ "$ARCHIVE_TYPE" = "tar.gz" ]; then
    tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"
else
    echo ">>> [Skrypt] BŁĄD: Nieznany typ archiwum: $ARCHIVE_TYPE"
    exit 1
fi

# Znajdź pliki
FILES=$(find "$TMP_DIR" -type f \( -name "lamedb" -o -name "*.tv" -o -name "*.radio" \))

if [ -n "$FILES" ]; then
    echo ">>> [Skrypt] Znaleziono pliki list. Przenoszę do $TARGET_DIR..."
    # Używamy xargs, jest bardziej niezawodne
    find "$TMP_DIR" -type f \( -name "lamedb" -o -name "*.tv" -o -name "*.radio" \) | xargs -r -I % mv -f % "$TARGET_DIR"
    
    echo ">>> [Skrypt] Pliki przeniesione."
    rm -rf "$TMP_DIR"
    rm -f "$ARCHIVE_PATH" # Usuń archiwum .zip/.tar.gz z /tmp/MyUpdater/
    echo ">>> [Skrypt] Lista zainstalowana i posprzątano."
    exit 0
else
    echo ">>> [Skrypt] BŁĄD: Nie znaleziono plików list (lamedb, *.tv) w archiwum!"
    rm -rf "$TMP_DIR"
    rm -f "$ARCHIVE_PATH" # Posprzątaj mimo błędu
    exit 1
fi
