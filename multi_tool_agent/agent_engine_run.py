import os
from vertexai import agent_engines

def get_agent_engine():
    """Get the agent engine"""
    agent_source = os.getenv("AGENT_RESOURCE_NAME")
    return agent_engines.get(agent_source)

def create_agent_session(user_id: str):
    """Create an agent session"""
    agent_engine = get_agent_engine()
    return agent_engine.create_session(user_id=user_id)

def get_agent_session(user_id: str, session_id: str):
    """Get an agent session"""
    agent_engine = get_agent_engine()
    return agent_engine.get_session(user_id=user_id, session_id=session_id)


# Get the agent engine
agent_engine = get_agent_engine()

# Create session using the app wrapper
remote_session = create_agent_session("u_456")

# Query using the app wrapper
for event in agent_engine.stream_query(
    user_id="u_456",
    session_id=remote_session["id"],  # Access the id attribute of the Session object
    message="recommend me a place to eat in taipei",
):
    print(event)