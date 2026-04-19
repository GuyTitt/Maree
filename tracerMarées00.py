import requests

# 1. Convertir les coordonnées géodésiques en décimal
latitude = 50.6344
longitude = 1.5789

# 2. Définir l'URL de l'API pour récupérer les données de hauteur de marée (sans hourly)
url = f"https://marine-api.open-meteo.com/v1/marine?latitude={latitude}&longitude={longitude}&timezone=Europe%2FBerlin"

# 3. Récupérer les données JSON depuis l'API
response = requests.get(url)

# Vérifier si la réponse est réussie (status code 200)
if response.status_code == 200:
    data = response.json()
    print(data)  # Afficher toute la réponse JSON
else:
    print(f"Erreur lors de l'appel à l'API, code de statut: {response.status_code}")