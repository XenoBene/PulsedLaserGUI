from PyQt6 import QtWidgets
import sys
import GUI
import DFB_functions

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = GUI.MainWindow(dfb=DFB_functions.DFB(ip="192.168.12.38"))
    window.connect_buttons()
    window.show()
    app.exec()
