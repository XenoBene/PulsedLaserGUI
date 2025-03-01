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
# wlm = WLM_functions.WavelengthMeter(debug=False)
# TODO: Was soll passieren wenn gar kein WLM angeschlossen ist?
# TODO: pylablib für WLM benutzen
window = GUI.MainWindow(
    rm=pyvisa.ResourceManager(),
    wlm=WLM_functions.WavelengthMeter(debug=False),
    dfb=DFB_functions.DFB(),
    lbo=LBO_functions.LBO(),
    bbo=BBO_functions.BBO(axis=1, addrFront=2, addrBack=1),
    ase=ASE_functions.ASE(),
    pm1=Powermeter_functions.PM(),
    pm2=Powermeter_functions.PM()
    )

window.connect_dfb_buttons()
window.connect_ase_buttons()
window.connect_lbo_buttons()
window.connect_bbo_buttons()
window.connect_pm_buttons()
window.connect_general_buttons()
window.show()
app.exec()