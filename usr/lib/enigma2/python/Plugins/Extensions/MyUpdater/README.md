# MyUpdater Enhanced V5

## Kompletna przebudowa aplikacji Enigma 2 z pełną kompatybilnością OpenATV/OpenPLI

### 🚀 Nowości w wersji V5 Enhanced

- **Pełna kompatybilność** z OpenATV 6.4-7.6 oraz OpenPLI
- **Inteligentna instalacja oscam** z automatyczną detekcją systemu
- **Ulepszona obsługa błędów** z przyjaznymi komunikatami
- **Kopia zapasowa** przed instalacją list kanałów
- **Diagnostyka systemu** przed instalacją
- **Fallback na alternatywne źródła** gdy główne niedostępne

### 📋 Wymagania systemowe

- Enigma2 (OpenATV, OpenPLI, ViX)
- Python 2/3
- Dostęp do internetu
- Minimum 50MB wolnego miejsca

### 🔧 Instalacja

#### Metoda 1 - Instalator automatyczny (ZALECANE)

1. **Uruchom terminal na swoim dekoderze**
2. **Wykonaj instalację:**
   ```bash
   wget -q -O - https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer_enhanced.sh | sh
   ```

#### Metoda 2 - Instalacja ręczna

1. **Skopiuj wszystkie pliki do katalogu:**
   ```
   /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
   ```

2. **Nadaj uprawnienia:**
   ```bash
   chmod +x /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/install_archive_script.sh
   chmod 644 /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/*.py
   chmod 644 /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/*.png
   ```

3. **Zrestartuj GUI Enigma2**

### 📁 Struktura plików

```
/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
├── plugin_enhanced.py      # Główny plik wtyczki (przebudowany)
├── plugin.py               # Link do głównego pliku
├── install_archive_script.sh    # Skrypt instalacji archiwów
├── installer_enhanced.sh       # Nowy instalator
├── diagnostic.sh           # Skrypt diagnostyczny
├── __init__.py            # Inicjalizacja wtyczki
├── logo.png               # Logo wtyczki
├── myupdater.png          # Ikona wtyczki
└── version.txt            # Wersja wtyczki
```

### 🛠️ Funkcje

#### 1. Listy kanałów
- Automatyczne pobieranie z wielu źródeł
- Kopia zapasowa przed instalacją
- Wsparcie dla formatów ZIP i TAR.GZ

#### 2. Softcamy
- **Oscam**: Inteligentna instalacja z detekcją systemu
- **nCam**: Instalacja z repozytorium biko-73
- **Usuwanie**: Kompletne usuwanie wszystkich softcamów

#### 3. Picony
- Automatyczne pobieranie picon transparent
- Optymalizacja struktury katalogów

#### 4. Diagnostyka
- Sprawdzenie kompatybilności systemu
- Testowanie połączenia internetowego
- Weryfikacja wymaganych pakietów

### 🔧 Rozwiązywanie problemów

#### Problem: Nie działa na OpenPLI
**Rozwiązanie**: Wersja V5 Enhanced ma pełną kompatybilność z OpenPLI

#### Problem: Oscam nie instaluje się z feed
**Rozwiązanie**: Aplikacja automatycznie przechodzi do alternatywnych źródeł

#### Problem: Brak miejsca na dysku
**Rozwiązanie**: Skrypt sprawdza dostępną przestrzeń przed instalacją

#### Problem: Błędy sieciowe
**Rozwiązanie**: Ulepszona obsługa błędów z fallback na różne źródła

### 📊 Diagnostyka przed instalacją

Przed instalacją zalecam uruchomienie diagnostyki:

```bash
wget -q https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/diagnostic.sh -O /tmp/diagnostic.sh
chmod +x /tmp/diagnostic.sh
/tmp/diagnostic.sh
```

### 📝 Logi

Wszystkie operacje są logowane do:
- `/tmp/MyUpdater_install.log` - logi instalacji
- `/tmp/MyUpdater_diagnostic.log` - logi diagnostyczne

### 🤝 Wsparcie

Jeśli napotkasz problemy:

1. **Uruchom diagnostykę systemu**
2. **Sprawdź logi** w `/tmp/MyUpdater_*.log`
3. **Upewnij się że masz dostęp do internetu**
4. **Sprawdź czy masz wystarczająco miejsca na dysku**

### ⚠️ Ostrzeżenia

- **Zawsze rób kopię zapasową** przed instalacją
- **Nie przerywaj instalacji** w trakcie jej trwania
- **Zrestartuj GUI** po instalacji dla pełnego efektu

### 🔄 Aktualizacja

Aplikacja automatycznie sprawdza dostępność aktualizacji.
Możesz też ręcznie sprawdzić aktualizację w menu wtyczki.

### 📄 Licencja

Wtyczka bazuje na oryginalnym MyUpdater autorstwa Sancho i gut.
Przebudowa i ulepszenia: Paweł Pawełek

### 🙏 Podziękowania

- **Sancho i gut** - oryginalny pomysł i kod
- **OliOli2013** - repozytorium PanelAIO
- **Levi45** - alternatywne źródło oscam
- **biko-73** - repozytorium nCam

---

**MyUpdater Enhanced V5** - Twój niezawodny asystent do zarządzania Enigma2!