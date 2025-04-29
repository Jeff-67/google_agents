import os
import requests
import json
from google.adk.agents import Agent
from google.adk.tools import agent_tool

from deep_tAIpei.tools.place import get_current_place
from deep_tAIpei.tools.search import google_search_agent
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL

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
    instruction="You are a helpful weather assistant. "
                "1. Weather Information: "
                "   - Use 'google_weather_api' to get precise weather data when latitude and longitude are known "
                "   - Use 'get_current_place' tool to find the current location including latitude and longitude "
                "   - You can extract latitude and longitude from get_current_place response and pass them to google_weather_api "
                "   - Use 'google_search_agent' to find weather information for specific cities "
                "   - If no city is specified, first use 'get_current_place' tool to find the current location and then use 'google_weather_api' or 'google_search_agent' to find weather for that location ",
    tools=[agent_tool.AgentTool(agent=google_search_agent), get_current_place, google_weather_api],
)





