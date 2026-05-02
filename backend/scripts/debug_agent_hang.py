"""
Debug Agent Logic Script.
Runs the agent locally to trace why it hangs on urgency questions.
"""
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.ai.agent import build_agent
from langchain_core.messages import HumanMessage
from sqlalchemy import select

async def debug_urgency():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).limit(1))
        actor = result.scalar_one()
        
        agent = build_agent(db, actor)
        print(f"🕵️ Debugging agent with user: {actor.email}")
        
        config = {"configurable": {"thread_id": "debug-urgency-thread"}}
        
        print("🤔 Asking: '¿cuál es el tiquet más urgente?'")
        try:
            async for event in agent.astream_events(
                {"messages": [HumanMessage(content="¿cuál es el tiquet más urgente?")]},
                config=config,
                version="v2"
            ):
                kind = event.get("event")
                name = event.get("name", "unknown")
                print(f"➡️ Event: {kind} | Name: {name}")
                
                if kind == "on_tool_start":
                    print(f"🛠️ CALLING TOOL: {name}")
                if kind == "on_tool_end":
                    print(f"✅ TOOL FINISHED: {name}")
                if kind == "on_chat_model_stream":
                    content = event.get("data", {}).get("chunk", {}).content
                    if content:
                        print(f"✍️ TOKEN: {content}", end="", flush=True)
            print("\n\n🏁 Agent finished correctly in local test.")
        except Exception as e:
            print(f"\n❌ CRASH DETECTED: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_urgency())
