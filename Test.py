from pyrpl import Pyrpl
import numpy as np

p = Pyrpl("169.254.204.79")
scope = p.rp.scope  # Nutzt den schnellen FPGA-Puffer

scope.decimation = 1  # Volle Geschwindigkeit (125 MSa/s)
scope.trigger_source = "immediately"
scope.setup()
scope.start()  # Starte die Erfassung

while True:
    if scope.finished():
        data = scope.curve(ch=1)  # Schneller Zugriff auf Messdaten
        max_voltage = np.max(data)
        print(f"Maximale Spannung: {max_voltage:.2f} V")

        if max_voltage > 0:
            print("✅ Puls erkannt!")
            break