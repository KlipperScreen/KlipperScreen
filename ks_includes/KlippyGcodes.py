class KlippyGcodes:
    MOVE_ABSOLUTE = "G90"
    MOVE_RELATIVE = "G91"
    EXTRUDE_ABS = "M82"
    EXTRUDE_REL = "M83"

    @staticmethod
    def set_bed_temp(temp):
        return f"M140 S{temp}"

    @staticmethod
    def set_ext_temp(temp, tool=0):
        return f"M104 T{tool} S{temp}"

    @staticmethod
    def set_heater_temp(heater, temp):
        return f'SET_HEATER_TEMPERATURE heater="{heater}" target={temp}'

    @staticmethod
    def set_temp_fan_temp(temp_fan, temp):
        return f'SET_TEMPERATURE_FAN_TARGET temperature_fan="{temp_fan}" target={temp}'

    @staticmethod
    def set_extrusion_rate(rate):
        return f"M221 S{rate}"

    @staticmethod
    def set_speed_rate(rate):
        return f"M220 S{rate}"

    @staticmethod
    def bed_mesh_load(profile):
        return f"BED_MESH_PROFILE LOAD='{profile}'"

    @staticmethod
    def bed_mesh_remove(profile):
        return f"BED_MESH_PROFILE REMOVE='{profile}'"

    @staticmethod
    def bed_mesh_save(profile):
        return f"BED_MESH_PROFILE SAVE='{profile}'"

    @staticmethod
    def set_led_color(led, color):
        return (
            f'SET_LED LED="{led}" '
            f'RED={color[0]} GREEN={color[1]} BLUE={color[2]} WHITE={color[3]} '
            f'SYNC=0 TRANSMIT=1'
        )
