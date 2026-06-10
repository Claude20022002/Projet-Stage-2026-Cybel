import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[OK] Connecte au broker MQTT du robot !")
        client.subscribe('#')  # Ecouter tous les topics
        print("[OK] Abonne a tous les topics...\n")
    else:
        print(f"[ERREUR] Connexion refusee, code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
    except:
        payload = msg.payload.hex()
    print(f"TOPIC : {msg.topic}")
    print(f"DATA  : {payload}")
    print("-" * 50)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print("Connexion a 10.42.0.1:1883 ...")
client.connect("10.42.0.1", 1883, 60)
client.loop_forever()