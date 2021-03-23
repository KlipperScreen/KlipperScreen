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
    MAX_EXT_TEMP    = 450

    SET_BED_TEMP    = "M140"
    MAX_BED_TEMP    = 150

    SET_EXT_FACTOR  = "M221"
    SET_FAN_SPEED   = "M106"
    SET_SPD_FACTOR  = "M220"

    PROBE_CALIBRATE = "PROBE_CALIBRATE"
    PROBE_MOVE      = "TESTZ Z="
    PROBE_ABORT     = "ABORT"
    PROBE_ACCEPT    = "ACCEPT"

    SAVE_CONFIG     = "SAVE_CONFIG"
    RESTART         = "RESTART"
    FIRMWARE_RESTART= "FIRMWARE_RESTART"


    @staticmethod
    def set_bed_temp(temp):
        return "%s S%s" % (KlippyGcodes.SET_BED_TEMP, str(temp))

    @staticmethod
    def set_ext_temp(temp, tool=0):
        return "%s T%s S%s" % (KlippyGcodes.SET_EXT_TEMP, str(tool), str(temp))

    @staticmethod
    def set_heater_temp(heater, temp):
        return 'SET_HEATER_TEMPERATURE heater="%s" target=%s' % (heater, str(temp))

    @staticmethod
    def set_fan_speed(speed):
        speed = str( int(float(int(speed) % 101)/100*255) )
        return "%s S%s" % (KlippyGcodes.SET_FAN_SPEED, speed)

    @staticmethod
    def set_extrusion_rate(rate):
        return "%s S%s" % (KlippyGcodes.SET_EXT_FACTOR, rate)

    @staticmethod
    def set_speed_rate(rate):
        return "%s S%s" % (KlippyGcodes.SET_SPD_FACTOR, rate)

    @staticmethod
    def probe_move(dist):
        return KlippyGcodes.PROBE_MOVE + dist

    @staticmethod
    def extrude(dist, speed=500):
        return "%s E%s F%s" % (KlippyGcodes.MOVE, dist, speed)

    @staticmethod
    def bed_mesh_load(profile):
        return "BED_MESH_PROFILE LOAD='%s'" % profile

    @staticmethod
    def bed_mesh_remove(profile):
        return "BED_MESH_PROFILE REMOVE='%s'" % profile

    @staticmethod
    def bed_mesh_save(profile):
        return "BED_MESH_PROFILE SAVE='%s'" % profile
