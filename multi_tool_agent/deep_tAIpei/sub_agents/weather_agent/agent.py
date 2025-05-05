import os
import requests
from google.adk.agents import Agent
from google.adk.tools import ToolContext

from deep_tAIpei.tools.place import get_current_place, get_specific_place
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL
from .prompt import WEATHER_AGENT_INSTRUCTION


def google_weather_api(latitude: float, longitude: float, hours: int = 24):
    """
    Get weather information for a specific location using Google Weather API
    
    Args:
        latitude (float): Latitude of the location
        longitude (float): Longitude of the location
        hours (int, optional): Number of hours to forecast. Defaults to 24.
        
    Returns:
        dict: Weather information for the specified location
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_WEATHER_API_KEY environment variable not set")
    
    url = f"https://weather.googleapis.com/v1/forecast/hours:lookup"
    params = {
        "key": api_key,
        "location.latitude": latitude,
        "location.longitude": longitude,
        "hours": hours
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error fetching weather data: {str(e)}")


def get_place_weather(tool_context: ToolContext, place_name: str, hours: int = 24):
    """
    Get weather information for a specific place using its name
    
    Args:
        tool_context (ToolContext): The tool context containing session state
        place_name (str): Name of the place to get weather for (e.g., "Taipei 101", "New York City")
        hours (int, optional): Number of hours to forecast. Defaults to 24.
        
    Returns:
        dict: Weather information for the specified place or error information
    """
    try:
        # Get place information using get_specific_place
        place_result = get_specific_place(tool_context, place_name)
        
        # Check if place information was retrieved successfully
        if place_result["status"] != "success" or not place_result.get("results"):
            return {
                "status": "error",
                "error_message": place_result.get("error_message", f"No place found matching '{place_name}'.")
            }
        
        # Get the first place from results
        place = place_result["results"][0]
        
        # According to the example, place information structure is:
        # {'id': 'ChIJC7UGYHJ2bjQR8Ary8UMUpg0', 'types': [...], 
        #  'formattedAddress': '...', 
        #  'location': {'latitude': 22.9933819, 'longitude': 120.1849162}, 
        #  'rating': 4.7, 'priceLevel': 'PRICE_LEVEL_MODERATE', 
        #  'displayName': {'text': '涵花庭', 'languageCode': 'zh-TW'}}
        
        # Extract location coordinates
        location = place.get("location", {})
        if not location or not location.get("latitude") or not location.get("longitude"):
            return {
                "status": "error",
                "error_message": f"Could not find coordinates for '{place_name}'."
            }
        
        # Call weather API with the coordinates
        weather_data = google_weather_api(
            latitude=location["latitude"],
            longitude=location["longitude"],
            hours=hours
        )
        
        return {
            "status": "success",
            "place_name": place.get("name", place_name),
            "coordinates": {
                "latitude": location["latitude"],
                "longitude": location["longitude"]
            },
            "weather_data": weather_data
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while getting weather for '{place_name}': {str(e)}"
        }


weather_agent = Agent(
    name="weather_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to find the weather information for a specific city.",
    instruction=WEATHER_AGENT_INSTRUCTION,
    tools=[get_current_place, google_weather_api, get_place_weather],
)





