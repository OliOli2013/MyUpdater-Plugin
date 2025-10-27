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
    def _open():
        c = session.open(Console, title=title, cmdlist=cmds_list, closeOnSuccess=close_on_finish)
        if callback:
            c.onClose.append(callback)
    reactor.callLater(0.1, _open)

def prepare_tmp_dir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        try:
            os.makedirs(PLUGIN_TMP_PATH)
        except OSError as e:
            print("[MyUpdater Mod] Error creating tmp dir:", e)

def install_archive(session, title, url, callback_on_finish=None):
    """
    Poprawka: rozróżniaj PICONY po tytule, a nie po rozszerzeniu.
    - jeśli 'picon' w tytule -> instalacja do /usr/share/enigma2/picon (zip)
    - wszystko inne (zip/tar.gz/tgz/ipk) -> przez install_archive_script.sh (listy kanałów itd.)
    """
    supported = (".zip", ".tar.gz", ".tgz", ".ipk")
    if not url.endswith(supported):
        show_message_compat(session, "Nieobsługiwany format archiwum!", message_type=MessageBox.TYPE_ERROR)
        if callback_on_finish:
            callback_on_finish()
        return

    # Rozpoznanie kontekstu po tytule (jak w PanelAIO)
    is_picons = "picon" in (title or "").lower()

    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    download_cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(tmp_archive_path, url)

    if is_picons:
        # Instalacja piconów (tylko, gdy tytuł zawiera "picon")
        picon_path = "/usr/share/enigma2/picon"
        nested_picon_path = os.path.join(picon_path, "picon")
        full_command = (
            "{download_cmd} && "
            "mkdir -p {picon_path} && "
            "unzip -o -q \"{archive_path}\" -d \"{picon_path}\" && "
            "if [ -d \"{nested_path}\" ]; then mv -f \"{nested_path}\"/* \"{picon_path}/\"; rmdir \"{nested_path}\"; fi && "
            "rm -f \"{archive_path}\" && "
            "echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 3"
        ).format(
            download_cmd=download_cmd,
            archive_path=tmp_archive_path,
            picon_path=picon_path,
            nested_path=nested_picon_path
        )
    else:
        # Listy kanałów i inne archiwa – zawsze przez skrypt bash
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        if not os.path.exists(install_script_path):
            show_message_compat(session, "BŁĄD: Brak pliku install_archive_script.sh!", message_type=MessageBox.TYPE_ERROR)
            if callback_on_finish:
                callback_on_finish()
            return
        chmod_cmd = 'chmod +x "{}"'.format(install_script_path)
        archive_type = (
            "tar.gz" if url.endswith((".tar.gz", ".tgz"))
            else "ipk" if url.endswith(".ipk")
            else "zip"
        )
        full_command = '{} && {} && bash "{}" "{}" "{}"'.format(
            download_cmd, chmod_cmd, install_script_path, tmp_archive_path, archive_type
        )

    console_screen_open(
        session,
        title,
        [full_command],
        callback=callback_on_finish,
        close_on_finish=True
    )

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
    """ Przeładowuje listy kanałów w Enigma2 używając eDVBDB """
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        show_message_compat(session, "Listy kanałów przeładowane.", message_type=MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        print("[MyUpdater Mod] Błąd podczas przeładowywania list:", e)
        show_message_compat(session, "Wystąpił błąd podczas przeładowywania list.", message_type=MessageBox.TYPE_ERROR)

# === KONIEC FUNKCJI POMOCNICZYCH ===

# Główna klasa wtyczki (Menu)
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
        mainmenu = [
            ("1. Listy kanałów", "menu_lists"),
            ("2. Instaluj Softcam", "menu_softcam"),
            ("3. Pobierz Picony Transparent", "picons_github"),
            ("4. Aktualizacja Wtyczki", "plugin_update"),
            ("5. Informacja o Wtyczce", "plugin_info")
        ]
        self['menu'] = MenuList(mainmenu)
        self['info'] = Label("Wybierz opcję i naciśnij OK")
        self['version'] =
