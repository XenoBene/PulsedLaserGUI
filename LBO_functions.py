from PyQt6 import QtCore
import pyvisa
import numpy as np
import time


class WorkerLBO(QtCore.QObject):
    def __init__(self, wlm, oc):
        self.wlm = wlm
        self.oc = oc
        self.finished = QtCore.pyqtSignal()

    def temperature_auto(self):
        self.keep_running = True
        try:
            while self.keep_running:
                wl = np.round(self.wlm.GetWavelength(1), 6)
                needed_temperature = np.round(1357.13 - wl * 1.1369, 2)
                if 1028 < wl < 1032:
                    self.oc.write("!i191;"+str(needed_temperature) + ";0;0;"+str(0.033)+";0;0;BF")
                    time.sleep(1)
        except pyvisa.errors.InvalidSession as e:
            print(f"LBO scan stopped working: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        pass


class LBO:
    def __init__(self, wlm):
        self.wlm = wlm
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False

    def connect_covesion(self, port):
        if not self._connect_button_is_checked:
            try:
                self.oc = self.rm.open_resource(port, baud_rate=19200, data_bits=8,
                                                parity=pyvisa.Parity.none, flow_control=0,
                                                stop_bits=pyvisa.StopBits.one)
            except pyvisa.errors.VisaIOError as e:
                print(f"Error: {e}")
            finally:
                self._connect_button_is_checked = True
        else:
            try:
                self.oc.close()  # disables the remote control
                try:
                    self.oc.session
                except pyvisa.errors.InvalidSession:
                    pass
            except pyvisa.errors.InvalidSession:
                # TODO: Richtiger Fehler wenn Disconnect obwohl nie Connected
                pass
            finally:
                self._connect_button_is_checked = False

    def set_temperature(self, set_temp, rate):
        if ((set_temp <= 200) and (set_temp >= 15) and (rate <= 2)):
            self.oc.write("!i191;"+str(set_temp)+";0;0;" +
                          str(np.round(rate/60, 3))+";0;0;BF")
        else:
            raise ValueError(
                "Only temperatures between 15°C and 200°C and rates lower than 2°C/min allowed")

    def get_status(self):
        status = self.oc.query("!j00CB").split(";")
        return status

    def get_status_q(self):
        status = self.oc.query("!q").split(";")
        return status

    def get_actTemp(self):
        values = self.get_status()
        act_temp = float(values[1])
        return act_temp

    def get_setTemp(self):
        values = self.get_status_q()
        set_temp = values[1]
        rate = float(values[4] * 60)
        return set_temp, rate

    def toggle_lbo_autoscan(self):
        if not self._autoscan_button_is_checked:
            self.threadLBO = QtCore.QThread()
            self.workerLBO = WorkerLBO(wlm=self.wlm, oc=self.oc)
            self.workerLBO.moveToThread(self.threadLBO)
            self.threadLBO.started.connect(self.workerLBO.temperature_auto)
            # TODO: GUI updaten mit T_act und T_set
            self.workerLBO.finished.connect(self.threadLBO.quit)
            self.workerLBO.finished.connect(self.workerLBO.deleteLater)
            self.threadLBO.finished.connect(self.threadLBO.deleteLater)
            self.threadLBO.start()
        else:
            self.workerLBO.stop()
