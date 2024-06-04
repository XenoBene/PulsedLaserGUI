from PyQt6 import QtWidgets, uic
import ASE_functions
import DFB_functions
import LBO_functions
import BBO_functions
import Powermeter_functions
import pyvisa
import pandas as pd
import csv


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self,
                 rm: pyvisa.ResourceManager,
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
        self.dfb = dfb
        self.lbo = lbo
        self.bbo = bbo
        self.ase = ase
        self.pm1 = pm1
        self.pm2 = pm2

        # Signal/Slots:
        self.dfb.widescan_status.connect(self.status_checkBox_wideScan.setChecked)
        self.dfb.update_values.connect(lambda values: self.dfb_update_values(*values))
        self.dfb.widescan_finished.connect(self.reset_wideScan_progressBar)
        self.dfb.update_progressbar.connect(lambda values: self.update_widescan_progressbar(*values))
        self.dfb.update_actTemp.connect(lambda value: self.dfb_label_actTemp.setText(f"Actual temperature: {value} °C"))

        self.bbo.voltageUpdated.connect(self.bbo_update_voltage)
        self.bbo.autoscan_status.connect(self.bbo_status_checkbox)

        self.lbo.autoscan_status.connect(self.lbo_status_checkbox)
        self.lbo.update_temperature.connect(lambda temp: self.lbo_update_temperatures(*temp))

        self.ase.autoscan_status.connect(self.status_checkBox_ase.setChecked)
        self.ase.autoscan_status.connect(self.ase_button_connectStage.setDisabled)
        self.ase.update_wl_pos.connect(lambda values: self.ase_update_values(*values))
        self.ase.autoscan_failsafe.connect(self.dfb.abort_wideScan)
        self.ase.autocalibration_progress.connect(lambda progress: self.ase_progressBar_autocal.setValue(progress))

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
        # TODO: Bei manueller Eingabe soll mit Enter bestätigt werden bevor sich die Temperatur ändert!
        # vllt mit self.dfb_spinBox_setTemp.editingFinished.connect() ?
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
        self.lbo_button_connectLBO.clicked.connect(
            lambda: self.lbo.connect_covesion(rm=self.rm, port=self.lbo_comboBox_visa.currentText())
        )
        self.lbo_button_connectLBO.clicked.connect(self.lbo_update_values)
        self.lbo_button_readValues.clicked.connect(self.lbo.read_values)
        self.lbo_button_readValues.clicked.connect(self.lbo_update_values)
        self.lbo_button_setTemp.clicked.connect(
            lambda: self.lbo.set_temperature(float(self.lbo_lineEdit_targetTemp.text()),
                                             float(self.lbo_lineEdit_rampSpeed.text()))
        )
        self.lbo_button_autoScan.clicked.connect(self.lbo.toggle_autoscan)

        """BBO Tab buttons:"""
        self.bbo_button_connectPiezo.clicked.connect(self.bbo.connect_piezos)
        self.bbo_button_connectRP.clicked.connect(
            lambda: self.bbo.connect_red_pitaya(ip=str(self.bbo_lineEdit_ipRedPitaya.text())))

        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.text())))
        self.bbo_button_forwards.clicked.connect(
            lambda: self.bbo.move_by(int(self.bbo_lineEdit_relativeSteps.text())))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.change_velocity(int(self.bbo_lineEdit_velocity.text())))
        self.bbo_button_back.clicked.connect(
            lambda: self.bbo.move_by(-int(self.bbo_lineEdit_relativeSteps.text())))

        self.bbo_button_startUvScan.clicked.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity.text(),
                steps=self.bbo_lineEdit_steps.text(),
                wait=self.bbo_lineEdit_break.text()))
        self.bbo_button_startUvScan.clicked.connect(self.bbo.start_autoscan)
        self.bbo_button_stopUvScan.clicked.connect(self.bbo.stop_autoscan)

        """ASE Tab buttons:"""
        self.ase_button_connectStage.clicked.connect(
            lambda: self.ase.connect_rotationstage(self.ase_lineEdit_stage.text()))
        self.ase_button_moveToStart.clicked.connect(self.ase.move_to_start)
        self.ase_button_startAutoScan.clicked.connect(self.ase.autoscan)
        self.ase_button_home.clicked.connect(self.ase.homing_motor)
        self.ase_button_startAutoCal.clicked.connect(self.autocalibration_popup)
        self.ase_button_selectPath.clicked.connect(self.open_calparfile)

        """PM Tab buttons:"""
        self.pm_comboBox_visaResources1.addItems(self.rm.list_resources())
        self.pm_comboBox_visaResources2.addItems(self.rm.list_resources())
        self.pm_button_connectPM1.clicked.connect(
            lambda: self.pm1.connect_pm(visa=self.pm_comboBox_visaResources1.currentText()))
        self.pm_button_connectPM2.clicked.connect(
            lambda: self.pm2.connect_pm(visa=self.pm_comboBox_visaResources2.currentText()))
        # TODO: Implement Adjust Zero button
        # TODO: Implement wavelength change

    def bbo_update_voltage(self, value):
        """Changes the label in the GUI. This is the slot method for the signal
        that is received from the uv autoscan class.

        Args:
            value (float): UV diode voltage [V]
        """
        try:
            print("Voltage updated")
            self.bbo_label_diodeVoltage.setText(f"UV Diode Voltage [V]: {value}")
        except AttributeError as e:
            print(e)

    def bbo_status_checkbox(self, boolean):
        """Sets the status checkbox for the UV scan to the value
        of the boolean

        Args:
            boolean (bool): True or False, depending if the uv scan is running or not
        """
        self.status_checkBox_bbo.setChecked(boolean)

    def ase_update_values(self, wavelength, position):
        try:
            self.ase_label_currentWL.setText(f"Current Wavelength: {wavelength}")
            self.ase_label_currentAngle.setText(f"Current Angle: {position}")
        except AttributeError as e:
            print(e)

    def lbo_status_checkbox(self, boolean):
        """Sets the status checkbox for the LBO scan to the value
        of the boolean

        Args:
            boolean (bool): True or False, depending if the LBO scan is running or not
        """
        self.status_checkBox_lbo.setChecked(boolean)

    def lbo_update_values(self):
        """Updates the GUI with the latest values for the
        ramp rate and the set temperature.
        """
        try:
            self.lbo_lineEdit_rampSpeed.setText(str(self.lbo.rate))
            self.lbo_lineEdit_targetTemp.setText(str(self.lbo.set_temp))
        except AttributeError as e:
            print(f"Covesion oven is not connected: {e}")

    def lbo_update_temperatures(self, set_temp, act_temp):
        """Updates the GUI with the latest values for the set and act temperature
        during a LBO automatic temperature scan.

        Args:
            set_temp (float): The set temperature of the LBO oven [°C]
            act_temp (float): The current temperature of the LBO oven [°C]
        """
        try:
            self.lbo_label_setTemp.setText(f"Set temperature [°C]: {set_temp}")
            self.lbo_label_actTemp.setText(f"Actual temperature [°C]: {act_temp}")
        except AttributeError as e:
            print(e)

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
            print(f"DFB is not connected: {e}")

    def update_widescan_progressbar(self, progress, time):
        self.dfb_progressBar_scan.setValue(progress)
        self.dfb_label_remainingTime.setText(f"Remaining time: {time} s")

    def reset_wideScan_progressBar(self):
        self.dfb_label_actTemp.setText("Actual temperature: ")
        self.dfb_progressBar_scan.reset()
        self.dfb_label_remainingTime.setText("Remaining time: ")

    def autocalibration_popup(self):
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
            self.ase.start_autocalibration(dfb=self.dfb, powermeter=self.pm1,
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
        try:
            calparfilename, _ = QtWidgets.QFileDialog.getOpenFileName(
                parent=self, caption="Select path", directory="", filter="All Files (*);;(*.csv)")
            if calparfilename != "":
                self.ase.cal_par = pd.read_csv(calparfilename, delimiter=';')
                try:
                    # call self.cal_par: if rubbish file is loaded, then there will be no key
                    # the corresponding names below. code then throws an error
                    self.ase.cal_par["m"]
                    self.ase.cal_par["b"]
                    with open(r"lastused_calpar.csv", 'w', encoding='UTF8', newline='') as f:
                        writer = csv.writer(f, delimiter=';')
                        header = ['Kalibrierung', 'm', 'b']
                        writer.writerow(header)
                        writer.writerow(['lo->hi (Kal 1)', self.ase.cal_par["m"][0], self.ase.cal_par["b"][0]])
                        writer.writerow(['hi->lo (Kal 2)', self.ase.cal_par["m"][1], self.ase.cal_par["b"][1]])
                except KeyError:
                    print("Please select a valid file with the motor calibration parameters!")
        except FileNotFoundError:
            print("File not found!")
