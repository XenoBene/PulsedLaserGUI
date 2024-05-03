from PyQt6 import QtWidgets
import sys
import pyvisa
import GUI
import DFB_functions
import WLM_functions
import LBO_functions
import BBO_functions
# from pylablib.devices import HighFinesse

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # wlm = HighFinesse.WLM(dll_path="C:\Windows\System32\wlmData.dll", autostart=False)
    wlm = WLM_functions.WavelengthMeter(debug=False)
    # TODO: Was soll passieren wenn gar kein WLM angeschlossen ist?
    # TODO: pylablib für WLM benutzen
    window = GUI.MainWindow(
        rm=pyvisa.ResourceManager(),
        # TODO: Hier wlm=Blabla hin, dann kann das von der Gui über Funktionen verteilt werden
        dfb=DFB_functions.DFB(),
        lbo=LBO_functions.LBO(wlm=wlm),
        bbo=BBO_functions.BBO(wlm=wlm, axis=1, addr=1)
        )
    window.connect_buttons()
    window.show()
    app.exec()
