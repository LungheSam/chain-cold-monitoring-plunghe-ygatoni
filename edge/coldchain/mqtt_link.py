"""MQTT connection of the node (paho-mqtt 2.x).

- TLS + username/password (docs/decisions.md D11).
- Last Will: coldchain/{unit}/status = "offline" (retained). On connect we publish "online" (retained).
- Subscribes to coldchain/{unit}/cmd. Commands are put in a queue for the main loop.
- Phase 1: while offline, events are kept in memory and sent on reconnect; telemetry is dropped.
  Phase 2 replaces this with a SQLite queue that survives a reboot.
"""
import json
import logging
import queue
import threading

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

MAX_PENDING = 1000


class MqttLink:
    def __init__(self, unit_id, host, port, username="", password="", use_tls=True, ca_file=""):
        self.base = "coldchain/%s" % unit_id
        self.connected = False
        self.commands = queue.Queue()
        self.pending = []                 # (topic, payload) waiting for a connection
        self.lock = threading.Lock()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=unit_id + "-edge")
        if username:
            self.client.username_pw_set(username, password)
        if use_tls:
            # ca_file empty: use the system CA list (HiveMQ Cloud has a public certificate)
            self.client.tls_set(ca_certs=ca_file or None)
        self.client.will_set(self.base + "/status", "offline", qos=1, retain=True)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        log.info("MQTT connecting to %s:%s (tls=%s)", host, port, use_tls)
        self.client.connect_async(host, port, keepalive=60)
        self.client.loop_start()          # background thread, reconnects by itself

    # ---------------------------------------------------------------- paho callbacks

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            log.error("MQTT connection refused: %s", reason_code)
            return
        self.connected = True
        log.info("MQTT connected")
        client.publish(self.base + "/status", "online", qos=1, retain=True)
        client.subscribe(self.base + "/cmd", qos=1)
        with self.lock:
            waiting, self.pending = self.pending, []
        if waiting:
            log.info("MQTT sending %d messages kept while offline", len(waiting))
        for topic, payload in waiting:
            client.publish(topic, payload, qos=1)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if self.connected:
            log.warning("MQTT disconnected: %s", reason_code)
        self.connected = False

    def _on_message(self, client, userdata, msg):
        try:
            self.commands.put(json.loads(msg.payload))
        except ValueError:
            log.warning("Ignoring command that is not JSON on %s", msg.topic)

    # ---------------------------------------------------------------- used by the node

    def publish(self, subtopic, payload, keep_if_offline=False):
        """Publish JSON on coldchain/{unit}/{subtopic}. Returns True if handed to the broker."""
        topic = "%s/%s" % (self.base, subtopic)
        data = json.dumps(payload)
        if self.connected:
            info = self.client.publish(topic, data, qos=1)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
        if keep_if_offline:
            with self.lock:
                self.pending.append((topic, data))
                if len(self.pending) > MAX_PENDING:
                    self.pending.pop(0)
                    log.error("Offline buffer full: oldest event dropped")
        return False

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
