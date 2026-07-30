from sdk import trace_agent
import time

# Decorate a mock agent tool function
@trace_agent(agent_name="ResearchAgent", tool_name="GoogleSearch")
def search_web(query: str):
    time.sleep(0.2)  # Simulate API latency
    return f"Search results for: '{query}' - Found 10 pages."

if __name__ == "__main__":
    print("--- Starting Trackton SDK Test Run ---")
    
    # Run the function
    result = search_web("What is AI agent observability?")
    
    print("\n--- Final Output ---")
    print(result)