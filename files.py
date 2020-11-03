import logging
import asyncio
import json

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

logger = logging.getLogger("KlipperScreen.KlippyFiles")

class KlippyFiles:
    callbacks = []
    filelist = []
    files = {}
    timeout = None

    def __init__(self, screen):
        self._screen = screen
        self.timeout = GLib.timeout_add(2000, self.ret_files)
        #GLib.idle_add(self.ret_files)


    def _callback(self, result, method, params):
        if method == "server.files.list":
            if isinstance(result['result'],list):
                newfiles = []
                deletedfiles = self.filelist.copy()
                for item in result['result']:
                    if item['filename'] in self.files:
                        deletedfiles.remove(item['filename'])
                    else:
                        newfiles.append(item['filename'])
                        logger.debug("New file: %s", item['filename'])
                        self.filelist.append(item['filename'])
                        self.files[item['filename']] = {
                            "size": item['size'],
                            "modified": item['modified']
                        }

                if len(self.callbacks) > 0 and (len(newfiles) > 0 or len(deletedfiles) > 0):
                    logger.debug("Running callbacks...")
                    for cb in self.callbacks:
                        cb(newfiles, deletedfiles)

                if len(deletedfiles) > 0:
                    logger.debug("Deleted files: %s", deletedfiles)
                    for file in deletedfiles:
                        self.filelist.remove(file)
                        self.files.pop(file, None)

                    #self.get_file_data(item['filename'])
                #files = [asyncio.create_task(self.get_file_data(file)) for file in self.files]
                #await asyncio.gather(files)
                #files = [GLib.idle_add(self.ret_file_data, file) for file in self.files]

        elif method == "get_file_metadata":
            print("Got metadata for %s" % (result['result']['filename']))
            #print(json.dumps(result, indent=4))

    def add_file_callback(self, callback):
        self.callbacks.append(callback)
        print("Callbacks...")
        print(self.callbacks)

    def ret_files(self):
        self._screen._ws.klippy.get_file_list(self._callback)
        return True

    def ret_file_data (self, filename):
        print("Getting file info for %s" % (filename))
        self._screen._ws.klippy.get_file_metadata(filename, self._callback)

    def get_file_list(self):
        return self.filelist

    def get_file_info(self, filename):
        if filename not in self.files:
            return None

        return self.files[filename]

    def add_file(self, file_name, size, modified, old_file_name = None):
        print(file_name)
