#!/bin/sh
# Skrypt install_archive_script.sh (v9) - Bazuje na wersji użytkownika (bez czyszczenia), ulepszone logowanie.

# set -e # Usunięto set -e, aby skrypt kontynuował mimo błędów kopiowania

LOG_FILE="/tmp/aio_install.log" # Log file for debugging

# Start logging
echo "--- START install_archive_script.sh (v9 - no clean) ---" > "$LOG_FILE"
echo "Argumenty: \$1='$1' \$2='$2'" >> "$LOG_FILE"
date >> "$LOG_FILE"

DOWNLOADED_FILE_PATH="$1"
ARCHIVE_TYPE="$2"
# ERROR_MSG="$3" # Argument $3 nie jest już potrzebny, bo nie przerywamy przy błędach rozpakowania od razu

TMP_EXTRACT_DIR="/tmp/list_extract_tmp"

echo "--> Przygotowuję katalog tymczasowy: $TMP_EXTRACT_DIR ..." | tee -a "$LOG_FILE"
rm -rf "$TMP_EXTRACT_DIR" && mkdir -p "$TMP_EXTRACT_DIR"
if [ $? -ne 0 ]; then
    echo "!!! KRYTYCZNY BŁĄD: Nie udało się utworzyć $TMP_EXTRACT_DIR!" | tee -a "$LOG_FILE"
    exit 1
fi
echo "--> Katalog tymczasowy gotowy." >> "$LOG_FILE"

# Rozpakowywanie
EXIT_CODE=1
echo "--> Rozpakowuję archiwum ($ARCHIVE_TYPE)..." | tee -a "$LOG_FILE"
if [ "$ARCHIVE_TYPE" = "zip" ]; then
    if ! command -v unzip >/dev/null 2>&1; then
        echo "!!! KRYTYCZNY BŁĄD: Narzędzie 'unzip' nie jest dostępne." | tee -a "$LOG_FILE"
        exit 1
    fi
    unzip -o "$DOWNLOADED_FILE_PATH" -d "$TMP_EXTRACT_DIR" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
elif [ "$ARCHIVE_TYPE" = "tar.gz" ]; then
    if ! command -v tar >/dev/null 2>&1; then
        echo "!!! KRYTYCZNY BŁĄD: Narzędzie 'tar' nie jest dostępne." | tee -a "$LOG_FILE"
        exit 1
    fi
    tar -xzf "$DOWNLOADED_FILE_PATH" -C "$TMP_EXTRACT_DIR" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
else
    echo "!!! KRYTYCZNY BŁĄD: Nieobsługiwany format archiwum '$ARCHIVE_TYPE'." | tee -a "$LOG_FILE"
    rm -f "$DOWNLOADED_FILE_PATH" # Cleanup downloaded file on error
    exit 1
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo "!!! BŁĄD PODCZAS ROZPAKOWYWANIA (kod: $EXIT_CODE)! Sprawdź $LOG_FILE. Przerywam." | tee -a "$LOG_FILE"
    rm -f "$DOWNLOADED_FILE_PATH" # Cleanup
    rm -rf "$TMP_EXTRACT_DIR"
    exit 1
fi
echo "--> Rozpakowywanie zakończone. Zawartość $TMP_EXTRACT_DIR:" >> "$LOG_FILE"
ls -R "$TMP_EXTRACT_DIR" >> "$LOG_FILE" 2>&1

# --- Wyszukiwanie katalogu z lamedb ---
echo "--> Wyszukuję katalog z plikiem 'lamedb'..." >> "$LOG_FILE"
SOURCE_DIR=""
FOUND_LAMEDB_PATH=$(find "$TMP_EXTRACT_DIR" -name "lamedb" -type f -print -quit)

if [ -n "$FOUND_LAMEDB_PATH" ]; then
    SOURCE_DIR=$(dirname "$FOUND_LAMEDB_PATH")
    echo "--> Znaleziono główny katalog z listą kanałów: $SOURCE_DIR" | tee -a "$LOG_FILE"
else
    echo "!!! KRYTYCZNY BŁĄD: Nie znaleziono pliku 'lamedb' w rozpakowanym archiwum. Anuluję." | tee -a "$LOG_FILE"
    rm -f "$DOWNLOADED_FILE_PATH" # Cleanup
    rm -rf "$TMP_EXTRACT_DIR"
    exit 1
fi
# --- Koniec wyszukiwania ---

# --- Kopiowanie Plików (nadpisywanie) ---
echo "--> Rozpoczynam kopiowanie plików (nadpisywanie)..." | tee -a "$LOG_FILE"
TARGET_ENIGMA2_DIR="/etc/enigma2"
TARGET_TUXBOX_DIR="/etc/tuxbox"
COPY_ERRORS=0

# Kopiowanie wszystkich plików z znalezionego katalogu źródłowego do /etc/enigma2
echo "--> Kopiowanie z '$SOURCE_DIR' do '$TARGET_ENIGMA2_DIR/'..." >> "$LOG_FILE"
cp -rf "$SOURCE_DIR"/* "$TARGET_ENIGMA2_DIR/" 2>> "$LOG_FILE" || { echo "!!! OSTRZEŻENIE: Wystąpiły problemy podczas kopiowania plików do $TARGET_ENIGMA2_DIR (szczegóły w $LOG_FILE)"; COPY_ERRORS=1; }

# Kopiowanie satellites.xml, jeśli istnieje
if [ -f "$SOURCE_DIR/satellites.xml" ]; then
    echo "--> Kopiowanie satellites.xml do '$TARGET_TUXBOX_DIR/'..." >> "$LOG_FILE"
    # Upewnij się, że katalog /etc/tuxbox istnieje
    mkdir -p "$TARGET_TUXBOX_DIR" >> "$LOG_FILE" 2>&1
    cp -f "$SOURCE_DIR/satellites.xml" "$TARGET_TUXBOX_DIR/" 2>> "$LOG_FILE" || { echo "!!! OSTRZEŻENIE: Nie udało się skopiować satellites.xml (szczegóły w $LOG_FILE)"; COPY_ERRORS=1; }
fi
echo "--> Kopiowanie plików zakończone." >> "$LOG_FILE"
# --- Koniec Kopiowania ---

# --- Przeładowanie Bukietów ---
# Sprawdźmy, czy skrypt reload_bouquets.sh istnieje w katalogu wtyczki
PLUGIN_SCRIPT_DIR=$(dirname "$(readlink -f "$0")") # Pobierz katalog bieżącego skryptu
RELOAD_SCRIPT_PATH="$PLUGIN_SCRIPT_DIR/reload_bouquets.sh"
echo "--> Próba przeładowania bukietów przy użyciu '$RELOAD_SCRIPT_PATH'..." >> "$LOG_FILE"

if [ -f "$RELOAD_SCRIPT_PATH" ]; then
    if [ -x "$RELOAD_SCRIPT_PATH" ]; then
        if "$RELOAD_SCRIPT_PATH"; then
            echo "--> Skrypt reload_bouquets.sh zakończony pomyślnie." >> "$LOG_FILE"
        else
            RELOAD_EXIT_CODE=$?
            echo "!!! OSTRZEŻENIE: Skrypt reload_bouquets.sh zwrócił błąd (kod: $RELOAD_EXIT_CODE). Może być konieczny restart GUI." | tee -a "$LOG_FILE"
            COPY_ERRORS=1 # Traktujemy to jako potencjalny problem
        fi
    else
        echo "!!! KRYTYCZNY BŁĄD: Skrypt reload_bouquets.sh '$RELOAD_SCRIPT_PATH' nie ma uprawnień do wykonywania!" | tee -a "$LOG_FILE"
        echo "Nadaj uprawnienia: chmod +x '$RELOAD_SCRIPT_PATH'"
        COPY_ERRORS=1 # To jest krytyczny błąd
    fi
else
    echo "!!! KRYTYCZNY BŁĄD: Skrypt reload_bouquets.sh '$RELOAD_SCRIPT_PATH' nie został znaleziony!" | tee -a "$LOG_FILE"
    COPY_ERRORS=1 # To jest krytyczny błąd
fi
# --- Koniec Przeładowania ---

# --- Czyszczenie ---
echo "--> Usuwam pliki tymczasowe..." | tee -a "$LOG_FILE"
rm -rf "$TMP_EXTRACT_DIR" >> "$LOG_FILE" 2>&1
rm -f "$DOWNLOADED_FILE_PATH" >> "$LOG_FILE" 2>&1
echo "--> Pliki tymczasowe usunięte." >> "$LOG_FILE"
# --- Koniec Czyszczenia ---

# --- Komunikat końcowy ---
echo "--- KONIEC install_archive_script.sh (v9) ---" >> "$LOG_FILE"
if [ $COPY_ERRORS -ne 0 ]; then
    echo ">>> Instalacja ZAKOŃCZONA Z OSTRZEŻENIAMI." | tee -a "$LOG_FILE"
    echo ">>> Sprawdź listę kanałów. W razie problemów może być konieczny restart GUI." | tee -a "$LOG_FILE"
    echo ">>> Szczegółowe logi znajdziesz w pliku: $LOG_FILE" | tee -a "$LOG_FILE"
else
    echo ">>> Instalacja listy kanałów ZAKOŃCZONA pomyślnie." | tee -a "$LOG_FILE"
    echo ">>> Listy powinny być już widoczne." | tee -a "$LOG_FILE"
fi
sleep 3 # Daj użytkownikowi chwilę na przeczytanie

exit 0
