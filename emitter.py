import socket
import time
import fastf1
import os

# Configuration du réseau (on envoie en local sur la machine)
UDP_IP = "127.0.0.1"
UDP_PORT = 5005

print(f"L'émetteur réseau (la voiture Alpine) va diffuser sur {UDP_IP}:{UDP_PORT}...")
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Chargement rapide des données de Gasly (comme dans le script précédent)
if not os.path.exists('cache'):
    os.makedirs('cache')
fastf1.Cache.enable_cache('cache')

session = fastf1.get_session(2024, 'Mexico', 'Q')
session.load()
telemetry = session.laps.pick_driver('GAS').pick_fastest().get_telemetry()

print("Début de la transmission de la télémétrie en direct...")

# On parcourt chaque ligne de la télémétrie pour l'envoyer en temps réel
for index, row in telemetry.iterrows():
    # Format : "Vitesse|Throttle|Brake|RPM"
    data_packet = f"SPEED:{row['Speed']:.1f},THROTTLE:{row['Throttle']:.1f},BRAKE:{row['Brake']},RPM:{row['RPM']:.0f}"
    
    
    sock.sendto(data_packet.encode('utf-8'), (UDP_IP, UDP_PORT))
    
    print(f"[VOITURE -> STANDS] Paquet envoyé : {data_packet}")
    
    #simulation du vrai rythme de la télémétrie (environ 10 Hz)
    time.sleep(0.1)

print("Fin de la session.")