# -*- coding: utf-8 -*-
#
# MyUpdater (Mod 2025) V4
# Kompatybilny Python 2/3 – Enigma2
#
from __future__ import print_function
from __future__ import absolute_import
import sys
import os
import subprocess
import json
import datetime
from twisted.internet import reactor
from threading import Thread

try:
    from enigma import eDVBDB
    from Screens.Screen import Screen
    from Screens.Console import Console
    from Screens.MessageBox import MessageBox
    from Screens.ChoiceBox import ChoiceBox
    from Components.ActionMap import ActionMap
    from Components.MenuList import MenuList
    from Components.Label import Label
    from Plugins.Plugin import PluginDescriptor
    from Tools.Directories import fileExists
except ImportError as e:
    print("[MyUpdater] Import error:", e)
    sys.exit(1)

# === GLOBALNE ===
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V4"

# === POMOCNICZE ===
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
            print("[MyUpdater] Błąd tworzenia tmp:", e)

def install_archive(session, title, url, callback_on_finish=None):
    if not url.endswith((".tar.gz", ".tgz", ".zip")):
        show_message_compat(session, "Nieobsługiwany format archiwum!", MessageBox.TYPE_ERROR)
        if callback_on_finish:
            callback_on_finish()
        return
    archive_type = "tar.gz" if url.endswith((".tar.gz", ".tgz")) else "zip"
    prepare_tmp_dir()
    tmp_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    download_cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(tmp_path, url)

    if archive_type == "zip":
        picon_path = "/usr/share/enigma2/picon"
        nested = os.path.join(picon_path, "picon")
        full_cmd = (
            '{dl} && mkdir -p {path} && '
            'unzip -o -q "{arc}" -d "{path}" && '
            'if [ -d "{nest}" ]; then mv -f "{nest}"/* "{path}"/ && rmdir "{nest}"; fi && '
            'rm -f "{arc}" && echo ">>> Picony zainstalowane." && sleep 2'
        ).format(dl=download_cmd, path=picon_path, arc=tmp_path, nest=nested)
    else:
        script = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        if not fileExists(script):
            show_message_compat(session, "BŁĄD: Brak install_archive_script.sh!", MessageBox.TYPE_ERROR)
            if callback_on_finish:
                callback_on_finish()
            return
        chmod_cmd = 'chmod +x "{}"'.format(script)
        full_cmd = '{} && {} && bash {} "{}" "{}"'.format(download_cmd, chmod_cmd, script, tmp_path, archive_type)

    console_screen_open(session, title, [full_cmd], callback=callback_on_finish, close_on_finish=True)

def _get_s4aupdater_lists_dynamic_sync():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"
    tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt")
    prepare_tmp_dir()
    try:
        subprocess.call(["wget", "--no-check-certificate", "-q", "-T", "20", "-O", tmp, url])
        if not (fileExists(tmp) and os.path.getsize(tmp) > 0):
            return []
    except Exception:
        return []
    lists = []
    try:
        urls, vers = {}, {}
        with open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if "_url:" in line:
                    k, v = line.split(':', 1)
                    urls[k.strip()] = v.strip()
                elif "_version:" in line:
                    k, v = line.split(':', 1)
                    vers[k.strip()] = v.strip()
        for k, url in urls.items():
            name = k.replace('_url', '').replace('_', ' ').title()
            ver_key = k.replace('_url', '_version')
            date_info = vers.get(ver_key, "brak daty")
            lists.append(("{} - {}".format(name, date_info), "archive:{}".format(url)))
    except Exception as e:
        print("[MyUpdater] Błąd parsowania S4A:", e)
        return []
    keywords = ['bzyk', 'jakitaki']
    lists = [it for it in lists if not any(kw in it[0].lower() for kw in keywords)]
    return lists

def _get_lists_from_repo_sync():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    prepare_tmp_dir()
    try:
        subprocess.call(["wget", "--no-check-certificate", "-q", "-T", "20", "-O", tmp, url])
        if not (fileExists(tmp) and os.path.getsize(tmp) > 0):
            return []
    except Exception as e:
        print("[MyUpdater] Błąd pobierania manifest:", e)
        return []
    lists_menu = []
    try:
        with open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            title = "{} - {} ({})".format(item.get('name', 'Brak nazwy'),
                                          item.get('author', ''),
                                          item.get('version', ''))
            url = item.get('url', '')
            if url:
                lists_menu.append((title, "archive:{}".format(url)))
    except Exception as e:
        print("[MyUpdater] Błąd parsowania manifest:", e)
        return []
    return lists_menu

def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        show_message_compat(session, "Listy kanałów przeładowane.", MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        print("[MyUpdater] Błąd przeładowania:", e)
        show_message_compat(session, "Błąd przeładowania list.", MessageBox.TYPE_ERROR)

# === GŁÓWNE OKNO ===
class Fantastic(Screen):
    skin = """
        <screen position="center,center" size="700,400" title="MyUpdater">
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
            <widget name="menu" position="10,70" size="680,280" scrollbarMode="showOnDemand" />
            <widget name="info" position="10,360" size="680,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
            <widget name="version" position="550,370" size="140,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
        </screen>"""

    def __init__(self, session, args=0):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("MyUpdater")
        menu_list = [("1. Listy kanałów", "menu_lists"),
                     ("2. Instaluj Softcam", "menu_softcam"),
                     ("3. Pobierz Picony Transparent", "picons_github"),
                     ("4. Aktualizacja Wtyczki", "plugin_update"),
                     ("5. Informacja o Wtyczce", "plugin_info")]
        self["menu"] = MenuList(menu_list)
        self["info"] = Label("Wybierz opcję i naciśnij OK")
        self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"],
                                    {"ok": self.runMenuOption,
                                     "back": self.close}, -1)
        prepare_tmp_dir()

    def runMenuOption(self):
        sel = self["menu"].l.getCurrentSelection()
        if not sel:
            return
        key = sel[1]
        if key == "menu_lists":
            self.runChannelListMenu()
        elif key == "menu_softcam":
            self.runSoftcamMenu()
        elif key == "picons_github":
            self.runPiconGitHub()
        elif key == "plugin_update":
            self.runPluginUpdate()
        elif key == "plugin_info":
            self.runInfo()

    def runChannelListMenu(self):
        self["info"].setText("Pobieranie list (GitHub i S4A)...")
        Thread(target=self._background_list_loader).start()

    def _background_list_loader(self):
        repo_lists = _get_lists_from_repo_sync()
        s4a_lists = _get_s4aupdater_lists_dynamic_sync()
        combined = repo_lists + s4a_lists
        reactor.callFromThread(self._onChannelListLoaded, combined)

    def _onChannelListLoaded(self, lists):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not lists:
            show_message_compat(self.session, "Błąd pobierania list. Sprawdź internet.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected,
                                      ChoiceBox,
                                      title="Wybierz listę kanałów do instalacji",
                                      list=lists)

    def runChannelListSelected(self, choice):
        if not choice:
            return
        try:
            title = choice[0]
            url = choice[1].split(":", 1)[1]
            show_message_compat(self.session, "Rozpoczynanie instalacji listy...", timeout=2)
            install_archive(self.session, title, url,
                            callback_on_finish=lambda: reload_settings_python(self.session))
        except Exception as e:
            print("[MyUpdater] Błąd wyboru listy:", e)
            show_message_compat(self.session, "Błąd wyboru listy.", MessageBox.TYPE_ERROR)

    def runSoftcamMenu(self):
        options = [("Oscam (z feedu + fallback Levi45)", "oscam_feed"),
                   ("Oscam (tylko Levi45)", "oscam_levi45"),
                   ("nCam (biko-73)", "ncam_biko")]
        self.session.openWithCallback(self.runSoftcamSelected,
                                      ChoiceBox,
                                      title="Wybierz Softcam do instalacji",
                                      list=options)

    def runSoftcamSelected(self, choice):
        if not choice:
            return
        key, title = choice[1], choice[0]
        cmd = ""
        if key == "oscam_feed":
            cmd = ('echo "Instalacja Oscam z feedu..." && '
                   'wget -O - -q http://updates.mynonpublic.com/oea/feed | bash && '
                   'opkg update && '
                   'PKG=$(opkg list | grep -m1 \'oscam.*ipv4only\' | cut -d" " -f1) && '
                   '[ -n "$PKG" ] && opkg install $PKG || '
                   'wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh')
        elif key == "oscam_levi45":
            cmd = ('wget -q --no-check-certificate '
                   'https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O - | /bin/sh')
        elif key == "ncam_biko":
            cmd = "wget https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O - | /bin/sh"
        if cmd:
            show_message_compat(self.session, "Rozpoczynanie instalacji {}...".format(title), timeout=2)
            console_screen_open(self.session, title, [cmd], close_on_finish=True)

    def runPiconGitHub(self):
        title = "Pobieranie Picon (Transparent)"
        url = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        show_message_compat(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        install_archive(self.session, title, url)

    def runPluginUpdate(self):
        show_message_compat(self.session, "Sprawdzanie dostępności aktualizacji...", timeout=3)
        self["info"].setText("Sprawdzanie wersji online...")
        Thread(target=self._check_version_online).start()

    def _check_version_online(self):
        version_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        installer_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_version = os.path.join(PLUGIN_TMP_PATH, "version.txt")
        online_ver = None
        try:
            subprocess.call(["wget", "--no-check-certificate", "-q", "-T", "10", "-t", "2", "-O", tmp_version, version_url])
            if fileExists(tmp_version) and os.path.getsize(tmp_version) > 0:
                with open(tmp_version, 'r') as f:
                    online_ver = f.read().strip()
        except Exception as e:
            print("[MyUpdater] Błąd pobierania wersji:", e)
        if fileExists(tmp_version):
            os.remove(tmp_version)
        reactor.callFromThread(self._on_version_check_complete, online_ver, installer_url)

    def _on_version_check_complete(self, online_ver, installer_url):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if online_ver and online_ver != VER:
            message = ("Dostępna jest nowa wersja: {}\n"
                       "Twoja wersja: {}\n\n"
                       "Czy chcesz zaktualizować teraz?").format(online_ver, VER)
            self.session.openWithCallback(
                lambda conf: self._doPluginUpdate(installer_url) if conf else None,
                MessageBox, message, type=MessageBox.TYPE_YESNO,
                title="Dostępna aktualizacja")
        else:
            show_message_compat(self.session,
                                "Używasz najnowszej wersji wtyczki ({}).".format(VER),
                                MessageBox.TYPE_INFO)

    def _doPluginUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console_screen_open(self.session, "Aktualizacja MyUpdater", [cmd], close_on_finish=True)

    def runInfo(self):
        info = ("MyUpdater (Mod 2025) {}\n\n"
                "Przebudowa: Paweł Pawełek\n"
                "(msisystem@t.pl)\n\n"
                "Wtyczka bazuje na kodzie PanelAIO.\n\n"
                "Oryginalni twórcy MyUpdater:\n"
                "Sancho, gut").format(VER)
        self.session.open(MessageBox, info, MessageBox.TYPE_INFO)

# === PLUGIN ENTRY ===
def main(session, **kwargs):
    session.open(Fantastic)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater",
                             description="MyUpdater Mod {} (bazuje na PanelAIO)".format(VER),
                             where=PluginDescriptor.WHERE_PLUGINMENU,
                             icon="myupdater.png",
                             fnc=main)]
