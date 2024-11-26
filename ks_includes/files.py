import logging
import os

import gi

gi.require_version("Gtk", "3.0")


class KlippyFiles:
    def __init__(self, screen):
        self._screen = screen
        self.callbacks = []
        self.files = {}
        self.directories = []
        self.gcodes_path = None

    def reinit(self):
        self.callbacks.clear()
        self.files.clear()
        self.directories.clear()
        self.gcodes_path = None

    def set_gcodes_path(self):
        virtual_sdcard = self._screen.printer.get_config_section("virtual_sdcard")
        if virtual_sdcard and "path" in virtual_sdcard:
            self.gcodes_path = os.path.expanduser(virtual_sdcard['path'])
        logging.info(f"Gcodes path: {self.gcodes_path}")

    def _callback(self, result, method, params):
        if "error" in result:
            logging.debug(result["error"])
            return
        if method == "server.files.list":
            for item in result["result"]:
                self.files[item["path"]] = item
                self.request_metadata(item["path"])
        elif method == "server.files.metadata":
            for x in result['result']:
                if params['filename'] not in self.files:
                    self.files[params['filename']] = {}
                self.files[params['filename']][x] = result['result'][x]
            if 'path' not in self.files[params['filename']]:
                self.files[params['filename']]['path'] = params['filename']
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda y: y['size'], reverse=True)
                for thumbnail in self.files[params['filename']]['thumbnails']:
                    thumbnail['local'] = False
                    if self.gcodes_path is not None:
                        path = os.path.join(
                            os.path.dirname(os.path.join(self.gcodes_path, params['filename'])),
                            thumbnail['relative_path']
                        )
                        if os.access(path, os.R_OK):
                            thumbnail['local'] = True
                            thumbnail['path'] = path
                    if thumbnail['local'] is False:
                        thumbnail['path'] = os.path.join(
                            os.path.dirname(params['filename']),
                            thumbnail['relative_path']
                        )
            self._screen.process_update("notify_metadata_update", params)
            self.run_callbacks(
                "modify_file", {'action': "modify_file", 'item': self.files[params['filename']]}
            )

    def add_file(self, item):
        if 'path' not in item:
            logging.info(f"Error adding item, unknown path: {item}")
            return
        self.files[item['path']] = item
        self.request_metadata(item['path'])

    def remove_file(self, filename):
        if filename in self.files:
            self.files.pop(filename)

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            return
        logging.info(f"callback not found {callback}")

    def process_update(self, data):
        if (
            'item' in data and data['item']['root'] != 'gcodes'
            or data['action'].endswith("file") and not self.is_gcode(data['item']['path'])
        ):
            return
        if data['action'] == "create_file":
            self.add_file(data['item'])
        elif data['action'] == "delete_file":
            self.remove_file(data['item']['path'])
        elif data['action'] == "modify_file":
            self.request_metadata(data['item']['path'])
        elif data['action'] == "move_file":
            self.files[data['item']['path']] = self.files.pop(data['source_item']['path'])
            self.files[data['item']['path']].update(data['item'])
        self.run_callbacks(data['action'], data)

    @staticmethod
    def is_gcode(path):
        return os.path.splitext(path)[1] in {'.gcode', '.gco', '.g'}

    def file_metadata_exists(self, filename):
        return filename in self.files and "slicer" in self.files[filename]

    def get_thumbnail_location(self, filename, small=False):
        if all((
            small,
            len(self.files[filename]['thumbnails']) > 1
        )):
            thumb = self.files[filename]['thumbnails'][1]
        else:
            thumb = self.files[filename]['thumbnails'][0]
        return ['file', thumb['path']] if thumb['local'] else ['http', thumb['path']]

    def has_thumbnail(self, filename):
        return filename in self.files and "thumbnails" in self.files[filename]

    def request_metadata(self, filename):
        if self.is_gcode(filename):
            self._screen._ws.klippy.get_file_metadata(filename, self._callback)
        else:
            logging.info("Not a gcode")

    def refresh_files(self):
        self._screen._ws.klippy.get_file_list(self._callback)

    def run_callbacks(self, action, item):
        for cb in self.callbacks:
            cb(action, item)

    def get_file_info(self, path):
        if path not in self.files:
            logging.info(f"Metadata not found {path}")
            self.request_metadata(path)
            return {}
        return self.files[path]

    def get_dir_info(self, directory):
        self._screen._ws.klippy.get_dir_info(self._callback, directory=directory)
