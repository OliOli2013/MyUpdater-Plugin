def install_archive(session, title, url, callback_on_finish=None, force_mode=None):
    """
    force_mode: None | "picons" | "channels"
    Autowykrywa typ archiwum po zawartości. Dla .zip list kanałów rozpakowuje do /etc/enigma2.
    """
    log_message("--- install_archive START ---")
    log_message("URL received: {}".format(url))
    log_message("Title received: {}".format(title))
    log_message("Force mode: {}".format(force_mode))

    prepare_tmp_dir()
    tmp_archive_path = os.path.join(PLUGIN_TMP_PATH, os.path.basename(url))

    # 1) Pobranie ARCHIWUM (w Pythonie, żeby móc je zbadać przed budową komendy)
    try:
        cmd = 'wget --no-check-certificate -O "{}" "{}"'.format(tmp_archive_path, url)
        log_message("Downloading archive: {}".format(cmd))
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0 or not fileExists(tmp_archive_path) or os.path.getsize(tmp_archive_path) == 0:
            show_message_compat(session, "Nie udało się pobrać archiwum.", MessageBox.TYPE_ERROR)
            log_message("Download failed: rc={}, err={}".format(p.returncode, err))
            if callback_on_finish:
                try: callback_on_finish()
                except Exception as e: log_message("Callback error after download fail: {}".format(e))
            return
    except Exception as e:
        log_message("Exception while downloading: {}".format(e))
        show_message_compat(session, "Błąd pobierania archiwum.", MessageBox.TYPE_ERROR)
        if callback_on_finish:
            try: callback_on_finish()
            except: pass
        return

    # 2) Ustalenie typu na podstawie zawartości (chyba że wymuszono force_mode)
    archive_lower = tmp_archive_path.lower()
    import zipfile, tarfile
    detected_mode = None  # "picons" albo "channels"

    try:
        if zipfile.is_zipfile(tmp_archive_path):
            with zipfile.ZipFile(tmp_archive_path, 'r') as zf:
                names = [n.lower() for n in zf.namelist()]
        elif archive_lower.endswith(('.tar.gz', '.tgz')) and tarfile.is_tarfile(tmp_archive_path):
            with tarfile.open(tmp_archive_path, 'r:gz') as tf:
                names = [m.name.lower() for m in tf.getmembers() if m.isfile()]
        else:
            show_message_compat(session, "Nieobsługiwany format archiwum.", MessageBox.TYPE_ERROR)
            log_message("Unsupported archive format: {}".format(tmp_archive_path))
            if callback_on_finish:
                try: callback_on_finish()
                except: pass
            return

        has_png = any(n.endswith('.png') for n in names)
        has_picon_dir = any('/picon/' in n or n.startswith('picon/') for n in names)
        has_tv = any(n.endswith('.tv') for n in names)
        has_lamedb = any('lamedb' in n for n in names)
        has_bouquets = any('bouquets.' in n for n in names)

        log_message("Archive scan -> png:{}, picon_dir:{}, tv:{}, lamedb:{}, bouquets:{}".format(
            has_png, has_picon_dir, has_tv, has_lamedb, has_bouquets
        ))

        if force_mode in ('picons', 'channels'):
            detected_mode = force_mode
        else:
            # jeśli są pliki list (tv/lamedb/bouquets) => channels; w przeciwnym razie picons
            if has_tv or has_lamedb or has_bouquets:
                detected_mode = "channels"
            elif has_png or has_picon_dir:
                detected_mode = "picons"
            else:
                # domyślnie spróbuj jako "channels" (bezpieczniej dla systemu)
                detected_mode = "channels"

        log_message("Detected mode: {}".format(detected_mode))
    except Exception as e:
        log_message("Archive content detection failed: {}".format(e))
        # Jeśli nie udało się wykryć – lepiej zainstalować jako listę (do /etc/enigma2), a nie zaśmiecać picon
        detected_mode = force_mode or "channels"

    # 3) Zbuduj właściwą komendę do konsoli (tylko rozpakowanie + sprzątanie)
    if detected_mode == "picons":
        picon_path = "/usr/share/enigma2/picon"
        nested_picon_path = os.path.join(picon_path, "picon")
        full_command = (
            "echo '>>> Tworzenie katalogu picon (jeśli nie istnieje): {picon_path}' && "
            "mkdir -p {picon_path} && "
            "echo '>>> Rozpakowywanie picon (unzip/tar)...' && "
            "{extract_cmd} && "
            "echo '>>> Sprawdzanie zagnieżdżonego katalogu...' && "
            "if [ -d \"{nested_path}\" ]; then echo '> Przenoszenie z {nested_path} do {picon_path}'; mv -f \"{nested_path}\"/* \"{picon_path}/\"; rmdir \"{nested_path}\"; else echo '> Brak zagnieżdżonego katalogu.'; fi && "
            "rm -f \"{archive_path}\" && "
            "echo '>>> Picony zostały pomyślnie zainstalowane.' && sleep 3"
        ).format(
            picon_path=picon_path,
            nested_path=nested_picon_path,
            archive_path=tmp_archive_path,
            extract_cmd=("unzip -o -q \"{a}\" -d \"{dst}\" || tar -xzf \"{a}\" -C \"{dst}\""
                         ).format(a=tmp_archive_path, dst=picon_path)
        )
    else:  # CHANNELS
        target_dir = "/etc/enigma2/"
        extract_dir = os.path.join(PLUGIN_TMP_PATH, "extract")
        full_command = (
            "echo '>>> Przygotowanie katalogów...' && "
            "mkdir -p {extract_dir} {target_dir} && "
            "echo '>>> Rozpakowywanie listy do katalogu tymczasowego...' && "
            "(unzip -o -q \"{archive_path}\" -d \"{extract_dir}\" || tar -xzf \"{archive_path}\" -C \"{extract_dir}\") && "
            "echo '>>> Kopiowanie plików list (.tv, lamedb*, bouquets.*) do {target_dir} ...' && "
            "find \"{extract_dir}\" -maxdepth 5 -type f \\( -name '*.tv' -o -name 'lamedb*' -o -name 'bouquets.*' \\) -print -exec cp -f {{}} {target_dir} \\; && "
            "rm -rf \"{extract_dir}\" && "
            "rm -f \"{archive_path}\" && "
            "echo '>>> Lista kanałów została pomyślnie zainstalowana.' && sleep 3"
        ).format(
            extract_dir=extract_dir,
            target_dir=target_dir,
            archive_path=tmp_archive_path
        )

    def run_callback_safely():
        if callback_on_finish:
            log_message("Console finished, executing callback.")
            try:
                callback_on_finish()
            except Exception as cb_e:
                log_message("!!! EXCEPTION in callback after console finish: {}".format(cb_e))

    console_screen_open(session, title, [full_command], callback=run_callback_safely, close_on_finish=True)
    log_message("--- install_archive END ---")
