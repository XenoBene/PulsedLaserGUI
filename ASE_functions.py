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
        self.stage.setup_homing(velocity=self.stage.to_steps(10), offset_distance=self.stage.to_steps(4))
        self.stage.home(sync=False)

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

    def init_wavelength_to_angle_calibration(self, dfb, temp, lowtohi, folderpath="Kalibrierung"):
        if lowtohi:
            dfb.change_dfb_setTemp(float(temp))
            QtTest.QTest.qWait(20 * 1000)

        with open(folderpath+'/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
            f.seek(0)
            # f = f.read().split('\r\n')
            f = f.read().split('\n')
            if f[0] == '':
                temp_datetime = str(datetime.date.today()) + '_' + str(
                    datetime.datetime.now().strftime("%H:%M")).replace(":", "")+'hrs'
            else:
                temp_datetime = str(f[-2].split()[0])+'_'+str(f[-2].split()[1][0:5].replace(":", ""))+'hrs'

            folderpath = folderpath+f'/{temp_datetime}'
            folderpath_lowtohi = folderpath+'/lowtohi'
            folderpath_hitolo = folderpath+'/hitolow'

            os.makedirs(folderpath_lowtohi, exist_ok=True)
            os.makedirs(folderpath_hitolo, exist_ok=True)

            temp_wavelength = str(np.round(self.wlm.GetWavelength(1), 2)).replace('.', ',')

            if lowtohi:
                self.cal_folderpath = folderpath_lowtohi  # paste desired folder path at r''
                self.cal_filename = 'kal' + temp_wavelength + 'nm_lowtohi'
                # self.ac_direction_lowtohi = True
            else:
                self.cal_folderpath = folderpath_hitolo
                self.cal_filename = 'kal' + temp_wavelength + 'nm_hitolow'
                # self.ac_direction_lowtohi = False

            with open(self.cal_folderpath+'/'+self.cal_filename+'.csv', 'w', encoding='UTF8', newline='') as f:
                self.writer = csv.writer(f, delimiter=';')
                header = ['Time [s]', 'Wavelength [nm]', 'Power [W]', 'Angle [°]']
                self.writer.writerow(header)

    def wavelength_to_angle_calibration(self, dfb, powermeter, temp_list: list[float], calibration_bounds,
                                        startangle, endangle):
        if self.ac_begincal:
            stage_velocity = 5
            self.stage.setup_gen_move(backlash_distance=(136533*3))
            self.stage.scan_to_angle(startangle, stage_velocity)
            # TODO: QtTest is only for test purposes, find a different solution (e.g. QThread and while-loop?)
            QtTest.QTest.qWait(int(((abs(startangle-self.stage.to_degree(
                self.stage.get_position()))) / stage_velocity)*1000 + 3000))
            if (not self.stage.is_moving()) and np.round(
                    self.stage.to_degree(self.stage.get_position()), 1) == startangle:
                self.stage.setup_gen_move(backlash_distance=0)
                self.cal_old_time = time.time()  # TODO: Zeit woanders reinschreiben?
                self.ac_begincal = False

        if self.initcal_bool:
            if self.lowtohi:
                self.init_wavelength_to_angle_calibration(dfb, temp_list[self.autocal_iterator], True)
                self.stage.scan_to_angle(endangle, 0.5)
                self.autocalibration_progress.emit(int((self.autocal_iterator + 0.5) * 100 / len(temp_list)))
            else:
                self.init_wavelength_to_angle_calibration(dfb, temp_list[self.autocal_iterator], False)
                self.stage.scan_to_angle(startangle, 0.5)
                self.autocalibration_progress.emit(int((self.autocal_iterator + 1) * 100 / len(temp_list)))
            self.initcal_bool = False

        with open(self.cal_folderpath+'/'+self.cal_filename+'.csv', 'a', encoding='UTF8', newline='') as f:
            power = powermeter.get_power()
            cal_actual_time = np.round(
                time.time()-self.cal_old_time, decimals=4)
            cal_wavelength = np.round(self.wlm.GetWavelength(1), 6)
            cal_current_angle = self.stage.to_degree(self.stage.get_position())

            csv.writer(f, delimiter=';').writerow(
                [cal_actual_time, cal_wavelength, power, cal_current_angle])

            if not self.stage.is_moving() and self.lowtohi:
                self.lowtohi = False
                self.initcal_bool = True
            elif not self.stage.is_moving() and not self.lowtohi:
                self.lowtohi = True
                self.initcal_bool = True

                if ((len(temp_list)-1) == self.autocal_iterator):  # stop the timer, calculate
                    self.calculate_autocalibration(showplots=True,
                                                   bounds=calibration_bounds
                                                   )
                    powermeter.enable_autorange(True)
                    print("Auto calibration finished! Please select the new calibration parameters "
                          f"located in the '{self.cal_folderpath[:-8]}' folder. "
                          "Furthermore, please take a look at the fits to ensure that none of the fits "
                          "diverge.")
                    self.autocalibration_loop_timer.stop()
                    self.autocalibration_progress.emit(0)
                else:
                    self.autocal_iterator += 1

    def start_autocalibration(self, dfb, powermeter, calibration_bounds, startangle, endangle):
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
        def flattopgauss(x, B=0.01, x0=23, a=1, n=2, y0=0):
            """The Flat-Top-Gaussian function, used later to fit the power-angle data.

            Args:
                x (_type_): list of numbers.
                B (float, optional): Amplitude of Gaussian. Defaults to 0.01.
                x0 (int, optional): Mean value of Gaussian. Defaults to 23.
                a (int, optional): Width of Gaussian. Defaults to 1.
                n (int, optional): Power of expression in index of exp function. Defaults to 4.
                y0 (int, optional): The y-offset of the Flat-Top-Gaussian.

            Returns:
                _type_: list of numbers.
            """
            return B*np.exp(-(((x-x0)**2)/(a**2))**n)+y0
        if foldername == '':
            with open(folderpath+'/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
                f.seek(0)
                # f = f.read().split('\r\n')
                f = f.read().split('\n')
                temp_datetime = str(f[-2].split()[0])+'_'+str(f[-2].split()[1][0:5].replace(":", ""))+'hrs'
                foldpath_cal_par = folderpath+f'/{temp_datetime}'
        else:
            foldpath_cal_par = folderpath+'/'+foldername

        foldpath_lotohi = foldpath_cal_par+'/lowtohi'
        foldpath_hitolo = foldpath_cal_par+'/hitolow'

        csv_files_lotohi = glob.glob(foldpath_lotohi+'/*.csv')
        csv_files_hitolo = glob.glob(foldpath_hitolo+'/*.csv')
        df_list_lotohi = [pd.read_csv(file, delimiter=';')
                          for file in csv_files_lotohi]
        x0lst_lotohi = []
        df_list_hitolo = [pd.read_csv(file, delimiter=';') for file in csv_files_hitolo]
        x0lst_hitolo = []

        wvlst_lotohi = [df['Wavelength [nm]'][0] for df in df_list_lotohi]
        wvlst_hitolo = [df['Wavelength [nm]'][0] for df in df_list_hitolo]
        popt_lotohi = []
        popt_hitolo = []

        for df in df_list_lotohi:
            popt, pcov = curve_fit(flattopgauss, df['Angle [°]'], df['Power [W]'], bounds=bounds
                                   )
            popt_lotohi.append(popt)
            x0lst_lotohi.append(popt[1])  # append x0
        for df in df_list_hitolo:
            popt, pcov = curve_fit(flattopgauss, df['Angle [°]'], df['Power [W]'], bounds=bounds
                                   )
            popt_hitolo.append(popt)
            x0lst_hitolo.append(popt[1])  # append x0

        par_lotohi = np.polyfit(wvlst_lotohi, x0lst_lotohi, 1)
        par_hitolo = np.polyfit(wvlst_hitolo, x0lst_hitolo, 1)

        with open(foldpath_cal_par+'/twowayscan_cal_par(GUI).csv', 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            header = ['Kalibrierung', 'm', 'b']
            writer.writerow(header)
            writer.writerow(['lo->hi (Kal 1)', par_lotohi[0], par_lotohi[1]])
            writer.writerow(['hi->lo (Kal 2)', par_hitolo[0], par_hitolo[1]])

        if showplots:
            for i in range(0, len(popt_lotohi)):
                plt.figure()
                plt.plot(df_list_lotohi[i]['Angle [°]'],
                         df_list_lotohi[i]['Power [W]'], 'b-', label='data')
                plt.plot(df_list_lotohi[i]['Angle [°]'], flattopgauss(
                    df_list_lotohi[i]['Angle [°]'], *popt_lotohi[i]), 'r-', label='fit')
                plt.grid(True)
                plt.ylim(bottom=0)
                plt.legend()
            plt.show()  # TODO: Replace show() with draw() and the creation of a popup or similar. Calling show() works,
            # but does print "QCoreApplication::exec: The event loop is already running" because GUI is already running
            for i in range(0, len(popt_hitolo)):
                plt.figure()
                plt.plot(df_list_hitolo[i]['Angle [°]'],
                         df_list_hitolo[i]['Power [W]'], 'b-', label='data')
                plt.plot(df_list_hitolo[i]['Angle [°]'], flattopgauss(
                    df_list_hitolo[i]['Angle [°]'], *popt_hitolo[i]), 'r-', label='fit')
                plt.grid(True)
                plt.ylim(bottom=0)
                plt.legend()
            plt.show()  # TODO: Replace show(), see above
            # TODO: Implement what should happen after the calculations: Choosing the correct calibration data, etc.
