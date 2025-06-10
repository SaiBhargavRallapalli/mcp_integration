import json
from langchain.tools import StructuredTool
import asyncio
from langchain_mcp_adapters.tools import from_mcp_config
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

config_path = "mcp_config.json" 

async def load_mcp_tools(config_path: str):
    # Try to use the langchain_mcp_adapters first
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return await from_mcp_config(config)
    except Exception as e:
        # Fallback to manual implementation if adapter fails
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        all_tools = []
        for server_name, server_config in config["mcpServers"].items():
            async with streamablehttp_client(server_config["url"]) as (read, write, *_):  
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    for tool in tools:
                        async def call_tool(params: dict, session=session, tool_name=tool["name"]):
                            return await session.call_tool(tool_name, params)
                        schema = {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "zodiac_sign": {"type": "string"},
                                "horoscope_type": {"type": "string", "enum": ["DAILY", "MONTHLY"]}
                            },
                            "required": ["zodiac_sign"] if tool["name"] == "get_horoscope" else ["query"]
                        }
                        all_tools.append(
                            StructuredTool.from_function(
                                func=call_tool,
                                name=tool["name"],
                                description=tool["description"],
                                args_schema=schema
                            )
                        )
        return all_tools