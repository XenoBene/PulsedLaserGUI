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
    update_textBox = QtCore.pyqtSignal(str)

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
        """
        Controls the UV autoscan process to maintain maximum UV output power during wavelength scanning.

        Behavior:
        ---------
        - Continuously adjusts the picomotor's position to maximize UV power using a Greedy algorithm.
        - Moves the picomotor by a set number of steps in the current direction.
        - Measures the UV power after each step and updates the position and power readings.
        - Determines the slope of UV power change and adjusts the movement direction accordingly.
        - If UV power falls below 80% of the threshold:
            - Corrects the picomotor's position based on the difference between the current and
            starting wavelength and position.
        - Operates in a loop until manually stopped.

        Signals:
        --------
        - `status` (bool): Emits True when the scan is active, and False when the scan is stopped.
        - `update_diodeVoltage` (float): Emits the current UV power measurement.
        - `update_motorSteps` (int): Emits the current position of the picomotor.
        - `finished`: Emits when the scanning process is completed.

        Internal Methods:
        -----------------
        - `measure_uv_power()`: Measures and returns the current UV power.
        - `update_position_and_measure()`: Updates and returns the current picomotor position.
        - `correct_position_if_needed(wl, uv_power, new_pos)`: Corrects the picomotor position
        if UV power is below the threshold.
        """
        def measure_uv_power():
            self.rp.tx_txt('ACQ:SOUR1:DATA:STA:N? 1,3000')
            buff = list(map(float, self.rp.rx_txt().strip('{}\n\r').replace("  ", "").split(',')))
            return np.round(np.mean(buff), 4)

        def update_position_and_measure():
            new_pos = self.stage.get_position(axis=self.axis, addr=self.addr)
            self.update_motorSteps.emit(new_pos)
            return new_pos

        def correct_position_if_needed(wl, uv_power, new_pos):
            if self.threshold_power * 0.8 > uv_power > 0:
                delta_wl = wl - self.delta_wl_start
                calculated_steps = -delta_wl * (3233 if delta_wl > 0 else 3500)
                delta_pos = calculated_steps - (new_pos - self.start_pos)
                self.stage.move_by(axis=self.axis, addr=self.addr, steps=int(delta_pos))
                time.sleep(float(abs(delta_pos) / self.velocity))
                return self.stage.get_position(axis=self.axis, addr=self.addr)
            return new_pos

        self.keep_running = True
        self.status.emit(True)

        while self.keep_running:
            start_time = time.time()
            direction = self.steps if self.going_right else -self.steps
            self.stage.move_by(axis=self.axis, addr=self.addr, steps=direction)
            time.sleep(float(self.steps / self.velocity) + self.wait)

            uv_power = measure_uv_power()
            self.update_diodeVoltage.emit(uv_power)
            new_pos = update_position_and_measure()

            slope = (uv_power - self.old_power) / (new_pos - self.old_pos)
            self.going_right = slope > 0
            # self.going_right = not self.going_right  # DELETE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            self.old_power, self.old_pos = uv_power, new_pos

            wl = np.round(self.wlm.GetWavelength(1), 6)
            self.iterator_steps += 1

            if self.iterator_steps > 20:
                self.delta_wl_start, self.start_pos, self.threshold_power = wl, new_pos, uv_power
                self.iterator_steps = 0

            new_pos = correct_position_if_needed(wl, uv_power, new_pos)  # Rettungsalgorithmus

            # self.update_textBox.emit(f"Delta wl: {wl - self.delta_wl_start}, Finished in: {time.time() - start_time}")  # Debugging

        self.status.emit(False)
        self.finished.emit()

    def stop(self):
        """Sets the attribute keep_running to False. This is needed
        to end the autoscan method to end the QThread.
        """
        self.keep_running = False
        self.update_textBox.emit("UV Autoscan stopped")


class WorkerBBO_Double(QtCore.QObject):
    # Signals need to be class variables, not instance variables:
    status = QtCore.pyqtSignal(bool)
    finished = QtCore.pyqtSignal()
    update_diodeVoltage = QtCore.pyqtSignal(float)
    update_motorSteps = QtCore.pyqtSignal(int)

    def __init__(self, wlm, rp, stage, axis, addrFront, addrBack, steps, velocity, wait):
        """Class that handles the logic of the UV autoscan. Needs to be an extra
        class so it can run as a QThread.
        WLM, RedPitaya and Picomotor need to be connected before this class can run.

        Args:
            wlm (WavelengthMeter):Device to measure the wavelength
            rp (RedPitaya): Device to measure the UV power (UV diode)
            stage (Picomotor8742): Picomotor to change the angle of the BBO crystal
            axis (int): Port of the picomotor (1 to 4, usually 1)
            addrFront (int): Device number of the daisy-chained controllers (1 or 2)
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
        self.addrFront = addrFront
        self.addrBack = addrBack
        self.steps = int(steps)
        self.velocity = float(velocity)
        self.wait = float(wait)

        self.going_right1 = True  # Direction of the first picomotor step for BBO 1
        self.going_right2 = False  # Direction of the second Picomotor step for BBO 2
        self.old_power = 0
        self.old_pos_front = self.stage.get_position(axis=self.axis, addr=self.addrFront)
        self.old_pos_back = self.stage.get_position(axis=self.axis, addr=self.addrBack)
        self.iterator_steps1 = 0
        self.iterator_steps2 = 0
        self.delta_wl_start1 = np.round(self.wlm.GetWavelength(1), 6)
        self.delta_wl_start2 = self.delta_wl_start1
        self.threshold_power1 = 0
        self.threshold_power2 = 0
        self.start_pos_front = self.old_pos_front
        self.start_pos_back = self.old_pos_back

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
            # TODO: addr1 and addr2 ? (class stage)

            # Move BBO 1
            # -------------------------------------------------------------------------
            if self.going_right1:
                self.stage.move_by(axis=self.axis, addr=self.addrFront, steps=self.steps)
            else:
                self.stage.move_by(axis=self.axis, addr=self.addrFront, steps=-self.steps)

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
            new_pos_front = self.stage.get_position(axis=self.axis, addr=self.addrFront)

            # Signal for the GUI or writing data:
            # self.update_motorSteps1.emit(new_pos_front) # TODO: pos1 und pos2 wegschreiben

            # Calculate the slope for BBO 1 (i.e. calculate if the power got higher
            # or not). The direction of the next step depends on the slope:
            slope1 = (uv_power - self.old_power) / (new_pos_front - self.old_pos_front)
            """if slope1 > 0:
                self.going_right1 = True
            else:
                self.going_right1 = False"""
            self.going_right1 = not self.going_right1  # DELETE!!!!!!!!!!!!!!!!!

            # Assign the newest values to attributes for the next iteration:
            self.old_power = uv_power
            self.old_pos_front = new_pos_front

            # Measure the current wavelength:
            wl = np.round(self.wlm.GetWavelength(1), 6)

            """ --> for testing 2 BBO Greedy off
            Here starts the implementation of a kind of power failsafe:
            If the output power suddenly drops down a certain threshold, the picomotor
            will not just take the usual steps in one direction. Instead, the wavelength difference
            between the last checkpoint and the current wavelength gets converted to the needed
            steps for this wavelength difference (based on empirical data).
            """
            """
            # Checkpoint: Every 20 iterations, the current values get saved to the
            # instance attributes and the iteration counter gets resetted.
            self.iterator_steps1 += 1
            if self.iterator_steps1 > 20:
                self.delta_wl_start = wl
                self.start_pos1 = new_pos1
                self.threshold_power1 = uv_power
                self.iterator_steps1 = 0
                print("Iteratorsteps reset")

            # Calculates the difference between the current wavelength and the wl at the last checkpoint
            delta_wl = wl - self.delta_wl_start
            print(f"Delta wl: {delta_wl}")

            # compare steps to calculated steps and move the necessary steps to the theoretical position,
            # if current power is a lot lower than control power
            if (self.threshold_power1 * 0.8 > uv_power > 0):
                if delta_wl > 0:
                    print(f"Position vor Korr1: {new_pos}")
                    calculated_steps1 = -delta_wl * 3233  # Empirical data
                elif delta_wl < 0:
                    print(f"Position vor Korr2: {new_pos}")
                    calculated_steps1 = -delta_wl * 3500  # Empirical data

                # Calculates and moves the motor to the theoretical position:
                delta_pos = (calculated_steps1 - (new_pos1 - self.start_pos1))
                self.stage.move_by(axis=self.axis, addrFront
=self.addr1, steps=int(delta_pos))  # TODO addr1
                time.sleep(float(abs(delta_pos) / self.velocity))

                new_pos1 = self.stage.get_position(axis=self.axis, addrFront
=self.addr1) # TODO addr1
                print(f"Position nach Korrektur: {new_pos}")

                # Reset the old values:
                self.old_pos1 = new_pos1
                self.iterator_steps1 = 0
                self.threshold_power1 = uv_power
            print(f"Fertig: {time.time() - start_time}")
            """

            # Move BBO 2
            # -------------------------------------------------------------------------
            if self.going_right2:
                self.stage.move_by(axis=self.axis, addr=self.addrBack, steps=self.steps)
            else:
                self.stage.move_by(axis=self.axis, addr=self.addrBack, steps=-self.steps)

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
            new_pos_back = self.stage.get_position(axis=self.axis, addr=self.addrBack)

            # Signal for the GUI or writing data:
            # self.update_motorSteps2.emit(new_pos_back)  # TODO: pos1 und pos2 wegschreiben

            # Calculate the slope for BBO 2 (i.e. calculate if the power got higher
            # or not). The direction of the next step depends on the slope:
            slope2 = (uv_power - self.old_power) / (new_pos_back - self.old_pos_back)  # TODO: old_pos1 und old_pos2 initialisieren
            """if slope2 > 0:
                self.going_right2 = True
            else:
                self.going_right2 = False"""
            self.going_right2 = not self.going_right2  # DELETE!!!!!!!!!!!!

            # Assign the newest values to attributes for the next iteration:
            self.old_power = uv_power
            self.old_pos_back = new_pos_back

        # TODO nach Test noch failsafe für 2 BBOs implementieren

        self.status.emit(False)
        self.finished.emit()

    def stop(self):
        """Sets the attribute keep_running to False. This is needed
        to end the autoscan method to end the QThread.
        """
        self.keep_running = False
        print("UV Autoscan stopped")


class BBO(QtCore.QObject):
    autoscan_status_single = QtCore.pyqtSignal(bool)
    autoscan_status_double = QtCore.pyqtSignal(bool)
    voltageUpdated = QtCore.pyqtSignal(float)
    stepsUpdated = QtCore.pyqtSignal(int)
    update_textBox = QtCore.pyqtSignal(str)

    def __init__(self, axis, addrFront, addrBack):
        """This class controls the picomotor which controls the angle
        of the BBO crystal.

        Args:
            axis (int): Port that the motor is connected to (1 to 4, usually 1)
            addr (int): Adress of the motor controller. Important because our two motors
                are daisy-chained together. Either 1 or 2 depending on the controller.
        """
        super().__init__()
        self.axis = axis
        self.addrFront = addrFront
        self.addrBack = addrBack
        self._connect_button_is_checked = False
        self._connect_rp_button_is_checked = False

    def connect_piezos(self):
        """Connects|Disconnects the picomotor depending on the state of the GUI button.
        """
        if not self._connect_button_is_checked:
            try:
                self.stage = Newport.Picomotor8742()
                self.update_textBox.emit("Picomotor connected")
                self._connect_button_is_checked = True
            except NewportBackendError as e:
                self.update_textBox.emit(f"Error: {e}")
                self._connect_button_is_checked = True
            except NewportError as e:
                self.update_textBox.emit(f"Picomotor application still opened? {e}")
                self._connect_button_is_checked = True
        else:
            self.update_textBox.emit("Picomotor disconnected")
            self.stage.close()
            del self.stage
            self._connect_button_is_checked = False

    def connect_red_pitaya(self, ip):
        """Connects|Disconnects the RedPitaya depending if the GUI button
        is already checked or not.

        Args:
            ip (str): IP adress of the RedPitaya (SCPI server needs to be turned on)
        """
        try:
            if not self._connect_rp_button_is_checked:
                self.rp = scpi.scpi(ip)
                self.rp.tx_txt('ACQ:RST')
                self.rp.acq_set(1)
                self.rp.tx_txt('ACQ:DATA:FORMAT ASCII')
                self.rp.tx_txt('ACQ:DATA:UNITS VOLTS')
                self.rp.tx_txt('ACQ:START')

                self._connect_rp_button_is_checked = True
            else:
                del self.rp
                self._connect_rp_button_is_checked = False
        except BrokenPipeError as e:
            self.update_textBox.emit(f"Error: {e}")
            self._connect_rp_button_is_checked = True

    def move_by(self, steps, move_front_bbo=False):
        """Moves the picomotor in one direction.

        Args:
            steps (int): Steps that the picomotor should move
                (can be negative depending on the direction).
            move_front_bbo (bool): True if front BBO should be moved,
                False if back BBO is moved
        """
        try:
            addr = self.addrFront if move_front_bbo else self.addrBack
            self.stage.move_by(axis=self.axis, addr=addr, steps=steps)
        except AttributeError:
            self.update_textBox.emit("Picomotor not connected!")

    def change_autoscan_parameters(self, velocity, steps, wait, double_bbo_setup=False):
        """Assigns the velocity, steps and wait time to instance attributes.

        Args:
            velocity (float): Velocity [steps/s] of the picomotor
            steps (int): Number of steps the motor should take
            wait (float): Time [s]
        """
        if double_bbo_setup:
            self.autoscan_velocity_double = velocity
            self.autoscan_steps_double = steps
            self.autoscan_wait_double = wait
        else:
            self.autoscan_velocity = velocity
            self.autoscan_steps = steps
            self.autoscan_wait = wait

    def change_velocity(self, velocity, change_front_bbo=False):
        """Changes the velocity of the picomotor

        Args:
            velocity (float): Velocity [steps/s] of the motor
            change_front_bbo (bool)
        """
        try:
            addr = self.addrFront if change_front_bbo else self.addrBack
            self.stage.setup_velocity(axis=self.axis, addr=addr, speed=velocity)
        except AttributeError:
            self.update_textBox.emit("Picomotor not connected!")

    def start_autoscan(self, wlm):
        """Starts the QThread (the WorkerBBO class) where the UV autoscan will operate.
        """
        self.update_textBox.emit("Start Autoscan")
        try:
            # Initiate QThread and WorkerLBO class:
            self.threadBBO = QtCore.QThread()
            self.workerBBO = WorkerBBO(wlm=wlm, rp=self.rp, stage=self.stage,
                                       axis=self.axis, addr=self.addrBack, steps=self.autoscan_steps,
                                       velocity=self.autoscan_velocity, wait=self.autoscan_wait)
            self.workerBBO.moveToThread(self.threadBBO)

            # Connect different methods to the signals of the thread:
            self.threadBBO.started.connect(self.workerBBO.autoscan)
            self.workerBBO.status.connect(self.autoscan_status_single.emit)
            self.workerBBO.update_diodeVoltage.connect(self.voltageUpdated.emit)
            self.workerBBO.update_motorSteps.connect(self.stepsUpdated.emit)
            self.workerBBO.update_textBox.connect(self.update_textBox.emit)
            self.workerBBO.finished.connect(self.threadBBO.quit)
            self.workerBBO.finished.connect(self.workerBBO.deleteLater)
            self.threadBBO.finished.connect(self.threadBBO.deleteLater)

            # Start the thread:
            self.threadBBO.start()
        except AttributeError as e:
            self.update_textBox.emit(f"Error: {e}")

    def stop_autoscan(self):
        """Stops the QThread (WorkerBBO class).
        """
        self.update_textBox.emit("Stop Autoscan")
        self.workerBBO.stop()

    def start_autoscan_double(self, wlm):
        """Starts the QThread (the WorkerBBO class) where the UV autoscan will operate.
        """
        print("Start Autoscan")
        try:
            # Initiate QThread and WorkerLBO class:
            self.threadBBO2 = QtCore.QThread()
            self.workerBBO2 = WorkerBBO_Double(wlm=wlm, rp=self.rp, stage=self.stage,
                                               axis=self.axis, addrFront=self.addrFront, addrBack=self.addrBack,
                                               steps=self.autoscan_steps_double, velocity=self.autoscan_velocity_double,
                                               wait=self.autoscan_wait_double)
            self.workerBBO2.moveToThread(self.threadBBO2)

            # Connect different methods to the signals of the thread:
            self.threadBBO2.started.connect(self.workerBBO2.autoscan)
            self.workerBBO2.status.connect(self.autoscan_status_double.emit)
            self.workerBBO2.update_diodeVoltage.connect(self.voltageUpdated.emit)
            self.workerBBO2.update_motorSteps.connect(self.stepsUpdated.emit)
            self.workerBBO2.finished.connect(self.threadBBO2.quit)
            self.workerBBO2.finished.connect(self.workerBBO2.deleteLater)
            self.threadBBO2.finished.connect(self.threadBBO2.deleteLater)

            # Start the thread:
            self.threadBBO2.start()
        except AttributeError as e:
            print(f"Error: {e}")

    def stop_autoscan_double(self):
        """Stops the QThread (WorkerBBO class).
        """
        self.update_textBox.emit("Stop Autoscan")
        self.workerBBO2.stop()
