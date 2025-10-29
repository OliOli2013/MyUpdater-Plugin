# -*- coding: utf-8 -*-
# MyUpdater Enhanced - Poprawiona inicjalizacja V5

from . import plugin  # <-- Ta linia importuje "plugin.py" (już po zmianie nazwy)

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
