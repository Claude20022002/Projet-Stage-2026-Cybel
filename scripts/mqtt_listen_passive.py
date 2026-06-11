"""Écoute passive du broker MQTT du robot — aucune publication, juste observation."""
import time

import paho.mqtt.client as mqtt

BROKER = "10.42.0.1"
PORT = 1883
LISTEN_SECONDS = 15

seen_topics: dict[str, str] = {}


def on_connect(client, userdata, flags, rc):
    print(f"[OK] Connecte au broker MQTT, code: {rc}")
    client.subscribe("#")
    print(f"[OK] Abonne a tous les topics, ecoute pendant {LISTEN_SECONDS}s...\n")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
    except Exception:
        payload = msg.payload.hex()
    if msg.topic not in seen_topics:
        seen_topics[msg.topic] = payload
        print(f"[TOPIC] {msg.topic} = {payload[:200]}")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()
time.sleep(LISTEN_SECONDS)
client.loop_stop()
client.disconnect()

print(f"\n=== {len(seen_topics)} topic(s) observe(s) ===")
for topic in sorted(seen_topics):
    print(f"  {topic}")
