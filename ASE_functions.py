from PyQt6 import QtCore, QtTest, QtWidgets
from ThorlabsRotationStage import Stage
import pylablib
from pylablib.devices.Thorlabs.base import ThorlabsBackendError
import numpy as np
import pandas as pd
import time
import datetime
import os
import csv
import glob
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import logging

# Setup of the calibration logfile:
logging.basicConfig(
    filename="Kalibrierung/calibrationlog.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


class ASE(QtCore.QObject):
    autoscan_status = QtCore.pyqtSignal(bool)
    update_wl_pos = QtCore.pyqtSignal(tuple)
    autoscan_failsafe = QtCore.pyqtSignal()
    autocalibration_progress = QtCore.pyqtSignal(int)

    def __init__(self, wlm):
        """This class controls the Thorlabs rotation stage that rotates the ASE filters.

        Args:
            wlm (WavelengthMeter): Device to measure the wavelength of the laser
        """
        super().__init__()
        self.wlm = wlm

        self.cal_par = pd.read_csv("lastused_calpar.csv", delimiter=';')

        # Booleans to check if the GUI buttons are checked or not:
        self._connect_button_is_checked = False
        self._autoscan_button_is_checked = False

    def connect_rotationstage(self, serial):
        """
        Connects or disconnects the rotation stage with the specified serial number.

        Args:
            serial (str): The serial number of the rotation stage to be connected.

        Behavior:
        ---------
        - If the stage is not connected:
            - Sets `_connect_button_is_checked` to `True`.
            - Initializes the stage with the given serial number.
            - Checks if the stage is homed:
                - If not homed, prompts the user to home the motor.
                - If homed, prints the connection status and current position.
            - Sets the stage's maximum velocity.
        - If the stage is already connected:
            - Sets `_connect_button_is_checked` to `False`.
            - Closes the stage connection.
            - Prints the disconnection status.

        Error Handling:
        ---------------
        - Prints "Device not found" if the stage cannot be found.
        - Prints "No stage was connected" if no stage was previously connected.

        Example:
        --------
        >>> obj.connect_rotationstage('12345')
        """
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
        """
        Moves the stage to the start position based on the current wavelength.

        This method retrieves the current wavelength, adjusts the stage's angle
        accordingly, and emits the updated wavelength and position. It handles
        errors by closing the stage connection and emitting fail-safe signals.

        Behavior:
        ---------
        - Retrieves the current wavelength rounded to six decimal places.
        - Changes the stage angle based on the wavelength and calibration parameters.
        - Gets the stage's current position in degrees.
        - Emits the updated wavelength and position.
        - On error, closes the stage connection and emits
        fail-safe and status signals, stopping the autoscan loop timer.

        Error Handling:
        ---------------
        - Handles `DeviceBackendError` and `AttributeError`.
        - If an error occurs, attempts to close the stage and emits fail-safe signals.

        Example:
        --------
        >>> obj.move_to_start()
        """
        try:
            wl = np.round(self.wlm.GetWavelength(1), 6)
            self.stage.calmode = self.stage.change_angle(wl, self.stage.calmode, self.cal_par)
            pos = self.stage.to_degree(self.stage.get_position())

            self.update_wl_pos.emit((wl, pos))
        except (pylablib.core.devio.comm_backend.DeviceBackendError, AttributeError):
            try:
                self.stage.close()
            except pylablib.core.devio.comm_backend.DeviceBackendError as e:
                print(e)
            finally:
                print(time.time())
                self.autoscan_failsafe.emit()
                self.autoscan_status.emit(False)
                self.autoscan_loop_timer.stop()

    def homing_motor(self):
        """
        Initiates the homing procedure for the motor.

        This method sets up the homing parameters for the motor, including velocity and offset distance,
        and starts the homing process.

        Behavior:
        ---------
        - Configures the motor's homing velocity and offset distance.
        - Starts the homing process. sync=False means that the method will not wait
        for the motor to stop moving before continuing.

        Error Handling:
        ---------------
        - Prints "No stage is connected" if there is an AttributeError.

        Example:
        --------
        >>> obj.homing_motor()
        """
        try:
            self.stage.setup_homing(velocity=self.stage.to_steps(10), offset_distance=self.stage.to_steps(4))
            self.stage.home(sync=False, force=True)  # sync=False means no waiting until motor is finished. force=True means homing even if already homed
        except AttributeError:
            print("No stage is connected")

    def autoscan(self):
        """
        Toggles the autoscan process.

        This method starts or stops the autoscan process based on the current state.
        If starting, it sets up a timer to repeatedly call the move_to_start method.
        If stopping, it stops the timer and updates the autoscan status.

        Behavior:
        ---------
        - If autoscan is not active, starts the autoscan process.
        - If autoscan is active, stops the autoscan process.
        - Updates the autoscan status signal at the start and stop.

        Example:
        --------
        >>> obj.autoscan()
        """
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

    def init_wavelength_to_angle_calibration(self, dfb, temp, lowtohi, folderpath="Kalibrierung"):
        """
        Initializes the wavelength to angle calibration process.

        This method sets up the calibration process by configuring the DFB laser
        temperature, creating necessary directories, and initializing a CSV file
        for logging calibration data.

        Parameters:
        -----------
        dfb : object
            The DFB laser object whose temperature (and therefore wavelength) is controlled.
        temp : float
            The temperature to set the DFB laser to.
        lowtohi : bool
            If True, performs low-to-high calibration. If False, performs high-to-low calibration.
            Low-to-high means that the stage moves from lower angles to higher angles.
        folderpath : str, optional
            The base folder path for saving calibration files (default is "Kalibrierung").

        Behavior:
        ---------
        - If `lowtohi` is True, sets the DFB laser temperature and waits for stabilization.
        - Opens the calibration log file and determines the current date and time for folder naming.
        - Creates directories for calibration data.
        - Initializes file paths and names for calibration data based on the wavelength and direction.
        - Writes the CSV header for the calibration file.

        Example:
        --------
        >>> obj.init_wavelength_to_angle_calibration(dfb, 25.0, True)
        """
        if lowtohi:
            dfb.change_dfb_setTemp(float(temp))
            QtTest.QTest.qWait(20 * 1000)

        with open(f'{folderpath}/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
            f.seek(0)
            lines = f.read().split('\n')
            date_str = str(datetime.date.today()) + '_' + datetime.datetime.now().strftime("%H:%M").replace(":", "") + 'hrs'
            if lines[0] != '':
                date_str = f"{lines[-2].split()[0]}_{lines[-2].split()[1][:5].replace(':', '')}hrs"

        folderpath = f'{folderpath}/{date_str}'
        folderpath_lowtohi = f'{folderpath}/lowtohi'
        folderpath_hitolow = f'{folderpath}/hitolow'

        os.makedirs(folderpath_lowtohi, exist_ok=True)
        os.makedirs(folderpath_hitolow, exist_ok=True)

        temp_wavelength = str(np.round(self.wlm.GetWavelength(1), 2)).replace('.', ',')

        self.cal_folderpath = folderpath_lowtohi if lowtohi else folderpath_hitolow
        direction = 'lowtohi' if lowtohi else 'hitolow'
        self.cal_filename = f'kal{temp_wavelength}nm_{direction}'

        with open(f'{self.cal_folderpath}/{self.cal_filename}.csv', 'w', encoding='UTF8', newline='') as f:
            csv.writer(f, delimiter=';').writerow(['Time [s]', 'Wavelength [nm]', 'Power [W]', 'Angle [°]'])

    def wavelength_to_angle_calibration(self, dfb, powermeter, temp_list: list[float], calibration_bounds,
                                        startangle, endangle):
        """
        Performs wavelength to angle calibration over a range of temperatures.

        This method calibrates the rotation stage by adjusting the DFB laser temperature,
        measuring the power at different angles, and logging the data.

        Parameters:
        -----------
        dfb : object
            The DFB laser object whose temperature (and therefore wavelength) is controlled.
        powermeter : object
            The powermeter object to measure power.
        temp_list : list of float
            List of temperatures to use for calibration.
        calibration_bounds : tuple
            Bounds for the calibration calculations.
        startangle : float
            The starting angle for the calibration scan.
        endangle : float
            The ending angle for the calibration scan.

        Behavior:
        ---------
        - If `self.ac_begincal` is True:
            - Sets up and moves the stage to the start angle.
            - Waits for the stage to reach the start angle and stops.
            - Sets `self.ac_begincal` to False after initialization.
        - If `self.initcal_bool` is True:
            - Initializes calibration in either low-to-high or high-to-low direction.
            - Scans the stage to the appropriate angle.
            - Emits progress updates.
        - Logs the current time, wavelength, power, and angle to the CSV file while the stage is scanned.
        - Toggles calibration direction and updates progress.
        - When all temperatures are processed, stops the calibration, calculates results, and emits completion signals.

        Example:
        --------
        >>> obj.wavelength_to_angle_calibration(dfb, powermeter, [25.0, 30.0, 35.0], (400, 700), 0, 180)
        """
        def handle_initcal(lowtohi, temp):
            self.init_wavelength_to_angle_calibration(dfb, temp, lowtohi)
            self.stage.scan_to_angle(endangle if lowtohi else startangle, 0.5)
            progress = (self.autocal_iterator + (0.5 if lowtohi else 1)) * 100 / len(temp_list)
            self.autocalibration_progress.emit(int(progress))
            self.initcal_bool = False

        if self.ac_begincal:
            stage_velocity = 5
            self.stage.setup_gen_move(backlash_distance=136533 * 3)
            self.stage.scan_to_angle(startangle, stage_velocity)
            # TODO: QtTest is only for test purposes, find a different solution (e.g. QThread and while-loop?)
            QtTest.QTest.qWait(int(abs(startangle-self.stage.to_degree(
                self.stage.get_position())) / stage_velocity * 1000 + 3000))
            if (not self.stage.is_moving()) and np.round(
                    self.stage.to_degree(self.stage.get_position()), 1) == startangle:

                # Turn the backlash correction completly off:
                self.stage.setup_gen_move(backlash_distance=0)

                self.cal_old_time = time.time()  # TODO: Zeit woanders reinschreiben?
                self.ac_begincal = False

        if self.initcal_bool:
            handle_initcal(self.lowtohi, temp_list[self.autocal_iterator])

        with open(self.cal_folderpath+'/'+self.cal_filename+'.csv', 'a', encoding='UTF8', newline='') as f:
            power = powermeter.get_power()
            cal_actual_time = np.round(
                time.time()-self.cal_old_time, decimals=4)
            cal_wavelength = np.round(self.wlm.GetWavelength(1), 6)
            cal_current_angle = self.stage.to_degree(self.stage.get_position())

            csv.writer(f, delimiter=';').writerow(
                [cal_actual_time, cal_wavelength, power, cal_current_angle])

        if not self.stage.is_moving():
            self.lowtohi = not self.lowtohi
            self.initcal_bool = True

            # If the last direction was high-to-low:
            if self.lowtohi:
                if self.autocal_iterator == len(temp_list) - 1:
                    self.calculate_autocalibration(showplots=True, bounds=calibration_bounds)
                    powermeter.enable_autorange(True)
                    print("Auto calibration finished! Please select the new calibration parameters located in the"
                          f"{self.cal_folderpath[:-8]} folder. Ensure none of the fits diverge.")
                    self.autocalibration_loop_timer.stop()
                    self.autocalibration_progress.emit(0)
                else:
                    self.autocal_iterator += 1

    def start_autocalibration(self, dfb, powermeter, calibration_bounds, startangle, endangle):
        """
        Starts the automatic wavelength to angle calibration process.

        This method sets up the powermeter, initializes calibration parameters, and
        starts a timer to periodically call the calibration routine.

        Parameters:
        -----------
        dfb : object
            The DFB laser object whose temperature (and therefore wavelength) is controlled.
        powermeter : object
            The powermeter object to measure power.
        calibration_bounds : tuple
            Bounds for the calibration calculations.
        startangle : float
            The starting angle for the calibration scan.
        endangle : float
            The ending angle for the calibration scan.

        Behavior:
        ---------
        - Disables auto range and sets the powermeter range to full.
        - Initializes a timer with a 20 ms interval.
        - Sets calibration control flags and iterator to initial values.
        - Connects the timer to the calibration method with specified parameters.
        - Starts the timer, logging and printing the initiation message.

        Example:
        --------
        >>> obj.start_autocalibration(dfb, powermeter, (400, 700), 0, 180)
        """
        powermeter.enable_autorange(False)
        powermeter.set_range("full")
        self.autocalibration_loop_timer = QtCore.QTimer()
        self.autocalibration_loop_timer.setInterval(20)

        self.ac_begincal = True
        self.lowtohi = True
        self.initcal_bool = True
        self.autocal_iterator = 0

        self.autocalibration_loop_timer.timeout.connect(
            lambda *args: self.wavelength_to_angle_calibration(dfb, powermeter, [15, 20, 25, 30, 35],
                                                               calibration_bounds, startangle, endangle))
        self.autocalibration_loop_timer.start()
        logging.info('Auto calibration initiated.')
        print('Start auto-calibration!')

    def calculate_autocalibration(self, folderpath='Kalibrierung', foldername='',
                                  bounds=([0, 108, 0.1, 1, 0], [1, 118, 2, 5, 0.1]), showplots=False):
        """
        Calculates autocalibration parameters based on collected data.

        This method processes the collected calibration data, fits it using the Flat-Top-Gaussian function,
        and calculates calibration parameters. It optionally displays the fitted plots.

        Parameters:
        -----------
        folderpath : str, optional
            The base folder path where calibration data is stored (default is "Kalibrierung").
        foldername : str, optional
            The name of the folder within folderpath (default is '').
        bounds : tuple, optional
            Bounds for the curve fitting optimization. Parameters are B, x0, a, n and y0 for the flattopgauss
            (default is ([0, 108, 0.1, 1, 0], [1, 118, 2, 5, 0.1])).
        showplots : bool, optional
            If True, displays plots of the fitted data (default is False).

        Behavior:
        ---------
        - Reads the calibration data files from the specified folder.
        - Fits the data using the Flat-Top-Gaussian function.
        - Calculates calibration parameters based on the fitted data.
        - Writes the calibration parameters to a CSV file.
        - Optionally displays plots of the fitted data.

        Example:
        --------
        >>> obj.calculate_autocalibration(showplots=True)
        """

        def flattopgauss(x, B=0.01, x0=23, a=1, n=2, y0=0):
            """
            The Flat-Top-Gaussian function used to fit power-angle data.

            Args:
            -----
            x : list or numpy array
                The input data points.
            B : float, optional
                Amplitude of the Gaussian. Defaults to 0.01.
            x0 : int, optional
                Mean value of the Gaussian. Defaults to 23.
            a : int, optional
                Width of the Gaussian. Defaults to 1.
            n : int, optional
                Power of the exponent in the Gaussian expression. Defaults to 2.
            y0 : int, optional
                Y-offset of the Flat-Top-Gaussian. Defaults to 0.

            Returns:
            --------
            numpy array
                The computed Flat-Top-Gaussian values for the input data points.

            Example:
            --------
            >>> flattopgauss(np.array([20, 21, 22, 23, 24, 25]))
            array([0.01004962, 0.0100025 , 0.01000004, 0.01      , 0.01000004, 0.0100025 ])
            """
            return B * np.exp(-(((x - x0) ** 2) / (a ** 2)) ** n) + y0

        if foldername == '':
            with open(f'{folderpath}/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
                f.seek(0)
                lines = f.read().split('\n')
                temp_datetime = f"{lines[-2].split()[0]}_{lines[-2].split()[1][:5].replace(':', '')}hrs"
            foldpath_cal_par = f'{folderpath}/{temp_datetime}'
        else:
            foldpath_cal_par = f'{folderpath}/{foldername}'

        foldpath_lowtohi = f'{foldpath_cal_par}/lowtohi'
        foldpath_hitolow = f'{foldpath_cal_par}/hitolow'

        def get_csv_files_and_data(folder):
            csv_files = glob.glob(f'{folder}/*.csv')
            data_frames = [pd.read_csv(file, delimiter=';') for file in csv_files]
            wavelengths = [df['Wavelength [nm]'][0] for df in data_frames]
            return data_frames, wavelengths

        df_list_lowtohi, wvlst_lowtohi = get_csv_files_and_data(foldpath_lowtohi)
        df_list_hitolow, wvlst_hitolow = get_csv_files_and_data(foldpath_hitolow)

        def fit_data_and_extract_x0(data_frames):
            x0_list = []
            popt_list = []
            for df in data_frames:
                popt, _ = curve_fit(flattopgauss, df['Angle [°]'], df['Power [W]'], bounds=bounds)
                popt_list.append(popt)
                x0_list.append(popt[1])  # append x0
            return x0_list, popt_list

        x0lst_lowtohi, popt_lowtohi = fit_data_and_extract_x0(df_list_lowtohi)
        x0lst_hitolow, popt_hitolow = fit_data_and_extract_x0(df_list_hitolow)

        par_lowtohi = np.polyfit(wvlst_lowtohi, x0lst_lowtohi, 1)
        par_hitolow = np.polyfit(wvlst_hitolow, x0lst_hitolow, 1)

        with open(f'{foldpath_cal_par}/twowayscan_cal_par(GUI).csv', 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Kalibrierung', 'm', 'b'])
            writer.writerow(['lo->hi (Kal 1)', par_lowtohi[0], par_lowtohi[1]])
            writer.writerow(['hi->lo (Kal 2)', par_hitolow[0], par_hitolow[1]])

        if showplots:
            def plot_data(df_list, popt_list):
                for df, popt in zip(df_list, popt_list):
                    plt.figure()
                    plt.plot(df['Angle [°]'], df['Power [W]'], 'b-', label='data')
                    plt.plot(df['Angle [°]'], flattopgauss(df['Angle [°]'], *popt), 'r-', label='fit')
                    plt.grid(True)
                    plt.ylim(bottom=0)
                    plt.legend()
                plt.show()  # TODO: Replace show() with draw() and the creation of a popup or similar.
                # Calling show() works, but does print "QCoreApplication::exec: The event loop is already
                # running" because GUI is already running

            plot_data(df_list_lowtohi, popt_lowtohi)
            plot_data(df_list_hitolow, popt_hitolow)
            # TODO: Implement what should happen after the calculations: Choosing the correct calibration data, etc.
