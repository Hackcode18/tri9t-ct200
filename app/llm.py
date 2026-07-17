import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def generate_test_cases(text: str) -> dict:
    prompt = f"""You are a QA engineer for a medical device. Given the following technical specification, generate exactly 4 QA test cases.

Respond ONLY with a valid JSON object in this exact format, nothing else, no markdown, no backticks:
{{"test_cases": [{{"id": "TC001", "title": "short title", "steps": "step by step instructions", "expected_result": "what should happen"}}, {{"id": "TC002", "title": "short title", "steps": "step by step instructions", "expected_result": "what should happen"}}, {{"id": "TC003", "title": "short title", "steps": "step by step instructions", "expected_result": "what should happen"}}, {{"id": "TC004", "title": "short title", "steps": "step by step instructions", "expected_result": "what should happen"}}]}}

Specification:
{text[:2000]}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1000
    }

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        print("Groq status:", response.status_code)
        print("Groq response:", response.text[:500])

        if response.status_code != 200:
            return {"test_cases": [], "error": f"Groq API error: {response.status_code}", "status": "failed"}

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        content = content.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)

        if "test_cases" not in parsed:
            raise ValueError("Missing test_cases key")
        return parsed

    except json.JSONDecodeError as e:
        return {"test_cases": [], "error": f"JSON parse error: {str(e)}", "status": "failed"}
    except Exception as e:
        return {"test_cases": [], "error": str(e), "status": "failed"}
