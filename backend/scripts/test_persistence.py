import asyncio
import uuid
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.ai.checkpoint import get_checkpointer
from app.ai.agent import build_agent
from app.core.config import settings
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import create_async_engine

async def test_memory():
    print("Connecting to DB...")
    checkpointer = await get_checkpointer()
    if not checkpointer:
        print("❌ No checkpointer found!")
        return

    # Use a fixed test thread_id
    test_thread_id = "test-persistent-thread-001"
    config = {"configurable": {"thread_id": test_thread_id}}
    
    # Dummy user
    from app.models.user import User
    dummy_user = User(id=uuid.uuid4(), email="test@example.com", full_name="Tester")
    
    # Build agent
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        agent = build_agent(db, dummy_user)
        
        print("\n--- ROUND 1 ---")
        print("Sending: 'My secret code is 1234'")
        input1 = {"messages": [HumanMessage(content="My secret code is 1234")], "remaining_steps": 10}
        async for event in agent.astream_events(input1, version="v2", config=config):
            pass
        print("Done Round 1.")

        print("\n--- ROUND 2 ---")
        print("Sending: 'What is my secret code?'")
        input2 = {"messages": [HumanMessage(content="What is my secret code?")], "remaining_steps": 10}
        
        full_response = ""
        async for event in agent.astream_events(input2, version="v2", config=config):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    full_response += content
        
        print(f"Agent Response: {full_response}")
        if "1234" in full_response:
            print("\n✅ SUCCESS: Memory is working persistently in DB!")
        else:
            print("\n❌ FAILURE: Agent forgot the secret code.")

if __name__ == "__main__":
    asyncio.run(test_memory())
