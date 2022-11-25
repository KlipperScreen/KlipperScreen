#!/bin/bash
# Change XCLIENT and/or display to your destination xserver (XSDL platform). 
# Example: export DISPLAY=192.168.1.101:0

# Note: You will likely want to reserve a DHCP address or set a static IP of the 
# Xserver clientso that your IP does not change and require reconfiguration. 

export XCLIENT=change_me
export DISPLAY=change_me

if [ $XCLIENT == "change_me" ]; then
	echo "launch_klipperscreen.sh for XSDL/XServer Clients has not been cofigured properly. Please edit this file to point to your XServer Client"
	exit 
fi


# Send script to daemon process so that it does not fail when tty closes.
#    

export PYKLIPPERSCREEN=~/.KlipperScreen-env/bin/python
export PYKLIPPERSCREENPARAM=~/KlipperScreen/screen.py


if [ -f $PYKLIPPERSCREEN ]; then
	echo "Testing $PYKLIPPERSCREEN"
	test -x $PYKLIPPERSCREEN || echo "$PYKLIPPERSCREEN is Not Executable"  
fi

if [ -f $PYKLIPPERSCREENPARAM ]; then
	echo "Testing $PYKLIPPERSCREENPARAM"
	test -f $PYKLIPPERSCREENPARAM || echo "$PYKLIPPERSCREENPARAM is not a file"
fi


case "$1" in
      start)
	      echo -n "Starting Klipper Screen Xclient Deamon .... "
	      setsid "$PYKLIPPERSCREEN" "$PYKLIPPERPARAM" #>/dev/null 2>&1 < /dev/null &
	      echo "running"
		;;
	stop)
		echo -n "Stopping Klipper Screen Xclient Deamon .... "
		PID=`ps -ef|grep KlipperScreen-env/bin/python|awk '{print $2}'`
		kill -9 $PID 
		echo "stopping"
	    	;;
	*)
           	echo "Usage: $0 start"
            	exit 1
             	;;
esac


