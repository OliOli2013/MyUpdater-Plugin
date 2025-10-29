# -*- coding: utf-8 -*-
# MyUpdater Enhanced - Inicjalizacja wtyczki
# Ten plik jest wymagany przez Enigma2 do prawidłowego działania wtyczki

from . import plugin_enhanced

# Wersja wtyczki
__version__ = "V5 Enhanced"
__author__ = "Paweł Pawełek, Sancho, gut"
__description__ = "MyUpdater Enhanced - kompatybilny z OpenATV/OpenPLI"

# Eksportujemy główną funkcję
def main(session, **kwargs):
    return plugin_enhanced.main(session, **kwargs)

# Eksportujemy deskryptor wtyczki
def Plugins(**kwargs):
    return plugin_enhanced.Plugins(**kwargs)