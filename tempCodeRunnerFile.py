from flask import Flask, render_template, request, jsonify
import folium
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests

app = Flask(__name__)

# Load crime data
data = pd.read_csv("backend/crime_data.csv")

# Function to get coordinates from location name
def get_coordinates(location):
    geolocator = Nominatim(user_agent="safenav")
    location = geolocator.geocode(location)
    if location:
        return location.latitude, location.longitude
    return None

# Function to calculate crime probability along a route
def calculate_crime_probability(route):
    total_crime = 0
    for point in route:
        lat, lon = point
        nearby_crimes = data[(data['Latitude'].between(lat-0.01, lat+0.01)) & 
                             (data['Longitude'].between(lon-0.01, lon+0.01))]
        total_crime += nearby_crimes['Total Crime'].sum()
    return total_crime

# Function to fetch routes from OSRM with alternatives
def get_routes(start, end):
    api_url = f"https://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson&alternatives=true"
    response = requests.get(api_url).json()
    
    routes = []
    if 'routes' in response:
        for route in response['routes']:
            coordinates = route['geometry']['coordinates']
            coordinates = [(lat, lon) for lon, lat in coordinates]
            crime_score = calculate_crime_probability(coordinates)
            routes.append((coordinates, crime_score))
    
    return routes

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start = request.form['start']
        end = request.form['end']
        start_coords = get_coordinates(start)
        end_coords = get_coordinates(end)
        
        if not start_coords or not end_coords:
            return render_template('index.html', error="Invalid locations")
        
        routes = get_routes(start_coords, end_coords)
        
        if not routes:
            return render_template('index.html', error="No routes found")
        
        # Sort routes based on crime score (lowest is safest)
        routes.sort(key=lambda x: x[1])
        
        safest_route = routes[0]
        alternative_route = routes[1] if len(routes) > 1 else None
        
        # Create map
        m = folium.Map(location=start_coords, zoom_start=12)
        
        # Add markers
        folium.Marker(start_coords, tooltip="Start", icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(end_coords, tooltip="End", icon=folium.Icon(color='red')).add_to(m)

        # Plot safest route
        folium.PolyLine(safest_route[0], color='blue', weight=5, opacity=0.7, tooltip="Safest Route").add_to(m)

        # Plot alternative route (if available)
        if alternative_route:
            folium.PolyLine(alternative_route[0], color='gray', weight=3, opacity=0.5, tooltip="Alternative Route").add_to(m)

        return render_template('index.html', map=m._repr_html_())

    return render_template('index.html', map=None)

if __name__ == '__main__':
    app.run(debug=True)
