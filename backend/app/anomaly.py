from supabase import Client

def check_for_infinite_loop(supabase_client: Client, trace_id: str, agent_id: str, tool_name: str, input_hash: str, threshold: int = 3) -> bool:
    response = supabase_client.table("spans") \
        .select("id") \
        .eq("trace_id", str(trace_id)) \
        .eq("agent_id", agent_id) \
        .eq("tool_name", tool_name) \
        .eq("input_hash", input_hash) \
        .execute()

    return len(response.data) >= threshold - 1