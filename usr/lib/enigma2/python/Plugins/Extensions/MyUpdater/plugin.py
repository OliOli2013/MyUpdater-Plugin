# -*- coding: utf-8 -*-
#
# MyUpdater (Mod 2025) V4
# Bazuje na oryginalnej wtyczce MyUpdater (Sancho, gut)
# Przebudowane z użyciem kodu PanelAIO (Paweł Pawełek)
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
from Tools.Directories import fileExists

import os
import subprocess
import json
import datetime
from twisted.internet import reactor
from threading import Thread

# === SEKCJA GLOBALNYCH ZMIENNYCH ===
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V4"  # Aktualna wersja zainstalowana

# === FUNKCJE POMOCNICZE ===
def show_message_compat(session, message, message_type=MessageBox.TYPE_INFO, timeout=10, on_close=None):
    reactor.callLater(0.2, lambda: session.openWithCallback(on_close, MessageBox, message, message_type, timeout=timeout))

def console_screen_open(session, title, cmds_with_args, callback=None, close_on_finish=False):
    cmds_list = cmds_with_args if isinstance(cmds_with_args, list) else [cmds_with_args]
    reactor.callLater(0.1, lambda: session.open(Console, title=title, cmdlist=cmds_list, closeOnSuccess=close_on_finish).onClose.append(callback) if callback else session.open(Console, title=title, cmdlist=cmds_list, closeOnSuccess=close_on_finish))

def prepare_tmp_dir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        try:
            os.makedirs(PLUGIN_TMP_PATH)
        except OSError as e:
            print("[MyUpdater Mod] Error creating tmp dir:", e)

def install_archive(session, title, url, callback_on_finish=None):
    if not url.endswith((".zip", ".tar.gz", ".tgz", ".ipk")):
        show_message_compat(session, "Nieobsługiwany format archiwum!", message_type=MessageBox.TYPE_ERROR)
        if callback_on_finish:
            callback_on_finish()
        return
    archive_type = "zip" if url.endswith(".zip") else ("tar.gz" if url.endswith((".tar.gz", ".tgz")) else "ipk")
    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    download_cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(tmp_archive_path, url)

    if archive_type == "zip":
        picon_path = "/usr/share/enigma2/picon"
        nested_picon_path = os.path.join(picon_path, "picon")
        full_command = (
            '{dl} && '
            'mkdir -p {path} && '
            'unzip -o -q "{arc}" -d "{path}" && '
            'if [ -d "{nest}" ]; then mv -f "{nest}"/* "{path}"/ && rmdir "{nest}"; fi && '
            'rm -f "{arc}" && '
            'echo ">>> Picony zostały pomyślnie zainstalowane." && sleep 2'
        ).format(dl=download_cmd, path=picon_path, arc=tmp_archive_path, nest=nested_picon_path)
    else:
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        if not os.path.exists(install_script_path):
            show_message_compat(session, "BŁĄD: Brak pliku install_archive_script.sh!", message_type=MessageBox.TYPE_ERROR)
            if callback_on_finish:
                callback_on_finish()
            return
        chmod_cmd = 'chmod +x "{}"'.format(install_script_path)
        full_command = '{} && {} && bash {} "{}" "{}"'.format(download_cmd, chmod_cmd, install_script_path, tmp_archive_path, archive_type)

    console_screen_open(session, title, [full_command], callback=callback_on_finish, close_on_finish=True)

def _get_s4aupdater_lists_dynamic_sync():
    s4aupdater_list_txt_url = 'http://s4aupdater.one.pl/s4aupdater_list.txt'
    prepare_tmp_dir()
    tmp_list_file = os.path.join(PLUGIN_TMP_PATH, 's4aupdater_list.txt')
    lists = []
    try:
        cmd = "wget --no-check-certificate -q -T 20 -O {} {}".format(tmp_list_file, s4aupdater_list_txt_url)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.communicate()
        if not (process.returncode == 0 and os.path.exists(tmp_list_file) and os.path.getsize(tmp_list_file) > 0):
            return []
    except Exception:
        return []
    try:
        urls_dict, versions_dict = {}, {}
        with open(tmp_list_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean_line = line.strip()
                if "_url:" in clean_line:
                    parts = clean_line.split(':', 1)
                    urls_dict[parts[0].strip()] = parts[1].strip()
                elif "_version:" in clean_line:
                    parts = clean_line.split(':', 1)
                    versions_dict[parts[0].strip()] = parts[1].strip()
        for var_name, url_value in urls_dict.items():
            display_name_base = var_name.replace('_url', '').replace('_', ' ').title()
            version_key = var_name.replace('_url', '_version')
            date_info = versions_dict.get(version_key, "brak daty")
            lists.append(("{} - {}".format(display_name_base, date_info), "archive:{}".format(url_value)))
    except Exception as e:
        print("[MyUpdater Mod] Błąd parsowania listy S4aUpdater:", e)
        return []
    keywords_to_remove = ['bzyk', 'jakitaki']
    lists = [item for item in lists if not any(keyword in item[0].lower() for keyword in keywords_to_remove)]
    return lists

def _get_lists_from_repo_sync():
    manifest_url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp_json_path = os.path.join(PLUGIN_TMP_PATH, 'manifest.json')
    prepare_tmp_dir()
    try:
        cmd = "wget --no-check-certificate -q -T 20 -O {} {}".format(tmp_json_path, manifest_url)
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        ret_code = process.returncode
        if ret_code != 0:
            return []
        if not (os.path.exists(tmp_json_path) and os.path.getsize(tmp_json_path) > 0):
            return []
    except Exception as e:
        print("[MyUpdater Mod] Błąd pobierania manifest.json (wyjątek):", e)
        return []
    lists_menu = []
    try:
        with open(tmp_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            menu_title = "{} - {} ({})".format(item.get('name', 'Brak nazwy'), item.get('author', ''), item.get('version', ''))
            action = "archive:{}".format(item.get('url', ''))
            if item.get('url'):
                lists_menu.append((menu_title, action))
    except Exception as e:
        print("[MyUpdater Mod] Błąd przetwarzania pliku manifest.json:", e)
        return []
    if not lists_menu:
        return []
    return lists_menu

def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        show_message_compat(session, "Listy kanałów przeładowane.", message_type=MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        print("[MyUpdater Mod] Błąd podczas przeładowywania list:", e)
        show_message_compat(session, "Wystąpił błąd podczas przeładowywania list.", message_type=MessageBox.TYPE_ERROR)

# === GŁÓWNA KLASA WTYCZKI (MENU) ===
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
        mainmenu = [("1. Listy kanałów", "menu_lists"),
                    ("2. Instaluj Softcam", "menu_softcam"),
                    ("3. Pobierz Picony Transparent", "picons_github"),
                    ("4. Aktualizacja Wtyczki", "plugin_update"),
                    ("5. Informacja o Wtyczce", "plugin_info")]
        self['menu'] = MenuList(mainmenu)
        self['info'] = Label("Wybierz opcję i naciśnij OK")
        self['version'] = Label("Wersja: " + VER)
        self['actions'] = ActionMap(['WizardActions', 'DirectionActions'], {'ok': self.runMenuOption, 'back': self.close}, -1)
        prepare_tmp_dir()

    def runMenuOption(self):
        selected = self['menu'].l.getCurrentSelection()
        if selected is None:
            return
        callback_key = selected[1]
        if callback_key == "menu_lists":
            self.runChannelListMenu()
        elif callback_key == "menu_softcam":
            self.runSoftcamMenu()
        elif callback_key == "picons_github":
            self.runPiconGitHub()
        elif callback_key == "plugin_update":
            self.runPluginUpdate()
        elif callback_key == "plugin_info":
            self.runInfo()

    def runChannelListMenu(self):
        self['info'].setText("Pobieranie list (GitHub i S4A)...")
        thread = Thread(target=self._background_list_loader)
        thread.start()

    def _background_list_loader(self):
        repo_lists = _get_lists_from_repo_sync()
        s4a_lists = _get_s4aupdater_lists_dynamic_sync()
        combined_lists = repo_lists + s4a_lists
        reactor.callFromThread(self._onChannelListLoaded, combined_lists)

    def _onChannelListLoaded(self, lists):
        self['info'].setText("Wybierz opcję i naciśnij OK")
        if not lists:
            show_message_compat(self.session, "Błąd pobierania list. Sprawdź internet.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected, ChoiceBox, title="Wybierz listę kanałów do instalacji", list=lists)

    def runChannelListSelected(self, choice):
        if not choice:
            return
        try:
            title = choice[0]
            url = choice[1].split(':', 1)[1]
            show_message_compat(self.session, "Rozpoczynanie instalacji listy...", timeout=2)
            install_archive(self.session, title, url, callback_on_finish=lambda: reload_settings_python(self.session))
        except Exception as e:
            print("[MyUpdater Mod] Błąd wyboru listy:", e)
            show_message_compat(self.session, "Błąd wyboru listy.", MessageBox.TYPE_ERROR)

    def runSoftcamMenu(self):
        options = [("Oscam (z feedu + fallback Levi45)", "oscam_feed"),
                   ("Oscam (tylko Levi45)", "oscam_levi45"),
                   ("nCam (biko-73)", "ncam_biko")]
        self.session.openWithCallback(self.runSoftcamSelected, ChoiceBox, title="Wybierz Softcam do instalacji", list=options)

    def runSoftcamSelected(self, choice):
        if not choice:
            return
        key, title = choice[1], choice[0]
        cmd = ""
        if key == "oscam_feed":
            cmd = """ echo "Instalowanie/Aktualizowanie Softcam Feed..." && wget -O - -q http://updates.mynonpublic.com/oea/feed | bash && echo "Aktualizuję listę pakietów..." && opkg update && echo "Wyszukuję najlepszą wersję Oscam w feedach..." && PKG_NAME=$(opkg list | grep 'oscam' | grep 'ipv4only' | grep -E -m 1 'master|emu|stable' | cut -d ' ' -f 1) && if [ -n "$PKG_NAME" ]; then echo "Znaleziono pakiet: $PKG_NAME. Rozpoczynam instalację..." && opkg install $PKG_NAME; else echo "Nie znaleziono odpowiedniego pakietu Oscam w feedach. Próbuję instalacji z alternatywnego źródła (Levi45)..." && wget -q "--no-check-certificate" https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh; fi && echo "Instalacja Oscam zakończona." && sleep 3 """
        elif key == "oscam_levi45":
            cmd = 'wget -q "--no-check-certificate" https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh'
        elif key == "ncam_biko":
            cmd = "wget https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O - | /bin/sh"
        if cmd:
            show_message_compat(self.session, "Rozpoczynanie instalacji {}...".format(title), timeout=2)
            console_screen_open(self.session, title, [cmd.strip()], close_on_finish=True)

    def runPiconGitHub(self):
        title, PICONS_URL = "Pobieranie Picon (Transparent)", "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
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
        try:
            cmd = "wget --no-check-certificate -q -T 10 -t 2 -O {} {}".format(tmp_version_path, version_url)
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate()
            if process.returncode == 0 and os.path.exists(tmp_version_path) and os.path.getsize(tmp_version_path) > 0:
                with open(tmp_version_path, 'r') as f:
                    online_version = f.read().strip()
            else:
                error_msg = "Nie udało się pobrać informacji o wersji."
        except Exception as e:
            print("[MyUpdater Mod] Błąd sprawdzania wersji online:", e)
            error_msg = "Błąd podczas sprawdzania wersji."
        if os.path.exists(tmp_version_path):
            os.remove(tmp_version_path)
        reactor.callFromThread(self._on_version_check_complete, online_version, installer_url, error_msg)

    def _on_version_check_complete(self, online_version, installer_url, error_msg):
        self['info'].setText("Wybierz opcję i naciśnij OK")
        if error_msg:
            show_message_compat(self.session, error_msg, MessageBox.TYPE_ERROR)
            return
        if online_version:
            print("[MyUpdater Mod] Wersja online: '{}', Wersja lokalna: '{}'".format(online_version, VER))
            if online_version != VER:
                message = "Dostępna jest nowa wersja: {}\nTwoja wersja: {}\n\nCzy chcesz zaktualizować teraz?".format(online_version, VER)
                self.session.openWithCallback(lambda confirmed: self._doPluginUpdate(installer_url) if confirmed else None,
                                              MessageBox, message, type=MessageBox.TYPE_YESNO, title="Dostępna aktualizacja")
            else:
                show_message_compat(self.session, "Używasz najnowszej wersji wtyczki ({}).".format(VER), MessageBox.TYPE_INFO)
        else:
            show_message_compat(self.session, "Nie udało się odczytać wersji online.", MessageBox.TYPE_ERROR)

    def _doPluginUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        title = "Aktualizacja Wtyczki MyUpdater"
        console_screen_open(self.session, title, [cmd], close_on_finish=True)

    def runInfo(self):
        info_text = ("MyUpdater (Mod 2025) {}\n\n"
                     "Przebudowa: Paweł Pawełek\n"
                     "(msisystem@t.pl)\n\n"
                     "Wtyczka bazuje na kodzie źródłowym PanelAIO.\n\n"
                     "Oryginalni twórcy MyUpdater:\n"
                     "Sancho, gut").format(VER)
        self.session.open(MessageBox, info_text, MessageBox.TYPE_INFO)

# === DEFINICJA PLUGINU ===
def main(session, **kwargs):
    session.open(Fantastic)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater",
                             description="MyUpdater Mod {} (bazuje na PanelAIO)".format(VER),
                             where=PluginDescriptor.WHERE_PLUGINMENU,
                             icon="myupdater.png",
                             fnc=main)]
