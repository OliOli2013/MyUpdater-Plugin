#!/bin/sh
# Instalator/aktualizator MyUpdater Enhanced V5
# Kompletna przebudowa z pełną kompatybilnością OpenATV/OpenPLI

# --- Konfiguracja ---
PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
GITHUB_RAW_URL="https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
REQUIRED_PKGS="wget curl tar unzip bash python-json python-core"

# Pliki do pobrania
FILES_TO_DOWNLOAD="
plugin_enhanced.py
logo.png
myupdater.png
__init__.py
install_archive_script.sh
"

# Funkcje pomocnicze
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a /tmp/MyUpdater_install.log
}

detect_distribution() {
    if [ -f /etc/openatv-release ]; then
        echo "openatv"
    elif [ -f /etc/openpli-release ]; then
        echo "openpli"
    elif [ -f /etc/vti-version-info ]; then
        echo "vix"
    else
        echo "unknown"
    fi
}

get_opkg_command() {
    if [ "$(detect_distribution)" = "openpli" ]; then
        echo "opkg --force-overwrite --force-downgrade"
    else
        echo "opkg --force-overwrite"
    fi
}

# --- Sprawdzenie uprawnień ---
if [ "$(id -u)" -ne 0 ]; then
    echo "------------------------------------------"
    echo "!!! BŁĄD: Skrypt wymaga uprawnień root!"
    echo "Użyj: sudo $0 lub zaloguj się jako root"
    echo "------------------------------------------"
    exit 1
fi

echo "------------------------------------------"
echo ">>> Rozpoczynam instalację/aktualizację MyUpdater Enhanced..."
echo ">>> Detekcja systemu: $(detect_distribution)"
echo "------------------------------------------"

# --- Sprawdzanie i instalacja zależności ---
echo ""
echo ">>> Sprawdzanie zależności..."
MISSING_PKGS=""

for PKG in $REQUIRED_PKGS; do
    if ! command -v $PKG >/dev/null 2>&1 && ! opkg list-installed | grep -q "^$PKG "; then
        echo "  > Brak pakietu: $PKG"
        MISSING_PKGS="$MISSING_PKGS $PKG"
    else
        echo "  > OK: $PKG"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    echo ""
    echo ">>> Próba instalacji brakujących pakietów:$MISSING_PKGS"
    log "Instalacja pakietów: $MISSING_PKGS"
    
    echo "> Aktualizacja listy pakietów..."
    opkg update >/dev/null 2>&1
    
    echo "> Instalowanie pakietów..."
    opkg install $MISSING_PKGS >/dev/null 2>&1
    
    # Sprawdzenie czy się udało
    RECHECK_MISSING=""
    for PKG in $MISSING_PKGS; do
        if ! command -v $PKG >/dev/null 2>&1 && ! opkg list-installed | grep -q "^$PKG " 2>/dev/null; then
            RECHECK_MISSING="$RECHECK_MISSING $PKG"
        fi
    done
    
    if [ -n "$RECHECK_MISSING" ]; then
        echo ""
        echo "!!! BŁĄD: Nie udało się zainstalować:$RECHECK_MISSING"
        echo "!!! Instalacja przerwana. Spróbuj zainstalować je ręcznie."
        log "Błąd instalacji pakietów: $RECHECK_MISSING"
        echo "------------------------------------------"
        exit 1
    else
        echo "> Wszystkie wymagane pakiety zostały zainstalowane."
        log "Pakiety zainstalowane pomyślnie"
    fi
else
    echo "> Wszystkie wymagane pakiety są już zainstalowane."
fi

# --- Tworzenie katalogu wtyczki ---
echo ""
echo ">>> Tworzenie katalogu wtyczki:"
echo "  $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"

# --- Pobieranie plików wtyczki ---
echo ""
echo ">>> Pobieranie plików wtyczki..."
SUCCESS=true
FAILED_FILES=""

for FILE in $FILES_TO_DOWNLOAD; do
    echo "  > Pobieranie $FILE..."
    
    # Specjalne traktowanie dla plugin_enhanced.py
    if [ "$FILE" = "plugin_enhanced.py" ]; then
        TARGET_FILE="plugin.py"
    else
        TARGET_FILE="$FILE"
    fi
    
    if wget -q --timeout=30 "$GITHUB_RAW_URL/$FILE" -O "$PLUGIN_DIR/$TARGET_FILE" 2>/dev/null; then
        echo "    ✓ Sukces"
        log "Pobrano: $FILE"
    else
        echo "    ✗ BŁĄD"
        log "Błąd pobierania: $FILE"
        SUCCESS=false
        FAILED_FILES="$FAILED_FILES $FILE"
    fi
done

if [ "$SUCCESS" = false ]; then
    echo ""
    echo "!!! BŁĄD: Nie udało się pobrać plików:$FAILED_FILES"
    echo "!!! Sprawdź połączenie internetowe i spróbuj ponownie."
    log "Błąd pobierania plików: $FAILED_FILES"
    echo "------------------------------------------"
    exit 1
fi

# --- Nadawanie uprawnień ---
echo ""
echo ">>> Ustawianie uprawnień dla plików wtyczki..."
chmod 644 "$PLUGIN_DIR"/*.png "$PLUGIN_DIR"/*.py 2>/dev/null || true
chmod +x "$PLUGIN_DIR/install_archive_script.sh"

# --- Czyszczenie starych plików ---
echo ""
echo ">>> Czyszczenie starych plików..."
rm -f "$PLUGIN_DIR"/*.pyo 2>/dev/null || true
rm -f "$PLUGIN_DIR"/*.pyc 2>/dev/null || true

# --- Sprawdzenie instalacji ---
echo ""
echo ">>> Sprawdzanie instalacji..."
MISSING_FILES=""
for FILE in plugin.py logo.png myupdater.png __init__.py install_archive_script.sh; do
    if [ ! -f "$PLUGIN_DIR/$FILE" ]; then
        MISSING_FILES="$MISSING_FILES $FILE"
    fi
done

if [ -n "$MISSING_FILES" ]; then
    echo "!!! BŁĄD: Brakujące pliki:$MISSING_FILES"
    log "Brakujące pliki: $MISSING_FILES"
    echo "------------------------------------------"
    exit 1
fi

# --- Informacja o zakończeniu ---
echo ""
echo "------------------------------------------"
echo ">>> INSTALACJA ZAKOŃCZONA POMYŚLNIE!"
echo ">>> MyUpdater Enhanced jest gotowy do użycia."
echo ">>> Zalecany restart GUI Enigma2!"
echo ">>> Wtyczka znajduje się w Menu -> Pluginy"
echo "------------------------------------------"

log "Instalacja zakończona sukcesem"

# Opcjonalny restart GUI
if [ "${1:-}" = "--restart" ]; then
    echo ""
    echo "Restartowanie GUI Enigma2..."
    killall -9 enigma2 2>/dev/null || systemctl restart enigma2 2>/dev/null || true
fi

exit 0