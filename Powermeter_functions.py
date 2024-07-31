from pylablib.devices import Thorlabs
from PyQt6 import QtCore
import numpy as np


class PM(QtCore.QObject):
    update_textBox = QtCore.pyqtSignal(str)
    updateWavelength = QtCore.pyqtSignal(float)
    updatePower = QtCore.pyqtSignal(float)

    def __init__(self):
        super().__init__()

        self._connect_button_is_checked = False

    def connect_pm(self, visa):
        if not self._connect_button_is_checked:
            self.pm = Thorlabs.PM160(visa)
            self._connect_button_is_checked = True
            self.updateWavelength.emit(np.round(self.get_wavelength() * 1e9, 2))
        else:
            self.pm.close()
            del self.pm
            self._connect_button_is_checked = False

    def get_power(self):
        power = self.pm.get_power()
        self.updatePower.emit(power)
        return power

    def set_wavelength(self, wl):
        try:
            wl = float(wl)
            wl_min = 250
            wl_max = 1100
            if wl_min < wl < wl_max:
                self.pm.set_wavelength(wl * 1e-9)
            else:
                self.update_textBox.emit(f"Wavelength has to be between {wl_min} and {wl_max} nm")
        except ValueError as e:
            self.update_textBox.emit(f"Value has to be a number: {e}")
        finally:
            self.updateWavelength.emit(np.round(self.get_wavelength() * 1e9, 2))

    def enable_autorange(self, enable):
        self.pm.enable_autorange(enable=enable)

    def set_range(self, range):
        self.pm.set_range(rng=range)

    def get_wavelength(self):
        wavelength = self.pm.get_wavelength()
        return wavelength
