from PyQt6 import QtCore
from pylablib.devices import Newport
from pylablib.devices.Newport.base import NewportBackendError, NewportError
import time
import numpy as np
import redpitaya_scpi as scpi


class WorkerBBO(QtCore.QObject):
    # Signals need to be class variables, not instance variables:
    status = QtCore.pyqtSignal(bool)
    finished = QtCore.pyqtSignal()
    update_diodeVoltage = QtCore.pyqtSignal(float)
    update_motorSteps = QtCore.pyqtSignal(int)

    def __init__(self, wlm, rp, stage, axis, addr, steps, velocity, wait):
        """Class that handles the logic of the UV autoscan. Needs to be an extra
        class so it can run as a QThread.
        WLM, RedPitaya and Picomotor need to be connected before this class can run.

        Args:
            wlm (WavelengthMeter):Device to measure the wavelength
            rp (RedPitaya): Device to measure the UV power (UV diode)
            stage (Picomotor8742): Picomotor to change the angle of the BBO crystal
            axis (int): Port of the picomotor (1 to 4, usually 1)
            addr (int): Device number of the daisy-chained controllers (1 or 2)
            steps (int): Steps that the picomotor should take every iteration
            velocity (float): Speed [steps/s] of the picomotor
            wait (float): Wait time [s] after the move of the picomotor before
                the uv power gets measured.
        """
        super().__init__()
        self.wlm = wlm
        self.rp = rp
        self.stage = stage
        self.axis = axis
        self.addr = addr
        self.steps = int(steps)
        self.velocity = float(velocity)
        self.wait = float(wait)

        self.going_right = True  # Direction of the first picomotor step
        self.old_power = 0
        self.old_pos = self.stage.get_position(axis=self.axis, addr=self.addr)
        self.iterator_steps = 0
        self.delta_wl_start = np.round(self.wlm.GetWavelength(1), 6)
        self.threshold_power = 0
        self.start_pos = self.old_pos

    def autoscan(self):
        """Logic behind the UV autoscan. This method should keep the uv output
        power at the maximum, even when the wavelength gets scanned.
        To achieve this, a Greedy algorithm is used. The picomotor will make a few steps
        in one direction, and will measure if the uv power after this step ist higher or
        lower than before. Based on the measurement, the next step will be in the same
        or opposite direction.
        """
        self.keep_running = True
        start_time = time.time()
        self.status.emit(True)
        while self.keep_running:
            # Makes a number of steps (self.steps) in one direction:
            if self.going_right:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=self.steps)
            else:
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=-self.steps)

            # Break while the motor is moving (plus some additional wait time):
            time.sleep(float(self.steps / self.velocity))
            time.sleep(float(self.wait))

            # Measure the voltage of the uv diode (proportional
            # to the uv output power):
            self.rp.tx_txt('ACQ:SOUR1:DATA:STA:N? 1,3000')
            buff_string = self.rp.rx_txt()
            buff_string = buff_string.strip(
                '{}\n\r').replace("  ", "").split(',')
            buff = list(map(float, buff_string))
            uv_power = np.round(np.mean(buff), 4)

            # Signal for the GUI:
            self.update_diodeVoltage.emit(uv_power)

            # Measure the current position (absolute steps):
            new_pos = self.stage.get_position(axis=self.axis, addr=self.addr)

            # Signal for the GUI or writing data:
            self.update_motorSteps.emit(new_pos)

            # Calculate the slope (i.e. calculate if the power got higher
            # or not). The direction of the next step depends on the slope:
            slope = (uv_power - self.old_power) / (new_pos - self.old_pos)
            if slope > 0:
                self.going_right = True
            else:
                self.going_right = False

            # Assign the newest values to attributes for the next iteration:
            self.old_power = uv_power
            self.old_pos = new_pos

            # Measure the current wavelength:
            wl = np.round(self.wlm.GetWavelength(1), 6)

            """
            Here starts the implementation of a kind of power failsafe:
            If the output power suddenly drops down a certain threshold, the picomotor
            will not just take the usual steps in one direction. Instead, the wavelength difference
            between the last checkpoint and the current wavelength gets converted to the needed
            steps for this wavelength difference (based on empirical data).
            """
            # Checkpoint: Every 20 iterations, the current values get saved to the
            # instance attributes and the iteration counter gets resetted.
            self.iterator_steps += 1
            if self.iterator_steps > 20:
                self.delta_wl_start = wl
                self.start_pos = new_pos
                self.threshold_power = uv_power
                self.iterator_steps = 0
                print("Iteratorsteps reset")

            # Calculates the difference between the current wavelength and the wl at the last checkpoint
            delta_wl = wl - self.delta_wl_start
            print(f"Delta wl: {delta_wl}")

            # compare steps to calculated steps and move the necessary steps to the theoretical position,
            # if current power is a lot lower than control power
            if (self.threshold_power * 0.8 > uv_power > 0):
                if delta_wl > 0:
                    print(f"Position vor Korr1: {new_pos}")
                    calculated_steps = -delta_wl * 3233  # Empirical data
                elif delta_wl < 0:
                    print(f"Position vor Korr2: {new_pos}")
                    calculated_steps = -delta_wl * 3500  # Empirical data

                # Calculates and moves the motor to the theoretical position:
                delta_pos = (calculated_steps - (new_pos - self.start_pos))
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=int(delta_pos))
                time.sleep(float(abs(delta_pos) / self.velocity))

                new_pos = self.stage.get_position(axis=self.axis, addr=self.addr)
                print(f"Position nach Korrektur: {new_pos}")

                # Reset the old values:
                self.old_pos = new_pos
                self.iterator_steps = 0
                self.threshold_power = uv_power
            print(f"Fertig: {time.time() - start_time}")
        self.status.emit(False)
        self.finished.emit()

    def stop(self):
        """Sets the attribute keep_running to False. This is needed
        to end the autoscan method to end the QThread.
        """
        self.keep_running = False
        print("UV Autoscan stopped")


class BBO(QtCore.QObject):
    autoscan_status = QtCore.pyqtSignal(bool)
    voltageUpdated = QtCore.pyqtSignal(float)
    stepsUpdated = QtCore.pyqtSignal(int)

    def __init__(self, wlm, axis, addr):
        """This class controls the picomotor which controls the angle
        of the BBO crystal.

        Args:
            wlm (WavelengthMeter): Device to measure the wavelength of the laser
            axis (int): Port that the motor is connected to (1 to 4, usually 1)
            addr (int): Adress of the motor controller. Important because our two motors
                are daisy-chained together. Either 1 or 2 depending on the controller.
        """
        super().__init__()
        self.wlm = wlm
        self.axis = axis
        self.addr = addr
        self._connect_button_is_checked = False
        self._connect_rp_button_is_checked = False

    def connect_piezos(self):
        """Connects|Disconnects the picomotor depending on the state of the GUI button.
        """
        if not self._connect_button_is_checked:
            try:
                self.stage = Newport.Picomotor8742()
                print("an")
                self._connect_button_is_checked = True
            except NewportBackendError as e:
                print(e)
                self._connect_button_is_checked = False
            except NewportError as e:
                print(f"Picomotor application still opened? {e}")
                self._connect_button_is_checked = False
        else:
            print("aus")
            self.stage.close()
            # TODO: Das disconnected den Motor nicht wirklich, man kann ihn immer noch ansteuern
            self._connect_button_is_checked = False

    def connect_red_pitaya(self, ip):
        """Connects|Disconnects the RedPitaya depending if the GUI button
        is already checked or not.

        Args:
            ip (str): IP adress of the RedPitaya (SCPI server needs to be turned on)
        """
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
        """Moves the picomotor in one direction.

        Args:
            steps (int): Steps that the picomotor should move
                (can be negative depending on the direction).
        """
        try:
            self.stage.move_by(axis=self.axis, addr=self.addr, steps=steps)
        except AttributeError:
            print("Picomotor not connected!")

    def change_autoscan_parameters(self, velocity, steps, wait):
        """Assigns the velocity, steps and wait time to instance attributes.

        Args:
            velocity (float): Velocity [steps/s] of the picomotor
            steps (int): Number of steps the motor should take
            wait (float): Time [s]
        """
        self.autoscan_velocity = velocity
        self.autoscan_steps = steps
        self.autoscan_wait = wait

    def change_velocity(self, velocity):
        """Changes the velocity of the picomotor

        Args:
            velocity (float): Velocity [steps/s] of the motor
        """
        try:
            self.stage.setup_velocity(axis=self.axis, addr=self.addr, speed=velocity)
        except AttributeError:
            print("Picomotor not connected!")

    def start_autoscan(self):
        """Starts the QThread (the WorkerBBO class) where the UV autoscan will operate.
        """
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
            self.workerBBO.status.connect(self.autoscan_status.emit)
            self.workerBBO.update_diodeVoltage.connect(self.voltageUpdated.emit)
            self.workerBBO.update_motorSteps.connect(self.stepsUpdated.emit)
            self.workerBBO.finished.connect(self.threadBBO.quit)
            self.workerBBO.finished.connect(self.workerBBO.deleteLater)
            self.threadBBO.finished.connect(self.threadBBO.deleteLater)

            # Start the thread:
            self.threadBBO.start()
        except AttributeError as e:
            print(f"Error: {e}")

    def stop_autoscan(self):
        """Stops the QThread (WorkerBBO class).
        """
        print("Stop Autoscan")
        self.workerBBO.stop()
