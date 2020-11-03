import json
import requests
import logging



class KlippyRest:
    def __init__(self, ip, port=7125):
        self.ip = ip
        self.port = port

    def get_info(self):
        return self.send_request("server/info")

    def send_request(self, method):
        r = requests.get("http://%s:%s/%s" % (self.ip, self.port, method))
        if r.status_code != 200:
            return False

        #TODO: Try/except
        data = json.loads(r.content)

        return data
