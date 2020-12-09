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
    metadata_timeout = {}
    timeout = None
    thumbnail_dir = "/tmp/.KS-thumbnails"

    def __init__(self, screen):
        self._screen = screen
        self.add_timeout()

        if not os.path.exists(self.thumbnail_dir):
            os.makedirs(self.thumbnail_dir)
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
                        self.request_metadata(item['filename'])

                if len(self.callbacks) > 0 and (len(newfiles) > 0 or len(deletedfiles) > 0):
                    logger.debug("Running callbacks...")
                    for cb in self.callbacks:
                        cb(newfiles, deletedfiles)

                if len(deletedfiles) > 0:
                    logger.debug("Deleted files: %s", deletedfiles)
                    for file in deletedfiles:
                        self.filelist.remove(file)
                        self.files.pop(file, None)

        elif method == "server.files.metadata":
            if "error" in result.keys():
                logger.debug("Error in getting metadata for %s. Retrying in 6 seconds" %(params['filename']))
                return

            logger.debug("Got metadata for %s" % (result['result']['filename']))
            if params['filename'] in self.metadata_timeout:
                GLib.source_remove(self.metadata_timeout[params['filename']])
                del self.metadata_timeout[params['filename']]

            for x in result['result']:
                self.files[params['filename']][x] = result['result'][x]
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda x: x['size'], reverse=True)

                for thumbnail in self.files[params['filename']]['thumbnails']:
                    f = open("%s/%s-%s" % (self.thumbnail_dir, params['filename'], thumbnail['size']), "wb")
                    f.write(base64.b64decode(thumbnail['data']))
                    f.close()
            for cb in self.callbacks:
                cb([], [], [params['filename']])

    def add_file_callback(self, callback):
        self.callbacks.append(callback)

    def add_timeout(self):
        if self.timeout == None:
            self.timeout = GLib.timeout_add(4000, self.ret_files)

    def file_exists(self, filename):
        return True if filename in self.filelist else False

    def file_metadata_exists(self, filename):
        if not self.file_exists(filename):
            return False
        if "slicer" in self.files[filename]:
            return True
        return False

    def get_thumbnail_location(self, filename):
        if not self.has_thumbnail(filename):
            return None
        return "%s/%s-%s" % (self.thumbnail_dir, filename, self.files[filename]['thumbnails'][0]['size'])

    def has_thumbnail(self, filename):
        if filename not in self.files:
            return False
        return "thumbnails" in self.files[filename] and len(self.files[filename]) > 0

    def remove_timeout(self):
        if self.timeout != None:
            self.timeout = None

    def request_metadata(self, filename):
        if filename not in self.filelist:
            return False
        if filename in self.metadata_timeout:
            GLib.source_remove(self.metadata_timeout[filename])
        self.metadata_timeout[filename] = GLib.timeout_add(
            6000, self._screen._ws.klippy.get_file_metadata, filename, self._callback
        )
        GLib.idle_add(
            lambda x, y: False if self._screen._ws.klippy.get_file_metadata(x,y) else False,
            filename, self._callback
        )

    def ret_files(self, retval=True):
        if not self._screen._ws.klippy.get_file_list(self._callback):
            self.timeout = None
            return False
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
