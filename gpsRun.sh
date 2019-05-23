sudo gpsd /dev/ttyS0 -F /var/run/gpsd.sock
stty -F /dev/ttyS0 -echo
sudo systemctl stop gpsd.socket
sudo systemctl disable gpsd.socket
sudo killall gpsd
sudo systemctl stop gpsd.socket
sudo systemctl disable gpsd.socket
sudo gpsd /dev/ttyS0 -F /var/run/gpsd.sock
