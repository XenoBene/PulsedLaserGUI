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
        """Connects/Disconnects the powermeter depending on
        if the Connect Button is already pressed or not.
        Upon connection, the wavelength of the PM is read and
        displayed in the GUI.

        Args:
            visa (str): VISA string of the powermeter
        """
        if not self._connect_button_is_checked:
            self.pm = Thorlabs.PM160(visa)
            self._connect_button_is_checked = True
            self.updateWavelength.emit(np.round(self.get_wavelength() * 1e9, 2))
        else:
            self.pm.close()
            del self.pm
            self._connect_button_is_checked = False

    def get_power(self):
        """Uses the get_power method of the Thorlabs
        pylablib library. Updates the measured power
        in the GUI.

        Returns:
            float: Measured power [W] by the pwoermeter
        """
        power = self.pm.get_power()
        self.updatePower.emit(power)
        return power

    def set_wavelength(self, wl):
        """Sets the wavelength of the powermeter. If the wavelength
        is not between 250 and 1100 nm, nothing happens.

        Args:
            wl (str): Desired wavelength. It is currently a string because
            of the way the GUI works.
        """
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
        """Enables/disables the autorange of the power range of the
        powermeter. If enable=True, the powermeter switches to a higher range
        if the measured power exceeds the current range.

        Args:
            enable (bool): If True, enables autorange. If False, disables it.
        """
        self.pm.enable_autorange(enable=enable)

    def set_range(self, range):
        """Sets the power range of the powermeter to the highest
        possible range, so that the value of 'range' still lies
        in that range.

        Args:
            range (float): Desired power that should be measurable with the powermeter
        """
        self.pm.set_range(rng=range)

    def get_wavelength(self):
        """Gets the set wavelength of the powermeter.

        Returns:
            float: Wavelength that the pm is currently set to.
        """
        wavelength = self.pm.get_wavelength()
        return wavelength
