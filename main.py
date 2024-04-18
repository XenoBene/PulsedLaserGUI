from PyQt6 import QtWidgets
import sys
import GUI
import DFB_functions
import WLM_functions
import LBO_functions
# from pylablib.devices import HighFinesse

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    wlm = WLM_functions.WavelengthMeter(debug=True)
    # TODO: Was soll passieren wenn gar kein WLM angeschlossen ist?
    window = GUI.MainWindow(
        dfb=DFB_functions.DFB(ip="192.168.12.38"),
        lbo=LBO_functions.LBO(wlm=wlm))
    window.connect_buttons()
    window.show()
    app.exec()
