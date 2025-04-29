import googlemaps
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional
from google.adk.agents import Agent
from google.adk.tools import google_search
from google.adk.tools import agent_tool

# Load environment variables from .env file in the demo_agent directory
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

MODEL_GEMINI_2_0_FLASH = "gemini-2.0-flash-001"


def get_current_place() -> dict:
    """Finds the current place using the Google Maps Places API.

    Returns:
        dict: A dictionary containing the place information with a 'status' key ('success' or 'error') 
        and a 'report' key with the place details if successful, or an 'error_message' if an error occurred.
    """
    try:
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        places = gmaps.find_place(
            "current location",
            "textquery",
            fields=["name", "geometry", "place_id", "formatted_address"],
        )

        if places and places["candidates"]:
            place = places["candidates"][0]
            return {
                "status": "success",
                "report": f"Found place: {place.get('name')} at {place.get('formatted_address')}",
                "place_id": place.get('place_id')
            }
        else:
            return {
                "status": "error",
                "error_message": "No current place found."
            }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while finding the current place: {str(e)}"
        }

def get_current_time(city: Optional[str] = None) -> dict:
    """Returns the current time in a specified city or current location.

    Args:
        city (Optional[str], optional): The name of the city to get the time for if provided.

    Returns:
        dict: A dictionary containing the time information with a 'status' key ('success' or 'error') 
        and a 'report' key with the time details if successful, or an 'error_message' if an error occurred.
    """
    try:
        gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
        
        if not city:
            # Get current place first
            place_result = get_current_place()
            if place_result["status"] != "success":
                return {
                    "status": "error",
                    "error_message": "Could not determine current location."
                }
            
            # Get place details using the place_id
            place_details = gmaps.place(place_result["place_id"])
            if place_details['status'] != 'OK':
                return {
                    "status": "error",
                    "error_message": "Could not get place details."
                }
            
            # Extract coordinates from place details
            location = (place_details['result']['geometry']['location']['lat'],
                       place_details['result']['geometry']['location']['lng'])
        else:
            # Geocode the city name to get coordinates
            geocode_result = gmaps.geocode(city)
            if not geocode_result:
                return {
                    "status": "error",
                    "error_message": f"Could not find coordinates for city: {city}"
                }
            location = (geocode_result[0]['geometry']['location']['lat'],
                       geocode_result[0]['geometry']['location']['lng'])

        # Get timezone information
        timezone_result = gmaps.timezone(location)
        
        if timezone_result['status'] == 'OK':
            # Calculate current time using timezone offset
            from datetime import datetime, timedelta
            utc_now = datetime.utcnow()
            local_time = utc_now + timedelta(seconds=timezone_result['rawOffset'] + timezone_result['dstOffset'])
            
            return {
                "status": "success",
                "report": f"The current time is {local_time.strftime('%Y-%m-%d %H:%M:%S')} ({timezone_result['timeZoneName']})"
            }
        else:
            return {
                "status": "error",
                "error_message": f"Could not get timezone information: {timezone_result.get('errorMessage', 'Unknown error')}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An error occurred while getting the time: {str(e)}"
        }

google_search_agent = Agent(
    name="google_search_agent",
    model=MODEL_GEMINI_2_0_FLASH,
    description="Agent to answer questions using Google Search.",
    instruction="I can answer your questions by searching the internet. Just ask me anything!",
    tools=[google_search]
)

get_current_place_agent = Agent(
    name="get_current_place_agent",
    model=MODEL_GEMINI_2_0_FLASH,
    description="Agent to find the current place.",
    instruction="You are a helpful place assistant. "
                "When the user asks for the current place, "
                "use the 'get_current_place' tool to find the information by searching the web. "
                "If the tool returns an error, inform the user politely. "
                "If the tool is successful, present the place report clearly.",
    tools=[get_current_place],
)

weather_agent = Agent(
    name="weather_agent",
    model=MODEL_GEMINI_2_0_FLASH,
    description="Agent to find the weather information for a specific city.",
    instruction="You are a helpful weather assistant. "
                "1. Location and Time Services: "
                "   - Use 'get_current_time' tool to provide current time information "
                "   - If no city is specified, it will use the current location "
                "   - If a city is specified, it will get the time for that city "
                "2. Weather Information: "
                "   - Use 'google_search_agent' to find weather information for specific cities "
                "   - If no city is specified, first use 'get_current_place_agent' to find the current location "
                "   - Then use 'google_search_agent' to find weather for that location "
                "3. Delegation Rules: "
                "   - For current location queries, delegate to 'get_current_place_agent' "
                "   - For weather queries, use 'google_search_agent' directly or after getting current location ",
    tools=[agent_tool.AgentTool(agent=google_search_agent), get_current_time],
    sub_agents=[get_current_place_agent]
)

root_agent = Agent(
    name="root_agent",
    model=MODEL_GEMINI_2_0_FLASH,
    description="The main coordinator agent. Handles location, time, and weather requests, delegating to specialized sub-agents.",
    instruction="Analyze the user's query carefully. ",
    tools=[get_current_time, agent_tool.AgentTool(agent=google_search_agent)],
    sub_agents=[weather_agent, get_current_place_agent]
)





