# Simulator fixture standing in for the device's /system/secrets.py.
# Its only job is to make networked apps (e.g. tdf) see a configured network so
# they go "online" and fetch. Values are dummies; the fake wifi ignores them.
WIFI_SSID = "sim-net"
WIFI_PASSWORD = ""
