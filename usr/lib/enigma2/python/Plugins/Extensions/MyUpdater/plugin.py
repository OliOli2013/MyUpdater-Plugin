# -*- coding: utf-8 -*-
#
# Panel AIO – naprawiona instalacja LIST / PICON
#
# Zgodne z Python 2/3 i większością image (OpenPLi / OpenATV).
# Główna poprawka: rozpoznawanie typu archiwum po ZAWARTOŚCI + force_mode.
#
from __future__ import print_function

import os
import sys
import time
import zipfile
import tarfile
import subprocess

from Plugins.Plugin import PluginDescriptor

# E2 GUI
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Console import Console as ScreenConsole

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from Tools.Directories import fileExists

# --- KONFIG / STAŁE ---------------------------------------------------------

PLUGIN_NAME = "Panel AIO – Listy/Picon"
PLUGIN_TMP_PATH = "/tmp/MyUpdater"

# Przykładowe źródła – PODMIEŃ WG POTRZEB
CHANNEL_LISTS = [
    # bzyk83 Hotbird (przykładowy link – podmień na aktualny)
    ("Bzyk83 Hotbird 13E (ZIP)", "https://enigma2.hswg.pl/wp-content/uploads/2025/05/Lista-bzyk83-hb-13E-05.05.2025.zip"),
    # Możesz dodać więcej pozycji...
]

# Picons – przykładowy ZIP (możesz wskazać swoje archiwum z png)
PICONS_SOURCES = [
    ("Picons 220x132 (przykład)", "https://picons.xyz/downloads/srp-bq-220x132.tar.gz"),
]

# --- NARZĘDZIA / LOG --------------------------------------------------------

def log_message(msg):
    try:
        t = time.strftime("%Y-%m-%d %H:%M:%S")
        line = "[PanelAIO] {} {}".format(t, msg)
        print(line)
        with open("/tmp/panel_aio.log", "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def show_message_compat(session, text, mtype=MessageBox.TYPE_INFO, timeout=4):
    try:
        session.openWithCallback(lambda *_: None, MessageBox, text, type=mtype, timeout=timeout)
    except Exception as e:
        log_message("show_message_compat EXC: {}".format(e))


def prepare_tmp_dir():
    try:
        if not os.path.isdir(PLUGIN_TMP_PATH):
            os.makedirs(PLUGIN_TMP_PATH)
    except Exception as e:
        log_message("prepare_tmp_dir EXC: {}".format(e))


def console_screen_open(session, title, cmd_list, callback=None, close_on_finish=True):
    """
    Otwórz wbudowaną konsolę E2 i wykonaj listę komend.
    """
    def _after(ret=None):
        if callback:
            try:
                callback()
            except Exception as e:
                log_message("callback EXC: {}".format(e))

    try:
        session.openWithCallback(_after, ScreenConsole, title, cmd_list, closeOnSuccess=close_on_finish)
    except Exception as e:
        log_message("console_screen_open EXC: {}".format(e))
        # awaryjnie wykonaj w tle
        for c in cmd_list:
            subprocess.call(c, shell=True)
        _after()


def reload_settings_python(session):
    """
    Delikatny reload list przez WebIf (jeśli dostępne).
    """
    cmd = (
        "echo '>>> Przeładowanie list (WebIf jeśli dostępne)...' && "
        "(command -v wget >/dev/null 2>&1 && "
        " wget -qO- http://127.0.0.1/web/servicelistreload?mode=0 >/dev/null 2>&1 && "
        " echo '>>> OK' ) || echo '>>> WebIf niedostępne – pomiń' "
    )
    console_screen_open(session, "Przeładowanie list", [cmd])


# --- KLUCZOWA POPRAWIONA FUNKCJA -------------------------------------------

def install_archive(session, title, url, callback_on_finish=None, force_mode=None):
    """
    Poprawiona instalacja archiwum.
    - Autowykrywanie po zawartości: *.tv / lamedb* / bouquets.* => channels (/etc/enigma2)
                                  *.png lub katalog 'picon/'     => picons   (/usr/share/enigma2/picon)
    - Można wymusić tryb: force_mode="channels" lub "picons"
    """
    log_message("--- install_archive START ---")
    log_message("URL: {}".format(url))
    log_message("Force mode: {}".format(force_mode))

    prepare_tmp_dir()
    archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))

    # 1) Pobranie
    dl_cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(archive_path, url)
    def _after_download(_=None):
        if not fileExists(archive_path) or os.path.getsize(archive_path) == 0:
            show_message_compat(session, "Nie udało się pobrać archiwum.", MessageBox.TYPE_ERROR)
            if callback_on_finish:
                try: callback_on_finish()
                except: pass
            return

        # 2) Detekcja zawartości
        detected_mode = None
        try:
            names = []
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    names = [n.lower() for n in zf.namelist()]
            elif archive_path.lower().endswith((".tar.gz", ".tgz")) and tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:gz") as tf:
                    names = [m.name.lower() for m in tf.getmembers() if m.isfile()]
            else:
                show_message_compat(session, "Nieobsługiwany format archiwum.", MessageBox.TYPE_ERROR)
                if callback_on_finish:
                    try: callback_on_finish()
                    except: pass
                return

            has_png = any(n.endswith(".png") for n in names)
            has_picon_dir = any("/picon/" in n or n.startswith("picon/") for n in names)
            has_tv = any(n.endswith(".tv") for n in names)
            has_lamedb = any("lamedb" in n for n in names)
            has_bouquets = any("bouquets." in n for n in names)

            log_message("Scan -> png:{} picon_dir:{} tv:{} lamedb:{} bouquets:{}".format(
                has_png, has_picon_dir, has_tv, has_lamedb, has_bouquets))

            if force_mode in ("picons", "channels"):
                detected_mode = force_mode
            else:
                if has_tv or has_lamedb or has_bouquets:
                    detected_mode = "channels"
                elif has_png or has_picon_dir:
                    detected_mode = "picons"
                else:
                    detected_mode = "channels"  # bezpieczniejszy domyślny

        except Exception as e:
            log_message("Detection EXC: {}".format(e))
            detected_mode = force_mode or "channels"

        # 3) Budowa komendy
        if detected_mode == "picons":
            picon_path = "/usr/share/enigma2/picon"
            nested_picon_path = os.path.join(picon_path, "picon")
            extract_cmd = '(unzip -o -q "{a}" -d "{dst}" || tar -xzf "{a}" -C "{dst}")'.format(
                a=archive_path, dst=picon_path)

            full_cmd = [
                'echo ">>> Tworzenie katalogu picon (jeśli nie istnieje): {p}" && '
                'mkdir -p "{p}" && '
                'echo ">>> Rozpakowywanie archiwum picon (unzip/tar)..." && '
                '{extract} && '
                'echo ">>> Sprawdzanie zagnieżdżonego katalogu..." && '
                'if [ -d "{nested}" ]; then '
                'echo "> Przenoszenie z {nested} do {p}"; '
                'mv -f "{nested}"/* "{p}/"; rmdir "{nested}"; '
                'else echo "> Brak zagnieżdżonego katalogu."; fi && '
                'rm -f "{a}" && '
                'echo ">>> Picony zostały pomyślnie zainstalowane." && sleep 2'
            .format(p=picon_path, extract=extract_cmd, nested=nested_picon_path, a=archive_path)]
        else:
            target_dir = "/etc/enigma2"
            extract_dir = os.path.join(PLUGIN_TMP_PATH, "extract")
            full_cmd = [
                'echo ">>> Przygotowanie katalogów..." && '
                'mkdir -p "{ed}" "{td}" && '
                'echo ">>> Rozpakowywanie listy do katalogu tymczasowego..." && '
                '(unzip -o -q "{a}" -d "{ed}" || tar -xzf "{a}" -C "{ed}") && '
                'echo ">>> Kopiowanie plików list (.tv, lamedb*, bouquets.*) do {td} ..." && '
                'find "{ed}" -maxdepth 5 -type f \\( -name "*.tv" -o -name "lamedb*" -o -name "bouquets.*" \\) '
                '-print -exec cp -f {{}} "{td}" \\; && '
                'rm -rf "{ed}" && rm -f "{a}" && '
                'echo ">>> Lista kanałów została pomyślnie zainstalowana." && sleep 2'
            .format(ed=extract_dir, td=target_dir, a=archive_path)]

        def _finalize():
            if callback_on_finish:
                try:
                    callback_on_finish()
                except Exception as e:
                    log_message("callback_on_finish EXC: {}".format(e))

        console_screen_open(session, title, full_cmd, callback=_finalize, close_on_finish=True)

    # uruchom pobieranie w konsoli, a po nim wykrywanie/instalacja
    console_screen_open(session, "Pobieranie: {}".format(title), [dl_cmd], callback=_after_download, close_on_finish=True)


# --- EKRANY -----------------------------------------------------------------

class RootMenu(Screen):
    skin = """
    <screen name="PanelAIO" position="center,center" size="900,560" title="%s">
        <widget name="info" position="30,20" size="840,40" font="Regular;26" transparent="1"/>
        <widget name="menu" position="30,80" size="840,420" scrollbarMode="showOnDemand"/>
        <widget name="hint" position="30,520" size="840,30" font="Regular;20" transparent="1"/>
    </screen>
    """ % PLUGIN_NAME

    def __init__(self, session):
        Screen.__init__(self, session)

        self["info"] = Label("Wybierz działanie:")
        items = [
            ("📁 Zainstaluj listę kanałów (bzyk83)", self.openChannelLists),
            ("🖼  Zainstaluj picony", self.openPicons),
            ("🔄 Przeładuj listy (WebIf)", self.reloadLists),
            ("❌ Wyjście", self.close),
        ]
        self.menu_items = items
        self["menu"] = MenuList([txt for (txt, cb) in items])
        self["hint"] = Label("OK – wybór  |  EXIT – wyjdź")

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self._ok,
            "cancel": self.close,
            "up": self._up,
            "down": self._down,
        }, -1)

    def _ok(self):
        idx = self["menu"].getSelectionIndex()
        cb = self.menu_items[idx][1]
        try:
            cb()
        except Exception as e:
            log_message("menu callback EXC: {}".format(e))
            show_message_compat(self.session, "Błąd akcji.", MessageBox.TYPE_ERROR)

    def _up(self):   self["menu"].up()
    def _down(self): self["menu"].down()

    # --- akcje
    def openChannelLists(self):
        self.session.open(ChannelListsScreen)

    def openPicons(self):
        self.session.open(PiconsScreen)

    def reloadLists(self):
        reload_settings_python(self.session)


class ChannelListsScreen(Screen):
    skin = """
    <screen name="ChannelLists" position="center,center" size="900,560" title="Listy kanałów">
        <widget name="info" position="30,20" size="840,40" font="Regular;24" transparent="1"/>
        <widget name="menu" position="30,80" size="840,420" scrollbarMode="showOnDemand"/>
        <widget name="hint" position="30,520" size="840,30" font="Regular;20" transparent="1"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["info"] = Label("Wybierz listę do instalacji:")
        self.items = list(CHANNEL_LISTS)
        self["menu"] = MenuList([t for (t, u) in self.items])
        self["hint"] = Label("OK – instaluj  |  EXIT – powrót")

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self._install,
            "cancel": self.close,
            "up": lambda: self["menu"].up(),
            "down": lambda: self["menu"].down(),
        }, -1)

    def _install(self):
        idx = self["menu"].getSelectionIndex()
        title, url = self.items[idx]
        install_archive(self.session, title, url,
                        callback_on_finish=lambda: reload_settings_python(self.session),
                        force_mode="channels")


class PiconsScreen(Screen):
    skin = """
    <screen name="Picons" position="center,center" size="900,560" title="Picony">
        <widget name="info" position="30,20" size="840,40" font="Regular;24" transparent="1"/>
        <widget name="menu" position="30,80" size="840,420" scrollbarMode="showOnDemand"/>
        <widget name="hint" position="30,520" size="840,30" font="Regular;20" transparent="1"/>
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self["info"] = Label("Wybierz paczkę piconów do instalacji:")
        self.items = list(PICONS_SOURCES)
        self["menu"] = MenuList([t for (t, u) in self.items])
        self["hint"] = Label("OK – instaluj  |  EXIT – powrót")

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self._install,
            "cancel": self.close,
            "up": lambda: self["menu"].up(),
            "down": lambda: self["menu"].down(),
        }, -1)

    def _install(self):
        idx = self["menu"].getSelectionIndex()
        title, url = self.items[idx]
        install_archive(self.session, title, url, force_mode="picons")


# --- WEJŚCIA PLUGINU -------------------------------------------------------

def main(session, **kwargs):
    session.open(RootMenu)

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            description="Listy, Picony – poprawiona instalacja",
            fnc=main
        ),
        PluginDescriptor(
            name=PLUGIN_NAME,
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            description="Listy, Picony – poprawiona instalacja",
            fnc=main
        ),
    ]
