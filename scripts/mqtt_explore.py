import paho.mqtt.client as mqtt
import time

BROKER = "10.42.0.1"
PORT   = 1883
ROBOT_ID = "TY1251D-03195"

# Topics de commande a tester (inspire des conventions CIOT/robots Android)
TOPICS_TO_TRY = [
    f"{ROBOT_ID}/cmd",
    f"{ROBOT_ID}/control",
    f"{ROBOT_ID}/move",
    f"{ROBOT_ID}/navigation",
    "robot/cmd",
    "robot/control",
    "chassis/cmd",
    "chassis/control",
    "cmd_vel",
    "control",
    "navigation",
    "move_base",
]

def on_connect(client, userdata, flags, rc):
    print(f"[OK] Connecte, code: {rc}")
    # S'abonner a tous les topics
    client.subscribe('#')
    print("[OK] Ecoute de tous les topics...\n")

    # Publier sur chaque topic potentiel de commande
    print("[TEST] Publication sur les topics de commande...\n")
    for topic in TOPICS_TO_TRY:
        # Commande stop (valeurs nulles = sans danger)
        payload = f"{ROBOT_ID},0.0,0.0,0.0,0.0"
        client.publish(topic, payload)
        print(f"  >> Publie sur [{topic}] : {payload}")
        time.sleep(0.3)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
    except:
        payload = msg.payload.hex()
    # Filtrer test_mul pour ne voir que les nouveaux topics
    if msg.topic != "test_mul":
        print(f"\n[NOUVEAU TOPIC DETECTE !]")
        print(f"  TOPIC   : {msg.topic}")
        print(f"  PAYLOAD : {payload}")
        print("-" * 50)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()