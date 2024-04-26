from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, NetworkConnection, DeviceNotFoundError
from toptica.lasersdk.client import UnavailableError
import numpy as np
from PyQt6 import QtCore


class DFB(QtCore.QObject):
    update_values = QtCore.pyqtSignal(tuple)

    def __init__(self, ip):
        super().__init__()
        self._connect_button_is_checked = False
        self.dlc_ip_adress = ip

    def connect_dfb(self):
        """Connects/disconnects the DFB laser depending on if the connect button
        is already checked or not. If the button changes its state from unchecked to checked,
        the DLC Pro connects and opens a session.
        If the button changes from a checked to an unchecked state, this session gets closed.
        """
        if not self._connect_button_is_checked:
            try:
                self.dlc = DLCpro(NetworkConnection(self.dlc_ip_adress))
                self.dlc.open()
                print("DFB connected")
                self.update_values.emit(self.read_actual_dfb_values())
                self._connect_button_is_checked = True
            except DeviceNotFoundError:
                print("DFB not found")
        else:
            self.dlc.close()
            print("DFB connection closed")
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
            print(f"DFB is not yet connected: {e}")
        except UnavailableError as e:
            print(f"DFB session was closed: {e}")

    def get_actual_temperature(self):
        """Reads out the current temperature of the DFB diode.

        Returns:
            float: Temperature of the DFB diode [°C]
        """
        try:
            act_temp = self.dlc.laser1.dl.tc.temp_act.get()
            return np.round(act_temp, 3)
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")

    def change_dfb_setTemp(self, set_temp):
        """Changes the set temperature of the diode.

        Args:
            set_temp (float): Desired set temperature [°C]
        """
        try:
            self.dlc.laser1.dl.tc.temp_set.set(np.round(set_temp, 2))
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")

    def change_wideScan_startTemp(self, start_temp):
        """Changes the start temperature of a WideScan.

        Args:
            start_temp (float): Desired start temperature [°C]
        """
        try:
            self.dlc.laser1.wide_scan.scan_begin.set(float(start_temp))
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")
        except ValueError as e:
            print(f"Value has to be a number: {e}")

    def change_wideScan_endTemp(self, end_temp):
        """Changes the end temperature of a WideScan.

        Args:
            end_temp (float): Desired end temperature [°C]
        """
        try:
            self.dlc.laser1.wide_scan.scan_end.set(float(end_temp))
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")
        except ValueError as e:
            print(f"Value has to be a number: {e}")

    def change_wideScan_scanSpeed(self, scan_speed):
        """Changes the scan speed of a WideScan

        Args:
            scan_speed (float): Desired scan speed [°C/s]
        """
        try:
            self.dlc.laser1.wide_scan.speed.set(float(scan_speed))
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")
        except ValueError as e:
            print(f"Value has to be a number: {e}")

    def start_wideScan(self):
        """Starts the WideScan
        """
        try:
            # TODO: Absicherung durch if/else damit man nur WideScan starten
            # kann falls ASE-Filter verbunden sind
            self.dlc.laser1.wide_scan.start()
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")

    def abort_wideScan(self):
        """Stops the WideScan and changes the set temperature to the
        actual temperature. This way, the diode temperature doesn't drop
        down to the start temperature.
        """
        try:
            temp = self.get_actual_temperature()
            self.dlc.laser1.wide_scan.stop()
            self.change_dfb_setTemp(temp)
        except AttributeError as e:
            print(f"DFB is not yet connected: {e}")

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
            print(f"DFB is not yet connected: {e}")

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
            print(f"DFB is not yet connected: {e}")
