# MyUpdater Enhanced V5.1

Wtyczka do aktualizacji list kanałów i oprogramowania dla dekoderów Enigma2.
Jest to wersja V5.1, przebudowana przez **Paweł Pawełek** na bazie popularnej wtyczki Sancho.

## Funkcje

* Pobieranie i instalacja list kanałów z repozytorium (AIO Panel Lists) oraz S4aUpdater.
* **Nowość (Logika AIO):** Wsparcie dla instalacji list typu `archive:` (pełne paczki), `m3u:` (jako bukiet) oraz `bouquet:` (np. listy Azman).
* Instalator Softcam (Oscam/nCam) z auto-detekcją systemu.
* Instalator piconów.
* Mechanizm auto-aktualizacji wtyczki.
* Prosta diagnostyka systemu.

## Kompatybilność

Wtyczka została przetestowana i działa na popularnych obrazach, m.in.:
* OpenATV (6.4 - 7.x)
* OpenPLI

## Licencja

To oprogramowanie jest wolne, wydane na licencji **GNU General Public License v3.0**. Korzystasz z niego na własną odpowiedzialność.

## Instalacja

Aby zainstalować wtyczkę, połącz się z dekoderem przez terminal (Telnet lub SSH) i wykonaj poniższą komendę:

```bash
wget -q --no-check-certificate -O - [https://raw.githubusercontent.com/TWOJA_NAZWA/TWOJE_REPO/main/installer.sh](https://raw.githubusercontent.com/TWOJA_NAZWA/TWOJE_REPO/main/installer.sh) | /bin/sh
```

Po instalacji wymagany jest restart GUI (Interfejsu Graficznego).
