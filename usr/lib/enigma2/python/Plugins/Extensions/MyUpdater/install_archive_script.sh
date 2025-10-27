#!/bin/bash
# install_archive_script.sh (MyUpdater Mod V4)
# Rozpakowuje listy kanałów (.tar.gz) do /etc/enigma2
# + przeładowuje eDVBDB

ARCHIVE_PATH="$1"
ARCHIVE_TYPE="$2"
TARGET_DIR="/etc/enigma2"
LOG_FILE="/tmp/MyUpdater_install.log"

# === logowanie wszystkiego ===
exec > >(tee -a "$LOG_FILE") 2>&1
echo ">>> $(date) Rozpoczynam rozpakowywanie: $ARCHIVE_PATH"
echo ">>> Typ: $ARCHIVE_TYPE"
echo ">>> Katalog docelowy: $TARGET_DIR"

[ ! -f "$ARCHIVE_PATH" ] && {
    echo "!!! Błąd: plik nie istnieje: $ARCHIVE_PATH"
    exit 1
}

if [ "$ARCHIVE_TYPE" = "tar.gz" ]; then
    echo ">>> Rozpakowuję tar.gz..."
    tar -xzf "$ARCHIVE_PATH" -C "$TARGET_DIR" --overwrite
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "!!! Błąd rozpakowania tar.gz (kod: $EXIT_CODE)"
        exit 1
    fi
    rm -f "$ARCHIVE_PATH"
    echo ">>> Przeładowuję listy kanałów..."
    # Python 3 lub 2 – obojętnie
    python3 -c "
from enigma import eDVBDB
db=eDVBDB.getInstance()
db.reloadServicelist()
db.reloadBouquets()
print('>>> Listy przeładowane.')
" 2>/dev/null || \
    python2 -c "
from enigma import eDVBDB
db=eDVBDB.getInstance()
db.reloadServicelist()
db.reloadBouquets()
print('>>> Listy przeładowane.')
"
    echo ">>> Zakończono sukcesem."
else
    echo "!!! Nieznany typ archiwum: $ARCHIVE_TYPE"
    exit 1
fi

exit 0
