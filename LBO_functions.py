from PyQt6 import QtCore
import pyvisa
import numpy as np
import time

import pyvisa.constants


class WorkerLBO(QtCore.QObject):
    # Signals need to be class variables, not instance variables:
    finished = QtCore.pyqtSignal()
    update_actTemp = QtCore.pyqtSignal()
    update_setTemp = QtCore.pyqtSignal(float)

    def __init__(self, wlm, oc):
        super().__init__()
        self.wlm = wlm
        self.oc = oc

    # Funktion vorerst auskommentiert, um eine simplere Funktion zu testen
    def temperature_auto(self):
        self.keep_running = True
        try:
            while self.keep_running:
                wl = np.round(self.wlm.GetWavelength(1), 6)
                needed_temperature = np.round(1357.13 - wl * 1.1369, 2)
                if 1028 < wl < 1032:
                    self.oc.write("!i191;"+str(needed_temperature) + ";0;0;"+str(0.033)+";0;0;BF")
                    self.update_actTemp.emit()
                    self.update_setTemp.emit(needed_temperature)
                    print(f"Set temp: {needed_temperature}")
                    time.sleep(1)
        except pyvisa.errors.InvalidSession as e:
            print(f"LBO scan stopped working: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        self.keep_running = False
        print("LBO Autoscan stopped by hand")


class LBO:
    def __init__(self, wlm):
        self.wlm = wlm
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False

    def connect_covesion(self, rm, port):
        if not self._connect_button_is_checked:
            try:
                self.oc = rm.open_resource(port, baud_rate=19200, data_bits=8,
                                           parity=pyvisa.constants.Parity.none, flow_control=0,
                                           stop_bits=pyvisa.constants.StopBits.one)
                print("Covesion oven connected")
                self.read_values()
            except pyvisa.errors.VisaIOError as e:
                print(f"Device not supported: {e}")
            finally:
                self._connect_button_is_checked = True
        else:
            try:
                self.oc.close()  # disables the remote control
                try:
                    self.oc.session
                except pyvisa.errors.InvalidSession:
                    print("Device closed")
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
        try:
            status = self.oc.query("!j00CB").split(";")
            return status
        except pyvisa.errors.InvalidSession as e:
            print(f"Device closed: {e}")

    def get_status_q(self):
        try:
            status = self.oc.query("!q").split(";")
            return status
        except pyvisa.errors.InvalidSession as e:
            print(f"Device closed: {e}")

    def get_actTemp(self):
        try:
            values = self.get_status()
            self.act_temp = float(values[1])
            return self.act_temp
        except pyvisa.errors.InvalidSession as e:
            print(f"Device closed: {e}")

    def set_needed_temperature(self, needed_temperature):
        self.needed_temperature = needed_temperature

    def read_values(self):
        values = self.get_status_q()
        self.set_temp = values[1]
        self.rate = float(values[4]) * 60
        return self.set_temp, self.rate

    def toggle_autoscan(self):
        if not self._autoscan_button_is_checked:
            try:
                self.threadLBO = QtCore.QThread()
                self.workerLBO = WorkerLBO(wlm=self.wlm, oc=self.oc)
                self.workerLBO.moveToThread(self.threadLBO)
                self.threadLBO.started.connect(self.workerLBO.temperature_auto)
                self.workerLBO.update_actTemp.connect(self.get_actTemp)
                self.workerLBO.update_setTemp.connect(lambda x: self.set_needed_temperature(x))
                self.workerLBO.finished.connect(self.threadLBO.quit)
                self.workerLBO.finished.connect(self.workerLBO.deleteLater)
                self.threadLBO.finished.connect(self.threadLBO.deleteLater)
                self.threadLBO.start()
            except AttributeError as e:
                print(f"Error: {e}")
        else:
            self.workerLBO.stop()
