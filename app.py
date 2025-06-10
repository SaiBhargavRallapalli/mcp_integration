from langchain_groq import ChatGroq
from langchain_mcp_adapters import tools
print(dir(tools))
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from mcp_utils import load_mcp_tools
import asyncio
import logging
from dotenv import load_dotenv
import os


load_dotenv()
logging.basicConfig(filename="app.log", level=logging.INFO)

class GraphState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], operator.add]
    tools_called: List[str]

async def setup_llm_and_tools(use_groq=True):
    tools = await load_mcp_tools("mcp_config.json")
    if use_groq:
        llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))
    else:
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        )
    return llm.bind_tools(tools), tools

async def llm_node(state: GraphState, llm):
    logging.info(f"Processing messages: {[msg.content for msg in state['messages']]}")
    response = await llm.ainvoke(state["messages"])
    tools_called = state.get("tools_called", []) + [call["name"] for call in response.tool_calls]
    return {"messages": [response], "tools_called": tools_called}

async def tool_node(state: GraphState, tools):
    tool_calls = state["messages"][-1].tool_calls
    results = []
    for call in tool_calls:
        tool = next(t for t in tools if t.name == call["name"])
        logging.info(f"Invoking tool: {call['name']} with args: {call['args']}")
        result = await tool.ainvoke(call["args"])
        results.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
    return {"messages": results}

def should_continue(state: GraphState):
    last_message = state["messages"][-1]
    return "continue" if hasattr(last_message, "tool_calls") and last_message.tool_calls else "end"

async def main(prompt: str, use_groq=True):
    llm, tools = await setup_llm_and_tools(use_groq)
    workflow = StateGraph(GraphState)
    workflow.add_node("llm", lambda state: llm_node(state, llm))
    workflow.add_node("tools", lambda state: tool_node(state, tools))
    workflow.set_entry_point("llm")
    workflow.add_conditional_edges("llm", should_continue, {"continue": "tools", "end": END})
    workflow.add_edge("tools", "llm")
    app = workflow.compile()
    
    result = await app.ainvoke({"messages": [HumanMessage(content=prompt)], "tools_called": []})
    logging.info(f"Tools called: {result['tools_called']}")
    return result["messages"][-1].content

if __name__ == "__main__":
    prompts = [
        "What's the daily horoscope for Virgo?",
        "What's the monthly horoscope for Leo?",
        "Search for recent AI news"
    ]
    for prompt in prompts:
        result = asyncio.run(main(prompt, use_groq=True))
        print(f"Prompt: {prompt}\nResponse: {result}\n")