import gi
import json
import os
import pathlib

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from screen import KlipperScreen

syncraft_path = os.path.join(pathlib.Path(__file__).parent.resolve().parent, "syncraft")
syncraft_images_path = os.path.join(syncraft_path, "images")
materials_path = os.path.join(syncraft_path, "materials.json")

class Panel(ScreenPanel):
    def __init__(self, screen, title):
        self._screen: KlipperScreen

        title = title or _("Materials")
        super().__init__(screen, title)

        grid = Gtk.Grid(column_homogeneous=True)

        repeat_three: int = 0
        i: int = 0

        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(grid)
        self.content.add(scroll)

        self.materials = self.get_materials()

        for material in self.materials:
            if self._config.nozzle in material["compatible"]:
                index_button = self._gtk.Button(
                    "circle-green",
                    material["name"],
                    "color3",
                    directory=syncraft_images_path
                )
                index_button.connect("clicked", self.set_material, material)
                grid.attach(index_button, repeat_three, i, 1, 1)
                
                if repeat_three == 4:
                    repeat_three = 0
                    i += 1
                else:
                    repeat_three += 1

        for material in self.materials:
            # TODO: Check if show_experimental is True in some configuration
            show_experimental = True
            if not show_experimental:
                break

            allowed_for_experimental = ["Standard 0.25mm", "Standard 0.4mm", "Standard 0.8mm"]
            
            if self._config.nozzle in material["experimental"] and self._config.nozzle in allowed_for_experimental:
                index_button = self._gtk.Button(
                    "circle-orange",
                    material["name"],
                    "color1",
                    directory=syncraft_images_path
                )
                index_button.connect("clicked", self.set_material, material)
                grid.attach(index_button, repeat_three, i, 1, 1)
                if repeat_three == 4:
                    repeat_three = 0
                    i += 1
                else:
                    repeat_three += 1

        # Add empty material
        size: int = 1
        index: int = repeat_three
        while index != 4:
            size += 1
            index += 1
        index_button = self._gtk.Button(
            "circle-white",
            _("Empty"),
            "color3",
            directory=syncraft_images_path
        )
        index_button.connect("clicked", self.set_material)
        grid.attach(index_button, repeat_three, i, size, 1)

    def get_materials(self) -> list:
        with open(materials_path, "r") as materials:
            return json.load(materials)
        
    def set_material(self, widget, material=None):
        material_name = material["name"] if material else "empty"
        self._screen._ws.klippy.gcode_script(
            f"CHANGE_MATERIAL M='{material_name}' EXT='{self._config.extruder}'"
        )
        self._screen._menu_go_back()