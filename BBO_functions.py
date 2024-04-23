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
    def __init__(self):
        # self.wlm = wlm
        self._connect_button_is_checked = False
        self.stage = Newport.Picomotor8742

    def connect_piezos(self):
        """Soll Piezos verbinden bzw. disconnecten"""
        if not self._connect_button_is_checked:
            print(Newport.get_usb_devices_number_picomotor())
            self.stage = Newport.Picomotor8742()
            # self.stage.move_by(axis=1, addr=1, steps=-100)
            print("an")
            self._connect_button_is_checked = True
        else:
            # self.stage.close()
            print("aus")
            self.stage.close()
            self._connect_button_is_checked = False

    def toogle_autoscan(self):
        """Startet den WorkerBBO für den Autoscan"""
        pass
