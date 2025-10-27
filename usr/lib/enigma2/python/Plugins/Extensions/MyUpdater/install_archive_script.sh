#!/bin/bash
# install_archive_script.sh (MyUpdater Mod V4 - Poprawiona wersja)
# Rozpakowuje listy kanałów (.tar.gz) do /etc/enigma2

ARCHIVE_PATH="$1"
ARCHIVE_TYPE="$2"
TARGET_DIR="/etc/enigma2" # Katalog docelowy dla list kanałów
# Plik logu (opcjonalny, do debugowania)
LOG_FILE="/tmp/MyUpdater_install_archive.log"

# Przekieruj standardowe wyjście i błędy do pliku logu, zachowując je na konsoli
exec > >(tee -a "$LOG_FILE") 2>&1

echo "------------------------------------------"
echo ">>> $(date) - Rozpoczynam rozpakowywanie: $ARCHIVE_PATH"
echo ">>> Typ archiwum: $ARCHIVE_TYPE"
echo ">>> Katalog docelowy: $TARGET_DIR"

# Sprawdzenie czy plik archiwum istnieje
if [ ! -f "$ARCHIVE_PATH" ]; then
    echo "!!! BŁĄD: Plik archiwum nie istnieje: $ARCHIVE_PATH"
    echo "------------------------------------------"
    exit 1
fi

# Logika tylko dla tar.gz (listy kanałów)
if [ "$ARCHIVE_TYPE" = "tar.gz" ]; then
    echo ">>> Rozpakowywanie tar.gz do $TARGET_DIR przy użyciu --strip-components=1 ..."
    # Używamy opcji -xzvf dla bardziej szczegółowego logowania
    # --strip-components=1 usuwa pierwszy poziom katalogu z archiwum
    # --overwrite zapewnia nadpisanie istniejących plików
    tar -xzvf "$ARCHIVE_PATH" -C "$TARGET_DIR" --strip-components=1 --overwrite
    EXIT_CODE=$? # Zapisz kod wyjścia polecenia tar

    if [ $EXIT_CODE -ne 0 ]; then
        echo "!!! BŁĄD podczas rozpakowywania tar.gz (kod: $EXIT_CODE)"
        # Usuń archiwum nawet przy błędzie, aby nie zajmowało miejsca
        rm -f "$ARCHIVE_PATH"
        echo "------------------------------------------"
        exit 1 # Zakończ z błędem
    else
        echo ">>> Archiwum tar.gz rozpakowane pomyślnie."
    fi

# Obsługa innych typów (choć nie powinny tu trafić wg plugin.py)
else
    echo "!!! OSTRZEŻENIE: Ten skrypt jest przeznaczony tylko dla tar.gz. Otrzymano: $ARCHIVE_TYPE"
    # Nie robimy nic, plugin.py powinien obsłużyć inne typy (np. zip dla picon)
    # Usuńmy jednak plik tymczasowy, skoro go nie użyliśmy
     rm -f "$ARCHIVE_PATH"
     echo "------------------------------------------"
    exit 1 # Zakończ z błędem, bo typ jest nieprawidłowy dla tego skryptu
fi

# Usuń plik archiwum po pomyślnym rozpakowaniu
echo ">>> Usuwanie pliku archiwum: $ARCHIVE_PATH"
rm -f "$ARCHIVE_PATH"

echo ">>> Rozpakowywanie zakończone pomyślnie."
echo "------------------------------------------"
exit 0 # Zakończ sukcesem
