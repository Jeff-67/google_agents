from google.adk.agents import Agent
from google.adk.tools import agent_tool

from deep_tAIpei.tools.place import find_places_nearby, get_place_details, show_place_details
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL

place_recommendation_agent = Agent(
    name="place_recommendation_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to handle place recommendations and detailed information flow.",
    instruction="You are a helpful place recommendation assistant. "
                "1. When the user asks for nearby places: "
                "   - Use 'find_places_nearby' to get a list of places "
                "   - If no location is specified, the tool will automatically use the user's current location "
                "   - The function will automatically store tuples of (place_id, place_name) "
                "     in the tool context for later reference "
                "   - Present the places in a clear, organized manner with basic info "
                "2. When the user provides feedback or selects a place: "
                "   - Use 'get_place_details' with the place name "
                "   - The function will automatically look up the place_id from stored tuples "
                "   - Present the detailed information in a user-friendly way "
                "3. When the user wants to see a place on a map or visualize its location: "
                "   - Use 'show_place_details' with the place name "
                "   - This will display an interactive map with the place location "
                "   - Let the user know they can view the place on the map "
                "4. Error Handling: "
                "   - If any tool returns an error, inform the user politely "
                "   - If no places are found, suggest alternative search parameters "
                "   - If a place name doesn't match stored names, ask for clarification "
                "   - If the user hasn't searched for places yet, guide them to do so first",
    tools=[find_places_nearby, get_place_details, show_place_details],
) 