import time
import numpy as np
import redpitaya_scpi as scpi

rp = scpi.scpi("169.254.204.79")  # Ersetze mit der IP deines Red Pitaya

# Setze den ADC auf kontinuierliche Messung
rp.tx_txt("ACQ:DEC 1")  # Maximale Abtastrate (125 MSa/s)
rp.tx_txt("ACQ:START")  # Starte kontinuierliche Messung

print("Warte auf Signal...")

while True:
    # Hole eine große Anzahl an Samples aus dem Puffer (~10 ms Daten)
    rp.tx_txt("ACQ:SOUR1:DATA?")
    response = rp.rx_txt()

    # Umwandeln in ein numpy-Array mit Spannungswerten
    try:
        voltages = np.array([float(v) for v in response.strip().split(',')])
    except ValueError:
        continue

    # Berechne den Maximalwert im Puffer
    max_voltage = np.max(voltages)

    # Drucke den Maximalwert aus
    print(f"Maximale Spannung im Buffer: {max_voltage:.2f} V")

    # Falls der Maximalwert über 2.5V liegt → Signal erkannt
    """if max_voltage > 2.5:
        print("TTL-Puls erkannt!")
        break  # Oder hier eine gewünschte Aktion ausführen"""

    time.sleep(0.01)  # Warte 10 ms bis zur nächsten Abfrage
