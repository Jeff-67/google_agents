"""
Example usage of the weather agent
"""
from google.adk import run
from mult_tool_agent.deep_tAIpei.sub_agents.weather_agent.agent import weather_agent

# Example showing how to run the weather agent
def main():
    # Initialize the agent runner
    runner = run.AgentRunner(weather_agent)
    
    # Chat with the agent
    print("Weather Agent Example")
    print("---------------------")
    print("Ask about weather for your current location or any place!")
    
    # Start the conversation
    response = runner.start("What's the weather like right now?")
    print(f"Agent: {response.text}")
    
    # Continue the conversation with more weather queries
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            break
            
        response = runner.continue_conversation(user_input)
        print(f"Agent: {response.text}")
        
    print("Conversation ended.")

if __name__ == "__main__":
    main() 