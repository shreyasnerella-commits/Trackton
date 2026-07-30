"""
Demo: INFINITE LOOP PATH
--------------------------
Simulates a recursive delegation loop where an agent keeps calling
itself with a SLIGHTLY MUTATED prompt each time (appending
"Try again, error: ..."), which is exactly the pattern that would
break naive exact-string-match loop detection.

Because our hash (see agenttrace/hashing.py) is based on
(agent_id + tool_name) and NOT the raw input, every one of these
calls produces the SAME input_hash -- which is what lets Member 2's
rolling-window cycle detector catch this as a loop even though the
literal prompt text is different every time.

This script also demonstrates the circuit breaker control flow: once
check_circuit_breaker() (currently a stub, see tracer.py) starts
returning True for this signature, the wrapper raises
CircuitBrokenError and execution halts.

Run:
    python demo/infinite_loop_path.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agenttrace import trace_agent, CircuitBrokenError
from agenttrace.hashing import compute_signature

MAX_SIMULATED_ITERATIONS = 8  # safety cap so a broken demo can't run forever


@trace_agent(agent_id="fixer", tool_name="retry_call")
def fixer_agent(prompt: str, iteration: int) -> str:
    time.sleep(0.02)

    if iteration >= MAX_SIMULATED_ITERATIONS:
        return f"Gave up after {iteration} iterations: {prompt}"

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
        print("NOTE: check_circuit_breaker() is currently a stub returning False.")
        print("Once Member 2's real detector is wired in, this same run should")
        print("raise CircuitBrokenError well before iteration 8.")
    except CircuitBrokenError as e:
        print(f"\nCircuit breaker tripped as expected: {e}")

    print("\nCheck agenttrace_spans.jsonl -- every span should show the SAME")
    print("input_hash despite different input_preview text, proving the")
    print("hash-based (not string-match) approach catches this loop.")
