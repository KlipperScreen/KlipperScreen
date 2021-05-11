import json
import requests
import logging

class KlippyRest:
    def __init__(self, ip, port=7125, api_key=False):
        self.ip = ip
        self.port = port
        self.api_key = api_key

    def get_server_info(self):
        return self.send_request("server/info")

    def get_oneshot_token(self):
        r = self.send_request("access/oneshot_token")
        if r == False:
            return False
        return r['result']

    def get_printer_info(self):
        return self.send_request("printer/info")

    def get_thumbnail_stream(self, thumbnail):
        url = "http://%s:%s/server/files/gcodes/%s" % (self.ip, self.port, thumbnail)
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            response.raw.decode_content = True
            return response.content
        return False

    def send_request(self, method):
        url = "http://%s:%s/%s" % (self.ip, self.port, method)
        logging.debug("Sending request to %s" % url)
        headers = {} if self.api_key == False else {"x-api-key":self.api_key}
        try:
            r = requests.get(url, headers=headers)
        except:
            return False
        if r.status_code != 200:
            return False

        #TODO: Try/except
        try:
            data = json.loads(r.content)
        except:
            logging.exception("Unable to parse response from moonraker:\n %s" % r.content)
            return False

        return data
