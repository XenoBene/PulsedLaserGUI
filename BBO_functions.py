from PyQt6 import QtCore
from pylablib.devices import Newport


class WorkerBBO(QtCore.QObject):
    def __init__(self, wlm, rp):
        super().__init__
        self.wlm = wlm
        self.rp = rp

    def autoscan(self):
        """Gesamte Logik des UV-Autoscans"""
        pass

    def stop(self):
        """Stoppt den Thread"""
        pass


class BBO:
    def __init__(self, wlm):
        self.wlm = wlm
        self._connect_button_is_checked = False
        self.stage = Newport.Picomotor8742

    def connect_piezos(self):
        """Soll Piezos verbinden bzw. disconnecten"""
        if not self._connect_button_is_checked:
            self.stage = Newport.Picomotor8742(0)
        else:
            self.stage.close()

    def toogle_autoscan(self):
        """Startet den WorkerBBO für den Autoscan"""
        pass
