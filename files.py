import logging
import asyncio
import json

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

class KlippyFiles:
    filelist = []
    files = {}

    def __init__(self, screen):
        self._screen = screen
        GLib.idle_add(self.ret_files)


    def _callback(self, result, method, params):
        if method == "get_file_list":
            if isinstance(result['result'],list):
                for item in result['result']:
                    self.filelist.append(item['filename'])
                    self.files[item['filename']] = {
                        "size": item['size'],
                        "modified": item['modified']
                    }
                    #self.get_file_data(item['filename'])
                #files = [asyncio.create_task(self.get_file_data(file)) for file in self.files]
                #await asyncio.gather(files)
                #files = [GLib.idle_add(self.ret_file_data, file) for file in self.files]

        if method == "get_file_metadata":
            print("Got metadata for %s" % (result['result']['filename']))
            #print(json.dumps(result, indent=4))

    def ret_files(self):
        self._screen._ws.send_method("get_file_list", {}, self._callback)

    def ret_file_data (self, filename):
        print("Getting file info for %s" % (filename))
        self._screen._ws.send_method("get_file_metadata", {"filename": filename}, self._callback)

    def get_file_list(self):
        return self.filelist

    def get_file_info(self, filename):
        if filename not in self.files:
            return None

        return self.files[filename]
