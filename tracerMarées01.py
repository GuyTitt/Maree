import requests
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta

# 1. Convertir les coordonnées géodésiques en décimal
latitude = 50.6344
longitude = 1.5789

# 2. Définir l'URL de l'API pour récupérer les données de hauteur de marée
url = f"https://marine-api.open-meteo.com/v1/marine?latitude={latitude}&longitude={longitude}&hourly=sea_level&timezone=Europe%2FBerlin"

# 3. Récupérer les données JSON depuis l'API
response = requests.get(url)
data = response.json()

# 4. Extraire les données de la réponse
time = data['hourly']['time']
sea_level = data['hourly']['sea_level']

# 5. Convertir les heures en format datetime
time = [datetime.fromisoformat(t) for t in time]

# 6. Créer un DataFrame pour organiser les données
df = pd.DataFrame({'Time': time, 'Sea Level (m)': sea_level})

# 7. Filtrer pour ne garder que les données d'aujourd'hui et demain
today = datetime.now().date()
tomorrow = today + timedelta(days=1)
df_filtered = df[(df['Time'].dt.date >= today) & (df['Time'].dt.date <= tomorrow)]

# 8. Tracer la courbe de la hauteur de la marée
plt.figure(figsize=(10, 6))
plt.plot(df_filtered['Time'], df_filtered['Sea Level (m)'], marker='o', linestyle='-', color='b')
plt.title("Hauteur de la marée pour aujourd'hui et demain")
plt.xlabel("Heure")
plt.ylabel("Hauteur de la mer (m)")
plt.xticks(rotation=45)
plt.grid(True)
plt.tight_layout()

# 9. Afficher le graphique
plt.show()