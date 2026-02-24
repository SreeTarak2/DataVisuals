import os
import time
import requests
from dotenv import load_dotenv

<<<<<<< HEAD
response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": "Bearer sk",
    "Content-Type": "application/json",
  },
  data=json.dumps({
    "model": "anthropic/claude-3-opus",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "What is in this image?"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
            }
          }
        ]
      }
    ]
  })
)

print(response.json())
=======
load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-r1-0528:free"
DEFAULT_MODEL = "openai/gpt-oss-120b:free"
DEFAULT_PROMPT = "What is the meaning of life?"


def main():
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = os.getenv("OPENROUTER_TEST_MODEL", DEFAULT_MODEL)
    prompt = os.getenv("OPENROUTER_TEST_PROMPT", DEFAULT_PROMPT)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 256,
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45)
    latency = time.perf_counter() - start

    print(f"HTTP {response.status_code} in {latency:.2f}s")
    print(response.json())
    if response.ok:
      
        body = response.json()
        # print(body)
    else:
        print("response.text")


if __name__ == "__main__":
    main()
>>>>>>> 7681d6d9 (prompts are updated and chat backend is corrected)
