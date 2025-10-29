# -*- coding: utf-8 -*-
#  MyUpdater Enhanced V5 – Kompletna przebudowa z pełną kompatybilnością
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
import os, subprocess, json, datetime, traceback, re
from twisted.internet import reactor
from threading import Thread

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V5 Enhanced"
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
                if "7." in content:
                    return "openatv7"
                elif "6." in content:
                    return "openatv6"
                return "openatv"
        elif os.path.exists("/etc/openpli-release"):
            return "openpli"
        elif os.path.exists("/etc/vti-version-info"):
            return "vix"
        else:
            return "unknown"
    except:
        return "unknown"

def get_opkg_command():
    """Zwraca poprawną komendę opkg dla danej dystrybucji"""
    distro = detect_distribution()
    if distro == "openpli":
        return "opkg --force-overwrite --force-downgrade"
    else:
        return "opkg --force-overwrite"

def msg(session, txt, typ=MessageBox.TYPE_INFO, timeout=6):
    log("Msg: " + txt)
    reactor.callLater(0.2, lambda: session.open(MessageBox, txt, typ, timeout=timeout))

def console(session, title, cmdlist, onClose, autoClose=True):
    log("Console: {} | {}".format(title, " ; ".join(cmdlist)))
    try:
        c = session.open(Console, title=title, cmdlist=cmdlist, closeOnSuccess=autoClose)
        c.onClose.append(onClose)
    except Exception as e:
        log("Console exception: " + str(e))
        onClose()

def tmpdir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        os.makedirs(PLUGIN_TMP_PATH)

def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        msg(session, "Listy kanałów przeładowane.", timeout=3)
    except Exception as e:
        log("[MyUpdater] Błąd podczas przeładowywania list: " + str(e))
        msg(session, "Wystąpił błąd podczas przeładowywania list.", MessageBox.TYPE_ERROR)

#
# *** FUNKCJA POPRAWIONA (INSTALACJA PICON) ***
#
def install_archive_enhanced(session, title, url, finish=None):
    log("install_archive_enhanced: " + url)
    
    if url.endswith(".zip"):
        archive_type = "zip"
    elif url.endswith((".tar.gz", ".tgz")):
        archive_type = "tar.gz"
    else:
        msg(session, "Nieobsługiwany format archiwum!", MessageBox.TYPE_ERROR)
        if finish: finish()
        return

    tmpdir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    
    # Backup starych list kanałów
    backup_cmd = ""
    if "picon" not in title.lower():
        backup_cmd = "tar -czf /tmp/MyUpdater/backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /etc/enigma2 lamedb *.tv *.radio 2>/dev/null || true"
    
    download_cmd = 'wget --no-check-certificate --timeout=30 -t 2 -O "{}" "{}"'.format(tmp_archive_path, url)
    
    if "picon" in title.lower() and archive_type == "zip":
        picon_path = "/usr/share/enigma2/picon"
        nested_picon_path = os.path.join(picon_path, "picon")
        
        # *** POPRAWKA LITERÓWKI PONIŻEJ (było "{\"/*" zamiast "\"{}\"/*") ***
        full_command = (
            "{} && " +
            "{} && " +
            "mkdir -p {} && " +
            "unzip -o -q \"{}\" -d \"{}\" && " +
            "if [ -d \"{}\" ]; then mv -f \"{}\"/* \"{}\"/; rmdir \"{}\"; fi && " +
            "rm -f \"{}\" && " +
            "echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 2"
        ).format(
            backup_cmd,
            download_cmd,
            picon_path,
            tmp_archive_path,
            picon_path,
            nested_picon_path,
            nested_picon_path, # Poprawiony argument
            picon_path,
            nested_picon_path,
            tmp_archive_path
        )
        console(session, title, [full_command], onClose=finish, autoClose=True)
    
    else:
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        
        if not os.path.exists(install_script_path):
             msg(session, "BŁĄD: Brak pliku install_archive_script.sh!", MessageBox.TYPE_ERROR)
             if finish: finish()
             return
        
        chmod_cmd = "chmod +x \"{}\"".format(install_script_path)
        
        full_command = "{} && {} && {} && bash {} \"{}\" \"{}\"".format(
            backup_cmd,
            download_cmd,
            chmod_cmd,
            install_script_path,
            tmp_archive_path,
            archive_type
        )
        
        def combined_callback():
            reload_settings_python(session) 
            if finish:
                finish() 
        
        console(session, title, [full_command], onClose=combined_callback, autoClose=True)

def install_oscam_enhanced(session, finish=None):
    """Inteligentna instalacja oscam z wieloma fallback"""
    distro = detect_distribution()
    
    def install_callback():
        if finish:
            finish()
    
    # Przygotuj komendy instalacji
    commands = []
    
    # 1. Aktualizacja feed
    commands.append("echo '>>> Aktualizacja feed...' && opkg update")
    
    # 2. Instalacja z feed (zależnie od dystrybucji)
    if distro == "openpli":
        # Dla OpenPLI użyj innego podejścia
        commands.append("echo '>>> Szukanie oscam w feed (OpenPLI)...' && {} install enigma2-plugin-softcams-oscam 2>/dev/null || echo 'Nie znaleziono w feed'".format(get_opkg_command()))
        commands.append("echo '>>> Próba instalacji alternatywnego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh")
    else:
        # Dla OpenATV i innych
        commands.append("echo '>>> Szukanie oscam w feed...' && PKG=$(opkg list | grep 'oscam.*ipv4only' | grep -E -m1 'master|emu|stable' | cut -d' ' -f1) && if [ -n \"$PKG\" ]; then echo 'Znaleziono pakiet: $PKG' && {} install $PKG; else echo 'Nie znaleziono w feed, używam alternatywnego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh; fi".format(get_opkg_command()))
    
    # 3. Weryfikacja instalacji
    commands.append("echo '>>> Weryfikacja instalacji...' && if [ -f /usr/bin/oscam ] || [ -f /usr/bin/oscam-emu ]; then echo 'Oscam został pomyślnie zainstalowany!'; else echo 'Uwaga: Plik oscam nie został znaleziony, sprawdź logi'; fi")
    
    console(session, "Instalacja Oscam", commands, onClose=install_callback, autoClose=True)

def get_repo_lists():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    lst = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        with io.open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i in data:
            if i.get('url'):
                lst.append(("{} - {} ({})".format(i.get('name',''), i.get('author',''), i.get('version','')),
                           "archive:{}".format(i['url'])))
    except Exception as e:
        log("Błąd pobierania repo lists: " + str(e))
    return lst

def get_s4a_lists():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"
    tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt")
    lst = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        urls, vers = {}, {}
        with io.open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
            for l in f:
                l = l.strip()
                if "_url:" in l:
                    k, v = l.split(':', 1)
                    urls[k.strip()] = v.strip()
                elif "_version:" in l:
                    k, v = l.split(':', 1)
                    vers[k.strip()] = v.strip()
        for k, u in urls.items():
            name = k.replace('_url', '').replace('_', ' ').title()
            ver = vers.get(k.replace('_url', '_version'), "brak daty")
            lst.append(("{} - {}".format(name, ver), "archive:{}".format(u)))
    except Exception as e:
        log("Błąd pobierania s4a lists: " + str(e))
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
        self.setTitle("MyUpdater Enhanced")
        
        # Sprawdź system
        self.distro = detect_distribution()
        
        self["menu"] = MenuList([
            ("1. Listy kanałów", "menu_lists"),
            ("2. Instaluj Softcam (Oscam/nCam)", "menu_softcam"),
            ("3. Pobierz Picony Transparent", "picons_github"),
            ("4. Aktualizacja Wtyczki", "plugin_update"),
            ("5. Informacja o Wtyczce", "plugin_info"),
            ("6. Diagnostyka Systemu", "system_diagnostic")
        ])
        
        self["info"] = Label("Wybierz opcję i naciśnij OK")
        self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"],
                                    {"ok": self.runMenuOption, "back": self.close}, -1)
        
        tmpdir()
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        
        log(u"MyUpdater Enhanced {} started on {}".format(VER, self.distro))
        
        # Wyświetl info o systemie
        if self.distro != "unknown":
            self["info"].setText("Wykryto system: {}".format(self.distro))
        else:
            self["info"].setText("Nieznany system - używam trybu uniwersalnego")

    def runMenuOption(self):
        sel = self["menu"].getCurrent()
        if not sel: return
        key = sel[1]
        log("Menu: " + key)
        
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
        elif key == "system_diagnostic":
            self.runDiagnostic()

    def runChannelListMenu(self):
        self["info"].setText("Pobieram listy...")
        Thread(target=self._bgLists).start()

    def _bgLists(self):
        repo = get_repo_lists()
        s4a = get_s4a_lists()
        all_lists = repo + s4a
        reactor.callFromThread(self._onLists, all_lists)

    def _onLists(self, lst):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not lst:
            msg(self.session, "Błąd pobierania list. Sprawdź połączenie internetowe.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected,
                                      ChoiceBox, title="Wybierz listę do instalacji", list=lst)

    def runChannelListSelected(self, choice):
        if not choice: return
        title = choice[0]
        url = choice[1].split(":",1)[1] 
        log("Selected: {} | {}".format(title, url))
        msg(self.session, "Rozpoczynam instalację:\n'{}'...".format(title), timeout=5)
        install_archive_enhanced(self.session, title, url,
                                finish=lambda: msg(self.session, "Instalacja '{}' zakończona.".format(title), timeout=3))

    def runSoftcamMenu(self):
        opts = [
            ("Oscam (auto-detekcja systemu)", "oscam_auto"),
            ("Oscam (tylko Levi45)", "oscam_levi45"),
            ("nCam (biko-73)", "ncam_biko"),
            ("Usuń wszystkie softcamy", "remove_softcam")
        ]
        self.session.openWithCallback(self.runSoftcamSelected,
                                      ChoiceBox, title="Softcam – wybierz", list=opts)

    def runSoftcamSelected(self, choice):
        if not choice: return
        key, title = choice[1], choice[0]
        
        if key == "oscam_auto":
            msg(self.session, "Instaluję {}...".format(title), timeout=2)
            install_oscam_enhanced(self.session, finish=lambda: msg(self.session, "Instalacja oscam zakończona.", timeout=3))
        
        elif key == "oscam_levi45":
            cmd = "wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh"
            msg(self.session, "Instaluję {}...".format(title), timeout=2)
            console(self.session, title, [cmd], onClose=lambda: None, autoClose=True)
        
        elif key == "ncam_biko":
            cmd = "wget -q https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O- | sh"
            msg(self.session, "Instaluję {}...".format(title), timeout=2)
            console(self.session, title, [cmd], onClose=lambda: None, autoClose=True)
        
        elif key == "remove_softcam":
            commands = [
                "echo '>>> Usuwanie softcamów...'",
                "opkg remove enigma2-plugin-softcams-oscam enigma2-plugin-softcams-oscam-emu enigma2-plugin-softcams-ncam 2>/dev/null || true",
                "rm -f /usr/bin/oscam* /usr/bin/ncam* 2>/dev/null || true",
                "echo '>>> Softcamy zostały usunięte.'"
            ]
            console(self.session, "Usuwanie softcamów", commands, onClose=lambda: msg(self.session, "Softcamy usunięte.", timeout=3), autoClose=True)

    def runPiconGitHub(self):
        # *** POPRAWKA: Link bezpośredni do pliku .zip ***
        url = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        title = "Pobieranie Picon (Transparent)" 
        log("Picons: " + url)
        msg(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        install_archive_enhanced(self.session, title, url,
                                finish=lambda: msg(self.session, "Picony gotowe.", timeout=3))

    def runPluginUpdate(self):
        msg(self.session, "Sprawdzam aktualizację...", timeout=3)
        self["info"].setText("Sprawdzam wersję online...")
        Thread(target=self._bgUpdate).start()

    def _bgUpdate(self):
        ver_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        inst_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_ver = os.path.join(PLUGIN_TMP_PATH, "version.txt")
        online = None
        try:
            subprocess.check_call("wget --no-check-certificate -q -T 10 -O {} {}".format(tmp_ver, ver_url), shell=True)
            with io.open(tmp_ver, 'r', encoding='utf-8') as f: 
                online = f.read().strip()
        except:
            pass
        if fileExists(tmp_ver):
            os.remove(tmp_ver)
        reactor.callFromThread(self._onUpdate, online, inst_url)

    def _onUpdate(self, online, inst_url):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not online:
            msg(self.session, "Nie udało się sprawdzić wersji. Sprawdź połączenie.", MessageBox.TYPE_ERROR)
            return
        
        if online and not online.startswith(VER):
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else None,
                                          MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else:
            msg(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: None, autoClose=True)

    #
    # *** FUNKCJA POPRAWIONA (INFORMACJE) ***
    #
    def runInfo(self):
        txt = (u"MyUpdater Enhanced {}\n\n"
               u"Kompatybilność: OpenATV 6.4-7.6, OpenPLI, ViX\n"
               u"Autorzy: Paweł Pawełek, przebudowa na bazie 3.11 Sancho\n\n"
               u"System: {}\n"
               u"Komenda opkg: {}").format(VER, self.distro, get_opkg_command())
        self.session.open(MessageBox, txt, MessageBox.TYPE_INFO)

    #
    # *** FUNKCJA POPRAWIONA (DIAGNOSTYKA) ***
    #
    def runDiagnostic(self):
        """Diagnostyka systemu"""
        commands = [
            "echo '=== Diagnostyka Systemu ==='",
            "echo 'Data: $(date)'",
            "echo 'System: {}'".format(self.distro),
            "echo 'Wersja Enigma2: $(opkg list-installed | grep enigma2 | head -1)'",
            "echo 'Dostępne softcamy (max 3): $(opkg list | grep -i oscam | head -3)'",
            "echo 'Przestrzeń dyskowa: $(df -h / | tail -1)'",
            "echo 'Połączenie internetowe: $(ping -c 1 8.8.8.8 >/dev/null && echo OK || echo BRAK)'",
            "echo '=== Koniec diagnostyki ==='",
            "echo ''",
            "echo 'Naciśnij EXIT aby zamknąć...' "
        ]
        # POPRAWKA: autoClose=False, aby okno konsoli nie znikało
        console(self.session, "Diagnostyka Systemu", commands, onClose=lambda: None, autoClose=False)

def main(session, **kwargs):
    session.open(MyUpdaterEnhanced)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater Enhanced",
                            description="MyUpdater Enhanced {} - kompatybilny z OpenATV/OpenPLI".format(VER),
                            where=PluginDescriptor.WHERE_PLUGINMENU,
                            icon="myupdater.png", fnc=main)]
