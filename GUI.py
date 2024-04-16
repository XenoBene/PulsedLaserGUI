from PyQt6 import QtWidgets, QtCore, uic


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dfb, lbo):
        """_summary_

        Args:
            dfb (_type_): _description_
        """
        super().__init__()

        # Load the ui
        self.ui = uic.loadUi("pulsed_laser_interface.ui", self)

        self.dfb = dfb
        self.lbo = lbo

    def connect_buttons(self):
        """
        Connect the buttons from the UI with the methods.
        The names of the buttons have to be looked up in the .ui file
        with QT Designer.
        """
        # DFB Tab buttons:
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
        self.dfb_button_startScan.clicked.connect(self.start_wideScan_loop)
        self.dfb_button_abortScan.clicked.connect(self.dfb.abort_wideScan)

        # LBO Tab buttons:
        self.lbo_button_connectLBO.clicked.connect(self.lbo.get_wavelength)

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
                self.status_checkBox_wideScan.setChecked(True)
                pass
        except TypeError as e:
            self.dfb_loopTimer_wideScan.stop()
            print(f"No DFB connected: {e}")
