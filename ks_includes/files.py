import logging
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

class KlippyFiles():
    def __init__(self, screen):
        self._screen = screen
        self.callbacks = []
        self.files = {}
        self.filelist = []
        self.thumbnail_dir = "/tmp/.KS-thumbnails"

        if not os.path.exists(self.thumbnail_dir):
            os.makedirs(self.thumbnail_dir)

        self.gcodes_path = None

    def initialize(self):
        self.gcodes_path = None
        if "virtual_sdcard" in self._screen.printer.get_config_section_list():
            vsd = self._screen.printer.get_config_section("virtual_sdcard")
            if "path" in vsd:
                self.gcodes_path = vsd['path']
        logging.info("Gcodes path: %s" % self.gcodes_path)

    def reset(self):
        self.run_callbacks()
        self.callbacks = None
        self.files = None
        self.filelist = None
        self.thumbnail_dir = None
        self.gcodes_path = None
        self._screen = None

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

                if len(newfiles) > 0 or len(deletedfiles) > 0:
                    self.run_callbacks(newfiles, deletedfiles)

                if len(deletedfiles) > 0:
                    for file in deletedfiles:
                        self.remove_file(file)
        elif method == "server.files.directory":
            if "result" in result:
                dir = params['path'][7:] if params['path'].startswith('gcodes/') else params['path']
                if dir[-1] == '/':
                    dir = dir[:-1]

                newfiles = []
                for file in result['result']['files']:
                    fullpath = "%s/%s" % (dir, file['filename'])
                    if fullpath not in self.filelist:
                        newfiles.append(fullpath)

                if len(newfiles) > 0:
                    self.run_callbacks(newfiles)
        elif method == "server.files.metadata":
            if "error" in result.keys():
                logging.debug("Error in getting metadata for %s. Retrying in 6 seconds" % (params['filename']))
                return

            for x in result['result']:
                self.files[params['filename']][x] = result['result'][x]
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda x: x['size'], reverse=True)

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
            logging.info("Error adding item, unknown filename or path: %s" % item)
            return

        filename = item['path'] if "path" in item else item['filename']
        if filename in self.filelist:
            logging.info("File already exists: %s" % filename)
            self.request_metadata(filename)
            GLib.timeout_add_seconds(1, self.run_callbacks, mods=[filename])
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
        except Exception:
            logging.debug("Callback not found: %s" % callback)

    def process_update(self, data):
        if 'item' in data and data['item']['root'] != 'gcodes':
            return

        if data['action'] == "create_dir":
            self._screen._ws.klippy.get_file_dir("gcodes/%s" % data['item']['path'], self._callback)
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
        return True if filename in self.filelist else False

    def file_metadata_exists(self, filename):
        if not self.file_exists(filename):
            return False
        if "slicer" in self.files[filename]:
            return True
        return False

    def get_thumbnail_location(self, filename):
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

    def ret_file_data(self, filename):
        print("Getting file info for %s" % (filename))
        self._screen._ws.klippy.get_file_metadata(filename, self._callback)

    def run_callbacks(self, newfiles=[], deletedfiles=[], mods=[]):
        if len(self.callbacks) <= 0:
            return False
        for cb in self.callbacks:
            GLib.idle_add(cb, newfiles, deletedfiles, mods)
        return False

    def get_file_list(self):
        return self.filelist

    def get_file_info(self, filename):
        if filename not in self.files:
            return {"path": None, "modified": 0, "size": 0}
        return self.files[filename]
