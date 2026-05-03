
import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd()))

from app.core.config import settings
from app.ai.agent import get_llm
from langchain_core.messages import HumanMessage

async def test_llm():
    print("--- AI DIAGNOSTIC ---")
    print(f"Provider: {settings.AI_PROVIDER}")
    print(f"Model: {settings.AI_MODEL}")
    print(f"Google Key: {'✅ Present' if settings.GOOGLE_API_KEY else '❌ MISSING'}")
    print(f"OpenAI Key: {'✅ Present' if settings.OPENAI_API_KEY else '❌ MISSING'}")
    
    try:
        print("\nInitializing LLM...")
        llm = get_llm()
        print("✅ LLM initialized (with fallback if applicable)")
        
        print("\nTesting simple response...")
        # Use a timeout to avoid hanging
        response = await llm.ainvoke([HumanMessage(content="Hola, ¿estás funcionando?")])
        print(f"✅ Response received: {response.content[:50]}...")
        
    except Exception as e:
        print(f"\n❌ ERROR during AI initialization/call:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_llm())
