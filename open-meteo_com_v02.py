import openmeteo_requests

import pandas as pd
import requests_cache
from retry_requests import retry
import pprint


def afficher_contenu_objet(obj):
	"""
    Affiche les attributs, leurs types et valeurs ainsi que les méthodes d'un objet.

    :param obj: L'objet à inspecter
    """
	# Afficher les attributs et leurs types
	print("\n--- Attributs de l'objet ---")
	attributes = [attr for attr in dir(obj) if not attr.startswith('__')]  # Filtrer pour éviter les méthodes spéciales
	for attribute in attributes:
		try:
			value = getattr(obj, attribute)
			print(f"Attribut: {attribute} -> Type: {type(value)} -> Valeur: {value}")
		except Exception as e:
			print(f"Erreur d'accès à l'attribut {attribute}: {e}")

	# Afficher les méthodes
	print("\n--- Méthodes de l'objet ---")
	methods = [method for method in dir(obj) if
			   callable(getattr(obj, method)) and not method.startswith('__')]  # Filtrer pour obtenir les méthodes
	pprint.pprint(methods)


# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://marine-api.open-meteo.com/v1/marine"
params = {
	"latitude": 50.625008,
	"longitude": 1.5416718,
	"hourly": "sea_level_height_msl",
	"current": "sea_surface_temperature",
	"timezone": "Europe/Berlin",
	"elevation": 0,
}
responses = openmeteo.weather_api(url, params = params)

# Process first location. Add a for-loop for multiple locations or weather models
response = responses[0]
afficher_contenu_objet(response.Hourly().Variables(0).ValuesAsNumpy())
print(f"Coordinates: {response.Latitude()}°N {response.Longitude()}°E")
print(f"Elevation: {response.Elevation()} m asl")
print(f"Timezone: {response.Timezone()}{response.TimezoneAbbreviation()}")
print(f"Timezone difference to GMT+0: {response.UtcOffsetSeconds()}s")

# Process current data. The order of variables needs to be the same as requested.
current = response.Current()
current_sea_surface_temperature = current.Variables(0).Value()

print(f"\nCurrent time: {current.Time()}")
print(f"Current sea_surface_temperature: {current_sea_surface_temperature}")

# Process hourly data. The order of variables needs to be the same as requested.
hourly = response.Hourly()
hourly_sea_level_height_msl = hourly.Variables(0).ValuesAsNumpy()

hourly_data = {"date": pd.date_range(
	start = pd.to_datetime(hourly.Time() + response.UtcOffsetSeconds(), unit = "s", utc = True),
	end =  pd.to_datetime(hourly.TimeEnd() + response.UtcOffsetSeconds(), unit = "s", utc = True),
	freq = pd.Timedelta(seconds = hourly.Interval()),
	inclusive = "left"
)}

hourly_data["sea_level_height_msl"] = hourly_sea_level_height_msl

hourly_dataframe = pd.DataFrame(data = hourly_data)
print("\nHourly data\n", hourly_dataframe)
