from PyQt6 import QtCore
from ThorlabsRotationStage import Stage
from pylablib.devices.Thorlabs.base import ThorlabsBackendError
import numpy as np
import pandas as pd


class ASE(QtCore.QObject):
    autoscan_status = QtCore.pyqtSignal(bool)
    update_wl_pos = QtCore.pyqtSignal(tuple)

    def __init__(self, wlm):
        super().__init__()
        self.wlm = wlm
        self.cal_par = pd.read_csv("lastused_calpar.csv", delimiter=';')
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False

    def connect_rotationstage(self, serial):
        if not self._connect_button_is_checked:
            try:
                self._connect_button_is_checked = True
                self.stage = Stage(serial_nr=serial, backlash=0)
                self.stage.calmode = True  # Sets the cal mode to Kal 1
                if not self.stage.is_homed():
                    # TODO: Richtige Nachricht bzw. auto Homing?
                    print("Motor is not homed! Please press 'Home'")
                else:
                    print(f"Motor {self.stage.serial_nr} connected.")
                    print(f"Motor is at the position {self.stage.to_degree(self.stage.get_position())}.")
                self.stage.setup_velocity(max_velocity=self.stage.to_steps(10))
            except ThorlabsBackendError:
                print("Device not found")
        else:
            try:
                self._connect_button_is_checked = False
                self.stage.close()
                print("Motor disconnected")
            except AttributeError:
                print("No stage was connected")

    def move_to_start(self):
        wl = np.round(self.wlm.GetWavelength(1), 6)
        self.stage.calmode = self.stage.change_angle(wl, self.stage.calmode, self.cal_par)
        pos = self.stage.to_degree(self.stage.get_position())
        print(f"Current Wavelength: {wl}")
        print(f"Current Angle: {pos}")
        print("--------------------------")
        self.update_wl_pos.emit((wl, pos))

    def homing_motor(self):
        self.stage.setup_homing(velocity=self.stage.to_steps(10), offset_distance=self.stage.to_steps(4))
        self.stage.home(sync=False)

    def initiate_auto_calibration(self):
        pass

    def autoscan(self):
        self.autoscan_loop_timer = QtCore.QTimer()
        if not self._autoscan_button_is_checked:
            self.autoscan_loop_timer.timeout.connect(self.move_to_start)
            self.autoscan_loop_timer.start(10)
            self.autoscan_status.emit(True)
            self._autoscan_button_is_checked = True
        else:
            self.autoscan_loop_timer.stop()
            self.autoscan_status.emit(False)
            self._autoscan_button_is_checked = False
