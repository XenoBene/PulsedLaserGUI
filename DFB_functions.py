from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, NetworkConnection, DeviceNotFoundError
from toptica.lasersdk.client import UnavailableError
import numpy as np
from PyQt6 import QtCore
import time


class DFB(QtCore.QObject):
    widescan_status = QtCore.pyqtSignal(bool)
    widescan_finished = QtCore.pyqtSignal()
    update_values = QtCore.pyqtSignal(tuple)
    update_progressbar = QtCore.pyqtSignal(tuple)
    update_actTemp = QtCore.pyqtSignal(float)
    update_textBox = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._connect_button_is_checked = False

    def connect_dfb(self, ip):
        """Connects/disconnects the DFB laser depending on if the connect button
        is already checked or not. If the button changes its state from unchecked to checked,
        the DLC Pro connects and opens a session.
        If the button changes from a checked to an unchecked state, this session gets closed.

        Args:
            ip (str): IP adress of the DLC laser controller
        """
        if not self._connect_button_is_checked:
            try:
                self.dlc = DLCpro(NetworkConnection(ip))
                self.dlc.open()
                self.update_textBox.emit("DFB connected\n")
                self.update_values.emit(self.read_actual_dfb_values())
                self._connect_button_is_checked = True
            except DeviceNotFoundError:
                self.update_textBox.emit("DFB not found\n")
        else:
            self.dlc.close()
            self.update_textBox.emit("DFB connection closed\n")
            self._connect_button_is_checked = False

    def read_actual_dfb_values(self):
        """Reads out the set temperature and the WideScan parameters 'Start temp.', 'End temp.' and 'Scan speed'.
        """
        try:
            self.set_temp = self.dlc.laser1.dl.tc.temp_set.get()
            self.start_temp = self.dlc.laser1.wide_scan.scan_begin.get()
            self.end_temp = self.dlc.laser1.wide_scan.scan_end.get()
            self.scan_speed = self.dlc.laser1.wide_scan.speed.get()
            return self.set_temp, self.start_temp, self.end_temp, self.scan_speed
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")
        except UnavailableError as e:
            self.update_textBox.emit(f"DFB session was closed: {e}")
            self.update_textBox.emit(f"DFB session was closed: {e}\n")

    def get_actual_temperature(self):
        """Reads out the current temperature of the DFB diode.

        Returns:
            float: Temperature of the DFB diode [°C]
        """
        try:
            act_temp = self.dlc.laser1.dl.tc.temp_act.get()
            return np.round(act_temp, 3)
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def change_dfb_setTemp(self, set_temp):
        """Changes the set temperature of the diode.

        Args:
            set_temp (float): Desired set temperature [°C]
        """
        try:
            self.dlc.laser1.dl.tc.temp_set.set(np.round(set_temp, 2))
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def change_wideScan_startTemp(self, start_temp):
        """Changes the start temperature of a WideScan.

        Args:
            start_temp (float): Desired start temperature [°C]
        """
        try:
            self.dlc.laser1.wide_scan.scan_begin.set(float(start_temp))
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")
        except ValueError as e:
            self.update_textBox.emit(f"Value has to be a number: {e}\n")

    def change_wideScan_endTemp(self, end_temp):
        """Changes the end temperature of a WideScan.

        Args:
            end_temp (float): Desired end temperature [°C]
        """
        try:
            self.dlc.laser1.wide_scan.scan_end.set(float(end_temp))
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")
        except ValueError as e:
            self.update_textBox.emit(f"Value has to be a number: {e}\n")

    def change_wideScan_scanSpeed(self, scan_speed):
        """Changes the scan speed of a WideScan

        Args:
            scan_speed (float): Desired scan speed [°C/s]
        """
        try:
            self.dlc.laser1.wide_scan.speed.set(float(scan_speed))
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")
        except ValueError as e:
            self.update_textBox.emit(f"Value has to be a number: {e}\n")

    def start_wideScan(self):
        """Starts the WideScan
        """
        try:
            # TODO: Absicherung durch if/else damit man nur WideScan starten
            # kann falls ASE-Filter verbunden sind
            self.widescan_loopTimer = QtCore.QTimer()
            self.widescan_loopTimer.timeout.connect(self.update_wideScan_progress)
            self.dlc.laser1.wide_scan.start()
            self.widescan_status.emit(True)
            self.widescan_loopTimer.start()
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def abort_wideScan(self):
        """Stops the WideScan and changes the set temperature to the
        actual temperature. This way, the diode temperature doesn't drop
        down to the start temperature.
        """
        try:
            temp = self.get_actual_temperature()
            self.dlc.laser1.wide_scan.stop()
            self.change_dfb_setTemp(temp)
            # self.widescan_status.emit(False)
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def get_wideScan_state(self):
        """Get the state of the WideScan process.

        Returns:
            int: State of the WideScan.
                0 - disabled
                1 - waiting for start condition to be reached
                2 - scan active
                3 - waiting for stop condition to be reached
        """
        try:
            state = self.dlc.laser1.wide_scan.state.get()
            return state
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def get_wideScan_progress(self):
        """Check the progress and remaining time of the WideScan.

        Returns:
            int: Progress of the WideScan [%] and remaining time [s]
        """
        try:
            progress = self.dlc.laser1.wide_scan.progress.get()
            remaining_time = self.dlc.laser1.wide_scan.remaining_time.get()
            return progress, remaining_time
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}\n")

    def update_wideScan_progress(self):
        progress, remaining_time = self.get_wideScan_progress()
        act_temp = self.get_actual_temperature()

        self.update_progressbar.emit((progress, remaining_time))
        self.update_actTemp.emit(act_temp)

        if self.get_wideScan_state() in {0, 3}:
            self.widescan_finished.emit()
            self.widescan_status.emit(False)
            self.widescan_loopTimer.stop()
