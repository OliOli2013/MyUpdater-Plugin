# -*- coding: utf-8 -*-
#
# Panel AIO – minimalny, pewny plugin.py z poprawnym rozróżnianiem
# archiwów list kanałów i piconów.
#
# Zależności: unzip, tar, wget
#
from __future__ import print_function

import os
import re
import time
import traceback
import subprocess

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Console import Console as ConsoleScreen
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS
from Plugins.Plugin import PluginDescriptor

# --- KONFIGUROWALNE ŹRÓDŁA ----------------------------------------------------

# Przykładowa lista bzyk83 (podmień na swoją, jeśli chcesz):
CHANNEL_BZYK83_URL = "https://enigma2.hswg.pl/wp-content/uploads/2025/05/Lista-bzyk83-hb-13E-05.05.2025.zip"

# Przykładowe picony 220x132 (ZIP/TAR – narzędzie wykryje samo):
PICONS_URL = "https://picons.xyz/downloads/picons-220x132.zip"

# --- ŚCIEŻKI I STAŁE -----------------------------------------------------------

PLUGIN_TMP_PATH = "/tmp/MyUpdater"
LOG_PATH = "/tmp/panel_aio.log"

# --- POMOCNICZE ----------------------------------------------------------------

def log_message(msg):
    try:
        with open(LOG_PATH, "a") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass

def show_message_compat(session, text, mtype=MessageBox.TYPE_INFO, timeout=5):
    try:
        session.openWithCallback(lambda *_: None, MessageBox, text, type=mtype, timeout=timeout)
    except Exception as e:
        log_message("show_message_compat error: %s" % e)

def prepare_tmp_dir():
    try:
        if not os.path.isdir(PLUGIN_TMP_PATH):
            os.makedirs(PLUGIN_TMP_PATH)
    except Exception as e:
        log_message("prepare_tmp_dir error: %s" % e)

def console_screen_open(session, title, cmd_list, callback=None, close_on_finish=True):
    try:
        c = session.open(ConsoleScreen, title=title, cmdlist=cmd_list, closeOnSuccess=close_on_finish)
        if callback:
            c.finishedCallback = callback
    except Exception as e:
        log_message("console_screen_open error: %s" % e)

def reload_settings_python(session):
    """
    Delikatny reload list/bukietów bez restartu GUI.
    """
    try:
        from enigma import eDVBDB
        eDVBDB.getInstance().reloadBouquets()
        eDVBDB.getInstance().reloadServicelist()
        show_message_compat(session, "Przeładowano listy kanałów.", MessageBox.TYPE_INFO, timeout=4)
        log_message("Bouquets + Servicelist reloaded.")
    except Exception as e:
        log_message("reload_settings_python failed: %s" % e)

# --- KLUCZOWA POPRAWKA: instalacja archiwum -----------------------------------

def install_archive(session, title, url, callback_on_finish=None, force_mode=None):
    """
    force_mode: None | "picons" | "channels"
    Autowykrywanie typu archiwum po ZAWARTOŚCI (nie po rozszerzeniu).
    - channels -> /etc/enigma2/
    - picons   -> /usr/share/enigma2/picon
    """
    log_message("--- install_archive START ---")
    log_message("URL: %s" % url)
    log_message("Title: %s" % title)
    log_message("Force mode: %s" % force_mode)

    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))

    # 1) Pobranie archiwum
    try:
        dl_cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(tmp_archive_path, url)
        log_message("Downloading: %s" % dl_cmd)
        p = subprocess.Popen(dl_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0 or not fileExists(tmp_archive_path) or os.path.getsize(tmp_archive_path) == 0:
            show_message_compat(session, "Nie udało się pobrać archiwum.", MessageBox.TYPE_ERROR)
            log_message("Download failed rc=%s err=%s" % (p.returncode, err))
            if callback_on_finish:
                try: callback_on_finish()
                except Exception as e: log_message("Callback err after fail: %s" % e)
            return
    except Exception as e:
        log_message("Exception while downloading: %s" % e)
        show_message_compat(session, "Błąd pobierania archiwum.", MessageBox.TYPE_ERROR)
        if callback_on_finish:
            try: callback_on_finish()
            except: pass
        return

    # 2) Detekcja zawartości
    archive_lower = tmp_archive_path.lower()
    detected_mode = None
    names = []
    try:
        import zipfile, tarfile
        if zipfile.is_zipfile(tmp_archive_path):
            with zipfile.ZipFile(tmp_archive_path, 'r') as zf:
                names = [n.lower() for n in zf.namelist()]
        elif archive_lower.endswith(('.tar.gz', '.tgz', '.tar.xz', '.txz', '.tar.bz2', '.tbz2')):
            # tarfile.is_tarfile rozpozna .tar.*, ale rozpakujemy w shellu
            import tarfile as _tar
            if _tar.is_tarfile(tmp_archive_path):
                with _tar.open(tmp_archive_path, 'r:*') as tf:
                    names = [m.name.lower() for m in tf.getmembers() if m.isfile()]
        else:
            # nieznany format – przerwij bezpiecznie
            show_message_compat(session, "Nieobsługiwany format archiwum.", MessageBox.TYPE_ERROR)
            log_message("Unsupported archive: %s" % tmp_archive_path)
            if callback_on_finish:
                try: callback_on_finish()
                except: pass
            return

        has_png = any(n.endswith('.png') for n in names)
        has_picon_dir = any('/picon/' in n or n.startswith('picon/') for n in names)
        has_tv = any(n.endswith('.tv') for n in names)
        has_lamedb = any(n.endswith('lamedb') or 'lamedb.' in n for n in names)
        has_bouquets = any('bouquets.' in n for n in names)

        log_message("Archive scan -> png:%s picon_dir:%s tv:%s lamedb:%s bouquets:%s" %
                    (has_png, has_picon_dir, has_tv, has_lamedb, has_bouquets))

        if force_mode in ('picons', 'channels'):
            detected_mode = force_mode
        else:
            if has_tv or has_lamedb or has_bouquets:
                detected_mode = "channels"
            elif has_png or has_picon_dir:
                detected_mode = "picons"
            else:
                detected_mode = "channels"  # bezpieczniej
        log_message("Detected mode: %s" % detected_mode)
    except Exception as e:
        log_message("Detection failed: %s" % e)
        detected_mode = force_mode or "channels"

    # 3) Budowa poleceń konsoli
    if detected_mode == "picons":
        picon_path = "/usr/share/enigma2/picon"
        nested_picon_path = os.path.join(picon_path, "picon")
        extract_cmd = (
            '(unzip -o -q "{a}" -d "{dst}" || '
            'tar -xpf "{a}" -C "{dst}")'
        ).format(a=tmp_archive_path, dst=picon_path)

        full_command = [
            'echo ">>> Tworzenie katalogu picon (jeśli nie istnieje): {p}"'.format(p=picon_path),
            'mkdir -p "{p}"'.format(p=picon_path),
            'echo ">>> Rozpakowywanie picon (unzip/tar)..."',
            extract_cmd,
            'echo ">>> Sprawdzanie zagnieżdżonego katalogu..."',
            'if [ -d "{nested}" ]; then echo "> Przenoszenie z {nested} do {dst}"; mv -f "{nested}"/* "{dst}/"; rmdir "{nested}"; else echo "> Brak zagnieżdżonego katalogu."; fi'.format(
                nested=nested_picon_path, dst=picon_path),
            'rm -f "{a}"'.format(a=tmp_archive_path),
            'echo ">>> Picony zostały pomyślnie zainstalowane."',
            'sleep 2'
        ]
    else:
        target_dir = "/etc/enigma2/"
        extract_dir = os.path.join(PLUGIN_TMP_PATH, "extract")
        extract_cmd = '(unzip -o -q "{a}" -d "{ext}" || tar -xpf "{a}" -C "{ext}")'.format(
            a=tmp_archive_path, ext=extract_dir
        )
        copy_cmd = (
            'find "{ext}" -maxdepth 6 -type f \\( -name "*.tv" -o -name "lamedb" -o -name "lamedb.*" -o -name "bouquets.*" \\) '
            '-print -exec cp -f {{}} "{dst}" \\;'
        ).format(ext=extract_dir, dst=target_dir)

        full_command = [
            'echo ">>> Przygotowanie katalogów..."',
            'mkdir -p "{ext}" "{dst}"'.format(ext=extract_dir, dst=target_dir),
            'echo ">>> Rozpakowywanie listy do katalogu tymczasowego..."',
            extract_cmd,
            'echo ">>> Kopiowanie plików list (.tv, lamedb*, bouquets.*) do {dst} ..."'.format(dst=target_dir),
            copy_cmd,
            'rm -rf "{ext}"'.format(ext=extract_dir),
            'rm -f "{a}"'.format(a=tmp_archive_path),
            'echo ">>> Lista kanałów została pomyślnie zainstalowana."',
            'sleep 2'
        ]

    def run_callback_safely():
        if callback_on_finish:
            log_message("Console finished -> callback")
            try:
                callback_on_finish()
            except Exception as cb_e:
                log_message("Callback exception: %s" % cb_e)

    console_screen_open(session, title, [" && ".join(full_command)], callback=run_callback_safely, close_on_finish=True)
    log_message("--- install_archive END ---")

# --- Ekrany GUI ----------------------------------------------------------------

class AIOStart(Screen):
    skin = """
    <screen name="AIOStart" position="center,center" size="880,520" title="Panel AIO – Listy / Picony">
        <widget name="menu" position="40,80" size="800,360" scrollbarMode="showOnDemand" />
        <widget name="info" position="40,460" size="800,40" font="Regular;20" />
    </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session

        self["menu"] = MenuList([
            ("Zainstaluj listę kanałów – bzyk83 (HB 13E)", "install_bzyk83"),
            ("Zainstaluj picony 220x132 (picons.xyz)", "install_picons"),
        ])
        self["info"] = Label("Czerwony: PL  •  Zielony: EN  •  Żółty: Restart GUI  •  Niebieski: Wyjście")

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.ok,
            "cancel": self.close,
            "red": self.lang_pl,
            "green": self.lang_en,
            "yellow": self.restart_gui,
            "blue": self.close
        }, -1)

    # Akcje
    def ok(self):
        sel = self["menu"].getCurrent()
        if not sel:
            return
        key = sel[1]
        if key == "install_bzyk83":
            self.runChannelListSelected("Bzyk83 Hotbird 13E", CHANNEL_BZYK83_URL)
        elif key == "install_picons":
            self.runPiconGitHub("Picon 220x132", PICONS_URL)

    def lang_pl(self):
        show_message_compat(self.session, "Język PL – (placeholder)", timeout=3)

    def lang_en(self):
        show_message_compat(self.session, "Language EN – (placeholder)", timeout=3)

    def restart_gui(self):
        # soft prompt; zostawiamy użytkownikowi decyzję
        def _do(ans):
            if ans:
                cmd = 'init 4; sleep 2; init 3'
                console_screen_open(self.session, "Restart GUI", [cmd], callback=None, close_on_finish=True)
        self.session.openWithCallback(_do, MessageBox, "Zrestartować GUI (Enigma2)?", type=MessageBox.TYPE_YESNO)

    # --- Wywołania instalacji --------------------------------------------------

    def runChannelListSelected(self, title, url):
        def _after():
            reload_settings_python(self.session)
        install_archive(self.session, title, url, callback_on_finish=_after, force_mode="channels")

    def runPiconGitHub(self, title, url):
        install_archive(self.session, title, url, callback_on_finish=None, force_mode="picons")

# --- Wejścia pluginu -----------------------------------------------------------

def main(session, **kwargs):
    session.open(AIOStart)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name="Panel AIO – Listy, Picony",
        where=PluginDescriptor.WHERE_PLUGINMENU,
        description="Instalacja list kanałów i piconów (z poprawną detekcją archiwów).",
        icon="plugin.png",
        fnc=main
    )]
