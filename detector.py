import socket

#same config que emetter.py
UDP_IP = "127.0.0.1"
UDP_PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f" [MURET DES STANDS / IDS] Système de détection à l'écoute sur {UDP_IP}:{UDP_PORT}...")
print("En attente des données de la monoplace...\n")

try:
    while True:
        # Réception du paquet UDP
        data, addr = sock.recvfrom(1024)
        packet_str = data.decode('utf-8')
        
        # Découpage du paquet pour analyser les valeurs (Format: "SPEED:,THROTTLE:,ect")
        values = {}
        for item in packet_str.split(','):
            key, val = item.split(':')
            values[key] = float(val)
            
        speed = values.get('SPEED', 0)
        throttle = values.get('THROTTLE', 0)
        brake = values.get('BRAKE', 0)
        
        #Règles des dectection d'anommalies
        # 1 : Une F1 ne dépasse pas 360 km/h en ligne droite même avec le DRS ( ou même aspirations si l'on prend les voiture hybride de 2021 a aujo_urd'hui)
        if speed > 360.0:
            print(f" [ALERTE CYBER/PHYSIQUE] Vitesse anormale détectée ! ({speed} km/h) -> Risque d'injection de données !")
            
        # 2 : Accélérateur à 100% ET Frein activé en même temps (Incohérence mécanique/logicielle)
        elif throttle == 100.0 and brake == 1.0:
            print(f"[ALERTE SÉCURITÉ] Anomalie critique : Gaz et Frein activés simultanément !")
            
        else:
            print(f"[OK] Paquet reçu | Vitesse: {speed} km/h | Throttle: {throttle}% | Frein: {brake}")

except KeyboardInterrupt:
    print("\nArrêt du système de détection.")
    sock.close()