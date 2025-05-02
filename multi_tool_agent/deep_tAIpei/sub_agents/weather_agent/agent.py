import os
import requests
import json
from google.adk.agents import Agent

from deep_tAIpei.tools.place import get_current_place
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

weather_agent = Agent(
    name="weather_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to find the weather information for a specific city.",
    instruction=WEATHER_AGENT_INSTRUCTION,
    tools=[get_current_place, google_weather_api],
)





