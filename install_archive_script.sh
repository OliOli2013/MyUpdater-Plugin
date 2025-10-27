#!/bin/bash
# Skrypt pomocniczy do rozpakowywania archiwów (z PanelAIO)

ARCHIVE_PATH="$1"
ARCHIVE_TYPE="$2"
TARGET_DIR="/etc/enigma2/" # Domyślny cel dla list kanałów

echo ">>> Rozpoczynam rozpakowywanie archiwum: $ARCHIVE_PATH"
echo ">>> Typ archiwum: $ARCHIVE_TYPE"
echo ">>> Katalog docelowy: $TARGET_DIR"

if [ ! -f "$ARCHIVE_PATH" ]; then
    echo "!!! BŁĄD: Plik archiwum nie istnieje: $ARCHIVE_PATH"
    exit 1
fi

# Logika dla tar.gz (listy kanałów)
if [ "$ARCHIVE_TYPE" = "tar.gz" ]; then
    echo ">>> Rozpakowywanie tar.gz do $TARGET_DIR..."
    # Sprawdź, czy archiwum zawiera jeden główny katalog
    # Zlicz liczbę elementów (plików/katalogów) w głównym katalogu archiwum
    ROOT_ITEMS_COUNT=$(tar -tf "$ARCHIVE_PATH" --exclude '*/*' | wc -l)

    if [ "$ROOT_ITEMS_COUNT" -eq 1 ]; then
        # Jeśli jest tylko jeden element (prawdopodobnie katalog), użyj --strip-components=1
        echo "> Wykryto strukturę z katalogiem nadrzędnym. Używam --strip-components=1."
        tar -xzf "$ARCHIVE_PATH" -C "$TARGET_DIR" --strip-components=1 --overwrite
        EXIT_CODE=$?
    else
        # Jeśli jest więcej elementów lub brak, rozpakuj normalnie
        echo "> Rozpakowywanie bezpośrednio do katalogu docelowego."
        tar -xzf "$ARCHIVE_PATH" -C "$TARGET_DIR" --overwrite
        EXIT_CODE=$?
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo "!!! BŁĄD podczas rozpakowywania tar.gz (kod: $EXIT_CODE)"
        rm -f "$ARCHIVE_PATH" # Usuń archiwum nawet przy błędzie
        exit 1
    else
        echo ">>> Archiwum tar.gz rozpakowane pomyślnie."
    fi

# Logika dla zip (choć nie używamy jej dla list)
elif [ "$ARCHIVE_TYPE" = "zip" ]; then
    echo "!!! OSTRZEŻENIE: Ten skrypt nie powinien być wywoływany dla .zip (obsługa w plugin.py)."
    # Mimo wszystko, dodajemy podstawową logikę jako fallback
    unzip -o -q "$ARCHIVE_PATH" -d "$TARGET_DIR"
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "!!! BŁĄD podczas rozpakowywania zip (kod: $EXIT_CODE)"
        rm -f "$ARCHIVE_PATH"
        exit 1
    else
        echo ">>> Archiwum zip rozpakowane pomyślnie."
    fi

else
    echo "!!! BŁĄD: Nieznany typ archiwum: $ARCHIVE_TYPE"
    rm -f "$ARCHIVE_PATH"
    exit 1
fi

# Usuń plik archiwum po pomyślnym rozpakowaniu
echo ">>> Usuwanie pliku archiwum: $ARCHIVE_PATH"
rm -f "$ARCHIVE_PATH"

echo ">>> Rozpakowywanie zakończone."
exit 0
