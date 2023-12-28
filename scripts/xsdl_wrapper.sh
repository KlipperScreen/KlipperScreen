# A wrapper for the popular script for KlipperScreen on Android over adb over USB.
# https://klipper.discourse.group/t/how-to-klipperscreen-on-android-smart-phones/1196
#
# Keeps the process alive while the server is active
# to mimic default X's behaviour and keep the service happy

if  [ -f $PWD/launch_klipperscreen.sh ]; then
	exec $PWD/launch_klipperscreen.sh
elif [ ! -f $PWD/launch_klipperscreen.sh ]; then
	echo "launch_klipperscreen.sh does not exist"
	exit
fi

ret=1
timeout=0
echo -n "Waiting for X-server to be ready "
while [ $ret -gt 0 ] && [ $timeout -lt 60 ]
do
    xset -display :100 -q > /dev/null 2>&1
    ret=$?
    timeout=$( expr $timeout + 1 )
    echo -n "."
    sleep 1
done
echo ""
if [ $timeout -lt 60 ]
then
echo -n "X server found. Monitoring connection"
ret=0
while [ $ret -eq 0 ]
do
    xset -display :100 -q > /dev/null 2>&1
    ret=$?
    sleep 60
done
echo -n "X Server connection lost"
    exit 0

else
echo -n "X server not found"
    exit 1
fi
