from PyQt6 import QtCore
from pylablib.devices import Newport
import time
import math
import numpy as np


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
        self.steps = steps
        self.velocity = velocity
        self.wait = wait

    def autoscan(self):
        """Gesamte Logik des UV-Autoscans"""
        self.keep_running = True
        while self.keep_running:
            if self.going_right:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=self.steps)
            else:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=-self.steps)
            time.sleep(math.ceil(self.steps / self.velocity))
            time.sleep(int(self.wait))

            uv_power = self.rp.measure_power()
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
            if self.threshold_power * 0.8 > uv_power:
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
    def __init__(self, wlm, rp, axis, addr):
        self.wlm = wlm
        self.rp = rp
        self.axis = axis
        self.addr = addr
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False
        self.stage = Newport.Picomotor8742

    def connect_piezos(self):
        """Soll Piezos verbinden bzw. disconnecten"""
        if not self._connect_button_is_checked:
            # print(Newport.get_usb_devices_number_picomotor())
            self.stage = Newport.Picomotor8742()
            # self.stage.move_by(axis=1, addr=1, steps=-100)
            print("an")
            self._connect_button_is_checked = True
        else:
            # self.stage.close()
            print("aus")
            self.stage.close()
            self._connect_button_is_checked = False

    def move_by(self, steps):
        """Bewegt den Motor um steps (+ oder -)"""
        self.stage.move_by(axis=self.axis, addr=self.addr, steps=steps)

    def change_autoscan_parameters(self, velocity, steps, wait):
        self.autoscan_velocity = velocity
        self.autoscan_steps = steps
        self.autoscan_wait = wait

    def change_velocity(self, velocity):
        self.stage.setup_velocity(axis=self.axis, addr=self.addr, speed=velocity)

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
