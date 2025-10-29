# -*- coding: utf-8 -*-
# Prosta inicjalizacja bez cyklicznych importów

__version__ = "V4 Enhanced"
__author__ = "Paweł Pawełek"

# Importujemy dopiero gdy jest to potrzebne
def main(session, **kwargs):
    from . import plugin
    return plugin.main(session, **kwargs)

def Plugins(**kwargs):
    from . import plugin
    return plugin.Plugins(**kwargs)
