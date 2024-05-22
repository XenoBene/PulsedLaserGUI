from PyQt6 import QtCore
from ThorlabsRotationStage import Stage
import pylablib
from pylablib.devices.Thorlabs.base import ThorlabsBackendError
import numpy as np
import pandas as pd
import time
import datetime
import os
import csv


class ASE(QtCore.QObject):
    autoscan_status = QtCore.pyqtSignal(bool)
    update_wl_pos = QtCore.pyqtSignal(tuple)
    autoscan_failsafe = QtCore.pyqtSignal()

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
            dfb.change_dfb_setTemp(temp)
            # TODO: Wait until settled

        with open(folderpath+'/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
            f.seek(0)
            f = f.read().split('\r\n')
            if f[0] == '':
                temp_datetime = str(datetime.date.today(
                )) + '_' + str(datetime.datetime.now().strftime("%H:%M")).replace(":", "")+'hrs'
                folderpath = folderpath+f'/{temp_datetime}'
                folderpath_lowtohi = folderpath+'/lowtohi'
                folderpath_hitolo = folderpath+'/hitolow'
            else:
                temp_datetime = str(
                    f[-2].split()[0])+'_'+str(f[-2].split()[1][0:5].replace(":", ""))+'hrs'
                folderpath = folderpath+f'/{temp_datetime}'
                folderpath_lowtohi = folderpath+'/lowtohi'
                folderpath_hitolo = folderpath+'/hitolow'

            os.makedirs(folderpath_lowtohi, exist_ok=True)
            os.makedirs(folderpath_hitolo, exist_ok=True)

            temp_wavelength = str(np.round(self.wlm.GetWavelength(1), 2)).replace('.', ',')

            if lowtohi:
                cal_folderpath = folderpath_lowtohi  # paste desired folder path at r''
                cal_filename = 'kal' + temp_wavelength + 'nm_lowtohi'
                # self.ac_direction_lowtohi = True
            else:
                cal_folderpath = folderpath_hitolo
                cal_filename = 'kal' + temp_wavelength + 'nm_hitolow'
                # self.ac_direction_lowtohi = False

            with open(cal_folderpath+'/'+cal_filename+'.csv', 'w', encoding='UTF8', newline='') as f:
                self.writer = csv.writer(f, delimiter=';')
                header = ['Time [s]', 'Wavelength [nm]', 'Power [W]', 'Angle [°]']
                self.writer.writerow(header)

    def wavelength_to_angle_calibration(self, dfb, temp_list: list[float]):
        # TODO: Autokalibrierung einbauen von Ryan
        if self.ac_begincal:
            stage_velocity = 5
            self.stage.setup_gen_move(backlash_distance=(136533*3))
            self.stage.scan_to_angle(self.ac_startangle, stage_velocity)
            # TODO: Warte bis Motor sich fertigbewegt hat
            """QtTest.QTest.qWait(int(
                ((abs(self.ac_startangle-to_degree(self.stage.get_position()))) / stage_velocity)*1000 + 3000))"""
            if (not self.stage.is_moving()) and np.round(self.stage.to_degree(self.stage.get_position()), 1) == self.ac_startangle:
                self.stage.setup_gen_move(backlash_distance=0)
                self.cal_old_time = time.time()  # TODO: Zeit woanders reinschreiben?
                self.ac_begincal = False

        if self.lowtohi:
            if self.initcal_bool:
                self.init_wavelength_to_angle_calibration(dfb, temp_list[self.autocal_iterator], True)
                self.stage.scan_to_angle(self.ac_endangle, 0.5)
                print('Stage starts moving')
                self.initcal_bool = False

            with open(self.cal_folderpath+'/'+self.cal_filename+'.csv', 'a', encoding='UTF8', newline='') as f:
                power = self.get_power()  # TODO: Implementiere PM160
                cal_actual_time = np.round(
                    time.time()-self.cal_old_time, decimals=4)
                cal_wavelength = np.round(self.wlm.GetWavelength(1), 6)
                cal_current_angle = self.stage.to_degree(self.stage.get_position())

                csv.writer(f, delimiter=';').writerow(
                    [cal_actual_time, cal_wavelength, power, cal_current_angle])

                if not self.stage.is_moving():
                    self.lowtohi = False
                    self.initcal_bool = True
        else:
            if self.initcal_bool:
                self.init_wavelength_to_angle_calibration(dfb, temp_list[self.autocal_iterator], False)
                self.stage.scan_to_angle(self.ac_startangle, 0.5)
                print('Stage starts moving')
                self.initcal_bool = False

            with open(self.cal_folderpath+'/'+self.cal_filename+'.csv', 'a', encoding='UTF8', newline='') as f:
                power = self.get_power()  # TODO: Implementiere PM160
                cal_actual_time = np.round(
                    time.time()-self.cal_old_time, decimals=4)
                cal_wavelength = np.round(self.wlm.GetWavelength(1), 6)
                cal_current_angle = self.stage.to_degree(self.stage.get_position())
                csv.writer(f, delimiter=';').writerow(
                    [cal_actual_time, cal_wavelength, power, cal_current_angle])

                if not self.stage.is_moving():
                    self.lowtohi = True
                    self.initcal_bool = True

                    if ((len(temp_list)-1) == self.autocal_iterator):  # stop the timer, calculate
                        self.stage_calibration(showplots=True,
                                               bounds=([self.ac_B_lower, self.ac_x0_lower, self.ac_a_lower, self.ac_n_lower, self.ac_y0_lower],
                                                       [self.ac_B_upper, self.ac_x0_upper, self.ac_a_upper, self.ac_n_upper, self.ac_y0_upper])
                                               )
                        # self.pm1.write('SENS:POW:RANG:AUTO ON')  # TODO: Autorange wieder an beim Messkopf
                        print("Auto calibration finished! Please select the new calibration parameters "
                              f"located in the '{self.cal_folderpath[:-8]}' folder. "
                              "Furthermore, please take a look at the fits to ensure that none of the fits "
                              "diverge.")
                    else:
                        self.autocal_iterator += 1
