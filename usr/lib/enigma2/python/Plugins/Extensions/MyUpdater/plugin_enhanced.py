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
        pass # Ignoruj błędy zapisu logu

def detect_distribution():
    """Detekcja dystrybucji Enigma2"""
    try:
        if os.path.exists("/etc/openatv-release"):
            with open("/etc/openatv-release", 'r') as f: content = f.read().lower()
            if "7." in content: return "openatv7"
            elif "6." in content: return "openatv6"
            return "openatv"
        elif os.path.exists("/etc/openpli-release"): return "openpli"
        elif os.path.exists("/etc/vti-version-info"): return "vix"
        else: return "unknown"
    except Exception as e:
        log("Error detecting distribution: " + str(e))
        return "unknown"

def get_opkg_command():
    """Zwraca poprawną komendę opkg dla danej dystrybucji"""
    distro = detect_distribution()
    if distro == "openpli": return "opkg --force-overwrite --force-downgrade"
    else: return "opkg --force-overwrite"

def msg(session, txt, typ=MessageBox.TYPE_INFO, timeout=6):
    log("Msg: " + txt)
    reactor.callLater(0.05, lambda: session.open(MessageBox, txt, typ, timeout=timeout))

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
    if not os.path.exists(PLUGIN_TMP_PATH):
        try: os.makedirs(PLUGIN_TMP_PATH)
        except OSError as e: log("Error creating tmpdir: " + str(e))


def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist(); db.reloadBouquets()
        msg(session, "Listy kanałów przeładowane.", timeout=3)
    except Exception as e:
        log("[MyUpdater] Błąd podczas przeładowywania list: " + str(e))
        msg(session, "Wystąpił błąd podczas przeładowywania list.", MessageBox.TYPE_ERROR)

#
# *** FUNKCJA Z OSTATNIĄ POPRAWKĄ (OKOLICE LINII 121) ***
#
def install_archive_enhanced(session, title, url, finish=None):
    """Poprawiona wersja instalacji archiwum"""
    log("install_archive_enhanced: " + url)
    archive_type = ""
    if url.endswith(".zip"):
        archive_type = "zip"
    elif url.endswith((".tar.gz", ".tgz")):
        archive_type = "tar.gz"
    else:
        msg(session, "Nieobsługiwany format archiwum!", MessageBox.TYPE_ERROR)
        if finish:
            try: finish()
            except Exception as e: log("Error in finish callback (unsupported format): " + str(e))
        return

    tmpdir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    cmd_chain = []

    # Backup tylko dla list kanałów
    if "picon" not in title.lower():
        backup_cmd = "tar -czf /tmp/MyUpdater/backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /etc/enigma2 lamedb *.tv *.radio 2>/dev/null || true"
        cmd_chain.append(backup_cmd)

    # Pobieranie zawsze
    download_cmd = 'wget --no-check-certificate --timeout=30 -t 2 -O "{}" "{}"'.format(tmp_archive_path, url)
    cmd_chain.append(download_cmd)

    callback = finish # Domyślny callback

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
            "echo '>>> Picony zainstalowane.' && sleep 0.5"
        ])
        # Callback 'finish' (przekazany z runPiconGitHub) zostaje użyty bez zmian
    
    else: # Logika dla list kanałów
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        # --- Sprawdzenie istnienia skryptu ---
        if not os.path.exists(install_script_path):
            msg(session, "BŁĄD: Brak pliku install_archive_script.sh!", MessageBox.TYPE_ERROR)
            log("FATAL: install_archive_script.sh not found at " + install_script_path)
            # Bezpieczne wywołanie finish, jeśli istnieje
            if finish:
                try:
                    finish()
                except Exception as e:
                    # Logowanie błędu w callbacku, linia ~121
                    log("Error in finish callback (missing script): " + str(e))
            return # Zakończ funkcję, jeśli brakuje skryptu
        # --- Koniec sprawdzenia ---
            
        # Dodaj polecenia, jeśli skrypt istnieje
        cmd_chain.extend([
            "chmod +x \"{}\"".format(install_script_path),
            "bash {} \"{}\" \"{}\"".format(install_script_path, tmp_archive_path, archive_type)
        ])
        
        # Definicja callbacku dla list kanałów
        def combined_callback():
            reload_settings_python(session) # Ta funkcja użyje msg()
            if finish:
                reactor.callLater(0.3, finish) # Wywołaj oryginalny finish z opóźnieniem
        
        callback = combined_callback # Nadpisz domyślny callback

    # Połącz i wykonaj polecenia
    full_command = " && ".join(filter(None, cmd_chain))
    console(session, title, [full_command], onClose=callback, autoClose=True)

def install_oscam_enhanced(session, finish=None):
    distro = detect_distribution()
    def install_callback():
        msg(session, "Instalacja Oscam zakończona (lub próba). Sprawdź logi.", timeout=4)
        if finish: try: finish(); except Exception as e: log("Error in Oscam finish callback: "+str(e))
    commands = ["echo '>>> Aktualizacja feed...' && opkg update"]
    if distro == "openpli":
        commands.append("echo '>>> Szukanie oscam w feed (OpenPLI)...' && {} install enigma2-plugin-softcams-oscam 2>/dev/null || echo 'Nie znaleziono'".format(get_opkg_command()))
        commands.append("echo '>>> Próba instalacji z innego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh")
    else:
        commands.append("echo '>>> Szukanie oscam w feed...' && PKG=$(opkg list | grep 'oscam.*ipv4only' | grep -E -m1 'master|emu|stable' | cut -d' ' -f1) && if [ -n \"$PKG\" ]; then echo 'Instaluję: $PKG'; {} install $PKG; else echo 'Nie znaleziono, używam innego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh; fi".format(get_opkg_command()))
    commands.append("echo '>>> Weryfikacja...' && if [ -f /usr/bin/oscam ] || [ -f /usr/bin/oscam-emu ]; then echo 'Oscam OK!'; else echo 'Uwaga: Brak pliku oscam'; fi")
    console(session, "Instalacja Oscam", commands, onClose=install_callback, autoClose=True)

def get_repo_lists():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"; tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json"); lst = []
    try:
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "10", "-O", tmp, url], stderr=subprocess.STDOUT)
        with io.open(tmp, 'r', encoding='utf-8') as f: data = json.load(f)
        for i in data:
            if i.get('url'): lst.append(("{} - {} ({})".format(i.get('name','?'), i.get('author','?'), i.get('version','?')), "archive:{}".format(i['url'])))
    except subprocess.CalledProcessError as e: log("Błąd subprocess (repo lists): " + e.output.decode('utf-8', errors='ignore'))
    except Exception as e: log("Błąd pobierania repo lists: " + str(e))
    if fileExists(tmp): try: os.remove(tmp); except Exception as e: log("Error removing tmp manifest: "+str(e))
    return lst

def get_s4a_lists():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"; tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt"); lst = []
    try:
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "10", "-O", tmp, url], stderr=subprocess.STDOUT)
        urls, vers = {}, {};
        with io.open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
            for l in f:
                l = l.strip()
                if "_url:" in l: k, v = l.split(':', 1); urls[k.strip()] = v.strip()
                elif "_version:" in l: k, v = l.split(':', 1); vers[k.strip()] = v.strip()
        for k, u in urls.items():
            name = k.replace('_url', '').replace('_', ' ').title()
            ver = vers.get(k.replace('_url', '_version'), "?")
            lst.append(("{} - {}".format(name, ver), "archive:{}".format(u)))
    except subprocess.CalledProcessError as e: log("Błąd subprocess (s4a lists): " + e.output.decode('utf-8', errors='ignore'))
    except Exception as e: log("Błąd pobierania s4a lists: " + str(e))
    if fileExists(tmp): try: os.remove(tmp); except Exception as e: log("Error removing tmp s4a list: "+str(e))
    return [i for i in lst if not any(x in i[0].lower() for x in ['bzyk', 'jakitaki'])]

class MyUpdaterEnhanced(Screen):
    skin = """<screen position="center,center" size="720,450" title="MyUpdater Enhanced V5">
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
        <widget name="menu" position="10,70" size="700,330" scrollbarMode="showOnDemand" />
        <widget name="info" position="10,410" size="700,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
        <widget name="version" position="580,420" size="130,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
    </screen>"""

    def __init__(self, session, args=0):
        Screen.__init__(self, session)
        self.session = session; self.setTitle("MyUpdater Enhanced V5")
        self.distro = detect_distribution()
        self.channel_lists = []; self.fetching_lists = False
        self["menu"] = MenuList([
            ("1. Listy kanałów", "menu_lists"), ("2. Instaluj Softcam", "menu_softcam"),
            ("3. Pobierz Picony", "picons_github"), ("4. Aktualizacja Wtyczki", "plugin_update"),
            ("5. Informacja", "plugin_info"), ("6. Diagnostyka", "system_diagnostic")
        ])
        self["info"] = Label("Wybierz opcję"); self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"], {"ok": self.runMenuOption, "back": self.close}, -1)
        self["menu"].onSelectionChanged.append(self.updateInfoLabel)
        tmpdir()
        if fileExists(LOG_FILE): try: os.remove(LOG_FILE); except Exception as e: log("Error removing old log: "+str(e))
        log(u"MyUpdater Enhanced {} started on {}".format(VER, self.distro))
        self.preloadChannelLists(); self.updateInfoLabel()

    def preloadChannelLists(self):
        if not self.fetching_lists:
             self.fetching_lists = True; self["info"].setText("Pobieram listy kanałów w tle...")
             Thread(target=self._bgPreloadLists).start()

    def _bgPreloadLists(self):
        log("Preloading channel lists..."); repo = get_repo_lists(); s4a = get_s4a_lists()
        all_lists = repo + s4a; log("Finished preloading {} lists.".format(len(all_lists)))
        reactor.callFromThread(self._onPreloadFinished, all_lists)

    def _onPreloadFinished(self, lst):
        self.channel_lists = lst; self.fetching_lists = False; self.updateInfoLabel()
        if not lst: log("Preloading failed or no lists found.")

    def updateInfoLabel(self):
        if self.fetching_lists: self["info"].setText("Pobieram listy kanałów w tle..."); return
        selection = self["menu"].getCurrent(); key = selection[1] if selection else None
        descriptions = {
            "menu_lists": "Pobierz i zainstaluj listy kanałów.", "menu_softcam": "Zainstaluj lub usuń Oscam/nCam.",
            "picons_github": "Pobierz zestaw picon transparent.", "plugin_update": "Sprawdź i zainstaluj aktualizacje.",
            "plugin_info": "Wyświetl informacje o tej wtyczce.", "system_diagnostic": "Sprawdź informacje o systemie."
        }
        self["info"].setText(descriptions.get(key, "Wybierz opcję i naciśnij OK"))

    def runMenuOption(self):
        sel = self["menu"].getCurrent();
        if not sel: return
        key = sel[1]; log("Menu: " + key); self["info"].setText("Pracuję...")
        reactor.callLater(0.05, self._delegateMenuOption, key)

    def _delegateMenuOption(self, key):
        action_map = {"menu_lists": self.runChannelListMenu, "menu_softcam": self.runSoftcamMenu,"picons_github": self.runPiconGitHub, "plugin_update": self.runPluginUpdate,"plugin_info": self.runInfo, "system_diagnostic": self.runDiagnostic}
        action = action_map.get(key)
        if action: action()

    def runChannelListMenu(self):
        if self.fetching_lists: msg(self.session, "Listy są jeszcze pobierane. Spróbuj za chwilę.", MessageBox.TYPE_INFO, timeout=4); self.updateInfoLabel(); return
        if not self.channel_lists: msg(self.session, "Brak list lub błąd pobierania. Sprawdź logi.", MessageBox.TYPE_ERROR); self.updateInfoLabel(); return
        self.session.openWithCallback(self.runChannelListSelected, ChoiceBox, title="Wybierz listę", list=self.channel_lists, cancelCallback=self.updateInfoLabel)

    def runChannelListSelected(self, choice):
        if not choice: self.updateInfoLabel(); return
        title, url_part = choice; url = url_part.split(":",1)[1]
        log("Selected: {} | {}".format(title, url)); msg(self.session, "Instaluję:\n'{}'...".format(title), timeout=3)
        # Używamy msg() w callbacku finish
        install_archive_enhanced(self.session, title, url, finish=lambda: msg(self.session, "Instalacja '{}' zakończona.".format(title), timeout=3))

    def runSoftcamMenu(self):
        opts = [("Oscam (auto)", "oscam_auto"), ("Oscam (Levi45)", "oscam_levi45"),("nCam (biko-73)", "ncam_biko"), ("Usuń softcamy", "remove_softcam")]
        self.session.openWithCallback(self.runSoftcamSelected, ChoiceBox, title="Softcam", list=opts, cancelCallback=self.updateInfoLabel)

    def runSoftcamSelected(self, choice):
        if not choice: self.updateInfoLabel(); return
        key, title = choice[1], choice[0]
        msg(self.session, "Akcja: '{}'...".format(title), timeout=2)
        def final_callback(message): msg(self.session, message, timeout=4); self.updateInfoLabel()
        action_map = {
            "oscam_auto": lambda: install_oscam_enhanced(self.session, finish=lambda: self.updateInfoLabel()), # install_oscam_enhanced ma swój callback msg
            "oscam_levi45": lambda: console(self.session, title, ["wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh"], onClose=lambda: final_callback("Instalacja '{}' zakończona.".format(title)), autoClose=True),
            "ncam_biko": lambda: console(self.session, title, ["wget -q https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O- | sh"], onClose=lambda: final_callback("Instalacja '{}' zakończona.".format(title)), autoClose=True),
            "remove_softcam": lambda: console(self.session, "Usuwanie softcamów", ["echo '>>> Usuwanie...'", "opkg remove --force-removal-of-dependent-packages enigma2-plugin-softcams-* 2>/dev/null || true", "rm -f /usr/bin/oscam* /usr/bin/ncam* 2>/dev/null || true", "echo '>>> Zakończono.'"], onClose=lambda: final_callback("Softcamy usunięte."), autoClose=True)
        }
        action = action_map.get(key);
        if action: action()
        else: self.updateInfoLabel()

    def runPiconGitHub(self):
        url = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"; title = "Pobieranie Picon (Transparent)"
        log("Picons: " + url); msg(self.session, "Pobieram picony...", timeout=2)
        # Używamy msg() w callbacku finish
        install_archive_enhanced(self.session, title, url, finish=lambda: msg(self.session, "Picony gotowe.", timeout=3))

    def runPluginUpdate(self):
        self["info"].setText("Sprawdzam wersję online...")
        Thread(target=self._bgUpdate).start()

    def _bgUpdate(self):
        ver_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"; inst_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_ver = os.path.join(PLUGIN_TMP_PATH, "version.txt"); online = None
        try:
            subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "10", "-O", tmp_ver, ver_url], stderr=subprocess.STDOUT)
            with io.open(tmp_ver, 'r', encoding='utf-8') as f: online = f.read().strip()
        except subprocess.CalledProcessError as e: log("Błąd subprocess (update check): " + e.output.decode('utf-8', errors='ignore'))
        except Exception as e: log("Błąd sprawdzania wersji: " + str(e))
        if fileExists(tmp_ver): try: os.remove(tmp_ver); except Exception as e: log("Error removing tmp version file: "+str(e))
        reactor.callFromThread(self._onUpdate, online, inst_url)

    def _onUpdate(self, online, inst_url):
        self.updateInfoLabel()
        if not online: msg(self.session, "Błąd sprawdzania wersji. Sprawdź logi.", MessageBox.TYPE_ERROR); return
        if online and online != VER and online.strip():
            txt = "Nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else self.updateInfoLabel(), MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else: msg(self.session, "Masz najnowszą wersję ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: msg(self.session, "Aktualizacja zakończona.\nRestart GUI może być potrzebny.", timeout=5), autoClose=True)

    def runInfo(self):
        txt = (u"MyUpdater Enhanced {}\n\n"
               u"Kompatybilność: OpenATV/OpenPLI/ViX\n"
               u"Autorzy: Paweł Pawełek (bazując na 3.11 Sancho)\n\n"
               u"System: {}\n"
               u"Komenda opkg: {}").format(VER, self.distro, get_opkg_command())
        self.session.openWithCallback(lambda *args: self.updateInfoLabel(), MessageBox, txt, MessageBox.TYPE_INFO)

    def runDiagnostic(self):
        commands = [
            "echo '=== Diagnostyka Systemu ==='", "echo \"Data: $(date)\"",
            "echo \"System: {}\"".format(self.distro),
            "echo \"Wersja Enigma2: $(opkg list-installed | grep enigma2 | head -1 2>/dev/null || echo 'Nieznana')\"",
            "echo \"\"", "echo \"Dostępne softcamy (max 3):\"",
            "opkg list | grep -i 'oscam\|ncam' | head -3 2>/dev/null || echo \" - Brak softcamów w feed\"",
            "echo \"\"", "echo \"Przestrzeń dyskowa (/):\"", "df -h / | tail -1", "echo \"\"",
            "ping -c 1 8.8.8.8 >/dev/null && echo \"Internet: OK\" || echo \"Internet: BRAK\"",
            "echo \"\"", "echo '=== Koniec ==='", "echo 'Naciśnij EXIT...' "
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
