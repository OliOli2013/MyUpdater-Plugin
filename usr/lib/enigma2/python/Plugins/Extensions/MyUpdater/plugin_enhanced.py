# -*- coding: utf-8 -*-
#  MyUpdater Enhanced V5.1 – Przebudowa by Paweł Pawełek (na bazie Sancho)
#  Kompatybilny z logiką list AIO Panel 4.2+
#
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
import shutil
from twisted.internet import reactor
from threading import Thread

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER = "V5.1"  # <-- ZMIANA WERSJI
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

def msg(session, txt, typ=MessageBox.TYPE_INFO, timeout=6, title="MyUpdater Info"):
    log("Msg: " + txt)
    reactor.callLater(0.2, lambda: session.open(MessageBox, txt, typ, timeout=timeout, title=title))

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

def install_archive_enhanced(session, title, url, finish=None):
    """Poprawiona wersja instalacji archiwum (TYLKO DLA TYPU 'archive:')"""
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
        cmd_chain.append("echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 2")
    
    else:
        install_script_path = os.path.join(PLUGIN_PATH, "install_archive_script.sh")
        
        if not os.path.exists(install_script_path):
             msg(session, "BŁĄD: Brak pliku install_archive_script.sh!", MessageBox.TYPE_ERROR)
             if finish: finish()
             return
        
        cmd_chain.append("chmod +x \"{}\"".format(install_script_path))
        cmd_chain.append("bash {} \"{}\" \"{}\"".format(install_script_path, tmp_archive_path, archive_type))
        
        def combined_callback():
            reload_settings_python(session) 
            if finish:
                finish()
        
        callback = combined_callback
    
    full_command = " && ".join(cmd_chain)
    
    console(session, title, [full_command], onClose=callback, autoClose=True)


def install_oscam_enhanced(session, finish=None):
    """Inteligentna instalacja oscam z wieloma fallback"""
    distro = detect_distribution()
    
    def install_callback():
        if finish:
            finish()
    
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
    """Pobiera listy z manifestu (Logika AIO)"""
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    lst = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        with io.open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            item_type = item.get("type", "LIST").upper()
            name = item.get('name', 'Brak nazwy')
            author = item.get('author', '')
            url = item.get('url', '')
            
            if not url: continue

            if item_type == "M3U":
                bouquet_id = item.get('bouquet_id', 'userbouquet.imported_m3u.tv')
                bouquet_name = item.get('name', bouquet_id)
                menu_title = "{} - {} (Dodaj jako Bukiet M3U)".format(name, author)
                action = "m3u:{}:{}:{}".format(url, bouquet_id, bouquet_name)
                lst.append((menu_title, action))
            
            elif item_type == "BOUQUET":
                bouquet_id = item.get('bouquet_id', 'userbouquet.imported_ref.tv')
                bouquet_name = item.get('name', bouquet_id)
                menu_title = "{} - {} (Dodaj Bukiet REF)".format(name, author)
                action = "bouquet:{}:{}:{}".format(url, bouquet_id, bouquet_name)
                lst.append((menu_title, action))

            else: # Domyślnie type == "LIST"
                version = item.get('version', '')
                menu_title = "{} - {} ({})".format(name, author, version)
                action = "archive:{}".format(url)
                lst.append((menu_title, action))
            
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
    # <-- ZMIENIONO ROZMIAR OKNA I ELEMENTÓW WEWNĘTRZNYCH -->
    skin = """<screen position="center,center" size="860,550" title="MyUpdater Enhanced">
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
        <widget name="menu" position="10,70" size="840,400" scrollbarMode="showOnDemand" itemHeight="40" font="Regular;22" />
        <widget name="info" position="10,480" size="840,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
        <widget name="version" position="720,520" size="130,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
    </screen>"""

    def __init__(self, session, args=0):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("MyUpdater Enhanced")
        
        self.distro = detect_distribution()
        
        self.wait_message_box = None 
        
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
        """Dyspozytor akcji dla list (Logika AIO)"""
        if not choice: return
        
        title = choice[0]
        action = choice[1]
        log("Selected: {} | {}".format(title, action))

        if action.startswith("archive:"):
            try:
                url = action.split(':', 1)[1]
                msg(self.session, "Rozpoczynam instalację (archiwum):\n'{}'...".format(title), timeout=5)
                install_archive_enhanced(self.session, title, url,
                                         finish=lambda: msg(self.session, "Instalacja '{}' zakończona.".format(title), timeout=3))
            except IndexError:
                msg(self.session, "Błąd: Nieprawidłowy format akcji archive.", message_type=MessageBox.TYPE_ERROR)
                log("Błąd parsowania archive: " + action)

        elif action.startswith("m3u:"):
            try:
                parts = action.split(':', 3)
                url = parts[1] + ":" + parts[2]
                bouquet_info = parts[3].split(':', 1)
                bouquet_id = bouquet_info[0]
                bouquet_name = bouquet_info[1] if len(bouquet_info) > 1 else bouquet_id
                msg(self.session, "Rozpoczynam dodawanie bukietu M3U:\n'{}'...".format(title), timeout=3)
                self.install_m3u_as_bouquet(title, url, bouquet_id, bouquet_name)
            except Exception as e:
                msg(self.session, "Błąd parsowania akcji M3U: {}".format(e), message_type=MessageBox.TYPE_ERROR)
                log("Błąd parsowania M3U: {} | {}".format(action, e))
        
        elif action.startswith("bouquet:"):
            try:
                parts = action.split(':', 3)
                url = parts[1] + ":" + parts[2]
                bouquet_info = parts[3].split(':', 1)
                bouquet_id = bouquet_info[0]
                bouquet_name = bouquet_info[1] if len(bouquet_info) > 1 else bouquet_id
                msg(self.session, "Rozpoczynam dodawanie bukietu REF:\n'{}'...".format(title), timeout=3)
                self.install_bouquet_reference(title, url, bouquet_id, bouquet_name)
            except Exception as e:
                msg(self.session, "Błąd parsowania akcji BOUQUET: {}".format(e), message_type=MessageBox.TYPE_ERROR)
                log("Błąd parsowania BOUQUET: {} | {}".format(action, e))
                
        else:
            log("Nieznana akcja: " + action)
            msg(self.session, "Nieznany typ akcji: {}".format(action), message_type=MessageBox.TYPE_ERROR)

    
    def install_bouquet_reference(self, title, url, bouquet_id, bouquet_name):
        """Instaluje plik bukietu .tv (tylko referencje, bez lamedb). (Logika AIO)"""
        log("install_bouquet_reference: {} | {} | {}".format(title, url, bouquet_id))
        
        e2_dir = "/etc/enigma2"
        bouquets_tv_path = os.path.join(e2_dir, "bouquets.tv")
        target_bouquet_path = os.path.join(e2_dir, bouquet_id)
        tmp_bouquet_path = os.path.join(PLUGIN_TMP_PATH, bouquet_id)

        cmd = """
        echo "Pobieranie pliku bukietu referencyjnego..."
        wget -T 30 --no-check-certificate -O "{tmp_path}" "{url}"
        if [ $? -eq 0 ] && [ -s "{tmp_path}" ]; then
            echo "Instalowanie bukietu..."
            mv "{tmp_path}" "{target_path}"
            BOUQUET_ENTRY='#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{b_id}" ORDER BY bouquet'
            if ! grep -q -F "{b_id}" "{bq_tv_path}"; then
                echo "Dodawanie wpisu do bouquets.tv..."
                echo "$BOUQUET_ENTRY" >> "{bq_tv_path}"
            else
                echo "Wpis dla {b_id} już istnieje w bouquets.tv."
            fi
            echo "Instalacja bukietu zakończona."
            echo " "
            echo "!!! UWAGA !!!"
            echo "To jest bukiet referencyjny. Kanały będą działać (nie będą 'N/A')"
            echo "TYLKO jeśli Twoja główna lista (np. bzyk83) zawiera pasujący plik lamedb!"
            echo " "
            sleep 8
        else
            echo "BŁĄD: Nie udało się pobrać pliku bukietu."
            sleep 5
        fi
        """.format(
            url=url,
            tmp_path=tmp_bouquet_path,
            target_path=target_bouquet_path,
            b_id=bouquet_id,
            bq_tv_path=bouquets_tv_path
        )
        
        console(self.session, title, [cmd], 
                onClose=lambda: reload_settings_python(self.session), 
                autoClose=True)

    def install_m3u_as_bouquet(self, title, url, bouquet_id, bouquet_name):
        """Pobiera M3U, konwertuje je w locie na bukiet E2 i dodaje do listy. (Logika AIO)"""
        log("install_m3u_as_bouquet: {} | {} | {}".format(title, url, bouquet_id))
        tmp_m3u_path = os.path.join(PLUGIN_TMP_PATH, "temp.m3u")
        download_cmd = "wget -T 30 --no-check-certificate -O \"{}\" \"{}\"".format(tmp_m3u_path, url)
        
        self.wait_message_box = None
        
        def on_download_finished(*args):
            if not (fileExists(tmp_m3u_path) and os.path.getsize(tmp_m3u_path) > 0):
                msg(self.session, "Błąd: Nie udało się pobrać pliku M3U.", message_type=MessageBox.TYPE_ERROR)
                return
            
            self.wait_message_box = self.session.open(MessageBox, "Pobrano plik M3U.\nTrwa konwersja na bukiet E2...\nProszę czekać.", MessageBox.TYPE_INFO, enable_input=False)
            
            Thread(target=self._parse_m3u_thread, args=(tmp_m3u_path, bouquet_id, bouquet_name)).start()

        console(self.session, "Pobieranie M3U: " + title, [download_cmd], 
                onClose=on_download_finished, 
                autoClose=True)

    def _parse_m3u_thread(self, tmp_m3u_path, bouquet_id, bouquet_name):
        """Wątek roboczy do parsowania M3U i tworzenia pliku bukietu. (Logika AIO)"""
        try:
            e2_bouquet_path = os.path.join(PLUGIN_TMP_PATH, bouquet_id)
            e2_lines = [u"#NAME {}\n".format(bouquet_name)]
            channel_name = u"N/A"
            
            with io.open(tmp_m3u_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#EXTINF:'):
                        try:
                            channel_name = line.split(',')[-1].strip()
                        except:
                            channel_name = u"Brak Nazwy"
                    elif line.startswith('http://') or line.startswith('https://'):
                        formatted_url = line.replace(':', '%3a')
                        e2_lines.append(u"#SERVICE 4097:0:1:0:0:0:0:0:0:0:{}:{}\n".format(formatted_url, channel_name))
                        channel_name = u"N/A"
            
            if len(e2_lines) <= 1:
                raise Exception("Nie znaleziono kanałów w pliku M3U")

            with io.open(e2_bouquet_path, 'w', encoding='utf-8') as f:
                f.writelines(e2_lines)

            reactor.callFromThread(self._install_parsed_bouquet, e2_bouquet_path, bouquet_id)

        except Exception as e:
            log("[MyUpdater] Błąd parsowania M3U: " + str(e))
            if self.wait_message_box: 
                reactor.callFromThread(self.wait_message_box.close)
            reactor.callFromThread(msg, self.session, "Błąd parsowania pliku M3U:\n{}".format(e), message_type=MessageBox.TYPE_ERROR)

    def _install_parsed_bouquet(self, tmp_bouquet_path, bouquet_id):
        """Wywoływane w głównym wątku: Kopiuje plik bukietu i aktualizuje bouquets.tv. (Logika AIO)"""
        if self.wait_message_box:
            try:
                reactor.callFromThread(self.wait_message_box.close)
            except:
                pass
            
        e2_dir = "/etc/enigma2"
        bouquets_tv_path = os.path.join(e2_dir, "bouquets.tv")
        target_bouquet_path = os.path.join(e2_dir, bouquet_id)
        
        try:
            shutil.move(tmp_bouquet_path, target_bouquet_path)
        except Exception as e:
            msg(self.session, "Błąd kopiowania bukietu: {}".format(e), message_type=MessageBox.TYPE_ERROR)
            return

        try:
            entry_to_add = u'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{}" ORDER BY bouquet\n'.format(bouquet_id)
            entry_exists = False
            
            if fileExists(bouquets_tv_path):
                with io.open(bouquets_tv_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if bouquet_id in line:
                            entry_exists = True
                            break
            
            if not entry_exists:
                with io.open(bouquets_tv_path, 'a', encoding='utf-8') as f:
                    f.write(entry_to_add)
            
        except Exception as e:
            msg(self.session, "Błąd edycji bouquets.tv: {}".format(e), message_type=MessageBox.TYPE_ERROR)
            return

        m = "Bukiet '{}' został pomyślnie dodany.\nPrzeładowuję listy...".format(bouquet_id) if not entry_exists else "Bukiet '{}' został zaktualizowany.\nPrzeładowuję listy...".format(bouquet_id)
        msg(self.session, m, message_type=MessageBox.TYPE_INFO, timeout=5)
        reload_settings_python(self.session)


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
        
        # Porównuje tylko główną wersję (np. V5.1 vs V5.2), ignoruje tekst w nawiasach
        current_ver_base = VER.split(" ")[0]
        
        if online and online != current_ver_base:
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else None,
                                          MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else:
            msg(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: None, autoClose=True)

    def runInfo(self):
        # <-- ZAKTUALIZOWANE INFORMACJE O AUTORZE I LICENCJI -->
        txt = (u"MyUpdater Enhanced {}\n\n"
               u"Autor: Paweł Pawełek (przebudowa na bazie 3.11 Sancho)\n"
               u"Kompatybilność: OpenATV 6.4-7.6, OpenPLI, ViX\n\n"
               u"--- Nota Licencyjna (GNU GPL) ---\n"
               u"Ta wtyczka jest wolnym oprogramowaniem, rozpowszechnianym\n"
               u"na warunkach Powszechnej Licencji Publicznej GNU (GPL) v2 lub v3, \n"
               u"opublikowanej przez Free Software Foundation.\n\n"
               u"Oprogramowanie jest udostępniane 'TAK JAK JEST', BEZ \n"
               u"JAKIEJKOLWIEK GWARANCJI. Korzystasz z niego na własną \n"
               u"odpowiedzialność.\n\n"
               u"--- Informacje diagnostyczne ---\n"
               u"System: {}\n"
               u"Komenda opkg: {}").format(VER, self.distro, get_opkg_command())
        # Używamy dłuższego okna MessageBox (domyślnie się skaluje) i dodajemy tytuł
        self.session.open(MessageBox, txt, MessageBox.TYPE_INFO, title="Informacje o wtyczce")

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
                             # <-- ZAKTUALIZOWANY OPIS -->
                             description="MyUpdater {} (by Paweł Pawełek, na bazie Sancho) - kompatybilny z OpenATV/OpenPLI".format(VER),
                             where=PluginDescriptor.WHERE_PLUGINMENU,
                             icon="myupdater.png", fnc=main)]
