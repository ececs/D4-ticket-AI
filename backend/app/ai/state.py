"""
Agent State Definition.

This module defines the schema for the AI agent's state using Pydantic-compatible 
TypedDicts. By using Annotated and add_messages, we enable LangGraph to 
automatically manage conversation history.
"""

from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    State schema for the AI agent.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # Required by create_react_agent to prevent infinite loops
    remaining_steps: int


class AgentConfig(BaseModel):
    """
    Configuration for the agent execution.
    """
    thread_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="ID of the user interacting with the agent")
