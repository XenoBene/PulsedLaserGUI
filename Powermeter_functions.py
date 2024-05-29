from pylablib.devices.Thorlabs import PM160


class PM():

    def __init__(self):
        super().__init__()

        self._connect_button_is_checked = False

    def connect_pm(self, visa):
        if not self._connect_button_is_checked:
            self.pm = PM160(visa)
            self._connect_button_is_checked = True
        else:
            self.pm.close()
            self._connect_button_is_checked = False

    def get_power(self):
        return self.pm.get_power()

    def set_wavelength(self, wl):
        self.pm.set_wavelength(wl)

    def enable_autorange(self, enable):
        self.pm.enable_autorange(enable=enable)

    def set_range(self, range):
        self.pm.set_range(rng=range)
