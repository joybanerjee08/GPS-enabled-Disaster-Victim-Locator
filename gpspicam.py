import base64
import zmq
from threading import Condition
import threading
import time
import io
import picamera
from gps3 import gps3
import os

os.system('sudo systemctl restart gpsd')

def send_array_and_str(socket, img, string, flags=0):
    socket.send_string(string, flags | zmq.SNDMORE)

    return socket.send(img, flags)

context = zmq.Context()
footage_socket = context.socket(zmq.PUB)
footage_socket.setsockopt(zmq.LINGER, 0)
footage_socket.connect('tcp://192.168.1.4:5555')

gps_socket = gps3.GPSDSocket()
data_stream = gps3.DataStream()
gps_socket.connect()
gps_socket.watch()

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


def sendimg():
    start_CLK = time.time() 
    i = 0
    with picamera.PiCamera(resolution='640x480', framerate=100) as camera:
        output = StreamingOutput()
        #Uncomment the next line to change your Pi's Camera rotation (in degrees)
        camera.rotation = 180
        camera.exif_tags['EXIF.UserComment'] = b'Something containing\x00NULL characters'
        camera.start_recording(output, format='mjpeg')
        while True:
            try:
                global exitnow
                global lat
                global lon
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                    altitude = "0.00"
                    mag = "0.00"
                    outstr = str(lat)+","+str(lon)+","+mag+","+altitude
                    #print(outstr)
                    send_array_and_str(footage_socket, frame, outstr)
                    print (i / ( time.time() - start_CLK ) )
                    i += 1
                    #time.sleep(0.1)
                    if exitnow:
                        raise KeyboardInterrupt
                    #jpg_as_text = base64.b64encode(buffer)
                    #footage_socket.send(jpg_as_text)
            except Exception as e:
                print(e)
                print('releasing')
                camera.stop_recording()
                camera.close()
                footage_socket.close()
                #cv2.destroyAllWindows()
                break

def getgps():    
    for new_data in gps_socket:
        if new_data:
            global exitnow
            global lat
            global lon
            data_stream.unpack(new_data)
            #print('Altitude = ', data_stream.TPV['alt'])
            print('Latitude = ', data_stream.TPV['lat'])
            print('Longitude = ', data_stream.TPV['lon'])
            if data_stream.TPV['lat']!="n/a" and data_stream.TPV['lon']!="n/a":
                lat = data_stream.TPV['lat']
                lon = data_stream.TPV['lon']
            time.sleep(0.5)
            if exitnow:
                break


if __name__ == "__main__": 
    try:
        exitnow = False
        lat = "22.483425"
        lon = "88.455463"
        # creating thread 
        t1 = threading.Thread(target=sendimg) 
        t2 = threading.Thread(target=getgps)  

        # starting thread 1 
        t1.start() 
        # starting thread 2 
        t2.start() 

        # wait until thread 1 is completely executed 
        t1.join() 
        # wait until thread 2 is completely executed 
        t2.join()
    except:
        exitnow = True
