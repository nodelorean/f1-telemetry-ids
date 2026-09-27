import fastf1
import os

# Configuration du cache (évite de retélécharger la data à chaque exécution)
if not os.path.exists('cache'):
    os.makedirs('cache')
    
fastf1.Cache.enable_cache('cache')

print("Chargement de la session de qualification...")
# test récupération des données de la session de qualification du Grand Prix du Mexique 2024
session = fastf1.get_session(2024, 'Mexico', 'Q')
session.load()

#Extraction du meilleur tour de Pierre Gasly (GAS)
gasly_lap = session.laps.pick_driver('GAS').pick_fastest()
telemetry = gasly_lap.get_telemetry()

print(f"\n--- Meilleur tour de Pierre Gasly (Temps: {gasly_lap['LapTime']}) ---")
# 4. Affichage des 10 premières lignes (avec les données vitesse, accélération, frein, régime moteur, DRS)
print(telemetry[['Date', 'Speed', 'Throttle', 'Brake', 'RPM', 'DRS']].head(10))