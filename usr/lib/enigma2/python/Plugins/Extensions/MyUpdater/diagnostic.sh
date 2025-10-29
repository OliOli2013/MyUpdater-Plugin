#!/bin/sh
# Skrypt diagnostyczny dla MyUpdater Enhanced
# Sprawdza kompatybilność systemu i wymagania

set -e

# Kolory dla wyświetlania
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a /tmp/MyUpdater_diagnostic.log
}

print_status() {
    if [ "$2" = "OK" ]; then
        echo -e "${GREEN}✓${NC} $1"
    elif [ "$2" = "WARN" ]; then
        echo -e "${YELLOW}⚠${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
    fi
}

# Nagłówek
echo "------------------------------------------"
echo -e "${BLUE}MyUpdater Enhanced - Diagnostyka Systemu${NC}"
echo "------------------------------------------"
echo ""

log "Rozpoczynam diagnostykę systemu"

# 1. Detekcja systemu
echo -e "${BLUE}1. Informacje o systemie:${NC}"
if [ -f /etc/openatv-release ]; then
    OPENATV_VERSION=$(cat /etc/openatv-release | head -1)
    print_status "System: OpenATV $OPENATV_VERSION" "OK"
    log "Wykryto OpenATV: $OPENATV_VERSION"
elif [ -f /etc/openpli-release ]; then
    OPENPLI_VERSION=$(cat /etc/openpli-release | head -1)
    print_status "System: OpenPLI $OPENPLI_VERSION" "OK"
    log "Wykryto OpenPLI: $OPENPLI_VERSION"
elif [ -f /etc/vti-version-info ]; then
    VIX_VERSION=$(cat /etc/vti-version-info | head -1)
    print_status "System: ViX $VIX_VERSION" "OK"
    log "Wykryto ViX: $VIX_VERSION"
else
    print_status "System: Nieznany (może nie być wspierany)" "WARN"
    log "Nieznany system"
fi

# 2. Sprawdzenie wersji Enigma2
echo ""
echo -e "${BLUE}2. Wersja Enigma2:${NC}"
if command -v opkg >/dev/null 2>&1; then
    ENIGMA2_VERSION=$(opkg list-installed | grep -i enigma2 | head -1)
    if [ -n "$ENIGMA2_VERSION" ]; then
        print_status "Enigma2: $ENIGMA2_VERSION" "OK"
        log "Enigma2: $ENIGMA2_VERSION"
    else
        print_status "Enigma2: Nie można określić wersji" "WARN"
        log "Nie można określić wersji Enigma2"
    fi
else
    print_status "Enigma2: Brak komendy opkg" "WARN"
    log "Brak komendy opkg"
fi

# 3. Sprawdzenie wymaganych pakietów
echo ""
echo -e "${BLUE}3. Wymagane pakiety:${NC}"
REQUIRED_PKGS="wget curl tar unzip bash python-json python-core"
MISSING_PKGS=""

for PKG in $REQUIRED_PKGS; do
    if command -v $PKG >/dev/null 2>&1 || opkg list-installed | grep -q "^$PKG " 2>/dev/null; then
        print_status "$PKG: Zainstalowany" "OK"
    else
        print_status "$PKG: Brak" "WARN"
        MISSING_PKGS="$MISSING_PKGS $PKG"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    log "Brakujące pakiety: $MISSING_PKGS"
fi

# 4. Sprawdzenie miejsca na dysku
echo ""
echo -e "${BLUE}4. Przestrzeń dyskowa:${NC}"
ROOT_AVAIL=$(df / | tail -1 | awk '{print $4}')
ROOT_SIZE=$(df -h / | tail -1 | awk '{print $4}')
ROOT_USED=$(df -h / | tail -1 | awk '{print $3}')

if [ "$ROOT_AVAIL" -gt 50000 ]; then
    print_status "Główny katalog (/): $ROOT_USED użyte, $ROOT_SIZE dostępne" "OK"
else
    print_status "Główny katalog (/): $ROOT_USED użyte, $ROOT_SIZE dostępne (mało miejsca!)" "WARN"
fi

ETC_AVAIL=$(df /etc | tail -1 | awk '{print $4}')
if [ "$ETC_AVAIL" -gt 10000 ]; then
    print_status "Katalog /etc: Dostępne miejsce OK" "OK"
else
    print_status "Katalog /etc: Mało miejsca" "WARN"
fi

log "Przestrzeń dyskowa - root: $ROOT_AVAIL KB dostępne"

# 5. Sprawdzenie połączenia internetowego
echo ""
echo -e "${BLUE}5. Połączenie internetowe:${NC}"
if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
    print_status "Internet: Połączenie aktywne" "OK"
    log "Połączenie internetowe: OK"
    
    # Test szybkości pobierania
    echo "  Testowanie prędkości pobierania..."
    if wget -q --timeout=10 --spider https://raw.githubusercontent.com/ 2>/dev/null; then
        print_status "GitHub: Dostępny" "OK"
        log "GitHub dostępny"
    else
        print_status "GitHub: Problem z dostępem" "WARN"
        log "Problem z dostępem do GitHub"
    fi
else
    print_status "Internet: Brak połączenia" "WARN"
    log "Brak połączenia internetowego"
fi

# 6. Sprawdzenie softcamów
echo ""
echo -e "${BLUE}6. Zainstalowane softcamy:${NC}"
if command -v opkg >/dev/null 2>&1; then
    SOFTCAMS=$(opkg list-installed | grep -i "softcam\|oscam\|ncam" | head -5)
    if [ -n "$SOFTCAMS" ]; then
        echo "$SOFTCAMS" | while read -r line; do
            print_status "$line" "OK"
        done
    else
        print_status "Brak zainstalowanych softcamów" "INFO"
    fi
else
    print_status "Nie można sprawdzić softcamów (brak opkg)" "WARN"
fi

# 7. Sprawdzenie uprawnień
echo ""
echo -e "${BLUE}7. Uprawnienia:${NC}"
if [ "$(id -u)" -eq 0 ]; then
    print_status "Uprawnienia: Uruchomiono jako root" "OK"
else
    print_status "Uprawnienia: Nie uruchomiono jako root" "WARN"
fi

# 8. Testowanie komend systemowych
echo ""
echo -e "${BLUE}8. Testowanie komend systemowych:${NC}"
TEST_COMMANDS="opkg wget curl tar unzip"
for CMD in $TEST_COMMANDS; do
    if command -v $CMD >/dev/null 2>&1; then
        print_status "$CMD: Dostępny" "OK"
    else
        print_status "$CMD: Brak" "WARN"
    fi
done

# 9. Podsumowanie
echo ""
echo "------------------------------------------"
echo -e "${BLUE}PODSUMOWANIE:${NC}"

ERRORS=$(grep -c "✗" <<< "$(echo -e "\n" && echo "")" 2>/dev/null || echo "0")
WARNINGS=$(grep -c "⚠" <<< "$(echo -e "\n" && echo "")" 2>/dev/null || echo "0")

if [ "$ERRORS" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
    echo -e "${GREEN}✓ System jest gotowy do instalacji MyUpdater Enhanced!${NC}"
    log "Diagnostyka zakończona sukcesem"
elif [ "$ERRORS" -eq 0 ]; then
    echo -e "${YELLOW}⚠ System ma pewne ostrzeżenia, ale instalacja powinna się udać.${NC}"
    echo "Sprawdź logi ostrzeżeń powyżej."
    log "Diagnostyka zakończona z ostrzeżeniami"
else
    echo -e "${RED}✗ System ma błędy uniemożliwiające instalację.${NC}"
    echo "Napraw problemy i uruchom diagnostykę ponownie."
    log "Diagnostyka zakończona błędami"
fi

echo ""
echo "Szczegóły znajdziesz w: /tmp/MyUpdater_diagnostic.log"
echo "------------------------------------------"

log "Diagnostyka zakończona"
exit 0