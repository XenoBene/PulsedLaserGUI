from PyQt6 import QtWidgets
import sys
import pyvisa
import GUI
import DFB_functions
import WLM_functions
import LBO_functions
import BBO_functions
import ASE_functions
import Powermeter_functions
# from pylablib.devices import HighFinesse


app = QtWidgets.QApplication(sys.argv)
# wlm = HighFinesse.WLM(dll_path="C:\Windows\System32\wlmData.dll", autostart=False)
wlm = WLM_functions.WavelengthMeter(debug=True)
# TODO: Was soll passieren wenn gar kein WLM angeschlossen ist?
# TODO: pylablib für WLM benutzen
window = GUI.MainWindow(
    rm=pyvisa.ResourceManager(),
    # TODO: Hier wlm=Blabla hin, dann kann das von der Gui über Funktionen verteilt werden
    dfb=DFB_functions.DFB(),
    lbo=LBO_functions.LBO(wlm=wlm),
    bbo=BBO_functions.BBO(wlm=wlm, axis=1, addr=1),
    ase=ASE_functions.ASE(wlm=wlm),
    pm1=Powermeter_functions.PM(),
    pm2=Powermeter_functions.PM()
    )
window.connect_buttons()
window.show()
app.exec()
