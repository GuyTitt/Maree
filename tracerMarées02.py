import requests
import matplotlib.pyplot as plt
from datetime import datetime

# 1. Coordonnées géographiques
latitude = 50.625008
longitude = 1.5416718

# 2. URL de l'API Open-Meteo
url = f"https://marine-api.open-meteo.com/v1/marine?latitude={latitude}&longitude={longitude}&hourly=sea_level_height_msl&current=sea_surface_temperature&timezone=Europe%2FBerlin&elevation=0&format=json"

# 3. Récupérer les données JSON depuis l'API
response = requests.get(url)

# Vérifier si la réponse est réussie (status code 200)
if response.status_code == 200:
    data = response.json()

    # 4. Extraire les données de marée
    time = data['hourly']['time']  # Liste des heures
    sea_level_height_msl = data['hourly']['sea_level_height_msl']  # Liste des hauteurs de marée (en mètres)

    # 5. Filtrer les données pour aujourd'hui et demain
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now().day + 1) % 31  # Simple incrementation pour demain (attention aux limites de mois)
    
    filtered_time = []
    filtered_sea_level = []

    # 6. Filtrer les données horaires pour inclure uniquement aujourd'hui et demain
    for t, level in zip(time, sea_level_height_msl):
        if t.startswith(today) or t.startswith(str(tomorrow)):
            filtered_time.append(t)
            filtered_sea_level.append(level)
    
    # 7. Tracer la courbe
    plt.figure(figsize=(10, 6))
    plt.plot(filtered_time, filtered_sea_level, marker='o', color='b', label='Niveau de la mer')
    plt.xticks(rotation=45)
    plt.xlabel('Heure')
    plt.ylabel('Hauteur de la marée (m)')
    plt.title('Courbe de la marée pour aujourd\'hui et demain')
    plt.tight_layout()

    # 8. Afficher le graphique
    plt.legend()
    plt.show()

else:
    print(f"Erreur lors de l'appel à l'API, code de statut: {response.status_code}")