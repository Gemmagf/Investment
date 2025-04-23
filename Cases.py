import requests
from bs4 import BeautifulSoup
import pandas as pd

# Exemple de URL pública de Flatfox
url = 'https://flatfox.ch/en/search/?type=rent&city=Zurich'

# Realitzar la petició HTTP per obtenir el contingut de la pàgina
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# Llistar totes les propietats que apareixen en la pàgina (aquest selector pot variar depenent de l'estructura de la pàgina)
properties = soup.find_all('div', class_='PropertyListing')

# Crear una llista per desar la informació
data = []

# Extraiem informació de cada propietat
for property in properties:
    try:
        # Obtenir el preu
        price = property.find('div', class_='Price').text.strip()

        # Obtenir la ubicació
        location = property.find('div', class_='Location').text.strip()

        # Obtenir la descripció
        description = property.find('div', class_='PropertyTitle').text.strip()

        # Obtenir la superfície (en alguns casos es pot afegir un selector específic per la superfície)
        size = property.find('div', class_='Size').text.strip()

        # Afegir les dades a la llista
        data.append({
            'Preu': price,
            'Ubicació': location,
            'Descripció': description,
            'Superfície': size
        })
    except AttributeError:
        continue

# Convertir les dades en un DataFrame
df = pd.DataFrame(data)

# Guardar el resultat en un fitxer CSV
df.to_csv('dades_pisos_flatfox.csv', index=False)

# Mostrar el resultat
print(df.head())
