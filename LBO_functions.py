from PyQt6 import QtWidgets


class WorkerLBO(QtWidgets.QObject):
    pass


class LBO:
    def __init__(self, wlm):
        self.wlm = wlm
