import json
import requests
import logging


class KlippyRest:
    def __init__(self, ip, port=7125, api_key=False):
        self.ip = ip
        self.port = port
        self.api_key = api_key

    @property
    def endpoint(self):
        protocol = "http"
        if int(self.port) == 443:
            protocol = "https"
        return f"{protocol}://{self.ip}:{self.port}"

    def get_server_info(self):
        return self.send_request("server/info")

    def get_oneshot_token(self):
        r = self.send_request("access/oneshot_token")
        if r is False:
            return False
        return r['result']

    def get_printer_info(self):
        return self.send_request("printer/info")

    def get_thumbnail_stream(self, thumbnail):
        url = f"{self.endpoint}/server/files/gcodes/{thumbnail}"

        response = requests.get(url, stream=True)
        if response.status_code == 200:
            response.raw.decode_content = True
            return response.content
        return False

    def send_request(self, method):
        url = f"{self.endpoint}/{method}"
        logging.debug(f"Sending request to {url}")
        headers = {} if self.api_key is False else {"x-api-key": self.api_key}
        try:
            r = requests.get(url, headers=headers)
        except Exception as e:
            logging.critical(e, exc_info=True)
            return False
        if r.status_code != 200:
            return False

        # TODO: Try/except
        try:
            data = json.loads(r.content)
        except Exception as e:
            logging.critical(e, exc_info=True)
            logging.exception(f"Unable to parse response from moonraker:\n {r.content}")
            return False

        return data
