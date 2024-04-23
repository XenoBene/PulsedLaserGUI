from PyQt6 import QtWidgets
import sys
import pyvisa
import GUI
import DFB_functions
import WLM_functions
import LBO_functions
from pylablib.devices import HighFinesse

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # wlm = HighFinesse.WLM(dll_path="C:\Windows\System32\wlmData.dll", autostart=False)
    wlm = WLM_functions.WavelengthMeter(debug=True)
    # TODO: Was soll passieren wenn gar kein WLM angeschlossen ist?
    # TODO: pylablib für WLM benutzen
    window = GUI.MainWindow(
        rm=pyvisa.ResourceManager(),
        # TODO: Hier wlm=Blabla hin, dann kann das von der Gui über Funktionen verteilt werden
        dfb=DFB_functions.DFB(ip="192.168.12.38"),  # TODO: IP nicht hardcoden!
        lbo=LBO_functions.LBO(wlm=wlm)
        )
    window.connect_buttons()
    window.show()
    app.exec()
