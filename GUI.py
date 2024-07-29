from PyQt6 import QtWidgets, uic, QtCore, QtTest
import ASE_functions
import WLM_functions
import DFB_functions
import LBO_functions
import BBO_functions
import Powermeter_functions
import pyvisa
import pandas as pd
import csv
import time
import numpy as np
from datetime import datetime


class MainWindow(QtWidgets.QMainWindow):
    update_textBox = QtCore.pyqtSignal(str)
    measurement_status = QtCore.pyqtSignal(bool)

    def __init__(self,
                 rm: pyvisa.ResourceManager,
                 wlm: WLM_functions.WavelengthMeter,
                 dfb: DFB_functions.DFB,
                 lbo: LBO_functions.LBO,
                 bbo: BBO_functions.BBO,
                 ase: ASE_functions.ASE,
                 pm1: Powermeter_functions.PM,
                 pm2: Powermeter_functions.PM
                 ):
        super().__init__()

        # Load the ui
        self.ui = uic.loadUi("pulsed_laser_interface.ui", self)

        self.rm = rm
        self.wlm = wlm
        self.dfb = dfb
        self.lbo = lbo
        self.bbo = bbo
        self.ase = ase
        self.pm1 = pm1
        self.pm2 = pm2

        self.data_uv = 0.0
        self.data_steps = 0
        self.data_pm1 = 0.0
        self.data_pm2 = 0.0
        self.data_wl = 0.0
        self.data_lbo_act = 0.0
        self.data_lbo_set = 0.0

        # Signal/Slots:
        self.dfb.widescan_status.connect(self.status_checkBox_wideScan.setChecked)
        self.dfb.widescan_status.connect(lambda bool:
                                         self.status_label_wideScan.setText("T[°C] =") if not bool else None)
        self.dfb.widescan_status.connect(lambda bool: self.disable_tab_widgets(
            "DFB_tab", self.dfb_button_abortScan, bool))
        self.dfb.update_values.connect(lambda values: self.dfb_update_values(*values))
        self.dfb.widescan_finished.connect(self.reset_wideScan_progressBar)
        self.dfb.update_progressbar.connect(lambda values: self.update_widescan_progressbar(*values))
        self.dfb.update_actTemp.connect(lambda value: self.dfb_label_actTemp.setText(f"Actual temperature: {value} °C"))
        self.dfb.update_actTemp.connect(lambda value: self.status_label_wideScan.setText(f"T[°C] = {value}"))

        self.bbo.voltageUpdated.connect(lambda value:
                                        self.bbo_label_diodeVoltage.setText(f"UV Diode Voltage [V]: {value}"))
        self.bbo.autoscan_status_single.connect(self.status_checkBox_bbo.setChecked)
        self.bbo.autoscan_status_double.connect(self.status_checkBox_bbo.setChecked)
        self.bbo.autoscan_status_single.connect(lambda bool: self.status_label_bbo.setText("U[V] =") if not bool else None)
        self.bbo.autoscan_status_double.connect(lambda bool: self.status_label_bbo.setText("U[V] =") if not bool else None)
        self.bbo.autoscan_status_single.connect(lambda bool: self.disable_tab_widgets(
            "BBO_tab", self.bbo_button_stopUvScan, bool))
        self.bbo.autoscan_status_single.connect(lambda: self.bbo_button_stopUvScan_double.setDisabled(True))
        self.bbo.autoscan_status_double.connect(lambda bool: self.disable_tab_widgets(
            "BBO_tab", self.bbo_button_stopUvScan_double, bool))
        self.bbo.autoscan_status_double.connect(lambda: self.bbo_button_stopUvScan.setDisabled(True))
        self.bbo.autoscan_status_single.connect(self.bbo_button_stopUvScan.setEnabled)
        self.bbo.autoscan_status_double.connect(self.bbo_button_stopUvScan_double.setEnabled)
        self.bbo.voltageUpdated.connect(lambda value: setattr(self, "data_uv", value))
        self.bbo.voltageUpdated.connect(lambda value: self.status_label_bbo.setText(f"U[V] = {value}"))
        self.bbo.stepsUpdated.connect(lambda value: setattr(self, "data_steps", value))

        self.lbo.autoscan_status.connect(self.status_checkBox_lbo.setChecked)
        self.lbo.autoscan_status.connect(lambda bool: self.status_label_lbo.setText("T[°C] =") if not bool else None)
        self.lbo.autoscan_status.connect(lambda bool: self.disable_tab_widgets(
            "LBO_tab", self.lbo_button_autoScan_stop, bool))
        self.lbo.update_set_temperature.connect(
            lambda temp: self.lbo_label_setTemp.setText(f"Set temperature [°C]: {temp}"))
        self.lbo.update_set_temperature.connect(lambda temp: setattr(self, "data_lbo_set", temp))
        self.lbo.update_act_temperature.connect(
            lambda temp: self.lbo_label_actTemp.setText(f"Actual temperature [°C]: {temp}"))
        self.lbo.update_act_temperature.connect(lambda value: self.status_label_lbo.setText(f"T[°C] = {value}"))
        self.lbo.update_act_temperature.connect(lambda temp: setattr(self, "data_lbo_act", temp))

        self.ase.autoscan_status.connect(self.status_checkBox_ase.setChecked)
        self.ase.autoscan_status.connect(lambda bool: self.status_label_ase.setText("theta[°] =") if not bool else None)
        self.ase.autoscan_status.connect(lambda bool: self.disable_tab_widgets(
            "ASE_tab", self.ase_button_autoScan_stop, bool))
        self.ase.update_wl_pos.connect(lambda values: (
            self.ase_label_currentWL.setText(f"Current Wavelength: {values[0]}"),
            self.ase_label_currentAngle.setText(f"Current Angle: {values[1]}")
            ))
        self.ase.update_wl_pos.connect(lambda values: self.status_label_ase.setText(f"theta[°] = {values[1]}"))
        self.ase.update_wl_pos.connect(lambda values: setattr(self, "data_wl", values[0]))
        self.ase.autoscan_failsafe.connect(self.dfb.abort_wideScan)
        self.ase.autocalibration_progress.connect(lambda progress: self.ase_progressBar_autocal.setValue(progress))

        self.pm1.updateWavelength.connect(lambda wl: self.pm_lineEdit_enterWL1.setText(str(wl)))
        self.pm2.updateWavelength.connect(lambda wl: self.pm_lineEdit_enterWL2.setText(str(wl)))
        self.pm1.updatePower.connect(lambda pow: self.pm_label_power1.setText(f"Power PM1: {pow} W"))
        self.pm2.updatePower.connect(lambda pow: self.pm_label_power2.setText(f"Power PM2: {pow} W"))

        self.pm1.update_textBox.connect(self.update_status_text)
        self.pm2.update_textBox.connect(self.update_status_text)
        self.dfb.update_textBox.connect(self.update_status_text)
        self.lbo.update_textBox.connect(self.update_status_text)
        self.bbo.update_textBox.connect(self.update_status_text)
        self.ase.update_textBox.connect(self.update_status_text)
        self.update_textBox.connect(self.update_status_text)

        self.measurement_status.connect(lambda bool: self.disable_tab_widgets(
            "general_tab", self.general_button_stopMeasurement, bool))

    def connect_buttons(self):
        """
        Connect the buttons from the UI with the methods.
        The names of the buttons have to be looked up in the .ui file
        with QT Designer.
        """
        """DFB Tab buttons:"""
        self.dfb_button_connectDfb.clicked.connect(
            lambda: self.dfb.connect_dfb(ip=str(self.dfb_lineEdit_ip.text())))
        self.dfb_button_readValues.clicked.connect(
            lambda: self.dfb_update_values(*self.dfb.read_actual_dfb_values()))
        self.dfb_spinBox_setTemp.valueChanged.connect(
            lambda: self.dfb.change_dfb_setTemp(self.dfb_spinBox_setTemp.value()))
        self.dfb_lineEdit_scanStartTemp.editingFinished.connect(
            lambda: self.dfb.change_wideScan_startTemp(self.dfb_lineEdit_scanStartTemp.text()))
        self.dfb_lineEdit_scanEndTemp.editingFinished.connect(
            lambda: self.dfb.change_wideScan_endTemp(self.dfb_lineEdit_scanEndTemp.text()))
        self.dfb_lineEdit_scanSpeed.editingFinished.connect(
            lambda: self.dfb.change_wideScan_scanSpeed(self.dfb_lineEdit_scanSpeed.text()))
        # TODO: Lieber einen "Set value" Knopf einbauen mit print Bestätigung statt dem editingFinished,
        # dann ist das alles konsistenter
        self.dfb_button_startScan.clicked.connect(self.dfb.start_wideScan)
        self.dfb_button_abortScan.clicked.connect(self.dfb.abort_wideScan)

        """LBO Tab buttons:"""
        self.lbo_comboBox_visa.addItems(self.rm.list_resources())
        self.lbo_button_refresh.clicked.connect(lambda: self.refresh_combobox(self.lbo_comboBox_visa))
        self.lbo_button_connectLBO.clicked.connect(
            lambda: self.lbo.connect_covesion(rm=self.rm, port=self.lbo_comboBox_visa.currentText())
        )
        self.lbo_button_connectLBO.clicked.connect(self.lbo_update_values)
        self.lbo_button_readValues.clicked.connect(self.lbo.read_values)
        self.lbo_button_readValues.clicked.connect(self.lbo_update_values)
        self.lbo_button_setTemp.clicked.connect(
            lambda: self.lbo.set_temperature(self.lbo_lineEdit_targetTemp.text(),
                                             self.lbo_lineEdit_rampSpeed.text())
        )
        # self.lbo_button_autoScan.clicked.connect(lambda: self.lbo.toggle_autoscan(wlm=self.wlm))
        self.lbo_button_autoScan_start.clicked.connect(lambda: self.lbo.start_autoscan(wlm=self.wlm))
        self.lbo_button_autoScan_stop.clicked.connect(self.lbo.stop_autoscan)

        """BBO Tab buttons:"""
        self.bbo_button_connectPiezo.clicked.connect(self.bbo.connect_piezos)
        self.bbo_button_connectRP.clicked.connect(
            lambda: self.bbo.connect_red_pitaya(ip=str(self.bbo_lineEdit_ipRedPitaya.text())))

        # Second/Back BBO:
        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.text()), False))
        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.move_by(int(self.bbo_lineEdit_relativeSteps.text()), False))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.text()), False))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.move_by(-int(self.bbo_lineEdit_relativeSteps.text()), False))

        # Single BBO setup:
        self.bbo_button_startUvScan.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity.text(),
                steps=self.bbo_lineEdit_steps.text(),
                wait=self.bbo_lineEdit_break.text(),
                double_bbo_setup=False))
        self.bbo_button_startUvScan.clicked.connect(lambda: self.bbo.start_autoscan(wlm=self.wlm))
        self.bbo_button_stopUvScan.clicked.connect(self.bbo.stop_autoscan)

        # First/Front BBO:
        self.bbo_button_forwards_front.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity_front.text()), True))
        self.bbo_button_forwards_front.clicked.connect(
            lambda: self.bbo.move_by(int(self.bbo_lineEdit_relativeSteps_front.text()), True))
        self.bbo_button_back_front.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity_front.text()), True))
        self.bbo_button_back_front.clicked.connect(
            lambda: self.bbo.move_by(-int(self.bbo_lineEdit_relativeSteps_front.text()), True))

        # Double BBO setup:
        self.bbo_button_startUvScan_double.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity_double.text(),
                steps=self.bbo_lineEdit_steps_double.text(),
                wait=self.bbo_lineEdit_break_double.text(),
                double_bbo_setup=True))
        self.bbo_button_startUvScan_double.clicked.connect(lambda: self.bbo.start_autoscan_double(wlm=self.wlm))
        self.bbo_button_stopUvScan_double.clicked.connect(self.bbo.stop_autoscan_double)

        """ASE Tab buttons:"""
        self.ase_button_connectStage.clicked.connect(
            lambda: self.ase.connect_rotationstage(self.ase_lineEdit_stage.text()))
        self.ase_button_moveToStart.clicked.connect(lambda: self.ase.move_to_start(wlm=self.wlm))
        self.ase_button_autoScan_start.clicked.connect(lambda: self.ase.start_autoscan(wlm=self.wlm))
        self.ase_button_autoScan_stop.clicked.connect(self.ase.stop_autoscan)
        self.ase_button_home.clicked.connect(self.ase_homing_popup)
        self.ase_button_startAutoCal.clicked.connect(self.autocalibration_popup)
        self.ase_button_selectPath.clicked.connect(self.open_calparfile)

        """PM Tab buttons:"""
        self.pm_comboBox_visaResources1.addItems(self.rm.list_resources())
        self.pm_comboBox_visaResources2.addItems(self.rm.list_resources())
        self.pm_button_connectPM1.clicked.connect(
            lambda: self.pm1.connect_pm(visa=self.pm_comboBox_visaResources1.currentText()))
        self.pm_button_connectPM2.clicked.connect(
            lambda: self.pm2.connect_pm(visa=self.pm_comboBox_visaResources2.currentText()))
        self.pm_button_changeWL1.clicked.connect(lambda:
                                                 self.pm1.set_wavelength(self.pm_lineEdit_enterWL1.text()))
        self.pm_button_changeWL2.clicked.connect(lambda:
                                                 self.pm2.set_wavelength(self.pm_lineEdit_enterWL2.text()))

        """General Tab buttons:"""
        self.general_button_selectPath.clicked.connect(self.create_measurement_file)
        self.general_button_startMeasurement.clicked.connect(self.start_measurement)
        self.general_button_stopMeasurement.clicked.connect(self.stop_measurement)

    def update_status_text(self, text):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.status_textEdit.insertPlainText(f"{timestamp} - {text}\n")

    def refresh_combobox(self, combobox):
        combobox.clear()
        combobox.addItems(self.rm.list_resources())

    def create_measurement_file(self):
        self.file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv)")
        self.general_label_chosenPath.setText(self.file_path)

    def start_measurement(self):
        self.measurement_loop_timer = QtCore.QTimer()
        start_time = time.time()
        self.measurement_loop_timer.timeout.connect(lambda: self.measurement(start_time))
        try:
            with open(self.file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(["Time [s]", "Timestamp", "Wavelength [nm]", "Power PM1 [W]", "Power PM2 [W]",
                                 "Motor position [steps]", "UV photodiode voltage [V]", "LBO temperature (act) [°C]",
                                 "LBO temperature (set) [°C]"])
            self.measurement_loop_timer.start(1000)
            self.measurement_status.emit(True)
        except AttributeError:
            self.update_textBox.emit("Couldn't start measurement: No file path chosen")
        except FileNotFoundError:
            self.update_textBox.emit("Couldn't start measurement: No file path chosen")

    def stop_measurement(self):
        self.measurement_loop_timer.stop()
        self.measurement_status.emit(False)

    def measurement(self, start_time):
        timestamp = time.time()
        time_since_start = np.round(timestamp - start_time, 6)

        data_pm1 = 0.0
        data_pm2 = 0.0
        data_wl = 0.0
        data_steps = 0
        data_uv = 0.0
        data_lbo_act = 0.0
        data_lbo_set = 0.0

        if self.general_checkbox_savePower1.isChecked():
            try:
                data_pm1 = self.pm1.get_power()
            except AttributeError:
                data_pm1 = 0.0
        if self.general_checkbox_savePower2.isChecked():
            try:
                data_pm2 = self.pm2.get_power()
            except AttributeError:
                data_pm2 = 0.0
        if self.general_checkbox_saveWL.isChecked():
            data_wl = self.data_wl
        if self.general_checkbox_saveMotorSteps.isChecked():
            data_steps = self.data_steps
        if self.general_checkbox_saveUvPdVolt.isChecked():
            data_uv = self.data_uv
        if self.general_checkbox_saveLboTemp.isChecked():
            data_lbo_act = self.data_lbo_act
            data_lbo_set = self.data_lbo_set

        with open(self.file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow([time_since_start, timestamp, data_wl, data_pm1,
                             data_pm2, data_steps, data_uv, data_lbo_act, data_lbo_set])
        self.reset_data_storage()

    def reset_data_storage(self):
        self.data_uv = 0.0
        self.data_steps = 0
        self.data_wl = 0.0
        self.data_lbo_act = 0.0
        self.data_lbo_set = 0.0

    def lbo_update_values(self):
        """Updates the GUI with the latest values for the
        ramp rate and the set temperature.
        """
        try:
            self.lbo_lineEdit_rampSpeed.setText(str(self.lbo.rate))
            self.lbo_lineEdit_targetTemp.setText(str(self.lbo.set_temp))
        except AttributeError as e:
            self.update_textBox(f"Covesion oven is not connected: {e}")

    def disable_tab_widgets(self, tab_name, excluded_widget, disable):
        tab = self.findChild(QtWidgets.QWidget, tab_name)
        for widget in tab.findChildren(QtWidgets.QWidget):
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QPushButton,
                                   QtWidgets.QComboBox, QtWidgets.QDoubleSpinBox,
                                   QtWidgets.QCheckBox)):
                if widget == excluded_widget:
                    widget.setEnabled(disable)
                else:
                    widget.setDisabled(disable)

    def dfb_update_values(self, set_temp, start_temp, end_temp, scan_speed):
        """Updates the GUI with the last known attributes of the set temperature,
        start & end temperature of the WideScan and the scan speed.

        Args:
            set_temp (float): Set temperature of the dfb diode [°C]
            start_temp (float): Start temperature of the WideScan [°C]
            end_temp (float): End temperature of the WideScan [°C]
            scan_speed (float): WideScan scan speed [K/s]
        """
        try:
            self.dfb_spinBox_setTemp.setValue(set_temp)
            self.dfb_lineEdit_scanStartTemp.setText(str(start_temp))
            self.dfb_lineEdit_scanEndTemp.setText(str(end_temp))
            self.dfb_lineEdit_scanSpeed.setText(str(scan_speed))
        except AttributeError as e:
            self.update_textBox(f"DFB is not connected: {e}")
        except TypeError as e:
            self.update_textBox(f"Error: {e}")

    def update_widescan_progressbar(self, progress, time):
        """
        Updates the progress bar and remaining time label during a wide scan.

        Parameters:
        -----------
        progress : int
            The current progress value to set on the progress bar.
        time : float
            The remaining time in seconds to display.

        Behavior:
        ---------
        - Sets the progress bar to the specified progress value.
        - Updates the remaining time label with the specified time.

        Example:
        --------
        >>> obj.update_widescan_progressbar(50, 120.5)
        """
        self.dfb_progressBar_scan.setValue(progress)
        self.dfb_label_remainingTime.setText(f"Remaining time: {time} s")

    def reset_wideScan_progressBar(self):
        """
        Resets the wide scan progress bar and related labels.

        Behavior:
        ---------
        - Resets the progress bar to its initial state.
        - Clears the actual temperature and remaining time labels.

        Example:
        --------
        >>> obj.reset_wideScan_progressBar()
        """
        self.dfb_label_actTemp.setText("Actual temperature: ")
        self.dfb_progressBar_scan.reset()
        self.dfb_label_remainingTime.setText("Remaining time: ")

    def ase_homing_popup(self):
        popup = QtWidgets.QMessageBox.question(
            self, 'Motor Homing',
            "Home the ASE filter rotation stage? Only press 'Yes' if all fiber amplifiers are turned off!",
            buttons=QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if popup == QtWidgets.QMessageBox.StandardButton.Yes:
            self.ase.homing_motor()

    def autocalibration_popup(self):
        """
        Displays a popup to initiate the auto-calibration process.

        This method reads the calibration log to display the previous calibration date and time,
        and prompts the user to start the auto-calibration of the rotation stage. If the user
        confirms, the auto-calibration process is initiated.

        Behavior:
        ---------
        - Reads the previous calibration details from the log file.
        - Displays a message box with instructions for the calibration process.
        - If the user clicks 'Yes', starts the auto-calibration.
        - If the user clicks 'No', does nothing.

        Example:
        --------
        >>> obj.autocalibration_popup()
        """
        with open(r'Kalibrierung/calibrationlog.log', mode='a+', encoding='UTF8', newline="\n") as f:
            f.seek(0)
            # f = f.read().split('\r\n')
            f = f.read().split('\n')
            if f == ['']:
                previous_cal = ("No calibration previously recorded. ")
            else:
                previous_cal = (f"Previous calibration: {f[-2].split()[0]} {f[-2].split()[1]} hrs. ")

            autocal_msg_str = (previous_cal +
                               "To perform the calibration of the rotation stage, please place "
                               "the desired powermeter directly after the first fibre amplifier. "
                               "Ensure that the WLM and rotation stage are connected beforehand. "
                               "Please connect the required powermeter with the 'PM1' button. "
                               "Then, please click 'Yes'.")
            autocal_request = QtWidgets.QMessageBox.question(self,
                                                             'Initiate auto calibration',
                                                             autocal_msg_str,
                                                             buttons=QtWidgets.QMessageBox.StandardButton.Yes
                                                             | QtWidgets.QMessageBox.StandardButton.No)
        if autocal_request == QtWidgets.QMessageBox.StandardButton.Yes:
            # TODO: Starte Autokalibration, dabei darf nichts anklickbar sein
            self.ase.start_autocalibration(wlm=self.wlm, dfb=self.dfb, powermeter=self.pm1,
                                           calibration_bounds=([float(self.ase_cal_B_lower.text()),
                                                                float(self.ase_cal_x0_lower.text()),
                                                                float(self.ase_cal_a_lower.text()),
                                                                float(self.ase_cal_n_lower.text()),
                                                                float(self.ase_cal_y0_lower.text())],
                                                               [float(self.ase_cal_B_upper.text()),
                                                                float(self.ase_cal_x0_upper.text()),
                                                                float(self.ase_cal_a_upper.text()),
                                                                float(self.ase_cal_n_upper.text()),
                                                                float(self.ase_cal_y0_upper.text())]),
                                           startangle=float(self.ase_cal_startangle.text()),
                                           endangle=float(self.ase_cal_endangle.text())
                                           )
        elif autocal_request == QtWidgets.QMessageBox.StandardButton.No:
            # TODO: Mache nichts
            pass

    def open_calparfile(self):
        """
        Opens a file dialog to select a calibration parameter file.

        This method allows the user to select a CSV file containing calibration parameters.
        It reads the selected file, validates its contents, and updates the calibration parameters.

        Behavior:
        ---------
        - Opens a file dialog for the user to select a CSV file.
        - Reads the selected file and updates the calibration parameters.
        - Saves the last used calibration parameters to a CSV file.
        - Updates the display with the path of the selected file.

        Error Handling:
        ---------------
        - If the selected file is not found, prints "File not found!".
        - If the selected file does not contain the required keys, prints an error message.

        Example:
        --------
        >>> obj.open_calparfile()
        """
        try:
            calparfilename, _ = QtWidgets.QFileDialog.getOpenFileName(
                parent=self, caption="Select path", directory="", filter="All Files (*);;(*.csv)")
            if calparfilename != "":
                self.ase.cal_par = pd.read_csv(calparfilename, delimiter=';')
                try:
                    # call self.cal_par: if rubbish file is loaded, then there will be no key
                    # the corresponding names below. code then throws an error
                    with open(r"lastused_calpar.csv", 'w', encoding='UTF8', newline='') as f:
                        writer = csv.writer(f, delimiter=';')
                        header = ['Kalibrierung', 'm', 'b']
                        writer.writerow(header)
                        writer.writerow(['lo->hi (Kal 1)', self.ase.cal_par["m"][0], self.ase.cal_par["b"][0]])
                        writer.writerow(['hi->lo (Kal 2)', self.ase.cal_par["m"][1], self.ase.cal_par["b"][1]])

                    self.ase_label_pathText.setText(calparfilename)
                except KeyError:
                    self.update_textBox("Please select a valid file with the motor calibration parameters!")
        except FileNotFoundError:
            self.update_textBox("File not found!")
