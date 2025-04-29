from google.adk.agents import Agent
from google.adk.tools import agent_tool

from deep_tAIpei.tools.place import get_current_place
from deep_tAIpei.tools.search import google_search_agent
from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL

weather_agent = Agent(
    name="weather_agent",
    model=FAST_GEMINI_MODEL,
    description="Agent to find the weather information for a specific city.",
    instruction="You are a helpful weather assistant. "
                "1. Weather Information: "
                "   - Use 'google_search_agent' to find weather information for specific cities "
                "   - If no city is specified, first use 'get_current_place' tool to find the current location and then use 'google_search_agent' to find weather for that location ",
    tools=[agent_tool.AgentTool(agent=google_search_agent), get_current_place],
)





