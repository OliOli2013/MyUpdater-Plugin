#!/bin/sh
# Instalator/aktualizator MyUpdater Mod V4
# Poprawiony URL install_archive_script.sh

# --- Konfiguracja ---
PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
GITHUB_RAW_URL="https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
REQUIRED_PKGS="wget curl tar unzip bash"

# Pliki do pobrania
FILES_TO_DOWNLOAD="
plugin.py
logo.png
myupdater.png
__init__.py
install_archive_script.sh
"
# --- Koniec Konfiguracji ---

echo "------------------------------------------"
echo ">>> Rozpoczynam instalację/aktualizację MyUpdater Mod..."
echo "------------------------------------------"

# --- Sprawdzanie i instalacja zależności ---
echo ""
echo ">>> Sprawdzanie zależności..."
MISSING_PKGS=""
for PKG in $REQUIRED_PKGS; do
    if ! command -v $PKG > /dev/null 2>&1; then
        if ! opkg list-installed | grep -q "^$PKG "; then
            echo "  > Brak pakietu: $PKG"
            MISSING_PKGS="$MISSING_PKGS $PKG"
        else
             echo "  > Znaleziono (jako pakiet): $PKG"
        fi
    else
        echo "  > Znaleziono (jako komenda): $PKG"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    echo ""
    echo ">>> Próba instalacji brakujących pakietów:$MISSING_PKGS"
    opkg update
    opkg install $MISSING_PKGS
    RECHECK_MISSING=""
    for PKG in $MISSING_PKGS; do
        if ! command -v $PKG > /dev/null 2>&1 && ! opkg list-installed | grep -q "^$PKG "; then
            RECHECK_MISSING="$RECHECK_MISSING $PKG"
        fi
    done
    if [ -n "$RECHECK_MISSING" ]; then
        echo ""
        echo "!!! BŁĄD: Nie udało się zainstalować:$RECHECK_MISSING"
        echo "!!! Instalacja przerwana."
        exit 1
    else
        echo "> Wymagane pakiety zostały zainstalowane."
    fi
else
    echo "> Wszystkie wymagane pakiety są już zainstalowane."
fi

# --- Tworzenie katalogu ---
echo ""
echo ">>> Tworzenie katalogu wtyczki:"
mkdir -p "$PLUGIN_DIR"

# --- Pobieranie plików ---
echo ""
echo ">>> Pobieranie plików wtyczki..."
SUCCESS=true
for FILE in $FILES_TO_DOWNLOAD; do
    echo "  > Pobieranie $FILE..."
    wget -q "$GITHUB_RAW_URL/$FILE" -O "$PLUGIN_DIR/$FILE"
    if [ $? -ne 0 ]; then
        echo "  !!! BŁĄD: nie udało się pobrać $FILE"
        SUCCESS=false
    fi
done

if [ "$SUCCESS" = false ]; then
    echo "!!! Błędy pobierania – instalacja niekompletna."
    exit 1
fi

# --- Uprawnienia ---
echo ""
echo ">>> Nadawanie uprawnień..."
chmod 644 "$PLUGIN_DIR"/*.py "$PLUGIN_DIR"/*.png
chmod +x "$PLUGIN_DIR/install_archive_script.sh"

# --- Czyszczenie ---
rm -f "$PLUGIN_DIR"/*.pyo

echo ""
echo "------------------------------------------"
echo ">>> Instalacja zakończona sukcesem!"
echo ">>> Zalecany restart GUI Enigma2."
echo "------------------------------------------"
exit 0
