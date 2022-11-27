import logging
import os

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib


class KlippyFiles:
    def __init__(self, screen):
        self._screen = screen
        self.callbacks = []
        self.files = {}
        self.filelist = []
        self.gcodes_path = None

    def initialize(self):
        if "virtual_sdcard" in self._screen.printer.get_config_section_list():
            vsd = self._screen.printer.get_config_section("virtual_sdcard")
            if "path" in vsd:
                self.gcodes_path = os.path.expanduser(vsd['path'])
        logging.info(f"Gcodes path: {self.gcodes_path}")

    def reset(self):
        self._screen = None
        self.callbacks = None
        self.files = None
        self.filelist = None
        self.gcodes_path = None

    def _callback(self, result, method, params):
        if method == "server.files.list":
            if "result" in result and isinstance(result['result'], list):
                newfiles = []
                deletedfiles = self.filelist.copy()
                for item in result['result']:
                    file = item['filename'] if "filename" in item else item['path']
                    if file in self.files:
                        deletedfiles.remove(file)
                    else:
                        newfiles.append(file)
                        self.add_file(item, False)

                if newfiles or len(deletedfiles) > 0:
                    self.run_callbacks(newfiles, deletedfiles)

                if len(deletedfiles) > 0:
                    for file in deletedfiles:
                        self.remove_file(file)
        elif method == "server.files.directory":
            if "result" in result:
                directory = params['path'][7:] if params['path'].startswith('gcodes/') else params['path']
                if directory[-1] == '/':
                    directory = directory[:-1]

                newfiles = []
                for file in result['result']['files']:
                    fullpath = f"{directory}/{file['filename']}"
                    if fullpath not in self.filelist:
                        newfiles.append(fullpath)

                if newfiles:
                    self.run_callbacks(newfiles)
        elif method == "server.files.metadata":
            if "error" in result.keys():
                logging.debug(f"Error in getting metadata for {params['filename']}. Retrying in 6 seconds")
                return

            for x in result['result']:
                self.files[params['filename']][x] = result['result'][x]
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda y: y['size'], reverse=True)

                for thumbnail in self.files[params['filename']]['thumbnails']:
                    thumbnail['local'] = False
                    if self.gcodes_path is not None:
                        fpath = os.path.join(self.gcodes_path, params['filename'])
                        fdir = os.path.dirname(fpath)
                        path = os.path.join(fdir, thumbnail['relative_path'])
                        if os.access(path, os.R_OK):
                            thumbnail['local'] = True
                            thumbnail['path'] = path
                    if thumbnail['local'] is False:
                        fdir = os.path.dirname(params['filename'])
                        thumbnail['path'] = os.path.join(fdir, thumbnail['relative_path'])
            self.run_callbacks(mods=[params['filename']])

    def add_file(self, item, notify=True):
        if 'filename' not in item and 'path' not in item:
            logging.info(f"Error adding item, unknown filename or path: {item}")
            return

        filename = item['path'] if "path" in item else item['filename']
        if filename in self.filelist:
            logging.info(f"File already exists: {filename}")
            self.request_metadata(filename)
            args = None, None, [filename]
            GLib.idle_add(self.run_callbacks, *args)
            return

        self.filelist.append(filename)
        self.files[filename] = {
            "size": item['size'],
            "modified": item['modified']
        }
        self.request_metadata(filename)
        if notify is True:
            self.run_callbacks(newfiles=[filename])

    def add_file_callback(self, callback):
        try:
            self.callbacks.append(callback)
        except Exception as e:
            logging.debug(f"Callback not found: {callback}:\n{e}")

    def process_update(self, data):
        if 'item' in data and data['item']['root'] != 'gcodes':
            return

        if data['action'] == "create_dir":
            self._screen._ws.klippy.get_file_dir(f"gcodes/{data['item']['path']}", self._callback)
        elif data['action'] == "create_file":
            self.add_file(data['item'])
        elif data['action'] == "delete_file":
            self.remove_file(data['item']['path'])
        elif data['action'] == "modify_file":
            self.request_metadata(data['item']['path'])
        elif data['action'] == "move_file":
            self.add_file(data['item'], False)
            self.remove_file(data['source_item']['path'], False)
            self.run_callbacks(newfiles=[data['item']['path']], deletedfiles=[data['source_item']['path']])

    def remove_file_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.pop(self.callbacks.index(callback))

    def file_exists(self, filename):
        return filename in self.filelist

    def file_metadata_exists(self, filename):
        if self.file_exists(filename):
            return "slicer" in self.files[filename]
        return False

    def get_thumbnail_location(self, filename, small=False):
        if small and len(self.files[filename]['thumbnails']) > 1 \
                and self.files[filename]['thumbnails'][0]['width'] > self.files[filename]['thumbnails'][1]['width']:
            thumb = self.files[filename]['thumbnails'][1]
        else:
            thumb = self.files[filename]['thumbnails'][0]
        if thumb['local'] is False:
            return ['http', thumb['path']]
        return ['file', thumb['path']]

    def has_thumbnail(self, filename):
        if filename not in self.files:
            return False
        return "thumbnails" in self.files[filename] and len(self.files[filename]) > 0

    def request_metadata(self, filename):
        if filename not in self.filelist:
            return False
        self._screen._ws.klippy.get_file_metadata(filename, self._callback)

    def refresh_files(self):
        self._screen._ws.klippy.get_file_list(self._callback)

    def remove_file(self, filename, notify=True):
        if filename not in self.filelist:
            return

        self.filelist.remove(filename)
        self.files.pop(filename, None)

        if notify is True:
            self.run_callbacks(deletedfiles=[filename])

    def run_callbacks(self, newfiles=None, deletedfiles=None, mods=None):
        if mods is None:
            mods = []
        if deletedfiles is None:
            deletedfiles = []
        if newfiles is None:
            newfiles = []
        if len(self.callbacks) <= 0:
            return False
        for cb in self.callbacks:
            args = newfiles, deletedfiles, mods
            GLib.idle_add(cb, *args)
        return False

    def get_file_list(self):
        return self.filelist

    def get_file_info(self, filename):
        if filename not in self.files:
            return {"path": None, "modified": 0, "size": 0}
        return self.files[filename]
