class KlippyGcodes:

    HOME            = "G28"
    HOME_X          = "G28 X"
    HOME_Y          = "G28 Y"
    HOME_Z          = "G28 Z"

    MOVE            = "G1"
    MOVE_ABSOLUTE   = "G90"
    MOVE_RELATIVE   = "G91"

    EXTRUDE_ABS     = "M82"
    EXTRUDE_REL     = "M83"

    SET_EXT_TEMP    = "M104"
    MAX_EXT_TEMP    = 300

    SET_BED_TEMP    = "M140"
    MAX_BED_TEMP    = 150

    SET_FAN_SPEED   = "M106"

    PROBE_CALIBRATE = "PROBE_CALIBRATE"
    PROBE_MOVE      = "TESTZ Z="
    PROBE_ABORT     = "ABORT"
    PROBE_ACCEPT    = "ACCEPT"

    SAVE_CONFIG     = "SAVE_CONFIG"
    RESTART         = "RESTART"
    FIRMWARE_RESTART= "FIRMWARE_RESTART"


    @staticmethod
    def set_bed_temp(temp):
        return KlippyGcodes.SET_BED_TEMP + " S" + str(temp)

    @staticmethod
    def set_ext_temp(temp, tool=0):
        return KlippyGcodes.SET_EXT_TEMP + " T" + tool + " S" + str(temp)

    @staticmethod
    def set_fan_speed(speed):
        speed = str( int(float(int(speed) % 101)/100*255) )
        return KlippyGcodes.SET_FAN_SPEED + " S"+ speed

    @staticmethod
    def probe_move(dist):
        return KlippyGcodes.PROBE_MOVE + dist

    @staticmethod
    def extrude(dist, speed=500):
        return KlippyGcodes.MOVE + " E" + dist + " F" + speed
