import py_qmc5883l
import time
sensor = py_qmc5883l.QMC5883L()

while True:
	mag = '{:05.3f}'.format(sensor.get_bearing())
	print(mag)
	time.sleep(1)
