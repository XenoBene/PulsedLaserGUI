from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, NetworkConnection, DeviceNotFoundError
from toptica.lasersdk.client import UnavailableError
from toptica.lasersdk.decop import DecopError
import numpy as np
from PyQt6 import QtCore


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
                self.update_textBox.emit("DFB connected")
                self.update_values.emit(self.read_actual_dfb_values())
                self._connect_button_is_checked = True
            except DeviceNotFoundError:
                self.update_textBox.emit("DFB not found")
                self._connect_button_is_checked = True
        else:
            self.dlc.close()
            self.update_textBox.emit("DFB connection closed")
            self._connect_button_is_checked = False

    def read_actual_dfb_values(self):
        """Reads out the set temperature and the WideScan parameters 'Start temp.', 'End temp.' and 'Scan speed'."""
        try:
            self.set_temp = self.dlc.laser1.dl.tc.temp_set.get()
            self.start_temp = self.dlc.laser1.wide_scan.scan_begin.get()
            self.end_temp = self.dlc.laser1.wide_scan.scan_end.get()
            self.scan_speed = self.dlc.laser1.wide_scan.speed.get()
            return self.set_temp, self.start_temp, self.end_temp, self.scan_speed
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}")
            return None, None, None, None
        except UnavailableError as e:
            self.update_textBox.emit(f"DFB session was closed: {e}")
            return None, None, None, None

    def get_actual_temperature(self):
        """Reads out the current temperature of the DFB diode.

        Returns:
            float: Temperature of the DFB diode [°C]
        """
        try:
            act_temp = self.dlc.laser1.dl.tc.temp_act.get()
            return np.round(act_temp, 3)
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}")

    def change_dfb_setTemp(self, set_temp):
        """Changes the set temperature of the diode.

        Args:
            set_temp (float): Desired set temperature [°C]
        """
        try:
            self.dlc.laser1.dl.tc.temp_set.set(np.round(set_temp, 2))
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}")

    def change_wideScan_values(self, start_temp, end_temp, scan_speed):
        """Changes the parameters for the WideScan of the connected
        DFB laser.

        Args:
            start_temp (float): Start temperature [°C] of the WideScan
            end_temp (float): End temperature [°C] of the WideScan
            scan_speed (float): WideScan speed [K/s]
        """
        try:
            self.dlc.laser1.wide_scan.scan_begin.set(start_temp)
            self.dlc.laser1.wide_scan.scan_end.set(end_temp)
            self.dlc.laser1.wide_scan.speed.set(scan_speed)
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}")
        except ValueError as e:
            self.update_textBox.emit(f"Value has to be a number: {e}")
        except DecopError as e:
            self.update_textBox.emit(f"DecopError: {e}")
        finally:
            self.update_values.emit(self.read_actual_dfb_values())

    def start_wideScan(self):
        """Creates a QTimer and starts the WideScan. The QTimer is
        connected to a method that updates the GUI with the WideScan
        progress.
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
            self.update_textBox.emit(f"DFB is not yet connected: {e}")
        except DecopError:
            self.update_textBox.emit("WideScan is already in progress!")

    def abort_wideScan(self):
        """Stops the WideScan and changes the set temperature to the
        actual temperature. This way, the diode temperature doesn't drop
        down to the start temperature.
        """
        try:
            temp = np.round(self.get_actual_temperature(), 1)
            self.dlc.laser1.wide_scan.stop()
            self.change_dfb_setTemp(temp)
            self.update_values.emit(self.read_actual_dfb_values())
            # self.widescan_status.emit(False)
        except AttributeError as e:
            self.update_textBox.emit(f"DFB is not yet connected: {e}")

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
            self.update_textBox.emit(f"DFB is not yet connected: {e}")

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
            self.update_textBox.emit(f"DFB is not yet connected: {e}")

    def update_wideScan_progress(self):
        """Gets the progress of the WideScan and the current
        temperature and sends signals to update the GUI with these values.

        When the WideScan is finished, stops the QTimer.
        """
        progress, remaining_time = self.get_wideScan_progress()
        act_temp = self.get_actual_temperature()

        self.update_progressbar.emit((progress, remaining_time))
        self.update_actTemp.emit(act_temp)

        if self.get_wideScan_state() in {0, 3}:
            self.widescan_finished.emit()
            self.widescan_status.emit(False)
            self.widescan_loopTimer.stop()
            self.update_values.emit(self.read_actual_dfb_values())
