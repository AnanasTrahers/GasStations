import requests, json

query = """
[out:json];
node["amenity"="fuel"](50.20,30.24,50.59,30.82);
out;
"""
r = requests.post("https://overpass-api.de/api/interpreter", data=query)
stations = r.json()["elements"]
# Each element has .lat, .lon, .tags (name, operator, fuel types...)
print(stations)