import sys
import binascii
import datetime
import json
import copy
from mqtt import MqttMessage
from workers.base import BaseWorker
from utils import booleanize
import logger

REQUIREMENTS = ["bluepy"]
_LOGGER = logger.get(__name__)

class XiaomimijaWorker(BaseWorker):
  devices = {}
  homeassistant_discovery = False
  homeassistant_discovery_prefix = "homeassistant"

  def __init__(self, command_timeout, global_topic_prefix, **kwargs):
    from bluepy.btle import Scanner, DefaultDelegate

    class ScanDelegate(DefaultDelegate):
      def __init__(self):
          DefaultDelegate.__init__(self)

      def handleDiscovery(self, dev, isNewDev, isNewData):
          if isNewDev:
              _LOGGER.debug("Discovered new device: %s" % dev.addr)

    super(XiaomimijaWorker, self).__init__(
      command_timeout, global_topic_prefix, **kwargs
    )

    self.scanner = Scanner().withDelegate(ScanDelegate())
    self.devices = {k.lower(): v for k,v in self.devices.items()}

    _LOGGER.info("Adding %d %s devices", len(self.devices), repr(self))


  def status_update(self):
    from bluepy import btle

    messages = []

    devices = self.scanner.scan(30, passive=True)

    for d in devices:
      v = d.getValueText(22)
      if v and v.startswith("1a18"):
        _LOGGER.debug("Found 1a18 device {}".format(d.addr))

        temp     = int.from_bytes(binascii.unhexlify(v[16:20]), byteorder=sys.byteorder) / 100
        humidity = int.from_bytes(binascii.unhexlify(v[20:24]), byteorder=sys.byteorder) / 100
        voltage  = int.from_bytes(binascii.unhexlify(v[24:28]), byteorder=sys.byteorder) / 1000
        battery  = int.from_bytes(binascii.unhexlify(v[28:30]), byteorder=sys.byteorder)

        if d.addr.lower() in self.devices:
          name = self.devices[d.addr.lower()]
        else:
          name = d.addr.replace(":", "").upper()

        if self.homeassistant_discovery:
          state_topic = "{}/sensor/{}/state".format(self.homeassistant_discovery_prefix, name)
          state_payload = {
            "temperature": temp,
            "humidity": humidity,
            "voltage": voltage,
            "battery": battery
          }
          messages += [MqttMessage(topic=state_topic, payload=json.dumps(state_payload))]

          attr_topic = "{}/sensor/{}/attr".format(self.homeassistant_discovery_prefix, name)
          attr_payload = {
            "RSSI": "{}dB".format(d.rssi),
            "MAC Address": d.addr.upper(),
          }
          messages += [MqttMessage(topic=attr_topic, payload=json.dumps(attr_payload))]

          config_template = {
            "state_topic": state_topic,
            "device": {
                "connections": [["mac", d.addr]],
                "identifiers": d.addr,
                "manufacturer": "Xiaomi",
                "model": "LYWSD03MMC",
                "name": name,
                "via_device": "bt-mqtt-gateway",
            },
            "expire_after": 120,
            "force_update": True,
            "json_attributes_topic": attr_topic,
          }

          temp_config_topic = "{}/sensor/{}T/config".format(self.homeassistant_discovery_prefix, name)
          temp_config_payload = copy.deepcopy(config_template)
          temp_config_payload["device_class"] = "temperature"
          temp_config_payload["name"] = "{} Temperature".format(name)
          temp_config_payload["unit_of_measurement"] = "°C"
          temp_config_payload["icon"] = "hass:thermometer"
          temp_config_payload["unique_id"] = "{}_temperature".format(name.lower().replace(" ", "_"))
          temp_config_payload["value_template"] = "{{ value_json.temperature }}"
          messages += [MqttMessage(topic=temp_config_topic, payload=json.dumps(temp_config_payload))]

          humidity_config_topic = "{}/sensor/{}H/config".format(self.homeassistant_discovery_prefix, name)
          humidity_config_payload = copy.deepcopy(config_template)
          humidity_config_payload["device_class"] = "humidity"
          humidity_config_payload["name"] = "{} Humidity".format(name)
          humidity_config_payload["unit_of_measurement"] = "%"
          humidity_config_payload["icon"] = "hass:water-percent"
          humidity_config_payload["unique_id"] = "{}_humidity".format(name.lower().replace(" ", "_"))
          humidity_config_payload["value_template"] = "{{ value_json.humidity }}"
          messages += [MqttMessage(topic=humidity_config_topic, payload=json.dumps(humidity_config_payload))]

          voltage_config_topic = "{}/sensor/{}V/config".format(self.homeassistant_discovery_prefix, name)
          voltage_config_payload = copy.deepcopy(config_template)
          voltage_config_payload["device_class"] = "voltage"
          voltage_config_payload["name"] = "{} Voltage".format(name)
          voltage_config_payload["unit_of_measurement"] = "V"
          voltage_config_payload["icon"] = "hass:sine-wave"
          voltage_config_payload["unique_id"] = "{}_voltage".format(name.lower().replace(" ", "_"))
          voltage_config_payload["value_template"] = "{{ value_json.voltage }}"
          messages += [MqttMessage(topic=voltage_config_topic, payload=json.dumps(voltage_config_payload))]

          battery_config_topic = "{}/sensor/{}B/config".format(self.homeassistant_discovery_prefix, name)
          battery_config_payload = copy.deepcopy(config_template)
          battery_config_payload["device_class"] = "battery"
          battery_config_payload["name"] = "{} Battery".format(name)
          battery_config_payload["unit_of_measurement"] = "%"
          battery_config_payload["icon"] = "hass:battery"
          battery_config_payload["unique_id"] = "{}_battery".format(name.lower().replace(" ", "_"))
          battery_config_payload["value_template"] = "{{ value_json.battery }}"
          messages += [MqttMessage(topic=battery_config_topic, payload=json.dumps(battery_config_payload))]
        else:
          temp_topic     = self.format_topic("{}/temp".format(name))
          humidity_topic = self.format_topic("{}/humidity".format(name))
          voltage_topic  = self.format_topic("{}/voltage".format(name))
          battery_topic  = self.format_topic("{}/battery".format(name))
          rssi_topic     = self.format_topic("{}/rssi".format(name))

          messages += [
            MqttMessage(topic=temp_topic,     payload=str(temp)),
            MqttMessage(topic=humidity_topic, payload=str(humidity)),
            MqttMessage(topic=voltage_topic,  payload=str(voltage)),
            MqttMessage(topic=battery_topic,  payload=str(battery)),
            MqttMessage(topic=rssi_topic,     payload=str(d.rssi)),
          ]


    return messages
