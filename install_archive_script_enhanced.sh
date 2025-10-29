#!/bin/sh
# Ulepszony skrypt do instalacji list kanałów (zip lub tar.gz)
# Argument 1: Ścieżka do archiwum
# Argument 2: Typ (zip lub tar.gz)

set -e  # Zatrzymaj na błędy

ARCHIVE_PATH="$1"
ARCHIVE_TYPE="$2"
TARGET_DIR="/etc/enigma2/"
TMP_DIR="/tmp/MyUpdater_chlist_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="/tmp/MyUpdater_install.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log ">>> [Skrypt] Rozpoczynam instalację: $ARCHIVE_PATH"
log ">>> [Skrypt] Typ archiwum: $ARCHIVE_TYPE"

# Sprawdzenie argumentów
if [ -z "$ARCHIVE_PATH" ] || [ -z "$ARCHIVE_TYPE" ]; then
    log ">>> [Skrypt] BŁĄD: Brak wymaganych argumentów!"
    echo "Użycie: $0 <ścieżka_do_archiwum> <zip|tar.gz>"
    exit 1
fi

if [ ! -f "$ARCHIVE_PATH" ]; then
    log ">>> [Skrypt] BŁĄD: Plik archiwum nie istnieje: $ARCHIVE_PATH"
    exit 1
fi

# Sprawdzenie miejsca na dysku
AVAILABLE_SPACE=$(df /etc/enigma2 | tail -1 | awk '{print $4}')
ARCHIVE_SIZE=$(du "$ARCHIVE_PATH" | cut -f1)

if [ "$AVAILABLE_SPACE" -lt "$((ARCHIVE_SIZE * 3))" ]; then
    log ">>> [Skrypt] OSTRZEŻENIE: Może być za mało miejsca na dysku"
    echo "Dostępne miejsce: ${AVAILABLE_SPACE}KB, wymagane: ${ARCHIVE_SIZE}KB"
fi

# Czyszczenie i przygotowanie katalogu tymczasowego
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

# Kopia zapasowa istniejących plików
if [ -f "/etc/enigma2/lamedb" ]; then
    BACKUP_DIR="/tmp/MyUpdater_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp /etc/enigma2/lamedb /etc/enigma2/*.tv /etc/enigma2/*.radio "$BACKUP_DIR" 2>/dev/null || true
    log ">>> [Skrypt] Utworzono kopię zapasową w: $BACKUP_DIR"
fi

# Rozpakowanie archiwum
log ">>> [Skrypt] Rozpakowuję archiwum..."
case "$ARCHIVE_TYPE" in
    "zip")
        if ! command -v unzip >/dev/null 2>&1; then
            log ">>> [Skrypt] BŁĄD: Brak programu unzip!"
            exit 1
        fi
        unzip -o -q "$ARCHIVE_PATH" -d "$TMP_DIR"
        ;;
    "tar.gz")
        if ! command -v tar >/dev/null 2>&1; then
            log ">>> [Skrypt] BŁĄD: Brak programu tar!"
            exit 1
        fi
        tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"
        ;;
    *)
        log ">>> [Skrypt] BŁĄD: Nieobsługiwany typ archiwum: $ARCHIVE_TYPE"
        exit 1
        ;;
esac

# Sprawdzenie zawartości archiwum
log ">>> [Skrypt] Analizuję zawartość archiwum..."

# Szukanie plików list kanałów
FOUND_FILES=0
FOUND_LAMEDB=0
FOUND_TV=0
FOUND_RADIO=0

# Przeszukanie katalogu tymczasowego
for file in "$TMP_DIR"/* "$TMP_DIR"/*/*; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        case "$filename" in
            "lamedb")
                FOUND_LAMEDB=$((FOUND_LAMEDB + 1))
                FOUND_FILES=$((FOUND_FILES + 1))
                log ">>> [Skrypt] Znaleziono lamedb"
                ;;
            *.tv)
                FOUND_TV=$((FOUND_TV + 1))
                FOUND_FILES=$((FOUND_FILES + 1))
                log ">>> [Skrypt] Znaleziono plik .tv: $filename"
                ;;
            *.radio)
                FOUND_RADIO=$((FOUND_RADIO + 1))
                FOUND_FILES=$((FOUND_FILES + 1))
                log ">>> [Skrypt] Znaleziono plik .radio: $filename"
                ;;
        esac
    fi
done

log ">>> [Skrypt] Podsumowanie znalezionych plików:"
log ">>> [Skrypt] - lamedb: $FOUND_LAMEDB"
log ">>> [Skrypt] - pliki .tv: $FOUND_TV"
log ">>> [Skrypt] - pliki .radio: $FOUND_RADIO"

if [ "$FOUND_FILES" -eq 0 ]; then
    log ">>> [Skrypt] BŁĄD: Nie znaleziono plików list kanałów w archiwum!"
    echo "W archiwum nie znaleziono plików: lamedb, *.tv, *.radio"
    rm -rf "$TMP_DIR"
    rm -f "$ARCHIVE_PATH"
    exit 1
fi

# Przenoszenie plików do katalogu docelowego
log ">>> [Skrypt] Przenoszę pliki do $TARGET_DIR..."

# Tworzenie katalogu docelowego jeśli nie istnieje
mkdir -p "$TARGET_DIR"

# Przenoszenie plików z zachowaniem struktury
find "$TMP_DIR" -type f \( -name "lamedb" -o -name "*.tv" -o -name "*.radio" \) -print0 | while IFS= read -r -d '' file; do
    filename=$(basename "$file")
    log ">>> [Skrypt] Przenoszę $filename"
    mv -f "$file" "$TARGET_DIR/"
done

# Sprawdzenie czy pliki zostały przeniesione
MISSING_AFTER_MOVE=0
for ext in lamedb tv radio; do
    count=$(find "$TARGET_DIR" -name "*.$ext" -type f | wc -l)
    if [ "$ext" = "lamedb" ]; then
        count=$(find "$TARGET_DIR" -name "lamedb" -type f | wc -l)
    fi
    log ">>> [Skrypt] Pliki $ext w $TARGET_DIR: $count"
done

# Czyszczenie
log ">>> [Skrypt] Czyszczenie plików tymczasowych..."
rm -rf "$TMP_DIR"
rm -f "$ARCHIVE_PATH"

# Ustawienie praw dostępu do plików
log ">>> [Skrypt] Ustawianie praw dostępu..."
chmod 644 "$TARGET_DIR"/*.tv "$TARGET_DIR"/*.radio 2>/dev/null || true
chmod 644 "$TARGET_DIR"/lamedb 2>/dev/null || true

log ">>> [Skrypt] Instalacja zakończona sukcesem!"
echo "Listy kanałów zostały zainstalowane."
echo "Zalecany restart GUI Enigma2 dla pełnego efektu."

exit 0