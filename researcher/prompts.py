PLAN_PROMPT = """You are a senior researcher. Given the question below, produce a numbered step-by-step research plan.
Each step must be concrete and verifiable. Do not execute, only do the planning.

Question: {question}

Respond in JSON format with a single key "plan_steps" containing a list of strings.
"""

EXTRACT_CLAIMS_PROMPT = """Extract every factual claim from the following text below as a list of JSON objects.
Each object must have the following keys: claim (string), source_id (integer), quote (exact text), page_url (if available).
Only include claims that could be verified or falsified.

Text: {text}
"""

CRITIC_PROMPT = """You are a ruthless fact-checker. Read the final report and the original sources.
List every claim that is not directly supported by at least one source.
If everything is supported, respond with "ALL_CLAIMS_SUPPORTED".
"""
