"""A fake MQTT link with the same interface as coldchain.mqtt_link.MqttLink."""
import json


class FakeLink:
    def __init__(self, connected=True, auto_ack=True):
        self.connected = connected
        self.epoch = 1 if connected else 0
        self.auto_ack = auto_ack   # acknowledge every message at once, like a healthy broker
        self.sent = []             # (subtopic, payload dict)
        self.inbox = []            # commands waiting for the node
        self._acked = []
        self._next_mid = 1

    def send(self, subtopic, data):
        if not self.connected:
            return None
        mid = self._next_mid
        self._next_mid += 1
        self.sent.append((subtopic, json.loads(data)))
        if self.auto_ack:
            self._acked.append(mid)
        return mid

    def publish(self, subtopic, payload):
        return self.send(subtopic, json.dumps(payload)) is not None

    def take_acked(self):
        mids, self._acked = self._acked, []
        return mids

    def take_commands(self):
        cmds, self.inbox = self.inbox, []
        return cmds

    def go_offline(self):
        self.connected = False

    def go_online(self):
        self.connected = True
        self.epoch += 1

    def stop(self):
        self.connected = False

    def of(self, subtopic):
        return [p for s, p in self.sent if s == subtopic]
