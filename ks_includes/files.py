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
        self.directories = []
        self.gcodes_path = None

    def set_gcodes_path(self):
        virtual_sdcard = self._screen.printer.get_config_section("virtual_sdcard")
        if virtual_sdcard and "path" in virtual_sdcard:
            self.gcodes_path = os.path.expanduser(virtual_sdcard['path'])
        logging.info(f"Gcodes path: {self.gcodes_path}")

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

                self.run_callbacks(newfiles=newfiles, deletedfiles=deletedfiles)

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

                self.run_callbacks(newfiles=newfiles)
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
        elif method == "server.files.get_directory":
            if 'result' not in result or 'dirs' not in result['result']:
                return
            for x in result['result']['dirs']:
                if x not in self.directories and not x['dirname'].startswith('.'):
                    self.directories.append(x)
                    self.get_dir_info(f"{params['path']}/{x['dirname']}")

    def add_file(self, item, notify=True):
        if 'filename' not in item and 'path' not in item:
            logging.info(f"Error adding item, unknown filename or path: {item}")
            return

        filename = item['path'] if "path" in item else item['filename']
        if filename in self.filelist:
            logging.info(f"File already exists: {filename}")
            self.request_metadata(filename)
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
        self.callbacks.append(callback)

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
        return False

    def remove_file_callback(self, callback):
        if callback not in self.callbacks:
            logging.info(f"callback not found {callback}")
            return
        logging.info(f"removing callback {callback}")
        self.callbacks.remove(callback)

    def file_metadata_exists(self, filename):
        return filename in self.filelist and "slicer" in self.files[filename]

    def get_thumbnail_location(self, filename, small=False):
        if all((
            small,
            len(self.files[filename]['thumbnails']) > 1,
            self.files[filename]['thumbnails'][0]['width'] > self.files[filename]['thumbnails'][1]['width']
        )):
            thumb = self.files[filename]['thumbnails'][1]
        else:
            thumb = self.files[filename]['thumbnails'][0]
        return ['file', thumb['path']] if thumb['local'] else ['http', thumb['path']]

    def has_thumbnail(self, filename):
        return filename in self.files and "thumbnails" in self.files[filename]

    def request_metadata(self, filename):
        self._screen._ws.klippy.get_file_metadata(filename, self._callback)

    def refresh_files(self):
        self._screen._ws.klippy.get_file_list(self._callback)
        self._screen._ws.klippy.get_dir_info(self._callback)
        return False

    def remove_file(self, filename, notify=True):
        if filename in self.filelist:
            self.filelist.remove(filename)
        if filename in self.files:
            self.files.pop(filename, None)
        if notify:
            self.run_callbacks(deletedfiles=[filename])

    def run_callbacks(self, newfiles=(), deletedfiles=(), mods=()):
        args = (newfiles, deletedfiles, mods)
        for cb in self.callbacks:
            GLib.idle_add(cb, *args)

    def get_file_list(self):
        return self.filelist

    def get_file_info(self, filename):
        if filename not in self.files:
            return {"path": None, "modified": 0, "size": 0}
        return self.files[filename]

    def get_dir_info(self, directory):
        self._screen._ws.klippy.get_dir_info(self._callback, directory=directory)
