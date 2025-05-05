from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp

# Get the agent engine
agent_engine = agent_engines.get('projects/758137355851/locations/us-central1/reasoningEngines/8893562528987086848')

# Create session using the app wrapper
remote_session = agent_engine.create_session(user_id="u_456")

# Query using the app wrapper
for event in agent_engine.stream_query(
    user_id="u_456",
    session_id=remote_session["id"],  # Access the id attribute of the Session object
    message="recommend me a place to eat in taipei",
):
    print(event)




