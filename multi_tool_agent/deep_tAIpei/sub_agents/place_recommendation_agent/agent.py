from google.adk.agents import Agent

from deep_tAIpei.tools.place import find_places_nearby, get_place_details, show_place_details, get_current_place
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL
from deep_tAIpei.sub_agents.place_recommendation_agent.prompt import PLACE_RECOMMENDATION_AGENT_INSTRUCTION

place_recommendation_agent = Agent(
    name="place_recommendation_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to handle place recommendations and detailed information flow.",
    instruction=PLACE_RECOMMENDATION_AGENT_INSTRUCTION,
    tools=[find_places_nearby, get_place_details, show_place_details, get_current_place],
) 