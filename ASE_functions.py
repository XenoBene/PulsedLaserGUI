from PyQt6 import QtCore
from ThorlabsRotationStage import Stage
import numpy as np


class ASE(QtCore.QObject):
    def __init__(self, wlm):
        super().__init__()
        self.wlm = wlm
        self._connect_button_is_checked = False

    def connect_rotationstage(self, serial):
        if not self._connect_button_is_checked:
            self.stage = Stage(serial_nr=serial, backlash=0)
            self.stage.calmode = True  # Sets the cal mode to Kal 1
            if not self.stage.is_homed():
                # TODO: Richtige Nachricht bzw. auto Homing?
                print("Motor is not homed! Please press 'Home'")
            else:
                print(f"Motor {self.stage.serial_nr} connected.")
                print(f"Motor is at the position {self.stage.to_degree(self.stage.get_position())}.")
            self.stage.setup_velocity(max_velocity=self.stage.to_steps(10))

            self._connect_button_is_checked = True
        else:
            self.stage.close()
            print("Motor disconnected")

            self._connect_button_is_checked = False

    def move_to_start(self):
        pass

    def initiate_auto_calibration(self):
        pass

    def autoscan(self):
        pass