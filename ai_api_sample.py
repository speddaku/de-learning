# ============================================================
# AI API Sample — Google Gemini (FREE tier)
# ============================================================
# 1. Get a free API key at: https://aistudio.google.com
#    (Sign in with Google → Get API key — no credit card needed)
#
# 2. Install the SDK:
#    pip3 install google-genai
#
# 3. Set your key in the terminal:
#    export GEMINI_API_KEY="your-key-here"
#
# 4. Run:
#    python3 ai_api_sample.py
# ============================================================

import os
import time
from google import genai

# ── Setup ─────────────────────────────────────────────────────
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise EnvironmentError("Set GEMINI_API_KEY in your terminal before running.")

client = genai.Client(api_key=API_KEY)

# Print available models so we know which names to use
print("Fetching available models...")
available = [m.name for m in client.models.list()
             if "generateContent" in (m.supported_actions or [])]
print("Available models:")
for name in available:
    print(" ", name)

# Pick the first flash/pro model automatically
MODEL = next(
    (n for n in available if "flash" in n or "pro" in n),
    available[0] if available else None
)
if not MODEL:
    raise RuntimeError("No usable models found for this API key.")
print(f"\nUsing: {MODEL}\n")


# ── 1. Simple one-shot question ───────────────────────────────
def simple_question(question: str) -> str:
    """Ask a single question and get an answer."""
    response = client.models.generate_content(
        model=MODEL,
        contents=question,
    )
    return response.text


# ── 2. Question with a persona ────────────────────────────────
def ask_as_de_expert(question: str) -> str:
    """
    Prepend a persona so the model answers like
    a senior data engineer every time.
    """
    prompt = (
        "You are a senior data engineer. "
        "Give concise, practical answers with Python code examples "
        "when relevant. Prefer PySpark and pandas idioms.\n\n"
        f"Question: {question}"
    )
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


# ── 3. Multi-turn conversation ────────────────────────────────
def multi_turn_chat():
    """
    Gemini tracks conversation history inside a Chat object —
    no need to manually append messages.
    """
    print("\n=== Multi-turn chat (type 'quit' to stop) ===\n")

    chat = client.chats.create(model=MODEL)

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        response = chat.send_message(user_input)
        print(f"\nGemini: {response.text}\n")


# ── 4. Streaming response ─────────────────────────────────────
def streaming_example(prompt: str):
    """Prints each chunk as it arrives — great for long answers."""
    print("\n=== Streaming response ===\n")

    for chunk in client.models.generate_content_stream(
        model=MODEL, contents=prompt
    ):
        print(chunk.text, end="", flush=True)

    print("\n")


# ── 5. Data Engineering helper: explain a SQL query ───────────
def explain_query(query: str) -> str:
    """Paste a SQL query — get a plain-English explanation + tips."""
    prompt = f"""You are a data engineering expert.
Explain this SQL query step by step, then suggest improvements:

```sql
{query}
```

Format:
1. What it does (plain English)
2. Step-by-step breakdown
3. Performance / readability suggestions
"""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


# ── Main demo ─────────────────────────────────────────────────
if __name__ == "__main__":

    # Example 1 — Simple question
    print("=" * 60)
    print("Example 1 — Simple question")
    print("=" * 60)
    print(simple_question(
        "What is the difference between a data lake and a data warehouse?"
    ))

    time.sleep(5)  # stay within free-tier rate limit (15 req/min)

    # Example 2 — DE expert persona
    print("\n" + "=" * 60)
    print("Example 2 — DE expert persona")
    print("=" * 60)
    print(ask_as_de_expert("When should I use partitioning in PySpark?"))

    time.sleep(5)

    # Example 3 — Explain a SQL query
    print("\n" + "=" * 60)
    print("Example 3 — Explain a SQL query")
    print("=" * 60)
    sample_query = """
        SELECT
            customer_id,
            COUNT(order_id)    AS total_orders,
            SUM(amount)        AS total_spent,
            MAX(order_date)    AS last_order_date
        FROM orders
        WHERE order_date >= '2024-01-01'
        GROUP BY customer_id
        HAVING SUM(amount) > 1000
        ORDER BY total_spent DESC
        LIMIT 100
    """
    print(explain_query(sample_query))

    time.sleep(5)

    # Example 4 — Streaming
    print("\n" + "=" * 60)
    print("Example 4 — Streaming")
    print("=" * 60)
    streaming_example(
        "Explain the medallion architecture (Bronze, Silver, Gold) for a data lake "
        "in about 200 words, with a short Python/PySpark snippet for each layer."
    )

    # Example 5 — Interactive chat (uncomment to try)
    # multi_turn_chat()
