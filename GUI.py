from PyQt6 import QtWidgets, QtCore, uic


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, rm, dfb, lbo, bbo):
        super().__init__()

        # Load the ui
        self.ui = uic.loadUi("pulsed_laser_interface.ui", self)

        self.rm = rm
        self.dfb = dfb
        self.lbo = lbo
        self.bbo = bbo

    def connect_buttons(self):
        """
        Connect the buttons from the UI with the methods.
        The names of the buttons have to be looked up in the .ui file
        with QT Designer.
        """
        """DFB Tab buttons:"""
        self.dfb_button_connectDfb.clicked.connect(self.dfb.connect_dfb)
        self.dfb_button_connectDfb.clicked.connect(self.dfb_update_values)
        self.dfb_button_readValues.clicked.connect(self.dfb.read_actual_dfb_values)
        self.dfb_button_readValues.clicked.connect(self.dfb_update_values)
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
        self.dfb_button_startScan.clicked.connect(self.start_wideScan_loop)
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
        self.lbo_button_autoScan.clicked.connect(self.lbo_start_autoscan_loop)

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

        self.bbo_button_startUvScan.connect(
            lambda: self.bbo.change_autoscan_parameters(
                velocity=self.bbo_lineEdit_scanVelocity.text(),
                steps=self.bbo_lineEdit_steps.text(),
                wait=self.bbo_lineEdit_break.text()))
        self.bbo_button_startUvScan.connect(self.bbo.start_autoscan)
        self.bbo_button_startUvScan.connect(self.bbo_start_autoscan_loop)
        self.bbo_button_stopUvScan.connect(self.bbo.stop_autoscan)
        self.bbo_button_stopUvScan.connect(self.bbo_stop_autoscan_loop)

    def bbo_update_voltage(self):
        try:
            self.bbo_label_diodeVoltage.setText(f"UV Diode Voltage [V]: {self.bbo.diode_voltage}")
        except AttributeError as e:
            print(e)

    def bbo_start_autoscan_loop(self):
        self.bbo_loopTimer_autoscan = QtCore.QTimer()
        self.bbo_loopTimer_autoscan.timeout.connect(self.bbo_update_voltage)
        self.bbo_loopTimer_autoscan.start.connect()
        self.status_checkBox_bbo.setChecked(True)
        self.bbo_loopTimer_autoscan.start(100)
        print("Looptimer started")

    def bbo_stop_autoscan_loop(self):
        self.bbo_loopTimer_autoscan.stop()
        self.status_checkBox_bbo.setChecked(False)
        self.bbo_label_diodeVoltage.setText("UV Diode Voltage [V]:")

    def lbo_update_values(self):
        """Updates the GUI with the latest values for the
        ramp rate and the set temperature.
        """
        try:
            self.lbo_lineEdit_rampSpeed.setText(str(self.lbo.rate))
            self.lbo_lineEdit_targetTemp.setText(str(self.lbo.set_temp))
        except AttributeError as e:
            print(f"Covesion oven is not connected: {e}")

    def lbo_start_autoscan_loop(self):
        """Start a QTimer event so that every second the function "lbo_update_actTemp"
        gets called to visually update the GUI with the LBO oven temperatures.
        """
        if not self.lbo._autoscan_button_is_checked:
            self.lbo_loopTimer_autoscan = QtCore.QTimer()
            self.lbo_loopTimer_autoscan.timeout.connect(self.lbo_update_actTemp)
            self.lbo_loopTimer_autoscan.start.connect()
            self.status_checkBox_lbo.setChecked(True)
            self.lbo_loopTimer_autoscan.start(1000)
            print("Looptimer started")
            self.lbo._autoscan_button_is_checked = True
        else:
            self.lbo_loopTimer_autoscan.stop()
            self.status_checkBox_lbo.setChecked(False)
            self.lbo_label_setTemp.setText("Set temperature [°C]: ")
            self.lbo_label_actTemp.setText("Actual temperature [°C]: ")
            self.lbo._autoscan_button_is_checked = False

    def lbo_update_actTemp(self):
        """Updates the GUI with the latest values for the actual and the set temperature
        during a LBO automatic temperature scan.
        """
        try:
            self.lbo_label_setTemp.setText(f"Set temperature [°C]: {self.lbo.needed_temperature}")
            self.lbo_label_actTemp.setText(f"Actual temperature [°C]: {self.lbo.act_temp}")
        except AttributeError as e:
            print(e)

    def dfb_update_values(self):
        """Updates the GUI with the last known attributes of the set temperature,
        start & end temperature of the WideScan and the scan speed.
        """
        try:
            self.dfb_spinBox_setTemp.setValue(self.dfb.set_temp)
            self.dfb_lineEdit_scanStartTemp.setText(str(self.dfb.start_temp))
            self.dfb_lineEdit_scanEndTemp.setText(str(self.dfb.end_temp))
            self.dfb_lineEdit_scanSpeed.setText(str(self.dfb.scan_speed))
        except AttributeError as e:
            print(f"DFB is not connected: {e}")

    def start_wideScan_loop(self):
        """Creates and starts a QTimer that starts the WideScan.
        After every loop of the QTimer, the progressbar and remeaining time
        gets updated in the GUI.
        """
        self.dfb_loopTimer_wideScan = QtCore.QTimer()
        self.dfb_loopTimer_wideScan.timeout.connect(self.update_wideScan_progressBar)
        self.dfb.start_wideScan()
        self.status_checkBox_wideScan.setChecked(True)  # Visual check to confirm if WideScan is currently enabled.
        self.dfb_loopTimer_wideScan.start()

    def update_wideScan_progressBar(self):
        """Updates the GUI with the progress & remaining time of the WideScan
        and the current temperature of the DFB diode.
        When the WideScan reaches its end, the progressbar is resetted and the QTimer loop
        is stopped.
        """
        try:
            progress, remaining_time = self.dfb.get_wideScan_progress()
            self.dfb_progressBar_scan.setValue(progress)
            self.dfb_label_remainingTime.setText(
                f"Remaining time: {remaining_time} s")
            self.dfb_label_actTemp.setText(
                f"Actual temperature: {self.dfb.get_actual_temperature()} °C")
            if self.dfb.get_wideScan_state() == 0:
                self.dfb_progressBar_scan.reset()
                self.dfb_label_remainingTime.setText("Remaining time: ")
                self.dfb_loopTimer_wideScan.stop()
                self.status_checkBox_wideScan.setChecked(False)  # Visual check to confirm that WideScan has finished.
            elif False:
                # TODO: Hier muss Überprüfung hin, ob die ASE-Filter nicht einen Error
                # geworfen haben.
                self.status_checkBox_wideScan.setChecked(False)
                pass
        except TypeError as e:
            self.dfb_loopTimer_wideScan.stop()
            print(f"No DFB connected: {e}")
