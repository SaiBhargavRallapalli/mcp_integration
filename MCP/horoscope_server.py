from mcp.server.fastmcp import FastMCP
import requests
import os
from dotenv import load_dotenv
import logging
from datetime import datetime
from bs4 import BeautifulSoup


# Setup logging
logging.basicConfig(filename="horoscope_tool.log", level=logging.INFO)

# Load environment variables
load_dotenv()
ASTROTALK_API = os.getenv("ASTROTALK_API")

# Create MCP server instance
mcp = FastMCP(
    "HoroscopeServer",
    stateless_http=True,
    strict_jsonrpc=False,  # Relax JSON-RPC validation
    host="0.0.0.0",
    port=8001,
    path="/mcp"
)

@mcp.tool(description="Generate a daily or monthly horoscope for a given zodiac sign")
def get_horoscope(zodiac_sign: str, horoscope_type: str = "DAILY") -> dict:
    valid_signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
    ]
    valid_types = ["DAILY", "MONTHLY"]
    
    zodiac_sign = zodiac_sign.capitalize()
    horoscope_type = horoscope_type.upper()
    
    if zodiac_sign not in valid_signs:
        logging.error(f"Invalid zodiac sign: {zodiac_sign}")
        return {
            "isError": True,
            "content": [{
                "type": "text",
                "text": f"Invalid zodiac sign: {zodiac_sign}. Valid signs: {', '.join(valid_signs)}"
            }]
        }

    if horoscope_type not in valid_types:
        logging.error(f"Invalid horoscope type: {horoscope_type}")
        return {
            "isError": True,
            "content": [{
                "type": "text",
                "text": f"Invalid horoscope type: {horoscope_type}. Valid types: DAILY, MONTHLY"
            }]
        }

    try:
        url = f"{ASTROTALK_API}&type={horoscope_type}&zodiac={zodiac_sign}"
        # logging.info(f"Calling horoscope API: {url}")

        response = requests.get(url)
        response.raise_for_status()
        result = response.json()
        logging.info(f"API response: {result}")

        combined_html = result.get("data", {}).get("combinedResult", "")
        horoscope_text = BeautifulSoup(combined_html, "html.parser").get_text(separator="\n").strip()

        if not horoscope_text:
            logging.warning("No horoscope data available in API response.")
            horoscope_text = "No horoscope data available"

        formatted_result = (
            f"🔮 Horoscope for *{zodiac_sign}* ({horoscope_type}) on {datetime.now().strftime('%Y-%m-%d')}:\n\n"
            f"{horoscope_text}"
        )

        logging.info(f"Generated horoscope for {zodiac_sign}: {formatted_result}")
        return {
            "isError": False,
            "content": [{"type": "text", "text": formatted_result}]
        }

    except requests.RequestException as e:
        logging.error(f"API call failed: {str(e)}")
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Failed to fetch horoscope: {str(e)}"}]
        }

# Run server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
