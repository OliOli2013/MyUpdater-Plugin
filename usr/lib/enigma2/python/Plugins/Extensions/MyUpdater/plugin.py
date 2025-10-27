# -*- coding: utf-8 -*-
#  MyUpdater  V4.4  –  always install & return
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
import os, subprocess, json, datetime, traceback
from twisted.internet import reactor
from threading import Thread

PLUGIN_PATH   = os.path.dirname(os.path.realpath(__file__))
PLUGIN_TMP_PATH = "/tmp/MyUpdater/"
VER           = "V4.4"
LOG_FILE      = "/tmp/MyUpdater_install.log"

def log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("{} - {}\n".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except:
        pass

def msg(session, txt, typ=MessageBox.TYPE_INFO, timeout=6):
    log("Msg: " + txt)
    reactor.callLater(0.2, lambda: session.open(MessageBox, txt, typ, timeout=timeout))

# --- POPRAWIONA FUNKCJA 'console' ---
def console(session, title, cmdlist, onClose, autoClose=True):
    log("Console: {} | {}".format(title, " ; ".join(cmdlist)))
    try:
        # Używamy 'autoClose' (domyślnie True) zamiast 'False' na stałe
        c = session.open(Console, title=title, cmdlist=cmdlist, closeOnSuccess=autoClose)
        # ‑‑->  ALWAYS run next step  <‑‑-
        c.onClose.append(onClose)
    except Exception as e:
        log("Console exception: " + str(e))
        onClose()

def tmpdir():
    if not os.path.exists(PLUGIN_TMP_PATH):
        os.makedirs(PLUGIN_TMP_PATH)

# ----------- detect archive type --------------------
def detect_type(path):
    import zipfile, tarfile
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            return 'channels' if any('.tv' in n or '.radio' in n or 'lamedb' in n for n in names) else 'picon'
    except:
        pass
    try:
        with tarfile.open(path) as t:
            names = t.getnames()
            return 'channels' if any('.tv' in n or '.radio' in n or 'lamedb' in n for n in names) else 'picon'
    except:
        pass
    return None

# ----------- install channels  (zip OR tar.gz) ------
def install_channels(session, archive, finish):
    target = "/etc/enigma2/"
    # universal unpack
    cmd = (
        'echo ">>> Rozpakowuję listę kanałów..." && '
        'TDIR="/tmp/MyUpdater_chlist" && rm -rf "$TDIR" && mkdir -p "$TDIR" && '
        'if [[ "{a}" == *.zip ]]; then '
        '    unzip -o -q "{a}" -d "$TDIR" && '
        '    SUBDIR=$(find "$TDIR" -maxdepth 1 -mindepth 1 -type d | head -n 1) && '
        '    if [ -n "$SUBDIR" ]; then mv -f "$SUBDIR"/* "{t}"; else mv -f "$TDIR"/* "{t}"; fi && '
        '    rm -rf "$TDIR"; '
        'else '
        '    tar -xzf "{a}" -C "{t}" --strip-components=1 --overwrite; '
        'fi && '
        'rm -f "{a}" && '
        'echo ">>> Lista zainstalowana."'
    ).format(a=archive, t=target)

    def _reload():
        try:
            db = eDVBDB.getInstance()
            db.reloadServicelist()
            db.reloadBouquets()
            msg(session, "Listy kanałów przeładowane.")
        except Exception as e:
            msg(session, "Błąd przeładowania: " + str(e), MessageBox.TYPE_ERROR)
        if finish:
            finish()

    # Dodano autoClose=True
    console(session, "Instalacja Listy Kanałów", [cmd], onClose=_reload, autoClose=True)

# ----------- install picons -------------------------
def install_picons(session, archive, finish):
    p = "/usr/share/enigma2/picon"
    n = os.path.join(p, "picon")
    cmd = (
        'mkdir -p "{p}" && '
        'unzip -o -q "{a}" -d "{p}" && '
        'if [ -d "{n}" ]; then mv -f "{n}"/* "{p}"/; rmdir "{n}"; fi && '
        'rm -f "{a}" && '
        'echo ">>> Picony gotowe."'
    ).format(p=p, a=archive, n=n)
    # Dodano autoClose=True
    console(session, "Instalacja Picon", [cmd], onClose=finish, autoClose=True)

# ----------- after download -------------------------
def after_download(session, title, path, finish):
    typ = detect_type(path)
    if not typ:
        msg(session, "Nie udało się rozpoznać typu archiwum.", MessageBox.TYPE_ERROR)
        if finish:
            finish()
        return
    log("Detected: " + typ)
    if typ == 'channels':
        install_channels(session, path, finish)
    else:
        install_picons(session, path, finish)

# ----------- download + start chain ---------------
def install_archive(session, title, url, finish=None):
    log("install_archive: " + url)
    tmpdir()
    path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))
    cmd  = 'wget --no-check-certificate -O "{}" "{}"'.format(path, url)
    # Dodano autoClose=True
    console(session, title, [cmd], onClose=lambda: after_download(session, title, path, finish), autoClose=True)

# ----------- sources --------------------------------
def get_repo_lists():
    url = "https://raw.githubusercontent.com/OliOli2013/PanelAIO-Lists/main/manifest.json"
    tmp = os.path.join(PLUGIN_TMP_PATH, "manifest.json")
    lst = []
    try:
        subprocess.check_call("wget --no-check-certificate -q -T 20 -O {} {}".format(tmp, url), shell=True)
        with open(tmp, 'r') as f:
            data = json.load(f)
        for i in data:
            if i.get('url'):
                lst.append(("{} - {} ({})".format(i.get('name',''), i.get('author',''), i.get('version','')),
                           "archive:{}".format(i['url'])))
    except:
        pass
    return lst

def get_s4a_lists():
    url = "http://s4aupdater.one.pl/s4aupdater_list.txt"
    tmp = os.path.join(PLUGIN_TMP_PATH, "s4aupdater_list.txt")
    lst = []
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
            lst.append(("{} - {}".format(name, ver), "archive:{}".format(u)))
    except:
        pass
    return [i for i in lst if not any(x in i[0].lower() for x in ['bzyk', 'jakitaki'])]

# ----------- main screen ----------------------------
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
        self["menu"]    = MenuList([("1. Listy kanałów", "menu_lists"),
                                    ("2. Instaluj Softcam", "menu_softcam"),
                                    ("3. Pobierz Picony Transparent", "picons_github"),
                                    ("4. Aktualizacja Wtyczki", "plugin_update"),
                                    ("5. Informacja o Wtyczce", "plugin_info")])
        self["info"]    = Label("Wybierz opcję i naciśnij OK")
        self["version"] = Label("Wersja: " + VER)
        self["actions"] = ActionMap(["WizardActions", "DirectionActions"],
                                    {"ok": self.runMenuOption, "back": self.close}, -1)
        tmpdir()
        if fileExists(LOG_FILE):
            try: os.remove(LOG_FILE)
            except: pass
        log("MyUpdater Mod {} started".format(VER))

    def runMenuOption(self):
        sel = self["menu"].getCurrent()
        if not sel: return
        key = sel[1]
        log("Menu: " + key)
        if key == "menu_lists":      self.runChannelListMenu()
        elif key == "menu_softcam":  self.runSoftcamMenu()
        elif key == "picons_github": self.runPiconGitHub()
        elif key == "plugin_update": self.runPluginUpdate()
        elif key == "plugin_info":   self.runInfo()

    def runChannelListMenu(self):
        self["info"].setText("Pobieram listy...")
        Thread(target=self._bgLists).start()

    def _bgLists(self):
        repo = get_repo_lists()
        s4a  = get_s4a_lists()
        all  = repo + s4a
        reactor.callFromThread(self._onLists, all)

    def _onLists(self, lst):
        self["info"].setText("Wybierz opcję i naciśnij OK")
        if not lst:
            msg(self.session, "Błąd pobierania list.", MessageBox.TYPE_ERROR)
            return
        self.session.openWithCallback(self.runChannelListSelected,
                                      ChoiceBox, title="Wybierz listę do instalacji", list=lst)

    def runChannelListSelected(self, choice):
        if not choice: return
        title = choice[0]
        url   = choice[1].split(":",1)[1]
        log("Selected: {} | {}".format(title, url))
        msg(self.session, "Rozpoczynam instalację...", timeout=2)
        install_archive(self.session, title, url,
                        finish=lambda: msg(self.session, "Instalacja zakończona.", timeout=3))

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
            msg(self.session, "Instaluję {}...".format(title), timeout=2)
            # --- POPRAWKA BŁĘDU: Dodano brakujący argument 'onClose' ---
            console(self.session, title, [cmd], onClose=lambda: None, autoClose=True)

    def runPiconGitHub(self):
        url   = "https://github.com/OliOli2013/PanelAIO-Plugin/raw/main/Picony.zip"
        title = "Pobieranie Picon (Transparent)"
        log("Picons: " + url)
        msg(self.session, "Rozpoczynam pobieranie picon...", timeout=2)
        install_archive(self.session, title, url,
                        finish=lambda: msg(self.session, "Picony gotowe.", timeout=3))

    def runPluginUpdate(self):
        msg(self.session, "Sprawdzam aktualizację...", timeout=3)
        self["info"].setText("Sprawdzam wersję online...")
        Thread(target=self._bgUpdate).start()

    def _bgUpdate(self):
        ver_url = "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/version.txt"
        inst_url= "https://raw.githubusercontent.com/OliOli2013/MyUpdater-Plugin/main/installer.sh"
        tmp_ver = os.path.join(PLUGIN_TMP_PATH, "version.txt")
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
            msg(self.session, "Nie udało się sprawdzić wersji.", MessageBox.TYPE_ERROR)
            return
        if online != VER:
            txt = "Dostępna nowa wersja: {}\nTwoja: {}\nZaktualizować?".format(online, VER)
            self.session.openWithCallback(lambda ans: self._doUpdate(inst_url) if ans else None,
                                          MessageBox, txt, type=MessageBox.TYPE_YESNO, title="Aktualizacja")
        else:
            msg(self.session, "Używasz najnowszej wersji ({}).".format(VER), MessageBox.TYPE_INFO)

    def _doUpdate(self, url):
        cmd = "wget -q -O - {} | /bin/sh".format(url)
        # --- POPRAWKA BŁĘDU: Dodano brakujący argument 'onClose' ---
        console(self.session, "Aktualizacja MyUpdater", [cmd], onClose=lambda: None, autoClose=True)

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
