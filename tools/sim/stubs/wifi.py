"""Fake badgeware `wifi` module for the desktop simulator.

Reports an instantly-associated link (so apps reach WIFI_UP and fetch), unless
SIM_WIFI=off in the environment, in which case connect() always fails so you can
exercise an app's offline path.
"""
import os

_connected = False


def _enabled():
    return os.environ.get("SIM_WIFI", "on") != "off"


def connect(ssid=None, psk=None, **kwargs):
    global _connected
    _connected = _enabled()
    return _connected


def tick():
    return None


def disconnect():
    global _connected
    _connected = False


def ip():
    return "192.168.0.n" if _connected else "0.0.0.0"


def is_connected():
    return _connected
