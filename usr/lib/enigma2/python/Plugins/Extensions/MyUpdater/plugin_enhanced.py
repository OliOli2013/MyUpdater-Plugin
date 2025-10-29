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
    # Ta funkcja jest nadal używana do ogólnych komunikatów z opóźnieniem
    log("Msg: " + txt)
    reactor.callLater(0.2, lambda: session.open(MessageBox, txt, typ, timeout=timeout))

def console(session, title, cmdlist, onClose, autoClose=True):
    log("Console: {} | {}".format(title, " ; ".join(cmdlist)))
    try:
        c = session.open(Console, title=title, cmdlist=cmdlist, closeOnSuccess=autoClose)
        c.onClose.append(onClose)
    except Exception as e:
        log("Console exception: " + str(e))
        # Upewnij się, że callback zostanie wywołany nawet przy błędzie otwarcia konsoli
        if onClose:
            try:
                onClose()
            except Exception as call_e:
                 log("Exception in onClose callback: " + str(call_e))

def tmpdir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        os.makedirs(PLUGIN_TMP_PATH)

def reload_settings_python(session, *args):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        # Używamy bezpośredniego MessageBox dla natychmiastowego efektu
        session.open(MessageBox, "Listy kanałów przeładowane.", type=MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        log("[MyUpdater] Błąd podczas przeładowywania list: " + str(e))
        session.open(MessageBox, "Wystąpił błąd podczas przeładowywania list.", type=MessageBox.TYPE_ERROR)

def install_archive_enhanced(session, title, url, finish=None):
    """Poprawiona wersja instalacji archiwum"""
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
    
    cmd_chain = []
    
    if "picon" not in title.lower():
        backup_cmd = "tar -czf /tmp/MyUpdater/backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /etc/enigma2 lamedb *.tv *.radio 2>/dev/null || true"
        cmd_chain.append(backup_cmd)

    download_cmd = 'wget --no-check-certificate --timeout=30 -t 2 -O "{}" "{}"'.format(tmp_archive_path, url)
    cmd_chain.append(download_cmd)
    
    callback = finish
    
    if "picon" in title.lower() and archive_type == "zip":
        picon_path = "/usr/share/enigma2/picon"
        tmp_extract_path = "/tmp/MyUpdater_picon_extract"
        
        cmd_chain.append("rm -rf " + tmp_extract_path)
        cmd_chain.append("mkdir -p " + tmp_extract_path)
        cmd_chain.append("unzip -o -q \"" + tmp_archive_path + "\" -d \"" + tmp_extract_path + "\"")
        cmd_chain.append("mkdir -p " + picon_path)
        
        mv_logic = (
            "if [ -d \"" + tmp_extract_path + "/picon\" ]; then "
            "mv -f \"" + tmp_extract_path + "/picon\"/* \"" + picon_path + "/\" 2>/dev/null || true; "
            "else "
            "mv -f \"" + tmp_extract_path + "\"/* \"" + picon_path + "/\" 2>/dev/null || true; "
            "fi"
        )
        cmd_chain.append(mv_logic)
        
        cmd_chain.append("rm -rf " + tmp_extract_path)
        cmd_chain.append("rm -f \"" + tmp_archive_path + "\"")
        cmd_chain.append("echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 1") # Skrócony sleep
    
    else:
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        
        if not os.path.exists(install_script_path):
             msg(session, "BŁĄD: Brak pliku install_archive_script.sh!", MessageBox.TYPE_ERROR)
             if finish: finish()
             return
        
        cmd_chain.append("chmod +x \"{}\"".format(install_script_path))
        cmd_chain.append("bash {} \"{}\" \"{}\"".format(install_script_path, tmp_archive_path, archive_type))
        
        def combined_callback():
            # Przeładowanie list wywoła własny MessageBox
            reload_settings_python(session)
            # Wywołaj oryginalny callback, jeśli istniał (chociaż reload_settings go zastępuje)
            if finish:
                 try: finish()
                 except: pass # Ignoruj błędy w starym finish, bo reload_settings jest ważniejszy
        
        callback = combined_callback
    
    full_command = " && ".join(filter(None, cmd_chain)) # filter(None, ...) usunie puste elementy (np. backup_cmd dla picon)
    
    console(session, title, [full_command], onClose=callback, autoClose=True)


def install_oscam_enhanced(session, finish=None):
    """Inteligentna instalacja oscam z wieloma fallback"""
    distro = detect_distribution()
    
    def install_callback():
        # Użyj bezpośredniego MessageBox po zakończeniu
        session.open(MessageBox, "Instalacja Oscam zakończona (lub próba zakończona). Sprawdź logi.", type=MessageBox.TYPE_INFO, timeout=4)
        if finish:
             try: finish()
             except: pass

    commands = []
    commands.append("echo '>>> Aktualizacja feed...' && opkg update")
    
    if distro == "openpli":
        commands.append("echo '>>> Szukanie oscam w feed (OpenPLI)...' && {} install enigma2-plugin-softcams-oscam 2>/dev/null || echo 'Nie znaleziono w feed'".format(get_opkg_command()))
        commands.append("echo '>>> Próba instalacji alternatywnego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh")
    else:
        commands.append("echo '>>> Szukanie oscam w feed...' && PKG=$(opkg list | grep 'oscam.*ipv4only' | grep -E -m1 'master|emu|stable' | cut -d' ' -f1) && if [ -n \"$PKG\" ]; then echo 'Znaleziono pakiet: $PKG' && {} install $PKG; else echo 'Nie znaleziono w feed, używam alternatywnego źródła...' && wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O /tmp/oscam_installer.sh && chmod +x /tmp/oscam_installer.sh && /bin/sh /tmp/oscam_installer.sh; fi".format(get_opkg_command()))
    
    commands.append("echo '>>> Weryfikacja instalacji...' && if [ -f /usr/bin/oscam ] || [ -f /usr/bin/oscam-emu ]; then echo 'Oscam został pomyślnie zainstalowany!'; else echo 'Uwaga: Plik oscam nie został znaleziony, sprawdź logi'; fi")
    
    console(session, "Instalacja Oscam", commands, onClose=install_callback, autoClose=True)

def get_repo_lists():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    lst = []
    try:
        # Użycie subprocess.check_output zamiast check_call do przechwycenia błędów
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "20", "-O", tmp, url], stderr=subprocess.STDOUT)
        with io.open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i in data:
            if i.get('url'):
                lst.append(("{} - {} ({})".format(i.get('name',''), i.get('author',''), i.get('version','')),
                           "archive:{}".format(i['url'])))
    except subprocess.CalledProcessError as e:
        log("Błąd subprocess przy pobieraniu repo lists: " + e.output.decode('utf-8', errors='ignore'))
    except Exception as e:
        log("Błąd pobierania repo lists: " + str(e))
    return lst

def get_s4a_lists():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"
    tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt")
    lst = []
    try:
        subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "20", "-O", tmp, url], stderr=subprocess.STDOUT)
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
    except subprocess.CalledProcessError as e:
         log("Błąd subprocess przy pobieraniu s4a lists: " + e.output.decode('utf-8', errors='ignore'))
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
        
        self.distro = detect_distribution()
        
        self["menu"] = MenuList([
            ("1. Listy kanałów", "menu_lists"),
            ("2. Instaluj Softcam (Oscam/nCam)", "menu_softcam"),
            ("3. Pobierz Picony Transparent", "picons_github"),
            ("4. Aktualizacja Wtyczki", "plugin_update"),
            ("5. Informacja o Wtyczce", "plugin_info"),
            ("6. Diagnostyka Systemu", "system_diagnostic")
        ])
        
        self["info"] = Label("Wybierz opcję i naciśnij OK") # Tekst startowy
        self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"],
                                    {"ok": self.runMenuOption, "back": self.close}, -1)
        
        # === NOWE LINIE - Dynamiczny opis opcji ===
        self["menu"].onSelectionChanged.append(self.updateInfoLabel) # Wywołaj funkcję przy zmianie zaznaczenia
        self.updateInfoLabel() # Ustaw tekst początkowy od razu
        # === KONIEC NOWYCH LINII ===

        tmpdir()
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        
        log(u"MyUpdater Enhanced {} started on {}".format(VER, self.distro))
        
        # Usunięto ustawianie tekstu o systemie w self["info"]

    # === NOWA FUNKCJA - Aktualizacja opisu ===
    def updateInfoLabel(self):
        """Aktualizuje dolną etykietę opisem wybranej opcji"""
        selection = self["menu"].getCurrent()
        if selection:
            key = selection[1]
            descriptions = {
                "menu_lists": "Pobierz i zainstaluj listy kanałów.",
                "menu_softcam": "Zainstaluj lub usuń Oscam/nCam.",
                "picons_github": "Pobierz zestaw picon transparent.",
                "plugin_update": "Sprawdź i zainstaluj aktualizacje wtyczki.",
                "plugin_info": "Wyświetl informacje o tej wtyczce.",
                "system_diagnostic": "Sprawdź podstawowe informacje o systemie."
            }
            self["info"].setText(descriptions.get(key, "Wybierz opcję i naciśnij OK"))
        else:
            self["info"].setText("Wybierz opcję i naciśnij OK")
    # === KONIEC NOWEJ FUNKCJI ===

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
        self.updateInfoLabel() # Przywróć opis opcji po pobraniu list
        if not lst:
            msg(self.session, "Błąd pobierania list. Sprawdź połączenie internetowe lub logi.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected,
                                      ChoiceBox, title="Wybierz listę do instalacji", list=lst)

    def runChannelListSelected(self, choice):
        if not choice: return
        title = choice[0]
        url = choice[1].split(":",1)[1]
        log("Selected: {} | {}".format(title, url))
        msg(self.session, "Rozpoczynam instalację:\n'{}'...".format(title), timeout=5)
        # Zmieniono callback na None, bo reload_settings_python() zajmie się komunikatem
        install_archive_enhanced(self.session, title, url, finish=None)

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
        
        # Używamy bezpośredniego MessageBox do informacji o rozpoczęciu
        self.session.open(MessageBox, "Rozpoczynam akcję dla: '{}'...".format(title), type=MessageBox.TYPE_INFO, timeout=2)
        
        if key == "oscam_auto":
            # Callback install_callback w install_oscam_enhanced zajmie się komunikatem końcowym
            install_oscam_enhanced(self.session, finish=None)
        
        elif key == "oscam_levi45":
            cmd = "wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh"
            # Użyj bezpośredniego MessageBox w onClose
            console(self.session, title, [cmd], onClose=lambda: self.session.open(MessageBox, "Instalacja '{}' zakończona (lub próba zakończona).".format(title), type=MessageBox.TYPE_INFO, timeout=4), autoClose=True)
        
        elif key == "ncam_biko":
            cmd = "wget -q https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O- | sh"
            # Użyj bezpośredniego MessageBox w onClose
            console(self.session, title, [cmd], onClose=lambda: self.session.open(MessageBox, "Instalacja '{}' zakończona (lub próba zakończona).".format(title), type=MessageBox.TYPE_INFO, timeout=4), autoClose=True)
        
        elif key == "remove_softcam":
            commands = [
                "echo '>>> Usuwanie softcamów...'",
                "opkg remove --force-removal-of-dependent-packages enigma2-plugin-softcams-oscam enigma2-plugin-softcams-oscam-emu enigma2-plugin-softcams-ncam 2>/dev/null || true",
                "rm -f /usr/bin/oscam* /usr/bin/ncam* 2>/dev/null || true",
                "echo '>>> Softcamy zostały usunięte.'"
            ]
             # Użyj bezpośredniego MessageBox w onClose
            console(self.session, "Usuwanie softcamów", commands, onClose=lambda: self.session.open(MessageBox, "Softcamy usunięte (lub próba usunięcia).", type=MessageBox.TYPE_INFO, timeout=3), autoClose=True)

    def runPiconGitHub(self):
        url = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        title = "Pobieranie Picon (Transparent)"
        log("Picons: " + url)
        msg(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        # Użyj bezpośredniego MessageBox w finish callback
        install_archive_enhanced(self.session, title, url,
                                finish=lambda: self.session.open(MessageBox, "Picony gotowe.", type=MessageBox.TYPE_INFO, timeout=3))

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
            # Użycie check_output do przechwycenia błędów wget
            subprocess.check_output(["wget", "--no-check-certificate", "-q", "-T", "10", "-O", tmp_ver, ver_url], stderr=subprocess.STDOUT)
            with io.open(tmp_ver, 'r', encoding='utf-8') as f:
                online = f.read().strip()
        except subprocess.CalledProcessError as e:
             log("Błąd subprocess przy sprawdzaniu wersji: " + e.output.decode('utf-8', errors='ignore'))
        except Exception as e:
            log("Błąd sprawdzania wersji: " + str(e))
        if fileExists(tmp_ver):
            try: os.remove(tmp_ver)
            except: pass
        reactor.callFromThread(self._onUpdate, online, inst_url)

    def _onUpdate(self, online, inst_url):
        self.updateInfoLabel() # Przywróć opis opcji po sprawdzeniu
        if not online:
            msg(self.session, "Nie udało się sprawdzić wersji. Sprawdź połączenie lub logi.", MessageBox.TYPE_ERROR)
            return
        
        if online and online != VER and online.strip(): # Sprawdź czy wersja online jest inna i niepusta
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else None,
                                          MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else:
            msg(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        # Użyj bezpośredniego MessageBox w onClose
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: self.session.open(MessageBox, "Aktualizacja zakończona (lub próba zakończona).\nRestart GUI może być potrzebny.", type=MessageBox.TYPE_INFO, timeout=5), autoClose=True)

    def runInfo(self):
        txt = (u"MyUpdater Enhanced {}\n\n"
               u"Kompatybilność: OpenATV 6.4-7.6, OpenPLI, ViX\n"
               u"Autorzy: Paweł Pawełek, przebudowa na bazie 3.11 Sancho\n\n"
               u"System: {}\n"
               u"Komenda opkg: {}").format(VER, self.distro, get_opkg_command())
        self.session.open(MessageBox, txt, MessageBox.TYPE_INFO)

    def runDiagnostic(self):
        """Diagnostyka systemu"""
        commands = [
            "echo '=== Diagnostyka Systemu ==='",
            "echo \"Data: $(date)\"",
            "echo \"System: {}\"".format(self.distro),
            "echo \"Wersja Enigma2: $(opkg list-installed | grep enigma2 | head -1 2>/dev/null || echo 'Nieznana')\"",
            "echo \"\"",
            "echo \"Dostępne softcamy (max 3):\"",
            "opkg list | grep -i 'oscam\|ncam' | head -3 2>/dev/null || echo \" - Brak softcamów w feed\"",
            "echo \"\"",
            "echo \"Przestrzeń dyskowa (/):\"",
            "df -h / | tail -1",
            "echo \"\"",
            "ping -c 1 8.8.8.8 >/dev/null && echo \"Połączenie internetowe: OK\" || echo \"Połączenie internetowe: BRAK\"",
            "echo \"\"",
            "echo '=== Koniec diagnostyki ==='",
            "echo 'Naciśnij EXIT aby zamknąć...' "
        ]
        console(self.session, "Diagnostyka Systemu", commands, onClose=lambda: None, autoClose=False)


def main(session, **kwargs):
    session.open(MyUpdaterEnhanced)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater Enhanced",
                            description="MyUpdater Enhanced {} - kompatybilny z OpenATV/OpenPLI".format(VER),
                            where=PluginDescriptor.WHERE_PLUGINMENU,
                            icon="myupdater.png", fnc=main)]
