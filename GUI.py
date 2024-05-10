from PyQt6 import QtWidgets, QtCore, uic


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, rm, dfb, lbo, bbo, ase):
        super().__init__()

        # Load the ui
        self.ui = uic.loadUi("pulsed_laser_interface.ui", self)

        self.rm = rm
        self.dfb = dfb
        self.lbo = lbo
        self.bbo = bbo
        self.ase = ase

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
