# -*- coding: utf-8 -*-
# MyUpdater (Mod 2025) V4.2-hotfix
# Poprawka: automatyczne rozpoznanie listy/piconów + przeładowanie kanałów
from __future__ import print_function, absolute_import
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
import os, subprocess, json, datetime, traceback
from twisted.internet import reactor
from threading import Thread

PLUGIN_PATH   = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER           = "V4.2-hotfix"
LOG_FILE      = "/tmp/MyUpdater_install.log"

def log_message(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("{} - {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception as e:
        print("[MyUpdater] log error:", e)

def show_message_compat(session, txt, typ=MessageBox.TYPE_INFO, timeout=10, cb=None):
    log_message("Msg: " + txt)
    reactor.callLater(0.2, lambda: session.openWithCallback(cb, MessageBox, txt, typ, timeout=timeout))

def console_screen_open(session, title, cmdlist, callback=None, close_on_finish=False):
    log_message("Console: {} | {}".format(title, " ; ".join(cmdlist)))
    try:
        c = session.open(Console, title=title, cmdlist=cmdlist, closeOnSuccess=close_on_finish)
        if callback:
            (c.finishedCallback if hasattr(c, 'finishedCallback') else c.onClose).append(callback)
    except Exception as e:
        log_message("Console exception: " + str(e))
        log_message(traceback.format_exc())

def prepare_tmp_dir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        os.makedirs(PLUGIN_TMP_PATH)

# ----------- rozpoznanie typu archiwum ----------------
def _detect_archive_type(path):
    import zipfile, tarfile
    try:
        with zipfile.ZipFile(path, 'r') as z:
            names = z.namelist()
            return 'channels' if any('.tv' in n or '.radio' in n or 'lamedb' in n for n in names) else 'picon'
    except:
        pass
    try:
        with tarfile.open(path, 'r:*') as t:
            names = t.getnames()
            return 'channels' if any('.tv' in n or '.radio' in n or 'lamedb' in n for n in names) else 'picon'
    except:
        pass
    return None

# ----------- instalacja picon -------------------------
def _install_picons(session, archive, cb):
    picon_path = "/usr/share/enigma2/picon"
    nested     = os.path.join(picon_path, "picon")
    cmd = (
        "mkdir -p {p} && "
        "unzip -o -q \"{a}\" -d \"{p}\" && "
        "if [ -d \"{n}\" ]; then mv -f \"{n}\"/* \"{p}\"/; rmdir \"{n}\"; fi && "
        "rm -f \"{a}\" && "
        "echo '>>> Picony gotowe.'"
    ).format(p=picon_path, a=archive, n=nested)
    console_screen_open(session, "Instalacja Picon", [cmd], close_on_finish=True, callback=cb)

# ----------- instalacja listy + przeładowanie --------
def _install_channels(session, archive, cb):
    target = "/etc/enigma2/"
    cmd = (
        "tar -xzvf \"{a}\" -C {t} --strip-components=1 --overwrite && "
        "rm -f \"{a}\" && "
        "echo '>>> Lista kanałów zainstalowana.'"
    ).format(a=archive, t=target)
    def _reload():
        reload_settings_python(session)
        if cb: cb()
    console_screen_open(session, "Instalacja Listy Kanałów", [cmd], close_on_finish=True, callback=_reload)

# ----------- reload ---------------------------------
def reload_settings_python(session, *a):
    try:
        db = eDVBDB.getInstance()
        db.reloadServicelist()
        db.reloadBouquets()
        show_message_compat(session, "Listy kanałów przeładowane.", MessageBox.TYPE_INFO, timeout=3)
    except Exception as e:
        show_message_compat(session, "Błąd przeładowania: {}".format(e), MessageBox.TYPE_ERROR)

# ----------- etap po pobraniu -----------------------
def _after_download(session, title, tmp_archive_path, callback_on_finish):
    typ = _detect_archive_type(tmp_archive_path)
    if not typ:
        show_message_compat(session, "Nie udało się rozpoznać typu archiwum.", MessageBox.TYPE_ERROR)
        if callback_on_finish: callback_on_finish()
        return
    log_message("Detected archive type: {}".format(typ))
    if typ == 'picon':
        _install_picons(session, tmp_archive_path, callback_on_finish)
    elif typ == 'channels':
        _install_channels(session, tmp_archive_path, callback_on_finish)

# ----------- główna funkcja instalacji --------------
def install_archive(session, title, url, callback_on_finish=None):
    log_message("--- install_archive START ---")
    log_message("URL: {}".format(url))
    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    download_cmd = "wget --no-check-certificate -O \"{}\" \"{}\"".format(tmp_archive_path, url)
    console_screen_open(session, title, [download_cmd], close_on_finish=False,
                        callback=lambda: _after_download(session, title, tmp_archive_path, callback_on_finish))
    log_message("--- install_archive END ---")

# ----------- źródła list -----------------------------
def _get_s4aupdater_lists_dynamic_sync():
    url = 'http://s4aupdater.one.pl/s4aupdater_list.txt'
    tmp = os.path.join(PLUGIN_TMP_PATH, 's4aupdater_list.txt')
    lists = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        urls, vers = {}, {}
        with open(tmp, 'r', encoding='utf-8', errors='ignore') as f:
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
            ver  = vers.get(k.replace('_url', '_version'), "brak daty")
            lists.append(("{} - {}".format(name, ver), "archive:{}".format(u)))
    except:
        pass
    return [i for i in lists if not any(x in i[0].lower() for x in ['bzyk', 'jakitaki'])]

def _get_lists_from_repo_sync():
    url  = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp  = os.path.join(PLUGIN_TMP_PATH, 'manifest.json')
    lst  = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        with open(tmp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for i in data:
            if i.get('url'):
                lst.append(("{} - {} ({})".format(i.get('name',''), i.get('author',''), i.get('version','')),
                           "archive:{}".format(i['url'])))
    except:
        pass
    return lst

# ----------- główne okno -----------------------------
class Fantastic(Screen):
    skin = """<screen position="center,center" size="700,400" title="MyUpdater">
        <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/MyUpdater/logo.png" position="10,10" size="350,50" alphatest="on" />
        <widget name="menu" position="10,70" size="680,280" scrollbarMode="showOnDemand" />
        <widget name="info" position="10,360" size="680,30" font="Regular;20" halign="center" valign="center" foregroundColor="yellow" />
        <widget name="version" position="550,370" size="140,20" font="Regular;16" halign="right" valign="center" foregroundColor="grey" />
    </screen>"""

    def __init__(self, session, args=0):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("MyUpdater")
        mainmenu = [("1. Listy kanałów", "menu_lists"),
                    ("2. Instaluj Softcam", "menu_softcam"),
                    ("3. Pobierz Picony Transparent", "picons_github"),
                    ("4. Aktualizacja Wtyczki", "plugin_update"),
                    ("5. Informacja o Wtyczce", "plugin_info")]
        self["menu"]   = MenuList(mainmenu)
        self["info"]   = Label("Wybierz opcję i naciśnij OK")
        self["version"]= Label("Wersja: " + VER)
        self["actions"]= ActionMap(["WizardActions", "DirectionActions"],
                                   {"ok": self.runMenuOption, "back": self.close}, -1)
        prepare_tmp_dir()
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        log_message("MyUpdater Mod {} started.".format(VER))

    def runMenuOption(self):
        sel = self["menu"].getCurrent()
        if not sel: return
        key = sel[1]
        log_message("Menu: {}".format(key))
        if key == "menu_lists":     self.runChannelListMenu()
        elif key == "menu_softcam": self.runSoftcamMenu()
        elif key == "picons_github":self.runPiconGitHub()
        elif key == "plugin_update":self.runPluginUpdate()
        elif key == "plugin_info":  self.runInfo()

    def runChannelListMenu(self):
        self["info"].setText("Pobieranie list...")
        Thread(target=self._bg_lists).start()

    def _bg_lists(self):
        repo = _get_lists_from_repo_sync()
        s4a  = _get_s4aupdater_lists_dynamic_sync()
        all  = repo + s4a
        reactor.callFromThread(self._onLists, all)

    def _onLists(self, lst):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not lst:
            show_message_compat(self.session, "Błąd pobierania list.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected,
                                      ChoiceBox, title="Wybierz listę do instalacji", list=lst)

    def runChannelListSelected(self, choice):
        if not choice: return
        title = choice[0]
        url   = choice[1].split(':',1)[1]
        log_message("Selected: {} | {}".format(title, url))
        show_message_compat(self.session, "Rozpoczynanie instalacji...", timeout=2)
        install_archive(self.session, title, url,
                        callback_on_finish=lambda: reload_settings_python(self.session))

    def runSoftcamMenu(self):
        opts = [("Oscam (feed + Levi45 fallback)", "oscam_feed"),
                ("Oscam (tylko Levi45)", "oscam_levi45"),
                ("nCam (biko-73)", "ncam_biko")]
        self.session.openWithCallback(self.runSoftcamSelected,
                                      ChoiceBox, title="Softcam – wybierz", list=opts)

    def runSoftcamSelected(self, choice):
        if not choice: return
        key, title = choice[1], choice[0]
        cmd = ""
        if key == "oscam_feed":
            cmd = """ echo "Instaluję Oscam (feed)..." && wget -q -O - http://updates.mynonpublic.com/oea/feed | bash && opkg update && PKG=$(opkg list | grep 'oscam.*ipv4only' | grep -E -m1 'master|emu|stable' | cut -d' ' -f1) && if [ -n "$PKG" ]; then opkg install $PKG; else wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh; fi && sleep 3 """
        elif key == "oscam_levi45":
            cmd = "wget -q --no-check-certificate https://raw.githubusercontent.com/levi-45/Levi45Emulator/main/installer.sh -O- | sh"
        elif key == "ncam_biko":
            cmd = "wget -q https://raw.githubusercontent.com/biko-73/Ncam_EMU/main/installer.sh -O- | sh"
        if cmd:
            show_message_compat(self.session, "Instaluję {}...".format(title), timeout=2)
            console_screen_open(self.session, title, [cmd], close_on_finish=True)

    def runPiconGitHub(self):
        url  = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        title= "Pobieranie Picon (Transparent)"
        log_message("Picons: "+url)
        show_message_compat(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        install_archive(self.session, title, url)

    def runPluginUpdate(self):
        show_message_compat(self.session, "Sprawdzanie aktualizacji...", timeout=3)
        self["info"].setText("Sprawdzam wersję online...")
        Thread(target=self._bg_update).start()

    def _bg_update(self):
        ver_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        inst_url= "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_ver = os.path.join(PLUGIN_TMP_PATH, 'version.txt')
        online  = None
        try:
            subprocess.check_call("wget --no-check-certificate -q -T 10 -O {} {}".format(tmp_ver, ver_url), shell=True)
            with open(tmp_ver, 'r') as f: online = f.read().strip()
        except:
            pass
        if fileExists(tmp_ver): os.remove(tmp_ver)
        reactor.callFromThread(self._onUpdate, online, inst_url)

    def _onUpdate(self, online, inst_url):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not online:
            show_message_compat(self.session, "Nie udało się sprawdzić wersji.", MessageBox.TYPE_ERROR)
            return
        if online != VER:
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._do_update(inst_url) if ans else None,
                                          MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else:
            show_message_compat(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _do_update(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        console_screen_open(self.session, "Aktualizacja MyUpdater", [cmd], close_on_finish=True)

    def runInfo(self):
        txt = ("MyUpdater (Mod 2025) {}\n\n"
               "Przebudowa: Paweł Pawełek\n"
               "Wtyczka bazuje na PanelAIO.\n\n"
               "Oryginał: Sancho, gut").format(VER)
        self.session.open(MessageBox, txt, MessageBox.TYPE_INFO)

# ----------- plugin entry -----------------------------
def main(session, **kwargs):
    session.open(Fantastic)

def Plugins(**kwargs):
    return [PluginDescriptor(name="MyUpdater",
                            description="MyUpdater Mod {} (PanelAIO)".format(VER),
                            where=PluginDescriptor.WHERE_PLUGINMENU,
                            icon="myupdater.png", fnc=main)]
