from PyQt6 import QtCore
import pyvisa
import numpy as np
import time
from pylablib.devices.HighFinesse.wlmData_lib import WlmDataLibError


class WorkerLBO(QtCore.QObject):
    """Class to start as a thread later.

    Attributes
    ----------
    wlm : class WavelengthMeter
        Device which measures the wavelength
    oc : ResourceManager.open_resource()
        Covesion oven
    """
    # Signals need to be class variables, not instance variables:
    status = QtCore.pyqtSignal(bool)
    finished = QtCore.pyqtSignal()
    update_set_temperature = QtCore.pyqtSignal(float)
    update_act_temperature = QtCore.pyqtSignal(float)
    update_textBox = QtCore.pyqtSignal(str)

    def __init__(self, wlm, oc):
        super().__init__()
        self.wlm = wlm
        self.oc = oc

    def temperature_auto(self):
        """Loop that measures the wavelength and calculates the needed LBO temperature
        for maximum conversion efficiency. The calculation is based on empirical data.

        The method emits signals to tell the classes outside of the QThread, where
        this class will run, the current calculated needed temperature.
        The "while"-loop only finished when keep_running equals False, which is
        being controlled with another method.
        """
        self.keep_running = True
        self.status.emit(True)
        try:
            old_wl = 0
            while self.keep_running:
                wl = np.round(self.wlm.GetWavelength(1), 6)
                time.sleep(0.1)    # This sleep timer is important, otherwise the WLM is overloaded when the ASE filter
                # also measure the wavelength all the time

                # wl = self.wlm.get_wavelength(channel=1, wait=False)  # PyLabLib
                if 1028 < wl < 1032:
                    if abs(old_wl - wl) > 0.001:
                        needed_temperature = np.round(1357.13 - wl * 1.1369, 2)  # Empirical data
                        self.oc.write("!i191;"+str(needed_temperature) + ";0;0;"+str(0.033)+";0;0;BF")
                        self.update_set_temperature.emit(needed_temperature)
                    actual_temperature = float(self.oc.query("!j00CB").split(";")[1])
                    self.update_act_temperature.emit(actual_temperature)
                    old_wl = wl
                    time.sleep(0.9)  # Sleep timer so that the needed CPU runtime is not as high.
        except pyvisa.errors.InvalidSession as e:
            self.update_textBox.emit(f"LBO scan stopped working: {e}")
        except WlmDataLibError as e:  # Needed when PyLabLib is used
            self.update_textBox.emit(f"Error: {e}")
        finally:
            # TODO: Wenn es mal einen Fehler gibt, wird hier der Thread beendet, aber
            # die GUI bekommt davon nichts mit. Also mit einem Signal den Knopf wieder umschalten?
            self.status.emit(False)
            self.finished.emit()  # Needed to exit the QThread

    def stop(self):
        """Sets the attribute keep_running to False. This is needed
        to end the temperature_auto method to end the QThread.
        """
        self.keep_running = False
        self.update_textBox.emit("LBO Autoscan stopped by hand")


class LBO(QtCore.QObject):
    autoscan_status = QtCore.pyqtSignal(bool)
    update_act_temperature = QtCore.pyqtSignal(float)
    update_set_temperature = QtCore.pyqtSignal(float)
    update_textBox = QtCore.pyqtSignal(str)

    def __init__(self):
        """Class to control the OC2 oven controller by Covesion.
        """
        super().__init__()
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False

    def connect_covesion(self, rm, port):
        """Connects | Disconnects the covesion oven OC2 depending on if the
        connect button was already in a checked state or not.

        Args:
            rm (ResourceManager()): The ResourceManager-Class is needed to
            find all connected devices
            port (str): Port number that the oven has on the connected PC
        """
        if not self._connect_button_is_checked:
            try:
                self.oc = rm.open_resource(port, baud_rate=19200, data_bits=8,
                                           parity=pyvisa.constants.Parity.none, flow_control=0,
                                           stop_bits=pyvisa.constants.StopBits.one)
                self.update_textBox.emit("Covesion oven connected")
                self.read_values()  # Read values as the first thing after connecting
            except pyvisa.errors.VisaIOError as e:
                self.update_textBox.emit(f"Device not supported: {e}")
            finally:
                self._connect_button_is_checked = True
        else:
            try:
                self.oc.close()  # disables the remote control
                try:
                    self.oc.session  # Checks if the oven is really disconnected
                except pyvisa.errors.InvalidSession:
                    self.update_textBox.emit("Device closed")
            except pyvisa.errors.InvalidSession:
                # TODO: Richtiger Fehler wenn Disconnect obwohl nie Connected
                pass
            finally:
                self._connect_button_is_checked = False

    def set_temperature(self, set_temp, rate):
        """Sets the desired temperature and the speed of the ramp of the
        covesion oven.

        Args:
            set_temp (str): Set temperature [°C]. Only values between 15°C and 200°C are allowed.
            rate (str): Temperature ramp speed [°C/min]. Only values under 2 °C/min are allowed.

        Raises:
            ValueError: Gets raised if the input values are not in the allowed bounds.
        """
        try:
            if ((float(set_temp) <= 200) and (float(set_temp) >= 15) and (0 < float(rate) <= 2)):
                self.oc.write("!i191;"+str(set_temp)+";0;0;" +
                              str(np.round(float(rate)/60, 3))+";0;0;BF")
            else:
                raise ValueError(
                    "Only temperatures between 15°C and 200°C and rates lower than 2°C/min allowed")
        except ValueError as e:
            self.update_textBox.emit(f"Error: {e}")

    def get_status(self):
        """Returns the status of the covesion controller.

        Returns:
            tuple: Status of the OC2 depicting values in the following order:
            (Setpoint, Actual Temp, Control, Output, Alarm, Status, Faults, Temp, Supply V, Version, Test Cycles)
        """
        try:
            status = self.oc.query("!j00CB").split(";")
            return status
        except pyvisa.errors.InvalidSession as e:
            self.update_textBox.emit(f"Device closed: {e}")

    def get_status_q(self):
        """Returns the q-status (different than the j-status of get_status) of the covesion controller.

        Returns:
            tuple: q-Status of the OC2 depicting values in the following order (only few are known):
            (Setpoint, ???, ???, Rate in °C/s, ???, ???)
        """
        try:
            status = self.oc.query("!q").split(";")
            return status
        except pyvisa.errors.InvalidSession as e:
            self.update_textBox.emit(f"Device closed: {e}")

    def get_actTemp(self):
        """Gets the current temperature of the covesion oven.

        Returns:
            float: Current temperature [°C].
        """
        try:
            values = self.get_status()
            self.act_temp = float(values[1])
            return self.act_temp
        except pyvisa.errors.InvalidSession as e:
            self.update_textBox.emit(f"Device closed: {e}")

    def read_values(self):
        """Reads out the set temperature and ramp speed of the oven.

        Returns:
            tuple: Set temp [°C] and ramp speed [°C/min] as a float tuple.
        """
        values = self.get_status_q()
        self.set_temp = values[1]
        self.rate = float(values[4]) * 60
        return self.set_temp, self.rate

    def toggle_autoscan(self, wlm):
        """Starts|Stops the automatic temperature scan of the LBO depending on the
        state of the "Autoscan" button in the GUI. This process
        gets started in a QThread because otherwise there would be problems
        when too many processes run at the same time.
        """
        if not self._autoscan_button_is_checked:
            self.update_textBox.emit("Start LBO Autoscan")
            try:
                self._autoscan_button_is_checked = True
                # Initiate QThread and WorkerLBO class:
                self.threadLBO = QtCore.QThread()
                self.workerLBO = WorkerLBO(wlm=wlm, oc=self.oc)
                self.workerLBO.moveToThread(self.threadLBO)

                # Connect different methods to the signals of the thread:
                self.threadLBO.started.connect(self.workerLBO.temperature_auto)
                self.workerLBO.update_act_temperature.connect(self.update_act_temperature.emit)
                self.workerLBO.update_set_temperature.connect(self.update_set_temperature.emit)
                self.workerLBO.update_textBox.connect(self.update_textBox.emit)
                self.workerLBO.status.connect(self.autoscan_status.emit)
                self.workerLBO.finished.connect(self.threadLBO.quit)
                self.workerLBO.finished.connect(self.workerLBO.deleteLater)
                self.threadLBO.finished.connect(self.threadLBO.deleteLater)

                # Start the thread:
                self.threadLBO.start()
            except AttributeError as e:
                self.update_textBox.emit(f"Error: {e}")
        else:
            try:
                self._autoscan_button_is_checked = False
                self.workerLBO.stop()
                self.update_textBox.emit("Stop LBO Autoscan")
            except AttributeError as e:
                self.update_textBox.emit(f"Error: {e}")
