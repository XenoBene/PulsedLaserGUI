from PyQt6 import QtCore
from pylablib.devices import Newport
from pylablib.devices.Newport.base import NewportBackendError
import time
import math
import numpy as np
import redpitaya_scpi as scpi


class WorkerBBO(QtCore.QObject):
    # Signals need to be class variables, not instance variables:
    finished = QtCore.pyqtSignal()
    update_diodeVoltage = QtCore.pyqtSignal(float)

    def __init__(self, wlm, rp, stage, axis, addr, steps, velocity, wait):
        super().__init__()
        self.wlm = wlm
        self.rp = rp
        self.stage = stage
        self.axis = axis
        self.addr = addr
        self.steps = int(steps)
        self.velocity = float(velocity)
        self.wait = float(wait)

        self.going_right = True
        self.old_power = 0
        self.old_pos = self.stage.get_position(axis=self.axis, addr=self.addr)
        self.iterator_steps = 0
        self.delta_wl_start = np.round(self.wlm.GetWavelength(1), 6)
        self.threshold_power = 0
        self.start_pos = self.old_pos

    def autoscan(self):
        """Gesamte Logik des UV-Autoscans"""
        self.keep_running = True
        while self.keep_running:
            if self.going_right:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=self.steps)
            else:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=-self.steps)
            time.sleep(float(self.steps / self.velocity))
            time.sleep(float(self.wait))
            self.rp.tx_txt('ACQ:SOUR1:DATA:STA:N? 1,3000')
            buff_string = self.rp.rx_txt()
            buff_string = buff_string.strip(
                '{}\n\r').replace("  ", "").split(',')
            buff = list(map(float, buff_string))
            uv_power = np.round(np.mean(buff), 4)
            self.update_diodeVoltage.emit(uv_power)
            new_pos = self.stage.get_position(axis=self.axis, addr=self.addr)
            slope = (uv_power - self.old_power) / (new_pos - self.old_pos)
            if slope > 0:
                self.going_right = True
            else:
                self.going_right = False

            self.old_power = uv_power
            self.old_pos = new_pos

            wl = np.round(self.wlm.GetWavelength(1), 6)

            self.iterator_steps += 1
            if self.iterator_steps > 20:
                self.delta_wl_start = wl
                self.start_pos = new_pos
                self.threshold_power = uv_power
                self.iterator_steps = 0
                print("Iteratorsteps reset")

            delta_wl = wl - self.delta_wl_start
            print(f"Delta wl: {delta_wl}")

            # compare steps to calculated steps and move the necessary steps to the theoretical position,
            # if current power is a lot lower than control power
            if (self.threshold_power * 0.8 > uv_power > 0):
                if delta_wl > 0:
                    print(f"Position vor Korr1: {new_pos}")
                    calculated_steps = -delta_wl * 3233
                elif delta_wl < 0:
                    print(f"Position vor Korr2: {new_pos}")
                    calculated_steps = -delta_wl * 3500

                delta_pos = (calculated_steps - (new_pos - self.start_pos))
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=int(delta_pos))
                time.sleep(math.ceil(abs(delta_pos) / self.velocity))

                new_pos = self.stage.get_position(axis=self.axis, addr=self.addr)

                print(f"Position nach Korrektur: {new_pos}")
                self.old_pos = new_pos
                self.iterator_steps = 0
                self.threshold_power = uv_power
        self.finished.emit()

    def stop(self):
        """Stoppt den Thread"""
        self.keep_running = False


class BBO:
    def __init__(self, wlm, axis, addr):
        self.wlm = wlm
        self.axis = axis
        self.addr = addr
        self._connect_button_is_checked = False
        self._connect_rp_button_is_checked = False

    def connect_piezos(self):
        """Soll Piezos verbinden bzw. disconnecten"""
        if not self._connect_button_is_checked:
            try:
                self.stage = Newport.Picomotor8742()
                print("an")
                self._connect_button_is_checked = True
            except NewportBackendError as e:
                print(e)
                self._connect_button_is_checked = False
        else:
            print("aus")
            self.stage.close()
            # TODO: Das disconnected den Motor nicht wirklich, man kann ihn immer noch ansteuern
            self._connect_button_is_checked = False

    def connect_red_pitaya(self, ip):
        if not self._connect_rp_button_is_checked:
            self.rp = scpi.scpi(ip)
            self.rp.tx_txt('ACQ:RST')
            self.rp.acq_set(1)
            self.rp.tx_txt('ACQ:DATA:FORMAT ASCII')
            self.rp.tx_txt('ACQ:DATA:UNITS VOLTS')
            self.rp.tx_txt('ACQ:START')

            self._connect_rp_button_is_checked = True
        else:
            # TODO: Disconnect Red Pitaya
            self._connect_rp_button_is_checked = False

    def move_by(self, steps):
        """Bewegt den Motor um steps (+ oder -)"""
        try:
            self.stage.move_by(axis=self.axis, addr=self.addr, steps=steps)
        except AttributeError:
            print("Picomotor not connected!")

    def change_autoscan_parameters(self, velocity, steps, wait):
        self.autoscan_velocity = velocity
        self.autoscan_steps = steps
        self.autoscan_wait = wait

    def change_velocity(self, velocity):
        try:
            self.stage.setup_velocity(axis=self.axis, addr=self.addr, speed=velocity)
        except AttributeError:
            print("Picomotor not connected!")

    def update_uv_diode_voltage(self, voltage):
        self.diode_voltage = voltage

    def start_autoscan(self):
        """Startet den WorkerBBO für den Autoscan"""
        print("Start Autoscan")
        try:
            # Initiate QThread and WorkerLBO class:
            self.threadBBO = QtCore.QThread()
            self.workerBBO = WorkerBBO(wlm=self.wlm, rp=self.rp, stage=self.stage,
                                       axis=self.axis, addr=self.addr, steps=self.autoscan_steps,
                                       velocity=self.autoscan_velocity, wait=self.autoscan_wait)
            self.workerBBO.moveToThread(self.threadBBO)

            # Connect different methods to the signals of the thread:
            self.threadBBO.started.connect(self.workerBBO.autoscan)
            self.workerBBO.update_diodeVoltage.connect(lambda x: self.update_uv_diode_voltage(x))
            self.workerBBO.finished.connect(self.threadBBO.quit)
            self.workerBBO.finished.connect(self.workerBBO.deleteLater)
            self.threadBBO.finished.connect(self.threadBBO.deleteLater)

            # Start the thread:
            self.threadBBO.start()
        except AttributeError as e:
            print(f"Error: {e}")

    def stop_autoscan(self):
        print("Stop Autoscan")
        self.workerBBO.stop()
