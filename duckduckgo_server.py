import logging
from duckduckgo_search import DDGS
from mcp.server.fastmcp import FastMCP

# Setup logging
logging.basicConfig(filename="duckduckgo_tool.log", level=logging.INFO)

# Create MCP server instance
mcp = FastMCP(
    "DuckDuckGoServer",
    stateless_http=True,
    strict_jsonrpc=False,  # Relax JSON-RPC validation
    host="0.0.0.0",
    port=8002,
    path="/mcp"
)

@mcp.tool(description="Search the web using DuckDuckGo and return top 3 results.")
def search_duckduckgo(query: str) -> str:
    logging.info(f"Searching DuckDuckGo with query: {query}")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        result_text = "\n".join([f"{r['title']}: {r['body']}" for r in results])
        logging.info(f"Results: {result_text[:100]}...")
        return {
            "isError": False,
            "content": [{"type": "text", "text": result_text}]
        }
    except Exception as e:
        logging.error(f"Search failed: {str(e)}")
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Search failed: {str(e)}"}]
        }

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
