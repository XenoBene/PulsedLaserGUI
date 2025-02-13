from PyQt6 import QtWidgets, uic, QtCore, QtGui
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

        # Initialise all values that can be written to file:
        self.data_uv = 0.0
        self.data_steps_front = 0
        self.data_steps_back = 0
        self.data_pm1 = 0.0
        self.data_pm2 = 0.0
        self.data_wl = 0.0
        self.data_lbo_act = 0.0
        self.data_lbo_set = 0.0

        # Signal/Slot connection for DFB tab:
        self.dfb.widescan_status.connect(self.status_checkBox_wideScan.setChecked)
        self.dfb.widescan_status.connect(lambda bool:
                                         self.status_label_wideScan.setText("T[°C] =") if not bool else None)
        self.dfb.widescan_status.connect(lambda bool: self.disable_tab_widgets(
            "DFB_tab", bool, excluded_widget=self.dfb_button_abortScan))
        self.dfb.update_values.connect(lambda values: self.dfb_update_values(*values))
        self.dfb.widescan_finished.connect(self.reset_wideScan_progressBar)
        self.dfb.update_progressbar.connect(lambda values: self.update_widescan_progressbar(*values))
        self.dfb.update_actTemp.connect(lambda value: self.dfb_label_actTemp.setText(f"Actual temperature: {value} °C"))
        self.dfb.update_actTemp.connect(lambda value: self.status_label_wideScan.setText(f"T[°C] = {value}"))
        self.dfb.wl_stabil_status.connect(lambda bool: self.disable_tab_widgets(
            "DFB_tab", bool, excluded_widget=self.dfb_button_stop_wl_stabil,
            ignored_widgets=[self.dfb_button_wl_step_forward, self.dfb_button_wl_step_back, self.dfb_lineEdit_wl_step]))
        self.dfb.update_wl_current.connect(lambda values: (
            self.dfb_label_currentWL.setText(f"Wavelength: {values[0]}"),
            self.dfb_label_injectionCurrent.setText(f"Injection Current: {values[1]}")
            ))
        self.dfb.update_target_wavelength.connect(lambda wl: self.dfb_lineEdit_wl_stabil.setValue(wl))

        # Signal/Slot connection for BBO tab:
        self.bbo.voltageUpdated.connect(lambda value:
                                        self.bbo_label_diodeVoltage.setText(f"UV Diode Voltage [V]: {value}"))
        self.bbo.autoscan_status_single.connect(self.status_checkBox_bbo.setChecked)
        self.bbo.autoscan_status_double.connect(self.status_checkBox_bbo.setChecked)
        self.bbo.autoscan_status_single.connect(
            lambda bool: self.status_label_bbo.setText("U[V] =") if not bool else None)
        self.bbo.autoscan_status_double.connect(
            lambda bool: self.status_label_bbo.setText("U[V] =") if not bool else None)
        self.bbo.autoscan_status_single.connect(lambda bool: self.disable_tab_widgets(
            "BBO_tab", bool, excluded_widget=self.bbo_button_stopUvScan,
            ignored_widgets=[self.bbo_button_generateSignal]))
        self.bbo.autoscan_status_single.connect(lambda: self.bbo_button_stopUvScan_double.setDisabled(True))
        self.bbo.autoscan_status_single.connect(lambda: self.bbo_button_stopDiodeVoltage.setDisabled(True))
        self.bbo.autoscan_status_double.connect(lambda bool: self.disable_tab_widgets(
            "BBO_tab", bool, excluded_widget=self.bbo_button_stopUvScan_double))
        self.bbo.autoscan_status_double.connect(lambda: self.bbo_button_stopUvScan.setDisabled(True))
        self.bbo.autoscan_status_double.connect(lambda: self.bbo_button_stopDiodeVoltage.setDisabled(True))
        self.bbo.autoscan_status_single.connect(self.bbo_button_stopUvScan.setEnabled)
        self.bbo.autoscan_status_double.connect(self.bbo_button_stopUvScan_double.setEnabled)
        self.bbo.voltageUpdated.connect(lambda value: setattr(self, "data_uv", value))
        self.bbo.voltageUpdated.connect(lambda value: self.status_label_bbo.setText(f"U[V] = {value}"))
        self.bbo.stepsUpdatedFront.connect(lambda value: setattr(self, "data_steps_front", value))
        self.bbo.stepsUpdatedBack.connect(lambda value: setattr(self, "data_steps_back", value))
        self.bbo.measurement_status.connect(lambda bool: self.disable_tab_widgets(
            "BBO_tab", bool, excluded_widget=self.bbo_button_stopDiodeVoltage,
            ignored_widgets=[self.bbo_button_generateSignal]))
        self.bbo.measurement_status.connect(lambda: self.bbo_button_stopUvScan.setDisabled(True))
        self.bbo.measurement_status.connect(lambda: self.bbo_button_stopUvScan_double.setDisabled(True))

        # Signal/Slot connection for LBO tab:
        self.lbo.autoscan_status.connect(self.status_checkBox_lbo.setChecked)
        self.lbo.autoscan_status.connect(lambda bool: self.status_label_lbo.setText("T[°C] =") if not bool else None)
        self.lbo.autoscan_status.connect(lambda bool: self.disable_tab_widgets(
            "LBO_tab", bool, excluded_widget=self.lbo_button_autoScan_stop))
        self.lbo.update_set_temperature.connect(
            lambda temp: self.lbo_label_setTemp.setText(f"Set temperature [°C]: {temp}"))
        self.lbo.update_set_temperature.connect(lambda temp: setattr(self, "data_lbo_set", temp))
        self.lbo.update_act_temperature.connect(
            lambda temp: self.lbo_label_actTemp.setText(f"Actual temperature [°C]: {temp}"))
        self.lbo.update_act_temperature.connect(lambda value: self.status_label_lbo.setText(f"T[°C] = {value}"))
        self.lbo.update_act_temperature.connect(lambda temp: setattr(self, "data_lbo_act", temp))

        # Signal/Slot connection for ASE filter tab:
        self.ase.autoscan_status.connect(self.status_checkBox_ase.setChecked)
        self.ase.autoscan_status.connect(lambda bool: self.status_label_ase.setText("theta[°] =") if not bool else None)
        self.ase.autoscan_status.connect(lambda bool: self.disable_tab_widgets(
            "ASE_tab", bool, excluded_widget=self.ase_button_autoScan_stop))
        self.ase.update_wl_pos.connect(lambda values: (
            self.ase_label_currentWL.setText(f"Current Wavelength: {values[0]}"),
            self.ase_label_currentAngle.setText(f"Current Angle: {values[1]}")
            ))
        self.ase.update_wl_pos.connect(lambda values: self.status_label_ase.setText(f"theta[°] = {values[1]}"))
        self.ase.update_wl_pos.connect(lambda values: setattr(self, "data_wl", values[0]))
        self.ase.autoscan_failsafe.connect(self.dfb.abort_wideScan)
        self.ase.autocalibration_progress.connect(lambda progress: self.ase_progressBar_autocal.setValue(progress))

        # Signal/Slot connection for PM tab:
        self.pm1.updateWavelength.connect(lambda wl: self.pm_lineEdit_enterWL1.setText(str(wl)))
        self.pm2.updateWavelength.connect(lambda wl: self.pm_lineEdit_enterWL2.setText(str(wl)))
        self.pm1.updatePower.connect(lambda pow: self.pm_label_power1.setText(f"Power PM1: {pow} W"))
        self.pm2.updatePower.connect(lambda pow: self.pm_label_power2.setText(f"Power PM2: {pow} W"))

        # Signal/Slot for the textbox updating:
        self.pm1.update_textBox.connect(self.update_status_text)
        self.pm2.update_textBox.connect(self.update_status_text)
        self.dfb.update_textBox.connect(self.update_status_text)
        self.lbo.update_textBox.connect(self.update_status_text)
        self.bbo.update_textBox.connect(self.update_status_text)
        self.ase.update_textBox.connect(self.update_status_text)
        self.update_textBox.connect(self.update_status_text)

        # Signal/Slot for the General tab:
        self.measurement_status.connect(lambda bool: self.disable_tab_widgets(
            "general_tab", bool, excluded_widget=self.general_button_stopMeasurement))

    def connect_dfb_buttons(self):
        """Connect the buttons/lineEdits/etc of the DFB tab to the methods that should be performed"""
        self.dfb_button_connectDfb.clicked.connect(
            lambda: self.dfb.connect_dfb(ip=str(self.dfb_lineEdit_ip.text())))
        self.dfb_button_readValues.clicked.connect(
            lambda: self.dfb_update_values(*self.dfb.read_actual_dfb_values()))
        self.dfb_spinBox_setTemp.valueChanged.connect(
            lambda: self.dfb.change_dfb_setTemp(self.dfb_spinBox_setTemp.value()))
        self.dfb_button_setScanValues.clicked.connect(
            lambda: self.dfb.change_wideScan_values(self.dfb_lineEdit_scanStartTemp.value(),
                                                    self.dfb_lineEdit_scanEndTemp.value(),
                                                    self.dfb_lineEdit_scanSpeed.value()))
        self.dfb_button_startScan.clicked.connect(
            lambda: self.dfb_wideScan_popup(*self.dfb.read_actual_dfb_values()[:2]))
        self.dfb_button_abortScan.clicked.connect(self.dfb.abort_wideScan)

        self.dfb_button_connectDfb.clicked.connect(
            lambda: self.disable_tab_widgets("DFB_tab",
                                             disable=not self.dfb._connect_button_is_checked,
                                             ignored_widgets=[self.dfb_button_connectDfb, self.dfb_lineEdit_ip,
                                                              self.dfb_button_abortScan, self.dfb_button_stop_wl_stabil]))
        self.dfb_button_start_wl_stabil.clicked.connect(
            lambda: setattr(self.dfb, "target_wavelength", self.dfb_lineEdit_wl_stabil.value()))
        self.dfb_button_start_wl_stabil.clicked.connect(
            lambda: self.dfb.start_wl_stabilisation(
                wlm=self.wlm, kp=self.dfb_lineEdit_kp.value(),
                ki=self.dfb_lineEdit_ki.value(), kd=self.dfb_lineEdit_kd.value()))
        self.dfb_button_stop_wl_stabil.clicked.connect(
            lambda: self.dfb.stop_wl_stabilisation())
        self.dfb_button_wl_step_forward.clicked.connect(
            lambda: self.dfb.change_target_wavelength(self.dfb_lineEdit_wl_step.value()))
        self.dfb_button_wl_step_back.clicked.connect(
            lambda: self.dfb.change_target_wavelength(-self.dfb_lineEdit_wl_step.value()))

    def connect_lbo_buttons(self):
        """Connect the buttons/lineEdits/etc of the LBO tab to the methods that should be performed"""
        self.lbo_comboBox_visa.addItems(self.rm.list_resources())
        self.lbo_button_refresh.clicked.connect(lambda: self.refresh_combobox(self.lbo_comboBox_visa))
        self.lbo_button_connectLBO.clicked.connect(
            lambda: self.lbo.connect_covesion(rm=self.rm, port=self.lbo_comboBox_visa.currentText()))
        self.lbo_button_connectLBO.clicked.connect(self.lbo_update_values)
        self.lbo_button_readValues.clicked.connect(self.lbo.read_values)
        self.lbo_button_readValues.clicked.connect(self.lbo_update_values)
        self.lbo_button_setTemp.clicked.connect(
            lambda: self.lbo.set_temperature(self.lbo_lineEdit_targetTemp.value(),
                                             self.lbo_lineEdit_rampSpeed.value()))
        self.lbo_button_autoScan_start.clicked.connect(
            lambda: self.lbo.start_autoscan(wlm=self.wlm,
                                            wl_to_T_slope=self.lbo_lineEdit_slope.value(),
                                            wl_to_T_offset=self.lbo_lineEdit_offset.value()))
        self.lbo_button_autoScan_stop.clicked.connect(self.lbo.stop_autoscan)

        self.lbo_button_connectLBO.clicked.connect(
            lambda: self.disable_tab_widgets("LBO_tab",
                                             disable=not self.lbo._connect_button_is_checked,
                                             ignored_widgets=[self.lbo_button_connectLBO, self.lbo_comboBox_visa,
                                                              self.lbo_button_refresh, self.lbo_button_autoScan_stop]))

    def connect_bbo_buttons(self):
        """Connect the buttons/lineEdits/etc of the BBO tab to the methods that should be performed"""
        self.bbo_button_connectPiezo.clicked.connect(self.bbo.connect_piezos)
        self.bbo_button_connectRP.clicked.connect(
            lambda: self.bbo.connect_red_pitaya(ip=str(self.bbo_lineEdit_ipRedPitaya.text())))
        self.bbo_button_connectPiezo.clicked.connect(
            lambda: self.disable_tab_widgets("BBO_tab",
                                             disable=not (self.bbo._connect_button_is_checked
                                                          and self.bbo._connect_rp_button_is_checked),
                                             ignored_widgets=[self.bbo_button_connectPiezo, self.bbo_button_connectRP,
                                                              self.bbo_lineEdit_ipRedPitaya, self.bbo_button_stopUvScan,
                                                              self.bbo_button_stopUvScan_double]))
        self.bbo_button_connectRP.clicked.connect(
            lambda: self.disable_tab_widgets("BBO_tab",
                                             disable=not (self.bbo._connect_button_is_checked
                                                          and self.bbo._connect_rp_button_is_checked),
                                             ignored_widgets=[self.bbo_button_connectPiezo, self.bbo_button_connectRP,
                                                              self.bbo_lineEdit_ipRedPitaya, self.bbo_button_stopUvScan,
                                                              self.bbo_button_stopUvScan_double,
                                                              self.bbo_button_stopDiodeVoltage]))
        self.bbo_button_generateSignal.clicked.connect(self.bbo.generate_signal)

        # Second/Back BBO:
        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.value()), False))
        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.move_by(int(self.bbo_lineEdit_relativeSteps.value()), False))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.value()), False))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.move_by(-int(self.bbo_lineEdit_relativeSteps.value()), False))

        # Single BBO setup:
        self.bbo_button_startUvScan.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity.value(),
                steps=self.bbo_lineEdit_steps.value(),
                wait=self.bbo_lineEdit_break.value(),
                double_bbo_setup=False))
        self.bbo_button_startUvScan.clicked.connect(lambda: self.bbo.start_autoscan(wlm=self.wlm))
        self.bbo_button_stopUvScan.clicked.connect(self.bbo.stop_autoscan)

        # First/Front BBO:
        self.bbo_button_forwards_front.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity_front.value()), True))
        self.bbo_button_forwards_front.clicked.connect(
            lambda: self.bbo.move_by(int(self.bbo_lineEdit_relativeSteps_front.value()), True))
        self.bbo_button_back_front.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity_front.value()), True))
        self.bbo_button_back_front.clicked.connect(
            lambda: self.bbo.move_by(-int(self.bbo_lineEdit_relativeSteps_front.value()), True))

        # Double BBO setup:
        self.bbo_button_startUvScan_double.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity_double.value(),
                steps=self.bbo_lineEdit_steps_double.value(),
                wait=self.bbo_lineEdit_break_double.value(),
                double_bbo_setup=True))
        self.bbo_button_startUvScan_double.clicked.connect(lambda: self.bbo.start_autoscan_double(wlm=self.wlm))
        self.bbo_button_stopUvScan_double.clicked.connect(self.bbo.stop_autoscan_double)

        # UV Measurement:
        self.bbo_button_startDiodeVoltage.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity.value(),
                steps=self.bbo_lineEdit_steps.value(),
                wait=self.bbo_lineEdit_break.value(),
                double_bbo_setup=False))
        self.bbo_button_startDiodeVoltage.clicked.connect(lambda: self.bbo.start_UV_measurement(wlm=self.wlm))
        self.bbo_button_stopDiodeVoltage.clicked.connect(self.bbo.stop_UV_measurement)

    def connect_ase_buttons(self):
        """Connect the buttons/lineEdits/etc of the ASE filter tab to the methods that should be performed"""
        self.ase_button_connectStage.clicked.connect(
            lambda: self.ase.connect_rotationstage(self.ase_lineEdit_stage.text()))
        self.ase_button_moveToStart.clicked.connect(lambda: self.ase.move_to_start(wlm=self.wlm))
        self.ase_button_autoScan_start.clicked.connect(lambda: self.ase.start_autoscan(wlm=self.wlm))
        self.ase_button_autoScan_stop.clicked.connect(self.ase.stop_autoscan)
        self.ase_button_home.clicked.connect(self.ase_homing_popup)
        self.ase_button_startAutoCal.clicked.connect(self.autocalibration_popup)
        self.ase_button_selectPath.clicked.connect(self.open_calparfile)

        self.ase_button_connectStage.clicked.connect(
            lambda: self.disable_tab_widgets("ASE_tab",
                                             disable=not self.ase._connect_button_is_checked,
                                             ignored_widgets=[self.ase_button_connectStage, self.ase_button_selectPath,
                                                              self.ase_lineEdit_stage, self.ase_button_autoScan_stop]))

    def connect_pm_buttons(self):
        """Connect the buttons/lineEdits/etc of the PM tab to the methods that should be performed"""
        self.pm_comboBox_visaResources1.addItems(self.rm.list_resources())
        self.pm_comboBox_visaResources2.addItems(self.rm.list_resources())
        self.pm_button_refresh.clicked.connect(lambda: self.refresh_combobox(self.pm_comboBox_visaResources1))
        self.pm_button_refresh.clicked.connect(lambda: self.refresh_combobox(self.pm_comboBox_visaResources2))
        self.pm_button_connectPM1.clicked.connect(
            lambda: self.pm1.connect_pm(visa=self.pm_comboBox_visaResources1.currentText()))
        self.pm_button_connectPM2.clicked.connect(
            lambda: self.pm2.connect_pm(visa=self.pm_comboBox_visaResources2.currentText()))
        self.pm_button_changeWL1.clicked.connect(lambda:
                                                 self.pm1.set_wavelength(self.pm_lineEdit_enterWL1.text()))
        self.pm_button_changeWL2.clicked.connect(lambda:
                                                 self.pm2.set_wavelength(self.pm_lineEdit_enterWL2.text()))

        self.pm_button_connectPM1.clicked.connect(
            lambda: self.disable_tab_widgets("PM_tab",
                                             disable=not self.pm1._connect_button_is_checked,
                                             ignored_widgets=[self.pm_button_connectPM1,
                                                              self.pm_comboBox_visaResources1,
                                                              self.pm_button_refresh,
                                                              self.pm_comboBox_visaResources2,
                                                              self.pm_button_connectPM2,
                                                              self.pm_lineEdit_enterWL2,
                                                              self.pm_button_changeWL2]))
        self.pm_button_connectPM2.clicked.connect(
            lambda: self.disable_tab_widgets("PM_tab",
                                             disable=not self.pm2._connect_button_is_checked,
                                             ignored_widgets=[self.pm_button_connectPM1,
                                                              self.pm_comboBox_visaResources1,
                                                              self.pm_button_refresh,
                                                              self.pm_comboBox_visaResources2,
                                                              self.pm_button_connectPM2,
                                                              self.pm_lineEdit_enterWL1,
                                                              self.pm_button_changeWL1]))

    def connect_general_buttons(self):
        """Connect the buttons/lineEdits/etc of the general tab to the methods that should be performed"""
        self.general_button_selectPath.clicked.connect(self.create_measurement_file)
        self.general_button_startMeasurement.clicked.connect(
            lambda: self.start_measurement(self.general_spinBox_samples.value()))
        self.general_button_stopMeasurement.clicked.connect(self.stop_measurement)

    def update_status_text(self, text):
        """This method displays a text in the textEdit field in the GUI

        Args:
            text (str): Text to be displayed
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.status_textEdit.insertPlainText(f"{timestamp} - {text}\n")

    def refresh_combobox(self, combobox):
        """Clears and re-adds items in a QComboBox.

        Args:
            combobox (QComboBox): ComboBox that should be refreshed
        """
        combobox.clear()
        combobox.addItems(self.rm.list_resources())

    # The next few methods are for the measurement process:
    def create_measurement_file(self):
        """This method lets you choose a file path for the file
        that the measurement data should be written to.
        """
        self.file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv)")
        self.general_label_chosenPath.setText(self.file_path)

    def start_measurement(self, samples):
        """Creates a QTimer that is connected to the measurement() method.
        This QTimer will trigger the measurement() method every (1000/samples) ms.
        This method collects the start time and writes the header line to the
        file in self.file_path. The QTimer then gets started.

        Args:
            samples (int): Number of samples per second
        """
        self.measurement_loop_timer = QtCore.QTimer()
        start_time = time.time()
        self.measurement_loop_timer.timeout.connect(lambda: self.measurement(start_time))
        try:
            with open(self.file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(["Time [s]", "Timestamp", "Wavelength [nm]", "Power PM1 [W]", "Power PM2 [W]",
                                 "Motor position Front BBO [steps]", "Motor position Back BBO [steps]", "UV photodiode voltage [V]", "LBO temperature (act) [°C]",
                                 "LBO temperature (set) [°C]"])
            self.measurement_loop_timer.start(int(1000 / samples))
            self.measurement_status.emit(True)
        except AttributeError:
            self.update_textBox.emit("Couldn't start measurement: No file path chosen")
        except FileNotFoundError:
            self.update_textBox.emit("Couldn't start measurement: No file path chosen")

    def stop_measurement(self):
        """Stops the QTimer that is running during the measurement process."""
        self.measurement_loop_timer.stop()
        self.measurement_status.emit(False)

    def measurement(self, start_time):
        """This method calculates the passed time since the given start_time.
        Depending on what boxes are checked in the GUI, this method will write
        the currently saved values in the instance attributes to the file.
        Then it will reset all values to zero. This is used as an indication on the
        next call of the method if there is a new value assigned to this instance
        attribute.

        Args:
            start_time (float): Should be the starting time of the measurement process in seconds since the Epoch.
        """
        timestamp = time.time()
        time_since_start = np.round(timestamp - start_time, 6)

        # Resets all variables so that Zero is written to file if there is no new measurement for an specific value:
        data_pm1 = 0.0
        data_pm2 = 0.0
        data_wl = 0.0
        data_steps_front = 0
        data_steps_back = 0
        data_uv = 0.0
        data_lbo_act = 0.0
        data_lbo_set = 0.0

        # Assigns the instance variables to the normal variables, depending on the status of the checkboxes in the GUI:
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
            data_steps_front = self.data_steps_front
            data_steps_back = self.data_steps_back
        if self.general_checkbox_saveUvPdVolt.isChecked():
            data_uv = self.data_uv
        if self.general_checkbox_saveLboTemp.isChecked():
            data_lbo_act = self.data_lbo_act
            data_lbo_set = self.data_lbo_set

        # Writes the values to the file in self.file_path:
        with open(self.file_path, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow([time_since_start, timestamp, data_wl, data_pm1,
                             data_pm2, data_steps_front, data_steps_back, data_uv, data_lbo_act, data_lbo_set])

        # Reset all instance variables for the next cycle:
        self.reset_data_storage()

    def reset_data_storage(self):
        """Sets all instance variables for the measurement back to Zero."""
        self.data_uv = 0.0
        self.data_steps_front = 0
        self.data_steps_back = 0
        self.data_wl = 0.0
        self.data_lbo_act = 0.0
        self.data_lbo_set = 0.0

    def lbo_update_values(self):
        """Updates the GUI with the latest values for the
        ramp rate and the set temperature.
        """
        try:
            self.lbo_lineEdit_rampSpeed.setValue(self.lbo.rate)
            self.lbo_lineEdit_targetTemp.setValue(self.lbo.set_temp)
        except AttributeError as e:
            self.update_textBox(f"Covesion oven is not connected: {e}")

    def disable_tab_widgets(self, tab_name, disable, excluded_widget=None, ignored_widgets=[]):
        """This method goes through every QWidget in a specified QTabWidget
        and disables (disable=True) or enables (disable=False) every QWidget,
        except for the excluded widget and the ignored widgets. The excluded widget will get the
        reversed treatment: It will be enabled if disable=True and vice versa. The ignored widgets
        will not change their state at all

        This method will be used for example when an autoscan gets started,
        so that the only clickable QWidget is the Stop-Button of the autoscan.

        Args:
            tab_name (str): Name of the QTabWidget where the QWidgets should be dis-/enabled.
            excluded_widget (QWidget): QWidget that will not be disabled, but rather enabled
            ignored_widget (list of QWidgets): List of widgets that should be ignored
            disable (bool): Boolean that decides wether all QWidgets should be disabled or enabled
        """
        tab = self.findChild(QtWidgets.QWidget, tab_name)
        for widget in tab.findChildren(QtWidgets.QWidget):
            if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QPushButton,
                                   QtWidgets.QComboBox, QtWidgets.QDoubleSpinBox,
                                   QtWidgets.QCheckBox, QtWidgets.QSpinBox)):
                if widget == excluded_widget:
                    widget.setEnabled(disable)
                elif widget not in ignored_widgets:
                    widget.setDisabled(disable)
                else:
                    pass

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
            self.dfb_lineEdit_scanStartTemp.setValue(start_temp)
            self.dfb_lineEdit_scanEndTemp.setValue(end_temp)
            self.dfb_lineEdit_scanSpeed.setValue(scan_speed)
        except AttributeError as e:
            self.update_textBox(f"DFB is not connected: {e}")
        except TypeError as e:
            self.update_textBox(f"Error: {e}")

    def update_widescan_progressbar(self, progress, time):
        """Updates the progress bar and remaining time label during a wide scan.

        Args:
            progress (int): The current progress value to set on the progress bar
            time (float): The remaining time in seconds to display
        """
        self.dfb_progressBar_scan.setValue(progress)
        self.dfb_label_remainingTime.setText(f"Remaining time: {time} s")

    def reset_wideScan_progressBar(self):
        """Resets the wide scan progress bar and related labels"""
        self.dfb_label_actTemp.setText("Actual temperature: ")
        self.dfb_progressBar_scan.reset()
        self.dfb_label_remainingTime.setText("Remaining time: ")

    def dfb_wideScan_popup(self, set_temp, start_temp):
        if abs(set_temp - start_temp) > 0.1 or not self.status_checkBox_ase.isChecked():
            message = ""
            if abs(set_temp - start_temp) > 0.1:
                message += (f"The current DFB temperature {set_temp} °C doesn't match the "
                            f"WideScan start temperature {start_temp} °C.\n")
            if not self.status_checkBox_ase.isChecked():
                message += "The autoscan of the ASE filters is currently disabled.\n"
            message += "Are you sure to start the WideScan?"

            popup = QtWidgets.QMessageBox.question(
                self, 'WideScan', message,
                buttons=QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)

            if popup == QtWidgets.QMessageBox.StandardButton.Yes:
                self.dfb.start_wideScan()
        else:
            self.dfb.start_wideScan()

    def ase_homing_popup(self):
        """Creates a pop-up if the ASE filter rotation stage should be homed.
        If the answer is 'Yes', the stage will get homed.
        """
        popup = QtWidgets.QMessageBox.question(
            self, 'Motor Homing',
            "Home the ASE filter rotation stage? Only press 'Yes' if all fiber amplifiers are turned off!",
            buttons=QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if popup == QtWidgets.QMessageBox.StandardButton.Yes:
            self.ase.homing_motor()

    def autocalibration_popup(self):
        """Displays a popup to initiate the auto-calibration process.

        This method reads the calibration log to display the previous calibration date and time,
        and prompts the user to start the auto-calibration of the rotation stage. If the user
        confirms, the auto-calibration process is initiated.
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
                               "the desired powermeter directly after the first fibre amplifier and the roataion stage with the ASE filters. "
                               "Ensure that the WLM and rotation stage are connected beforehand als well as the DFB laser. "
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
        """Opens a file dialog to select a calibration parameter file.

        This method allows the user to select a CSV file containing calibration parameters.
        It reads the selected file, validates its contents, and updates the calibration parameters.
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
