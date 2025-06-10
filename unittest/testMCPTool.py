import requests
import json

url = "http://localhost:8001/mcp/"

payload = json.dumps({
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_horoscope",
    "arguments": {
      "zodiac_sign": "Gemini",
      "horoscope_type": "DAILY"
    }
  }
})
headers = {
  'Content-Type': 'application/json',
  'Accept': 'application/json, text/event-stream'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
