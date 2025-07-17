import sys
import redpitaya_scpi as scpi

IP = '169.254.204.79'
rp = scpi.scpi(IP)

wave_form = 'pwm'
freq = 1
ampl = 0.5
offset = 0.5
duty = 0.05

rp.tx_txt('ACQ:RST')
#rp.tx_txt('GEN:RST')

rp.tx_txt('SOUR1:FUNC ' + str(wave_form).upper())
rp.tx_txt('SOUR1:FREQ:FIX ' + str(freq))
rp.tx_txt('SOUR1:VOLT ' + str(ampl))
rp.tx_txt('SOUR1:VOLT:OFFS ' + str(offset))
rp.tx_txt('SOUR1:DCYC ' + str(duty))
rp.tx_txt('SOUR1:BURS:STAT BURST')                # activate Burst mode
rp.tx_txt('SOUR1:BURS:NCYC 1')                    # Signal periods in a Burst pulse
rp.tx_txt('SOUR1:BURS:NOR 1');                # Total number of bursts (set to 65536 for INF pulses)
# rp.tx_txt('SOUR1:BURS:INT:PER 5000');             # Burst period (time between two bursts (signal + delay in microseconds))

rp.tx_txt('OUTPUT1:STATE ON')
rp.tx_txt('SOUR1:TRig:INT')

rp.close()