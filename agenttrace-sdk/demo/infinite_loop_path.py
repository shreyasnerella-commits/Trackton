"""
Demo: Infinite Loop Path
Demonstrates how the AnomalyEngine catches repeating agent tool calls
and trips the circuit breaker before reaching maximum iterations.

Run:
    python agenttrace-sdk/demo/infinite_loop_path.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agenttrace import trace_agent, CircuitBrokenError
from agenttrace.hashing import compute_signature
from backend.app.anomaly import engine

MAX_SIMULATED_ITERATIONS = 8  # safety cap so a broken demo can't run forever


@trace_agent(agent_id="fixer", tool_name="retry_call")
def fixer_agent(prompt: str, iteration: int) -> str:
    time.sleep(0.02)

    if iteration >= MAX_SIMULATED_ITERATIONS:
        return f"Gave up after {iteration} iterations: {prompt}"

    # Check circuit breaker using AnomalyEngine
    if engine.check_for_infinite_loop("retry_call", {"agent_id": "fixer"}):
        raise CircuitBrokenError(f"Infinite loop detected by AnomalyEngine at iteration {iteration}!")

    # Simulate the agent "mutating" its own prompt on each retry --
    # this is the exact pattern that breaks naive exact-match hashing.
    mutated_prompt = f"{prompt} Try again, error: timeout_{iteration}"

    print(f"  [iter {iteration}] calling fixer_agent again with mutated prompt "
          f"(same signature: {compute_signature('fixer', 'retry_call')[:8]}...)")

    return fixer_agent(mutated_prompt, iteration + 1)


if __name__ == "__main__":
    print("Running infinite loop demo...")
    print(f"Signature for this loop: {compute_signature('fixer', 'retry_call')}")
    print("(Every recursive call below shares this exact signature, despite")
    print(" the prompt text mutating each time.)\n")

    try:
        result = fixer_agent("Initial task: fetch data", 0)
        print(f"\nCompleted without circuit breaker tripping: {result}")
        print("NOTE: Circuit breaker failed to catch the loop.")
    except CircuitBrokenError as e:
        print(f"\nCircuit breaker tripped as expected: {e}")

    print("\nCheck agenttrace_spans.jsonl -- every span should show the SAME")
    print("input_hash despite different input_preview text, proving the")
    print("hash-based (not string-match) approach catches this loop.")