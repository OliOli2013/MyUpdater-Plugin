# -*- coding: utf-8 -*-
# MyUpdater Enhanced - Poprawiona inicjalizacja
# Ten plik jest wymagany przez Enigma2 do prawidłowego działania wtyczki

from . import plugin  # <-- POPRAWKA: Zmieniono 'plugin_enhanced' na 'plugin'

# Wersja wtyczki
__version__ = "V5 Enhanced"
__author__ = "Paweł Pawełek, Sancho, gut"
__description__ = "MyUpdater Enhanced - kompatybilny z OpenATV/OpenPLI"

# Eksportujemy główną funkcję
def main(session, **kwargs):
    return plugin.main(session, **kwargs)

# Eksportujemy deskryptor wtyczki
def Plugins(**kwargs):
    return plugin.Plugins(**kwargs)
