# -*- coding: utf-8 -*-
#  MyUpdater Enhanced V5 – Kompletna przebudowa z pełną kompatybilnością
#  Plik na GitHub jako: plugin_enhanced.py
from __future__ import print_function, absolute_import
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

import io
import os, subprocess, json, datetime, traceback, re, weakref
from twisted.internet import reactor
from threading import Thread

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V5 Enhanced" # Wersja wewnętrzna nadal może być szczegółowa
LOG_FILE = "/tmp/MyUpdater_install.log"

def log(msg):
    try:
        with io.open(LOG_FILE, "a", encoding='utf-8') as f:
            f.write(u"{} - {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except:
        pass

def detect_distribution():
    """Detekcja dystrybucji Enigma2"""
    try:
        if os.path.exists("/etc/openatv-release"):
            with open("/etc/openatv-release", 'r') as f:
                content = f.read().lower()
                if "7." in content: return "openatv7"
                elif "6." in content: return "openatv6"
                return "openatv"
        elif os.path.exists("/etc/openpli-release"): return "openpli"
        elif os.path.exists("/etc/vti-version-info"): return "vix"
        else: return "unknown"
    except: return "unknown"

def get_opkg_command():
    """Zwraca poprawną komendę opkg dla danej dystrybucji"""
    distro = detect_distribution()
    if distro == "openpli": return "opkg --force-overwrite --force-downgrade"
    else: return "opkg --force-overwrite"

def msg(session, txt, typ=MessageBox.TYPE_INFO, timeout=3):
    # Skrócono domyślny timeout i usunięto zbędne opóźnienie wywołania
    log("Msg: " + txt)
    reactor.callLater(0, lambda: session.open(MessageBox, txt, typ, timeout=timeout))

def console(session, title, cmdlist, onClose, autoClose=True):
    log("Console: {} | {}".format(title, " ; ".join(cmdlist)))
    try:
        c = session.open(Console, title=title, cmdlist=cmdlist, closeOnSuccess=autoClose)
        if onClose: c.onClose.append(onClose)
    except Exception as e:
        log("Console exception: " + str(e))
        if onClose:
            try: onClose()
            except Exception as call_e: log("Exception in onClose callback after console error: " + str(call_e))

def tmpdir():
    if not os.path.exists(PLUGIN_TMP_PATH): os.makedirs(PLUGIN_TMP_PATH)

def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        msg(session, "Listy kanałów przeładowane.", timeout=2)
    except Exception as e:
        log("[MyUpdater] Błąd podczas przeładowywania list: " + str(e))
        msg(session, "Wystąpił błąd podczas przeładowywania list.", MessageBox.TYPE_ERROR)

def install_archive_enhanced(session, title, url, finish=None):
    """Poprawiona wersja instalacji archiwum"""
    log("install_archive_enhanced: " + url)
    
    archive_type = ""
    if url.endswith(".zip"): archive_type = "zip"
    elif url.endswith((".tar.gz", ".tgz")): archive_type = "tar.gz"
    else:
        msg(session, "Nieobsługiwany format archiwum!", MessageBox.TYPE_ERROR)
        if finish: finish()
        return

    tmpdir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    
    cmd_chain = []
    
    if "picon" not in title.lower():
        backup_cmd = "tar -czf /tmp/MyUpdater/backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /etc/enigma2 lamedb *.tv *.radio 2>/dev/null || true"
        cmd_chain.append(backup_cmd)

    # Szybsze time-outy i mniej prób, by nie blokować startu
    download_cmd = 'wget --no-check-certificate --timeout=8 -t 1 -O "{}" "{}"'.format(tmp_archive_path, url)
    cmd_chain.append(download_cmd)
    
    callback = finish
    
    if "picon" in title.lower() and archive_type == "zip":
        picon_path = "/usr/share/enigma2/picon"
        tmp_extract_path = "/tmp/MyUpdater_picon_extract"
        
        cmd_chain.extend([
            "rm -rf " + tmp_extract_path,
            "mkdir -p " + tmp_extract_path,
            "unzip -o -q \"" + tmp_archive_path + "\" -d \"" + tmp_extract_path + "\"",
            "mkdir -p " + picon_path,
            ("if [ -d \"" + tmp_extract_path + "/picon\" ]; then "
             "mv -f \"" + tmp_extract_path + "/picon\"/* \"" + picon_path + "/\" 2>/dev/null || true; "
             "else "
             "mv -f \"" + tmp_extract_path + "\"/* \"" + picon_path + "/\" 2>/dev/null || true; "
             "fi"),
            "rm -rf " + tmp_extract_path,
            "rm -f \"" + tmp_archive_path + "\"",
            "echo '>>> Picony zostały pomyślnie zainstalowane.'"
        ])
    
    else: # Logika dla list kanałów
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        if not os.path.exists(install_script_path):
             msg(session, "BŁĄD: Brak pliku install_archive_script.sh!", MessageBox.TYPE_ERROR)
             if finish:
                 try: finish()
                 except: pass
             return
        
        cmd_chain.extend([
            "chmod +x \"{}\"".format(install_script_path),
            "bash {} \"{}\" \"{}\"".format(install_script_path, tmp_archive_path, archive_type)
        ])
        
        def combined_callback():
            reload_settings_python(session)
            if finish: reactor.callLater(0, finish)
        
        callback = combined_callback
    
    full_command = " && ".join(filter(None, cmd_chain))
    console(session, title, [full_command], onClose=callback, autoClose=True)

def install_oscam_enhanced(session, finish=None):
    """Inteligentna instalacja oscam z wieloma fallback"""
    distro = detect_distribution()
    
    def install_callback():
        msg(session, "Instalacja Oscam zakończona (lub próba zakończona). Sprawdź logi.", timeout=3)
        if finish:
            try: finish()
            except: pass

    # Szybszy update feed (jeśli sieć wolna, nie blokuje długo)
    commands = ["echo '>>> Aktualizacja feed...' && opkg update"]
    if distro == "openpli":
        commands.append("echo '>>> Szukanie oscam w feed (OpenPLI)...' && {} install enigma2-plugin-softcams-oscam 2>/dev/null || echo 'Nie znaleziono w feed'".format(get_opkg_command()))
        commands.append("echo '>>> Próba instalacji alternatywnego źródła...' && wget -q --no-check-certificate --timeout=8 -t 1 https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh")
    else:
        commands.append("echo '>>> Szukanie oscam w feed...' && PKG=$(opkg list | grep 'oscam.*ipv4only' | grep -E -m1 'master|emu|stable' | cut -d' ' -f1) && if [ -n \"$PKG\" ]; then echo 'Znaleziono pakiet: $PKG' && {} install $PKG; else echo 'Nie znaleziono w feed, używam alternatywnego źródła...' && wget -q --no-check-certificate --timeout=8 -t 1 https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh; fi".format(get_opkg_command()))
    commands.append("echo '>>> Weryfikacja instalacji...' && if [ -f /usr/bin/oscam ] || [ -f /usr/bin/oscam-emu ]; then echo 'Oscam został pomyślnie zainstalowany!'; else echo 'Uwaga: Plik oscam nie został znaleziony, sprawdź logi'; fi")
    console(session, "Instalacja Oscam", commands, onClose=install_callback, autoClose=True)

def get_repo_lists():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    lst = []
    try:
        # Szybszy timeout pobierania listy
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "6", "-O", tmp, url], stderr=subprocess.STDOUT)
        with io.open(tmp, 'r', encoding='utf-8') as f: data = json.load(f)
        for i in data:
            if i.get('url'): lst.append(("{} - {} ({})".format(i.get('name',''), i.get('author',''), i.get('version','')), "archive:{}".format(i['url'])))
    except subprocess.CalledProcessError as e: log("Błąd subprocess przy pobieraniu repo lists: " + e.output.decode('utf-8', errors='ignore'))
    except Exception as e: log("Błąd pobierania repo lists: " + str(e))
    return lst

def get_s4a_lists():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"
    tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt")
    lst = []
    try:
        # Szybszy timeout pobierania listy
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "6", "-O", tmp, url], stderr=subprocess.STDOUT)
        urls, vers = {}, {}
        with io.open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
            for l in f:
                l = l.strip()
                if "_url:" in l: k, v = l.split(':', 1); urls[k.strip()] = v.strip()
                elif "_version:" in l: k, v = l.split(':', 1); vers[k.strip()] = v.strip()
        for k, u in urls.items():
            name = k.replace('_url', '').replace('_', ' ').title()
            ver = vers.get(k.replace('_url', '_version'), "brak daty")
            lst.append(("{} - {}".format(name, ver), "archive:{}".format(u)))
    except subprocess.CalledProcessError as e: log("Błąd subprocess przy pobieraniu s4a lists: " + e.output.decode('utf-8', errors='ignore'))
    except Exception as e: log("Błąd pobierania s4a lists: " + str(e))
    return [i for i in lst if not any(x in i[0].lower() for x in ['bzyk', 'jakitaki'])]

class MyUpdaterEnhanced(Screen):
    skin = """<screen position="center,center" size="720,450" title="MyUpdater Enhanced">
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
        <widget name="menu" position="10,70" size="700,330" scrollbarMode="showOnDemand" />
        <widget name="info" position="10,410" size="700,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
        <widget name="version" position="580,420" size="130,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
    </screen>"""

    def __init__(self, session, args=0):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("MyUpdater Enhanced V5") # Tytuł okna może być dłuższy
        self.distro = detect_distribution()
        
        self["menu"] = MenuList([
            ("1. Listy kanałów", "menu_lists"),
            ("2. Instaluj Softcam (Oscam/nCam)", "menu_softcam"),
            ("3. Pobierz Picony Transparent", "picons_github"),
            ("4. Aktualizacja Wtyczki", "plugin_update"),
            ("5. Informacja o Wtyczce", "plugin_info"),
            ("6. Diagnostyka Systemu", "system_diagnostic")
        ])
        
        self["info"] = Label("Wybierz opcję")
        self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"], {"ok": self.runMenuOption, "back": self.close}, -1)
        self["menu"].onSelectionChanged.append(self.updateInfoLabel)
        self.updateInfoLabel()
        tmpdir()
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        log(u"MyUpdater Enhanced {} started on {}".format(VER, self.distro))

    def updateInfoLabel(self):
        selection = self["menu"].getCurrent()
        key = selection[1] if selection else None
        descriptions = {
            "menu_lists": "Pobierz i zainstaluj listy kanałów.",
            "menu_softcam": "Zainstaluj lub usuń Oscam/nCam.",
            "picons_github": "Pobierz zestaw picon transparent.",
            "plugin_update": "Sprawdź i zainstaluj aktualizacje wtyczki.",
            "plugin_info": "Wyświetl informacje o tej wtyczce.",
            "system_diagnostic": "Sprawdź podstawowe informacje o systemie."
        }
        self["info"].setText(descriptions.get(key, "Wybierz opcję i naciśnij OK"))

    def runMenuOption(self):
        sel = self["menu"].getCurrent()
        if not sel: return
        key = sel[1]
        log("Menu: " + key)
        self["info"].setText("Pracuję...")
        # Natychmiastowe delegowanie bez opóźnienia
        reactor.callLater(0, self._delegateMenuOption, key)

    def _delegateMenuOption(self, key):
        action_map = {
            "menu_lists": self.runChannelListMenu,
            "menu_softcam": self.runSoftcamMenu,
            "picons_github": self.runPiconGitHub,
            "plugin_update": self.runPluginUpdate,
            "plugin_info": self.runInfo,
            "system_diagnostic": self.runDiagnostic
        }
        action = action_map.get(key)
        if action:
            action()
            if key in ["plugin_info"]:
                 pass
            elif key not in ["system_diagnostic"]:
                 pass
        else:
             self.updateInfoLabel() # Jeśli nieznana akcja, przywróć opis

    def runChannelListMenu(self):
        self["info"].setText("Pobieram listy...")
        Thread(target=self._bgLists).start()

    def _bgLists(self):
        repo = get_repo_lists(); s4a = get_s4a_lists()
        reactor.callFromThread(self._onLists, repo + s4a)

    def _onLists(self, lst):
        self.updateInfoLabel()
        if not lst: msg(self.session, "Błąd pobierania list. Sprawdź połączenie lub logi.", MessageBox.TYPE_ERROR); return
        self.session.openWithCallback(self.runChannelListSelected, ChoiceBox, title="Wybierz listę do instalacji", list=lst, cancelCallback=self.updateInfoLabel)

    def runChannelListSelected(self, choice):
        if not choice: self.updateInfoLabel(); return
        title, url_part = choice; url = url_part.split(":",1)[1]
        log("Selected: {} | {}".format(title, url))
        msg(self.session, "Rozpoczynam instalację:\n'{}'...".format(title), timeout=1)
        install_archive_enhanced(self.session, title, url, finish=lambda: msg(self.session, "Instalacja '{}' zakończona.".format(title), timeout=2))

    def runSoftcamMenu(self):
        opts = [("Oscam (auto-detekcja)", "oscam_auto"), ("Oscam (Levi45)", "oscam_levi45"),
                ("nCam (biko-73)", "ncam_biko"), ("Usuń softcamy", "remove_softcam")]
        self.session.openWithCallback(self.runSoftcamSelected, ChoiceBox, title="Softcam – wybierz", list=opts, cancelCallback=self.updateInfoLabel)

    def runSoftcamSelected(self, choice):
        if not choice: self.updateInfoLabel(); return
        key, title = choice[1], choice[0]
        msg(self.session, "Rozpoczynam akcję: '{}'...".format(title), timeout=1)
        
        def final_callback(message):
            msg(self.session, message, timeout=3)
            self.updateInfoLabel()

        action_map = {
            "oscam_auto": lambda: install_oscam_enhanced(self.session, finish=lambda: self.updateInfoLabel()),
            "oscam_levi45": lambda: console(self.session, title, ["wget -q --no-check-certificate --timeout=8 -t 1 https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh"], onClose=lambda: final_callback("Instalacja '{}' zakończona (lub próba).".format(title)), autoClose=True),
            "ncam_biko": lambda: console(self.session, title, ["wget -q --timeout=8 -t 1 https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O- | sh"], onClose=lambda: final_callback("Instalacja '{}' zakończona (lub próba).".format(title)), autoClose=True),
            "remove_softcam": lambda: console(self.session, "Usuwanie softcamów", ["echo '>>> Usuwanie...'", "opkg remove --force-removal-of-dependent-packages enigma2-plugin-softcams-* 2>/dev/null || true", "rm -f /usr/bin/oscam* /usr/bin/ncam* 2>/dev/null || true", "echo '>>> Zakończono.'"], onClose=lambda: final_callback("Softcamy usunięte (lub próba)."), autoClose=True)
        }
        action = action_map.get(key)
        if action: action()
        else: self.updateInfoLabel() # Przywróć, jeśli nieznana akcja

    def runPiconGitHub(self):
        url = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        title = "Pobieranie Picon (Transparent)"
        log("Picons: " + url)
        msg(self.session, "Rozpoczynam pobieranie picon...", timeout=1)
        install_archive_enhanced(self.session, title, url, finish=lambda: msg(self.session, "Picony gotowe.", timeout=2))

    def runPluginUpdate(self):
        self["info"].setText("Sprawdzam wersję online...")
        Thread(target=self._bgUpdate).start()

    def _bgUpdate(self):
        ver_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        inst_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_ver = os.path.join(PLUGIN_TMP_PATH, "version.txt"); online = None
        try:
            subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "5", "-O", tmp_ver, ver_url], stderr=subprocess.STDOUT)
            with io.open(tmp_ver, 'r', encoding='utf-8') as f: online = f.read().strip()
        except subprocess.CalledProcessError as e: log("Błąd subprocess przy sprawdzaniu wersji: " + e.output.decode('utf-8', errors='ignore'))
        except Exception as e: log("Błąd sprawdzania wersji: " + str(e))
        if fileExists(tmp_ver):
            try: os.remove(tmp_ver)
            except: pass
        reactor.callFromThread(self._onUpdate, online, inst_url)

    def _onUpdate(self, online, inst_url):
        self.updateInfoLabel()
        if not online: msg(self.session, "Nie udało się sprawdzić wersji. Sprawdź połączenie lub logi.", MessageBox.TYPE_ERROR); return
        if online and online != VER and online.strip():
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else self.updateInfoLabel(), MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else: msg(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: msg(self.session, "Aktualizacja zakończona (lub próba).\nRestart GUI może być potrzebny.", timeout=4), autoClose=True)

    def runInfo(self):
        txt = (u"MyUpdater Enhanced {}\n\n"
               u"Kompatybilność: OpenATV 6.4-7.6, OpenPLI, ViX\n"
               u"Autorzy: Paweł Pawełek, przebudowa na bazie 3.11 Sancho\n\n"
               u"System: {}\n"
               u"Komenda opkg: {}").format(VER, self.distro, get_opkg_command())
        self.session.openWithCallback(lambda *args: self.updateInfoLabel(), MessageBox, txt, MessageBox.TYPE_INFO)

    def runDiagnostic(self):
        commands = [
            "echo '=== Diagnostyka Systemu ==='", "echo \"Data: $(date)\"",
            "echo \"System: {}\"".format(self.distro),
            "echo \"Wersja Enigma2: $(opkg list-installed | grep enigma2 | head -1 2>/dev/null || echo 'Nieznana')\"",
            "echo \"\"", "echo \"Dostępne softcamy (max 3):\"",
            "opkg list | grep -i 'oscam\\|ncam' | head -3 2>/dev/null || echo \" - Brak softcamów w feed\"",
            "echo \"\"", "echo \"Przestrzeń dyskowa (/):\"", "df -h / | tail -1", "echo \"\"",
            "ping -c 1 8.8.8.8 >/dev/null && echo \"Połączenie internetowe: OK\" || echo \"Połączenie internetowe: BRAK\"",
            "echo \"\"", "echo '=== Koniec diagnostyki ==='", "echo 'Naciśnij EXIT aby zamknąć...' "
        ]
        console(self.session, "Diagnostyka Systemu", commands, onClose=self.updateInfoLabel, autoClose=False)

def main(session, **kwargs):
    session.open(MyUpdaterEnhanced)

#
# *** ZMIENIONA NAZWA I OPIS WTYCZKI ***
#
def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater V5", # <-- NOWA NAZWA
                            description="Aktualizator list, picon i softcamów", # <-- NOWY OPIS
                            where=PluginDescriptor.WHERE_PLUGINMENU,
                            icon="myupdater.png", fnc=main)]
