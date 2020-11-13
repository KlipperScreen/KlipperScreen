import logging
import asyncio
import json
import os
import base64

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

        if not os.path.exists('/tmp/.KS-thumbnails'):
            os.makedirs('/tmp/.KS-thumbnails')
        GLib.idle_add(self.ret_files, False)


    def _callback(self, result, method, params):
        if method == "server.files.list":
            if "result" in result and isinstance(result['result'],list):
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
                        self.update_metadata(item['filename'])

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

        elif method == "server.files.metadata":
            if "error" in result.keys():
                logger.debug("Error in getting metadata for %s" %(params['filename']))
                GLib.timeout_add(2000, self._screen._ws.klippy.get_file_metadata, params['filename'], self._callback)
                return

            logger.debug("Got metadata for %s" % (result['result']['filename']))
            for x in result['result']:
                self.files[params['filename']][x] = result['result'][x]
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda x: x['size'], reverse=True)

                for thumbnail in self.files[params['filename']]['thumbnails']:
                    f = open("/tmp/.KS-thumbnails/%s-%s" % (params['filename'], thumbnail['size']), "wb")
                    f.write(base64.b64decode(thumbnail['data']))
                    f.close()
            for cb in self.callbacks:
                cb([], [], [params['filename']])

    def add_file_callback(self, callback):
        self.callbacks.append(callback)

    def ret_files(self, retval=True):
        self._screen._ws.klippy.get_file_list(self._callback)
        return retval

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

    def update_metadata(self, filename):
        self._screen._ws.klippy.get_file_metadata(filename, self._callback)
