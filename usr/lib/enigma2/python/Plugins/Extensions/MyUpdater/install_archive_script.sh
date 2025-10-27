#!/bin/sh
# Instalator/aktualizator MyUpdater Mod V4

# --- Konfiguracja ---
PLUGIN_DIR="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
GITHUB_RAW_URL="https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater"
REQUIRED_PKGS="wget curl tar unzip bash" # Dodano bash

# Pliki do pobrania (w tym skrypt pomocniczy)
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
    # Sprawdź czy komenda istnieje
    if ! command -v $PKG > /dev/null 2>&1; then
        # Sprawdź czy pakiet jest zainstalowany (alternatywna metoda)
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
    echo "> Aktualizacja listy pakietów (opkg update)..."
    opkg update
    echo "> Instalowanie pakietów..."
    opkg install $MISSING_PKGS
    RECHECK_MISSING=""
    for PKG in $MISSING_PKGS; do
        if ! command -v $PKG > /dev/null 2>&1 && ! opkg list-installed | grep -q "^$PKG "; then
            RECHECK_MISSING="$RECHECK_MISSING $PKG"
        fi
    done
    if [ -n "$RECHECK_MISSING" ]; then
        echo ""
        echo "!!! BŁĄD: Nie udało się zainstalować następujących pakietów:$RECHECK_MISSING"
        echo "!!! Instalacja przerwana. Spróbuj zainstalować je ręcznie."
        echo "------------------------------------------"
        exit 1
    else
        echo "> Wymagane pakiety zostały zainstalowane."
    fi
else
    echo "> Wszystkie wymagane pakiety są już zainstalowane."
fi
# --- Koniec sprawdzania zależności ---

# --- Pobieranie i instalacja plików wtyczki ---
echo ""
echo ">>> Tworzenie katalogu wtyczki (jeśli nie istnieje):"
echo "  $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"

echo ""
echo ">>> Pobieranie plików wtyczki..."
SUCCESS=true
for FILE in $FILES_TO_DOWNLOAD; do
    echo "  > Pobieranie $FILE..."
    # Używamy -q (quiet) dla wget i sprawdzamy kod wyjścia ($?)
    wget -q "$GITHUB_RAW_URL/$FILE" -O "$PLUGIN_DIR/$FILE"
    if [ $? -ne 0 ]; then
        # Wyświetl błąd dla konkretnego pliku
        echo "  !!! BŁĄD podczas pobierania $FILE"
        SUCCESS=false
    fi
done

if [ "$SUCCESS" = false ]; then
    echo ""
    echo "!!! Wystąpiły błędy podczas pobierania plików. Instalacja niekompletna."
    echo "------------------------------------------"
    exit 1
fi
# --- Koniec pobierania ---

# --- Nadawanie uprawnień ---
echo ""
echo ">>> Ustawianie uprawnień dla plików wtyczki..."
chmod 644 "$PLUGIN_DIR"/*.png "$PLUGIN_DIR"/*.py # Uprawnienia dla .png i .py
chmod +x "$PLUGIN_DIR/install_archive_script.sh" # Nadanie uprawnień wykonywania dla skryptu
# --- Koniec nadawania uprawnień ---

# --- Czyszczenie starych plików .pyo ---
echo ""
echo ">>> Usuwanie starych skompilowanych plików Pythona (.pyo)..."
rm -f "$PLUGIN_DIR"/*.pyo
# --- Koniec czyszczenia ---

echo ""
echo "------------------------------------------"
echo ">>> Instalacja/Aktualizacja MyUpdater Mod zakończona pomyślnie."
echo ">>> Zalecany restart GUI Enigma2!"
echo "------------------------------------------"
echo ""

exit 0
