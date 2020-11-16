import json
import requests
import logging

logger = logging.getLogger("KlipperScreen.KlippyRest")

class KlippyRest:
    def __init__(self, ip, port=7125):
        self.ip = ip
        self.port = port

    def get_server_info(self):
        return self.send_request("server/info")

    def get_printer_info(self):
        return self.send_request("printer/info")

    def send_request(self, method):
        url = "http://%s:%s/%s" % (self.ip, self.port, method)
        logger.debug("Sending request to %s" % url)
        r = requests.get(url)
        if r.status_code != 200:
            return False

        #TODO: Try/except
        try:
            data = json.loads(r.content)
        except:
            logger.exception("Unable to parse response from moonraker:\n %s" % r.content)
            return False

        return data
