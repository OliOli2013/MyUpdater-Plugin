# Lista plików MyUpdater Enhanced V5

## Wszystkie pliki wymagane do prawidłowej instalacji

### 🔧 Pliki główne wtyczki

| Plik | Opis | Wymagany | Uprawnienia |
|------|------|----------|-------------|
| `plugin_enhanced.py` | Główny plik wtyczki (przebudowany) | ✅ TAK | 644 |
| `plugin.py` | Link symboliczny do głównego pliku | ✅ TAK | 644 |
| `__init__.py` | Inicjalizacja wtyczki | ✅ TAK | 644 |
| `version.txt` | Wersja wtyczki | ✅ TAK | 644 |

### 🖼️ Pliki graficzne

| Plik | Opis | Wymagany | Uprawnienia |
|------|------|----------|-------------|
| `logo.png` | Logo wtyczki | ✅ TAK | 644 |
| `myupdater.png` | Ikona wtyczki | ✅ TAK | 644 |

### 🔧 Skrypty systemowe

| Plik | Opis | Wymagany | Uprawnienia |
|------|------|----------|-------------|
| `install_archive_script.sh` | Skrypt instalacji archiwów | ✅ TAK | 755 |
| `installer_enhanced.sh` | Nowy instalator | ❌ NIE* | 755 |
| `diagnostic.sh` | Skrypt diagnostyczny | ❌ NIE* | 755 |

*Pliki opcjonalne - nie są wymagane do działania wtyczki, ale pomocne

### 📄 Pliki dokumentacji

| Plik | Opis | Wymagany | Uprawnienia |
|------|------|----------|-------------|
| `README.md` | Instrukcja instalacji | ❌ NIE | 644 |
| `FILE_LIST.md` | Lista plików | ❌ NIE | 644 |

## 📁 Struktura katalogów

```
/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
├── plugin_enhanced.py          # Główny kod wtyczki
├── plugin.py                   # Link do głównego pliku
├── __init__.py                 # Inicjalizacja
├── version.txt                 # Wersja
├── logo.png                    # Logo
├── myupdater.png               # Ikona
├── install_archive_script.sh   # Skrypt instalacji
├── installer_enhanced.sh       # Instalator (opcjonalny)
├── diagnostic.sh               # Diagnostyka (opcjonalny)
├── README.md                   # Instrukcje (opcjonalny)
└── FILE_LIST.md                # Lista plików (opcjonalny)
```

## 🔧 Komendy instalacyjne

### Instalacja automatyczna
```bash
# Pobierz i uruchom instalator
wget -q -O - https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer_enhanced.sh | sh
```

### Instalacja ręczna
```bash
# Tworzenie katalogu
mkdir -p /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/

# Kopiowanie plików
cp plugin_enhanced.py /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/plugin.py
cp __init__.py /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
cp version.txt /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
cp logo.png /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
cp myupdater.png /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/
cp install_archive_script.sh /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/

# Nadawanie uprawnień
chmod 644 /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/*.py
chmod 644 /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/*.txt
chmod 644 /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/*.png
chmod +x /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/install_archive_script.sh
```

## 📋 Weryfikacja instalacji

Po instalacji sprawdź czy wszystkie pliki istnieją:

```bash
# Sprawdź czy pliki istnieją
ls -la /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/

# Sprawdź uprawnienia
ls -la /usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/ | grep -E "plugin\.py|install_archive_script\.sh"
```

## 🚀 Uruchomienie

Po instalacji wtyczka będzie dostępna w:
- **Menu główne** → **Pluginy** → **MyUpdater Enhanced**

## 📝 Logi

Pliki logów są tworzone w:
- `/tmp/MyUpdater_install.log` - logi instalacji
- `/tmp/MyUpdater_diagnostic.log` - logi diagnostyczne

## ⚠️ Ważne informacje

1. **Wszystkie pliki są wymagane** do prawidłowego działania wtyczki
2. **Uprawnienia muszą być ustawione dokładnie** jak w tabeli
3. **Nazwy plików są case-sensitive**
4. **Plugin_enhanced.py** musi być skopiowany jako **plugin.py**
5. **Po instalacji wymagany restart GUI**

## 🔧 Rozwiązywanie problemów

Jeśli wtyczka nie działa:

1. **Sprawdź czy wszystkie pliki istnieją**
2. **Zweryfikuj uprawnienia**
3. **Sprawdź logi** w `/tmp/MyUpdater_install.log`
4. **Uruchom diagnostykę** używając `diagnostic.sh`

---

**MyUpdater Enhanced V5** - Kompletna lista plików do instalacji