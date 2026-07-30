"""
Demo: HAPPY PATH
------------------
A clean 3-agent chain: Planner -> Researcher -> Summarizer.
Each is decorated with @trace_agent. Run this and inspect
agenttrace_spans.jsonl (or check your backend if it's running) to see:
  - one shared trace_id across all three calls
  - depth incrementing 0 -> 1 -> 2
  - parent_span_id correctly chaining each call to its caller

Run:
    python demo/happy_path.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agenttrace import trace_agent, get_current_trace_id


@trace_agent(agent_id="summarizer", tool_name="summarize_text")
def summarize(text: str) -> str:
    time.sleep(0.05)  # simulate API latency
    return f"Summary of: {text[:30]}..."


@trace_agent(agent_id="researcher", tool_name="web_search")
def research(query: str) -> str:
    time.sleep(0.08)
    raw_findings = f"Findings about '{query}': lorem ipsum research data here."
    # Researcher calls Summarizer -- nested span, depth+1, same trace_id
    return summarize(raw_findings)


@trace_agent(agent_id="planner", tool_name="plan_task")
def plan(user_goal: str) -> str:
    time.sleep(0.03)
    # Planner calls Researcher -- nested span, depth+1, same trace_id
    return research(user_goal)


if __name__ == "__main__":
    print("Running happy path demo...")
    final_result = plan("What are the latest trends in agent observability?")
    print(f"\nFinal result: {final_result}")
    print("(Trace ID is scoped to the call context and resets once the top-level")
    print(" call returns -- see 'trace_id' inside each emitted span instead.)")
    print("\nCheck 'agenttrace_spans.jsonl' in this directory (or wherever you ran this from)")
    print("for the emitted spans -- you should see 3 spans sharing one trace_id,")
    print("with depth 0, 1, 2 and parent_span_id chaining correctly.")
