"""MQTT connection of the node (paho-mqtt 2.x).

- TLS + username/password (docs/decisions.md D11).
- Last Will: coldchain/{unit}/status = "offline" (retained). On connect we publish "online" (retained).
- Subscribes to coldchain/{unit}/cmd. Commands are put in a queue for the main loop.
- send() is used by the outbox: it returns the MQTT message id, and the id comes back through
  take_acked() once the broker has acknowledged it (PUBACK).
"""
import json
import logging
import queue

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MqttLink:
    def __init__(self, unit_id, host, port, username="", password="", use_tls=True, ca_file=""):
        self.base = "coldchain/%s" % unit_id
        self.connected = False
        self.epoch = 0                    # +1 on every new connection
        self.commands = queue.Queue()
        self.acked = queue.Queue()        # message ids acknowledged by the broker

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=unit_id + "-edge")
        if username:
            self.client.username_pw_set(username, password)
        if use_tls:
            # ca_file empty: use the system CA list (HiveMQ Cloud has a public certificate)
            self.client.tls_set(ca_certs=ca_file or None)
        self.client.will_set(self.base + "/status", "offline", qos=1, retain=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)   # retry at least every 10 s
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish

        log.info("MQTT connecting to %s:%s (tls=%s)", host, port, use_tls)
        self.client.connect_async(host, port, keepalive=60)
        self.client.loop_start()          # background thread, reconnects by itself

    # ---------------------------------------------------------------- paho callbacks (network thread)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connection refused: %s", reason_code)
            return
        client.publish(self.base + "/status", "online", qos=1, retain=True)
        client.subscribe(self.base + "/cmd", qos=1)
        self.epoch += 1
        self.connected = True
        log.info("MQTT connected")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if self.connected:
            log.warning("MQTT disconnected: %s", reason_code)
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            self.commands.put(json.loads(msg.payload))
        except ValueError:
            log.warning("Ignoring command that is not JSON on %s", msg.topic)

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        self.acked.put(mid)

    # ---------------------------------------------------------------- used by the node

    def send(self, subtopic, data):
        """Publish a JSON string with QoS 1. Returns the message id, or None if not connected."""
        if not self.connected:
            return None
        info = self.client.publish("%s/%s" % (self.base, subtopic), data, qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            return None
        return info.mid

    def publish(self, subtopic, payload):
        """Fire-and-forget publish (command results: useless if late, so not queued)."""
        return self.send(subtopic, json.dumps(payload)) is not None

    def take_acked(self):
        mids = []
        while not self.acked.empty():
            mids.append(self.acked.get_nowait())
        return mids

    def take_commands(self):
        cmds = []
        while not self.commands.empty():
            cmds.append(self.commands.get_nowait())
        return cmds

    def stop(self):
        """Clean shutdown: say offline ourselves (the broker does not send the Will on a clean disconnect)."""
        if self.connected:
            info = self.client.publish(self.base + "/status", "offline", qos=1, retain=True)
            info.wait_for_publish(timeout=2)
        self.connected = False  # so _on_disconnect does not log a warning
        self.client.disconnect()
        self.client.loop_stop()
