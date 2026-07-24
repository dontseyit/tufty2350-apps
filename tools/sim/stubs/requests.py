"""Fake badgeware/MicroPython `requests` module for the desktop simulator.

get() ignores the URL and serves a local JSON fixture (the path in SIM_HTTP_DATA,
e.g. the repo's tdf_cache.json) so networked apps render real-looking data with
no proxy/LAN. Set SIM_HTTP_DATA to a different file to feed other snapshots.
"""
import json
import os


class Response:
    def __init__(self, path):
        self.status_code = 200
        with open(path, encoding="utf-8") as f:
            self.text = f.read()

    def json(self):
        return json.loads(self.text)

    def close(self):
        pass


def get(url, timeout=None, **kwargs):
    path = os.environ.get("SIM_HTTP_DATA")
    if not path:
        raise OSError("SIM_HTTP_DATA not set: no fixture for %s" % url)
    return Response(path)
