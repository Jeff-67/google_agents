"""Deep tAIpei agents demonstration"""

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import agent_tool

from deep_tAIpei import prompt
from deep_tAIpei.sub_agents.weather_agent.agent import weather_agent
from deep_tAIpei.sub_agents.place_recommendation_agent.agent import place_recommendation_agent
from deep_tAIpei.tools.search import google_search_agent

from deep_tAIpei.shared_libraries.constants import FAST_GEMINI_MODEL

# Load environment variables
load_dotenv()

root_agent = Agent(
    model=FAST_GEMINI_MODEL,
    name="root_agent",
    description="A Taipei food and bar discovery assistant using the services of multiple sub-agents",
    instruction=prompt.ROOT_AGENT_INSTR,
    tools=[agent_tool.AgentTool(agent=google_search_agent)],
    sub_agents=[
        weather_agent,
        place_recommendation_agent,
    ],
)