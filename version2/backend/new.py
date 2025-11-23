import requests
import json

response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": "Bearer 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",
    "Content-Type": "application/json",
  },
  data=json.dumps({
    "model": "qwen/qwen3-coder:free",
    "messages": [
        {
          "role": "user",
          "content": "What is the meaning of life?"
        }
      ]
  })
)

print(response.json())