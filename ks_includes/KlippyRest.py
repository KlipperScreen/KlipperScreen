import logging
import re

import requests


class KlippyRest:
    def __init__(self, ip, port=7125, api_key=False, path='', ssl=None):
        self.ip = ip
        self.port = port
        self.path = f"/{path}" if path else ''
        self.ssl = ssl
        self.api_key = api_key
        self.ssl = int(self.port) in {443, 7130} if ssl is None else bool(ssl)
        self.status = ''

    @property
    def endpoint(self):
        return f"{'https' if self.ssl else 'http'}://{self.ip}:{self.port}{self.path}"

    @staticmethod
    def process_response(response):
        return response['result'] if response and 'result' in response else response

    def get_server_info(self):
        return self.send_request("server/info")

    def get_oneshot_token(self):
        return self.send_request("access/oneshot_token")

    def get_printer_info(self):
        return self.send_request("printer/info")

    def get_gcode_help(self):
        return self.send_request("printer/gcode/help")

    def get_thumbnail_stream(self, thumbnail):
        return self.send_request(f"server/files/gcodes/{thumbnail}", json=False)

    def _do_request(self, method, request_method, data=None, json=None, json_response=True, timeout=3):
        url = f"{self.endpoint}/{method}"
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        try:
            callee = getattr(requests, request_method)
            response = callee(url, json=json, data=data, headers=headers, timeout=timeout)
            response.raise_for_status()
            self.status = ''
            return response.json() if json_response else response.content
        except Exception as e:
            self.status = self.format_status(e)
            logging.error(self.status.replace('\n', '>>'))
            return False

    def post_request(self, method, data=None, json=None, json_response=True):
        return self._do_request(method, "post", data, json, json_response)

    def send_request(self, method, json=True, timeout=4):
        res = self._do_request(method, "get", json_response=json, timeout=timeout)
        return self.process_response(res) if json else res

    @staticmethod
    def format_status(status):
        try:
            rep = {"HTTPConnectionPool": "", "/server/info ": "", "Caused by ": "", "(": "", ")": "",
                   ": ": "\n", "'": "", "`": "", "\"": ""}
            rep = {re.escape(k): v for k, v in rep.items()}
            pattern = re.compile("|".join(rep.keys()))
            status = pattern.sub(lambda m: rep[re.escape(m.group(0))], f"{status}").split("\n")
            return "\n".join(_ for _ in status if "urllib3" not in _ and _ != "")
        except TypeError or KeyError:
            return status
