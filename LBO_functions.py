from PyQt6 import QtWidgets


class WorkerLBO(QtWidgets.QObject):
    def temperature_autO(self):
        pass

    def stop(self):
        pass


class LBO:
    def __init__(self, wlm):
        self.wlm = wlm

    def connect_covesion(self):
        pass

    def disconnect_covesion(self):
        pass

    def set_temperature(self):
        pass

    def get_status(self):
        pass

    def get_status_g(self):
        pass

    def get_actTemp(self):
        pass

    def get_setTemp(self):
        pass

    def toggle_lbo_autoscan(self):
        pass
