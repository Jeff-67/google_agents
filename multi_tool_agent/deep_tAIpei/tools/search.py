from google.adk.agents import Agent
from google.adk.tools.google_search_tool import google_search

google_search_agent = Agent(
    model="gemini-2.0-flash-001",
    name="google_search_agent",
    description="An agent providing Google-search capability",
    instruction=""",
    Answer the user's question directly using google_search tool; Provide a brief but concise response. 
    Rather than a detail response, provide the immediate actionable item for a tourist or traveler, in a single sentence.
    Do not ask the user to check or look up information for themselves, that's your role; do your best to be informative.
    """,
    tools=[google_search],
)

