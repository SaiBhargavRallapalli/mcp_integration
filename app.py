from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from mcp_utils import load_mcp_tools
import asyncio
import logging
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(filename="app.log", level=logging.INFO)
load_dotenv()

app = FastAPI(title="Grok MCP Query API")

# Define request model
class QueryRequest(BaseModel):
    query: str

# Define LangGraph state
class GraphState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], operator.add]
    tools_called: List[str]

async def setup_llm_and_tools():
    tools = await load_mcp_tools("mcp_config.json")
    llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))
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

async def fallback_node(state: GraphState, llm):
    logging.info("Using fallback LLM node")
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response], "tools_called": state.get("tools_called", [])}

def should_continue(state: GraphState):
    last_message = state["messages"][-1]
    return "tools" if hasattr(last_message, "tool_calls") and last_message.tool_calls else "fallback"

# Initialize LangGraph workflow
async def create_workflow():
    llm, tools = await setup_llm_and_tools()
    workflow = StateGraph(GraphState)
    workflow.add_node("llm", lambda state: llm_node(state, llm))
    workflow.add_node("tools", lambda state: tool_node(state, tools))
    workflow.add_node("fallback", lambda state: fallback_node(state, llm))
    workflow.set_entry_point("llm")
    workflow.add_conditional_edges("llm", should_continue, {"tools": "tools", "fallback": "fallback"})
    workflow.add_edge("tools", "llm")
    workflow.add_edge("fallback", END)
    return workflow.compile()

@app.on_event("startup")
async def startup_event():
    app.state.workflow = await create_workflow()

@app.post("/query")
async def process_query(request: QueryRequest):
    try:
        result = await app.state.workflow.ainvoke(
            {"messages": [HumanMessage(content=request.query)], "tools_called": []}
        )
        logging.info(f"Tools called: {result['tools_called']}")
        return {"response": result["messages"][-1].content, "tools_called": result["tools_called"]}
    except Exception as e:
        logging.error(f"Query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))