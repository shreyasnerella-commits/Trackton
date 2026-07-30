from sdk import trace_agent, TracktonCircuitBreakerException, _send_telemetry
import time

# A mock tool stuck in a repetitive loop
@trace_agent(agent_name="LoopingAgent", tool_name="StuckTool")
def stuck_function(step: int):
    time.sleep(0.1)
    return f"Processing step {step}"

if __name__ == "__main__":
    print("--- Running Trackton Circuit Breaker Demonstration ---")
    
    try:
        # Simulate an infinite loop running 10 times
        for i in range(1, 10):
            print(f"\n--- Iteration {i} ---")
            
            # Simulate the backend tripping the circuit breaker on iteration 3
            if i >= 3:
                _send_telemetry({"is_loop_detected": True})
            else:
                stuck_function(i)
                
    except TracktonCircuitBreakerException as e:
        print(f"\n🛑 SUCCESS! Trackton caught the loop and safely halted execution!")
        print(f"   Reason: {e}")