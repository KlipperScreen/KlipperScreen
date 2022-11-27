class KlippyGcodes:
    HOME = "G28"
    HOME_XY = "G28 X Y"
    Z_TILT = "Z_TILT_ADJUST"
    QUAD_GANTRY_LEVEL = "QUAD_GANTRY_LEVEL"

    MOVE = "G1"
    MOVE_ABSOLUTE = "G90"
    MOVE_RELATIVE = "G91"

    EXTRUDE_ABS = "M82"
    EXTRUDE_REL = "M83"

    SET_EXT_TEMP = "M104"
    SET_BED_TEMP = "M140"

    SET_EXT_FACTOR = "M221"
    SET_FAN_SPEED = "M106"
    SET_SPD_FACTOR = "M220"

    PROBE_CALIBRATE = "PROBE_CALIBRATE"
    Z_ENDSTOP_CALIBRATE = "Z_ENDSTOP_CALIBRATE"
    TESTZ = "TESTZ Z="
    ABORT = "ABORT"
    ACCEPT = "ACCEPT"

    @staticmethod
    def set_bed_temp(temp):
        return f"{KlippyGcodes.SET_BED_TEMP} S{temp}"

    @staticmethod
    def set_ext_temp(temp, tool=0):
        return f"{KlippyGcodes.SET_EXT_TEMP} T{tool} S{temp}"

    @staticmethod
    def set_heater_temp(heater, temp):
        return f'SET_HEATER_TEMPERATURE heater="{heater}" target={temp}'

    @staticmethod
    def set_temp_fan_temp(temp_fan, temp):
        return f'SET_TEMPERATURE_FAN_TARGET temperature_fan="{temp_fan}" target={temp}'

    @staticmethod
    def set_fan_speed(speed):
        return f"{KlippyGcodes.SET_FAN_SPEED} S{speed * 2.55:.0f}"

    @staticmethod
    def set_extrusion_rate(rate):
        return f"{KlippyGcodes.SET_EXT_FACTOR} S{rate}"

    @staticmethod
    def set_speed_rate(rate):
        return f"{KlippyGcodes.SET_SPD_FACTOR} S{rate}"

    @staticmethod
    def testz_move(dist):
        return KlippyGcodes.TESTZ + dist

    @staticmethod
    def extrude(dist, speed=500):
        return f"{KlippyGcodes.MOVE} E{dist} F{speed}"

    @staticmethod
    def bed_mesh_load(profile):
        return f"BED_MESH_PROFILE LOAD='{profile}'"

    @staticmethod
    def bed_mesh_remove(profile):
        return f"BED_MESH_PROFILE REMOVE='{profile}'"

    @staticmethod
    def bed_mesh_save(profile):
        return f"BED_MESH_PROFILE SAVE='{profile}'"
