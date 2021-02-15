import logging
import asyncio
import json
import os
import base64

from contextlib import suppress
from threading import Thread

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

logger = logging.getLogger("KlipperScreen.KlippyFiles")

RESCAN_INTERVAL = 4

class KlippyFiles(Thread):
    callbacks = []
    filelist = []
    files = {}
    metadata_timeout = {}
    timeout = None
    thumbnail_dir = "/tmp/.KS-thumbnails"

    def __init__(self, screen, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = None
        self._poll_task = None
        self._screen = screen

        if not os.path.exists(self.thumbnail_dir):
            os.makedirs(self.thumbnail_dir)

    def run(self):
        self.loop = asyncio.new_event_loop()
        loop = self.loop
        asyncio.set_event_loop(loop)
        try:
            self._poll_task = asyncio.ensure_future(self._poll())
            loop.run_forever()
            loop.run_until_complete(loop.shutdown_asyncgens())

            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                loop.run_until_complete(self._poll_task)
        finally:
            loop.close()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _poll(self):
        await self.ret_files()
        while True:
            logger.debug("Polling files")
            try:
                await self.ret_files()
            except:
                logger.exception("Poll files error")
            await asyncio.sleep(4)


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
                        cb(newfiles, deletedfiles, [])

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

            for x in result['result']:
                self.files[params['filename']][x] = result['result'][x]
            if "thumbnails" in self.files[params['filename']]:
                self.files[params['filename']]['thumbnails'].sort(key=lambda x: x['size'], reverse=True)

                for thumbnail in self.files[params['filename']]['thumbnails']:
                    f = open("%s/%s-%s" % (self.thumbnail_dir, params['filename'].split('/')[-1], thumbnail['size']),
                        "wb")
                    f.write(base64.b64decode(thumbnail['data']))
                    f.close()
            for cb in self.callbacks:
                logger.debug("Running metadata callbacks")
                cb([], [], [params['filename']])

    def add_file_callback(self, callback):
        try:
            self.callbacks.append(callback)
        except:
            logger.debug("Callback not found: %s" % callback)

    def remove_file_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.pop(self.callbacks.index(callback))

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
        return "%s/%s-%s" % (self.thumbnail_dir, filename.split('/')[-1], self.files[filename]['thumbnails'][0]['size'])

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
        self.loop.call_soon(lambda x, y: False if self._screen._ws.klippy.get_file_metadata(x,y) else False,
            filename, self._callback)

    async def ret_files(self, retval=True):
        logger.debug("Scanning for files")
        if not self._screen._ws.klippy.get_file_list(self._callback):
            self.timeout = None

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
