# -*- coding: utf-8 -*-
#
# MyUpdater (Mod 2025) V4
# Bazuje na oryginalnej wtyczce MyUpdater (Sancho, gut)
# Przebudowane z użyciem kodu PanelAIO (Paweł Pawełek)
# Wersja z dodatkowym logowaniem warunku if/elif w install_archive
#
from __future__ import print_function
from __future__ import absolute_import
from enigma import eDVBDB
from Screens.Screen import Screen
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Screens.ChoiceBox import ChoiceBox
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.Label import Label
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists, SCOPE_PLUGINS, resolveFilename

import os
import subprocess
import json
import datetime
from twisted.internet import reactor
from threading import Thread
import traceback # Dodano import traceback do logowania pełnych błędów

# === SEKCJA GLOBALNYCH ZMIENNYCH ===
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V4" # Aktualna wersja zainstalowana
LOG_FILE = "/tmp/MyUpdater_install.log" # Plik logu dla instalacji

# Funkcja logująca do pliku
def log_message(message):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + str(message) + "\n")
    except Exception as e:
        print("[MyUpdater Mod] Error writing to log file:", e)

# === FUNKCJE POMOCNICZE ===

def show_message_compat(session, message, message_type=MessageBox.TYPE_INFO, timeout=10, on_close=None):
    log_message("MessageBox: " + str(message)) # Dodano str()
    reactor.callLater(0.2, lambda: session.openWithCallback(on_close, MessageBox, message, message_type, timeout=timeout))

def console_screen_open(session, title, cmds_with_args, callback=None, close_on_finish=False):
    cmds_list = cmds_with_args if isinstance(cmds_with_args, list) else [cmds_with_args]
    log_message("Console Open: Title='{}', Cmd='{}'".format(title, "; ".join(cmds_list)))
    # Używamy finishedCallback, jak sugeruje dokumentacja dla nowszych E2, onClose jako fallback
    try:
        console_instance = session.open(Console, title=title, cmdlist=cmds_list, closeOnSuccess=close_on_finish)
        if callback:
            # Preferuj finishedCallback, jeśli istnieje
            if hasattr(console_instance, 'finishedCallback'):
                 console_instance.finishedCallback.append(callback)
                 log_message("Attached callback to finishedCallback.")
            elif hasattr(console_instance, 'onClose'):
                 console_instance.onClose.append(callback)
                 log_message("Attached callback to onClose.")
            else:
                 log_message("Warning: Could not attach callback to Console.")
        # Otwieranie przez reactor może być nadal potrzebne, jeśli wywoływane z wątku
        # Ale zróbmy to tylko jeśli nie jesteśmy w głównym wątku
        # is_main_thread = not reactor.running or reactor.callFromThread(lambda: True) # Ta metoda może być zawodna
        # Na razie zostawmy reactor.callLater dla bezpieczeństwa
        # reactor.callLater(0.1, lambda: _open_console_safely(session, title, cmds_list, callback, close_on_finish))

    except Exception as e:
        log_message("!!! EXCEPTION in console_screen_open: {}".format(e))
        log_message(traceback.format_exc())

# Funkcja pomocnicza dla console_screen_open (choć może nie być potrzebna)
# def _open_console_safely(session, title, cmds_list, callback, close_on_finish):
#     try:
#         console_instance = session.open(Console, title=title, cmdlist=cmds_list, closeOnSuccess=close_on_finish)
#         if callback:
#             if hasattr(console_instance, 'finishedCallback'):
#                  console_instance.finishedCallback.append(callback)
#                  log_message("Attached callback to finishedCallback (delayed).")
#             elif hasattr(console_instance, 'onClose'):
#                  console_instance.onClose.append(callback)
#                  log_message("Attached callback to onClose (delayed).")
#             else:
#                  log_message("Warning: Could not attach callback to Console (delayed).")
#     except Exception as e:
#         log_message("!!! EXCEPTION in _open_console_safely: {}".format(e))
#         log_message(traceback.format_exc())


def prepare_tmp_dir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        try:
            os.makedirs(PLUGIN_TMP_PATH)
            log_message("Created tmp dir: {}".format(PLUGIN_TMP_PATH))
        except OSError as e:
            log_message("Error creating tmp dir: {}".format(e))
            print("[MyUpdater Mod] Error creating tmp dir:", e)

# POPRAWIONA funkcja install_archive z BARDZO szczegółowym logowaniem warunku if/elif
def install_archive(session, title, url, callback_on_finish=None):
    log_message("--- install_archive START ---")
    log_message("URL received: {}".format(url))
    log_message("Title received: {}".format(title))

    is_zip = url.lower().endswith(".zip") # Sprawdzamy małe litery dla pewności
    is_tar = url.lower().endswith((".tar.gz", ".tgz")) # Sprawdzamy małe litery

    log_message("Checking URL ends with .zip: {}".format(is_zip))
    log_message("Checking URL ends with .tar.gz/.tgz: {}".format(is_tar))

    if not is_zip and not is_tar:
        msg = "Nieobsługiwany format archiwum! URL: {}".format(url)
        log_message("Error: " + msg)
        show_message_compat(session, msg, message_type=MessageBox.TYPE_ERROR)
        if callback_on_finish:
            try: callback_on_finish()
            except Exception as cb_e: log_message("Exception in callback (unsupported format): {}".format(cb_e))
        log_message("--- install_archive END (Unsupported format) ---")
        return

    # Określenie typu archiwum JESZCZE RAZ dla pewności
    archive_type = "zip" if is_zip else "tar.gz"
    log_message("Determined archive_type: '{}'".format(archive_type)) # Powtórzone logowanie dla debugowania

    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    download_cmd = "wget --no-check-certificate -O \"{}\" \"{}\"".format(tmp_archive_path, url)
    log_message("Temp archive path: '{}'".format(tmp_archive_path))

    full_command = "" # Zainicjuj pustą komendę

    # Logika dla ZIP (picon)
    if archive_type == "zip":
        log_message("*** EXECUTING ZIP LOGIC (PICONS) ***")
        picon_path = "/usr/share/enigma2/picon"
        log_message("Target directory (picons): {}".format(picon_path))
        nested_picon_path = os.path.join(picon_path, "picon")
        full_command = (
            "echo '>>> Rozpoczynam pobieranie picon...' && "
            "{download_cmd} && "
            "echo '>>> Tworzenie katalogu picon (jeśli nie istnieje): {picon_path}' && "
            "mkdir -p {picon_path} && "
            "echo '>>> Rozpakowywanie archiwum picon (unzip)...' && "
            "unzip -o -q \"{archive_path}\" -d \"{picon_path}\" && "
            "echo '>>> Sprawdzanie zagnieżdżonego katalogu...' && "
            "if [ -d \"{nested_path}\" ]; then echo '> Przenoszenie z {nested_path} do {picon_path}'; mv -f \"{nested_path}\"/* \"{picon_path}/\"; rmdir \"{nested_path}\"; else echo '> Brak zagnieżdżonego katalogu.'; fi && "
            "echo '>>> Usuwanie archiwum picon...' && "
            "rm -f \"{archive_path}\" && "
            "echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 3"
        ).format(
            download_cmd=download_cmd,
            archive_path=tmp_archive_path,
            picon_path=picon_path,
            nested_path=nested_picon_path
        )
    # Logika dla TAR.GZ (listy kanałów)
    elif archive_type == "tar.gz":
        log_message("*** EXECUTING TAR.GZ LOGIC (CHANNEL LISTS) ***")
        target_dir = "/etc/enigma2/"
        log_message("Target directory (channel list): {}".format(target_dir))
        full_command = (
            "echo '>>> Rozpoczynam pobieranie listy kanałów...' && "
            "{download_cmd} && "
            "echo '>>> Rozpakowywanie archiwum listy kanałów do {target_dir} (tar)...' && "
            # Używamy -C {target_dir} i --strip-components=1, dodano -v dla logów
            "tar -xzvf \"{archive_path}\" -C {target_dir} --strip-components=1 --overwrite && "
            "echo '>>> Zawartość {target_dir} PO rozpakowaniu (pliki .tv i lamedb):' && "
            "ls -l {target_dir} | grep -E '(\\.tv|lamedb)' || echo '> Nie znaleziono plików list?' && "
            "echo '>>> Usuwanie archiwum listy kanałów...' && "
            "rm -f \"{archive_path}\" && "
            "echo '>>> Lista kanałów została pomyślnie zainstalowana.' && sleep 3"
        ).format(
            download_cmd=download_cmd,
            archive_path=tmp_archive_path,
            target_dir=target_dir
        )
    else:
        # Ten blok nie powinien być nigdy osiągnięty
        log_message("!!! INTERNAL ERROR: Unknown archive_type '{}' after initial check".format(archive_type))
        show_message_compat(session, "Wewnętrzny błąd - nieznany typ archiwum!", MessageBox.TYPE_ERROR)
        if callback_on_finish:
             try: callback_on_finish()
             except Exception as cb_e: log_message("Exception in callback (internal error): {}".format(cb_e))
        log_message("--- install_archive END (Internal Error) ---")
        return


    # Logowanie finalnej komendy przed wykonaniem
    if full_command:
        log_message("Final command to be executed: {}".format(full_command))
        # Wywołanie konsoli - używamy lambda, aby upewnić się, że callback jest wywołany poprawnie
        def run_callback_safely():
            if callback_on_finish:
                log_message("Console finished, executing callback.")
                try:
                    callback_on_finish()
                except Exception as cb_e:
                    log_message("!!! EXCEPTION in callback after console finish: {}".format(cb_e))
                    log_message(traceback.format_exc())
            else:
                log_message("Console finished, no callback defined.")

        console_screen_open(session, title, [full_command], callback=run_callback_safely, close_on_finish=True)
    else:
        log_message("!!! Error: full_command is empty before calling console_screen_open.")

    log_message("--- install_archive END ---")


# --- Reszta funkcji pomocniczych (bez zmian) ---

def _get_s4aupdater_lists_dynamic_sync():
    s4aupdater_list_txt_url = 'http://s4aupdater.one.pl/s4aupdater_list.txt'
    prepare_tmp_dir()
    tmp_list_file = os.path.join(PLUGIN_TMP_PATH, 's4aupdater_list.txt')
    lists = []
    log_message("Fetching S4A list from: {}".format(s4aupdater_list_txt_url))
    try:
        cmd = "wget --no-check-certificate -q -T 20 -O {} {}".format(tmp_list_file, s4aupdater_list_txt_url)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0 or not fileExists(tmp_list_file) or os.path.getsize(tmp_list_file) == 0:
             log_message("Error fetching S4A list. wget code: {}, stderr: {}".format(process.returncode, stderr))
             return []
    except Exception as e:
        log_message("Exception fetching S4A list: {}".format(e))
        return []
    try:
        urls_dict, versions_dict = {}, {}
        with open(tmp_list_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean_line = line.strip()
                if "_url:" in clean_line: parts = clean_line.split(':', 1); urls_dict[parts[0].strip()] = parts[1].strip()
                elif "_version:" in clean_line: parts = clean_line.split(':', 1); versions_dict[parts[0].strip()] = parts[1].strip()
        for var_name, url_value in urls_dict.items():
            display_name_base = var_name.replace('_url', '').replace('_', ' ').title()
            version_key = var_name.replace('_url', '_version')
            date_info = versions_dict.get(version_key, "brak daty")
            lists.append(("{} - {}".format(display_name_base, date_info), "archive:{}".format(url_value)))
        log_message("Parsed {} lists from S4A".format(len(lists)))
    except Exception as e:
        log_message("Exception parsing S4A list: {}".format(e))
        return []
    keywords_to_remove = ['bzyk', 'jakitaki']
    lists = [item for item in lists if not any(keyword in item[0].lower() for keyword in keywords_to_remove)]
    log_message("Filtered S4A lists, remaining: {}".format(len(lists)))
    return lists

def _get_lists_from_repo_sync():
    manifest_url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp_json_path = os.path.join(PLUGIN_TMP_PATH, 'manifest.json')
    prepare_tmp_dir()
    log_message("Fetching repo manifest from: {}".format(manifest_url))
    try:
        cmd = "wget --no-check-certificate -q -T 20 -O {} {}".format(tmp_json_path, manifest_url)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        ret_code = process.returncode
        if ret_code != 0 or not fileExists(tmp_json_path) or os.path.getsize(tmp_json_path) == 0:
            log_message("Error fetching repo manifest. wget code: {}, stderr: {}".format(ret_code, stderr))
            return []
    except Exception as e:
        log_message("Exception fetching repo manifest: {}".format(e))
        return []
    lists_menu = []
    try:
        with open(tmp_json_path, 'r', encoding='utf-8') as f: data = json.load(f)
        for item in data:
            menu_title = "{} - {} ({})".format(item.get('name', 'Brak nazwy'), item.get('author', ''), item.get('version', ''))
            action = "archive:{}".format(item.get('url', ''))
            if item.get('url'): lists_menu.append((menu_title, action))
        log_message("Parsed {} lists from repo manifest".format(len(lists_menu)))
    except Exception as e:
        log_message("Exception parsing repo manifest: {}".format(e))
        return []
    if not lists_menu:
         log_message("No lists found in repo manifest.")
         return []
    return lists_menu

# Funkcja przeładowania z PanelAIO
def reload_settings_python(session, *args):
    log_message("Reloading channel lists using eDVBDB...")
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        log_message("Channel lists reloaded successfully.")
        show_message_compat(session, "Listy kanałów przeładowane.", message_type=MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        log_message("Error reloading channel lists: {}".format(e))
        print("[MyUpdater Mod] Błąd podczas przeładowywania list:", e)
        show_message_compat(session, "Wystąpił błąd podczas przeładowywania list.", message_type=MessageBox.TYPE_ERROR)

# === KONIEC FUNKCJI POMOCNICZYCH ===


# Główna klasa wtyczki (Menu) - bez zmian
class Fantastic(Screen):
    skin = """
        <screen position="center,center" size="700,400" title="MyUpdater">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
            <widget name="menu" position="10,70" size="680,280" scrollbarMode="showOnDemand" />
            <widget name="info" position="10,360" size="680,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
            <widget name="version" position="550,370" size="140,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
        </screen>"""

    def __init__(self, session, args=0):
        self.session = session
        Screen.__init__(self, session)
        self.setTitle("MyUpdater")
        mainmenu = [ ("1. Listy kanałów", "menu_lists"), ("2. Instaluj Softcam", "menu_softcam"), ("3. Pobierz Picony Transparent", "picons_github"), ("4. Aktualizacja Wtyczki", "plugin_update"), ("5. Informacja o Wtyczce", "plugin_info") ]
        self['menu'] = MenuList(mainmenu)
        self['info'] = Label("Wybierz opcję i naciśnij OK")
        self['version'] = Label("Wersja: " + VER)
        self['actions'] = ActionMap(['WizardActions', 'DirectionActions'], {'ok': self.runMenuOption, 'back': self.close}, -1)
        # Czyszczenie logu przy starcie
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        log_message("MyUpdater Mod V4 started.")
        prepare_tmp_dir()

    def runMenuOption(self):
        selected = self['menu'].l.getCurrentSelection()
        if selected is None: return
        callback_key = selected[1]
        log_message("Menu option selected: {}".format(callback_key))
        if callback_key == "menu_lists": self.runChannelListMenu()
        elif callback_key == "menu_softcam": self.runSoftcamMenu()
        elif callback_key == "picons_github": self.runPiconGitHub()
        elif callback_key == "plugin_update": self.runPluginUpdate()
        elif callback_key == "plugin_info": self.runInfo()

    def runChannelListMenu(self):
        self['info'].setText("Pobieranie list (GitHub i S4A)...")
        thread = Thread(target=self._background_list_loader)
        thread.start()

    def _background_list_loader(self):
        log_message("Starting background list loading thread.")
        repo_lists = _get_lists_from_repo_sync()
        s4a_lists = _get_s4aupdater_lists_dynamic_sync()
        combined_lists = repo_lists + s4a_lists
        log_message("Finished background list loading. Found {} lists total.".format(len(combined_lists)))
        reactor.callFromThread(self._onChannelListLoaded, combined_lists)

    def _onChannelListLoaded(self, lists):
        self['info'].setText("Wybierz opcję i naciśnij OK")
        if not lists:
            msg = "Błąd pobierania list. Sprawdź internet."
            log_message("Error: " + msg)
            show_message_compat(self.session, msg, MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected, ChoiceBox, title="Wybierz listę kanałów do instalacji", list=lists)

    def runChannelListSelected(self, choice):
        if not choice:
            log_message("Channel list selection cancelled.")
            return
        try:
            title = choice[0]
            url = choice[1].split(':', 1)[1]
            log_message("Selected channel list: '{}', URL: {}".format(title, url))
            show_message_compat(self.session, "Rozpoczynanie instalacji listy...", timeout=2)
            # Używamy callback reload_settings_python
            install_archive(self.session, title, url, callback_on_finish=lambda: reload_settings_python(self.session))
        except Exception as e:
            log_message("Error processing channel list selection: {}".format(e))
            log_message(traceback.format_exc()) # Loguj pełny traceback błędu
            print("[MyUpdater Mod] Błąd wyboru listy:", e)
            show_message_compat(self.session, "Błąd wyboru listy.", MessageBox.TYPE_ERROR)

    # --- Reszta funkcji bez zmian (Softcam, Picony, Aktualizacja, Info) ---

    def runSoftcamMenu(self):
        options = [ ("Oscam (z feedu + fallback Levi45)", "oscam_feed"), ("Oscam (tylko Levi45)", "oscam_levi45"), ("nCam (biko-73)", "ncam_biko") ]
        self.session.openWithCallback(self.runSoftcamSelected, ChoiceBox, title="Wybierz Softcam do instalacji", list=options)

    def runSoftcamSelected(self, choice):
        if not choice:
            log_message("Softcam selection cancelled.")
            return
        key, title, cmd = choice[1], choice[0], ""
        log_message("Selected softcam: '{}'".format(key))
        if key == "oscam_feed":
            cmd = """ echo "Instalowanie/Aktualizowanie Softcam Feed..." && wget -O - -q http://updates.mynonpublic.com/oea/feed | bash && echo "Aktualizuję listę pakietów..." && opkg update && echo "Wyszukuję najlepszą wersję Oscam w feedach..." && PKG_NAME=$(opkg list | grep 'oscam' | grep 'ipv4only' | grep -E -m 1 'master|emu|stable' | cut -d ' ' -f 1) && if [ -n "$PKG_NAME" ]; then echo "Znaleziono pakiet: $PKG_NAME. Rozpoczynam instalację..." && opkg install $PKG_NAME; else echo "Nie znaleziono odpowiedniego pakietu Oscam w feedach. Próbuję instalacji z alternatywnego źródła (Levi45)..." && wget -q "--no-check-certificate" https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh; fi && echo "Instalacja Oscam zakończona." && sleep 3 """
        elif key == "oscam_levi45": cmd = "wget -q \"--no-check-certificate\" https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh"
        elif key == "ncam_biko": cmd = "wget https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O - | /bin/sh"
        if cmd:
             show_message_compat(self.session, "Rozpoczynanie instalacji {}...".format(title), timeout=2)
             console_screen_open(self.session, title, [cmd.strip()], close_on_finish=True)

    def runPiconGitHub(self):
        title, PICONS_URL = "Pobieranie Picon (Transparent)", "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        log_message("Starting picon download from: {}".format(PICONS_URL))
        show_message_compat(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        install_archive(self.session, title, PICONS_URL)

    def runPluginUpdate(self):
        show_message_compat(self.session, "Sprawdzanie dostępności aktualizacji...", timeout=3)
        self['info'].setText("Sprawdzanie wersji online...")
        thread = Thread(target=self._check_version_online)
        thread.start()

    def _check_version_online(self):
        version_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        installer_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_version_path = os.path.join(PLUGIN_TMP_PATH, 'version.txt')
        online_version, error_msg = None, None
        log_message("Checking for updates at: {}".format(version_url))
        try:
            cmd = "wget --no-check-certificate -q -T 10 -t 2 -O {} {}".format(tmp_version_path, version_url)
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate()
            if process.returncode == 0 and fileExists(tmp_version_path) and os.path.getsize(tmp_version_path) > 0:
                with open(tmp_version_path, 'r') as f: online_version = f.read().strip()
                log_message("Online version found: {}".format(online_version))
            else:
                error_msg = "Nie udało się pobrać informacji o wersji."
                log_message("Error fetching version file. wget code: {}".format(process.returncode))
        except Exception as e:
            log_message("Exception during update check: {}".format(e))
            print("[MyUpdater Mod] Błąd sprawdzania wersji online:", e)
            error_msg = "Błąd podczas sprawdzania wersji."
        if fileExists(tmp_version_path):
            try: os.remove(tmp_version_path)
            except: pass
        reactor.callFromThread(self._on_version_check_complete, online_version, installer_url, error_msg)

    def _on_version_check_complete(self, online_version, installer_url, error_msg):
        self['info'].setText("Wybierz opcję i naciśnij OK")
        if error_msg:
            log_message("Update check finished with error: {}".format(error_msg))
            show_message_compat(self.session, error_msg, MessageBox.TYPE_ERROR)
            return
        if online_version:
            log_message("Update check complete. Online: '{}', Local: '{}'".format(online_version, VER))
            if online_version != VER:
                message = "Dostępna jest nowa wersja: {}\nTwoja wersja: {}\n\nCzy chcesz zaktualizować teraz?".format(online_version, VER)
                self.session.openWithCallback( lambda confirmed: self._doPluginUpdate(installer_url) if confirmed else log_message("Update declined by user."), MessageBox, message, type=MessageBox.TYPE_YESNO, title="Dostępna aktualizacja" )
            else:
                show_message_compat(self.session, "Używasz najnowszej wersji wtyczki ({}).".format(VER), MessageBox.TYPE_INFO)
        else:
             log_message("Update check failed: Could not read online version.")
             show_message_compat(self.session, "Nie udało się odczytać wersji online.", MessageBox.TYPE_ERROR)

    def _doPluginUpdate(self, url):
        log_message("Starting plugin update process from URL: {}".format(url))
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        title = "Aktualizacja Wtyczki MyUpdater"
        console_screen_open(self.session, title, [cmd], close_on_finish=True)

    def runInfo(self):
        info_text = ( "MyUpdater (Mod 2025) {}\n\nPrzebudowa: Paweł Pawełek\n(msisystem@t.pl)\n\nWtyczka bazuje na kodzie źródłowym PanelAIO.\n\nOryginalni twórcy MyUpdater:\nSancho, gut" ).format(VER)
        self.session.open(MessageBox, info_text, MessageBox.TYPE_INFO)

# === DEFINICJA PLUGINU ===

def main(session, **kwargs):
    session.open(Fantastic)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater", description="MyUpdater Mod {} (bazuje na PanelAIO)".format(VER), where = PluginDescriptor.WHERE_PLUGINMENU, icon = "myupdater.png", fnc = main)]
