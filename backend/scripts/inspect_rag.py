import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.knowledge_chunk import KnowledgeChunk

async def inspect_knowledge():
    print("\n🔍 --- INSPECCIONANDO BASE DE CONOCIMIENTO (RAG) ---\n")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeChunk)
            .order_by(KnowledgeChunk.created_at.desc())
            .limit(10)
        )
        chunks = result.scalars().all()
        
        if not chunks:
            print("⚠️ No hay información guardada en la base de conocimiento todavía.")
            return

        for chunk in chunks:
            print(f"📄 ID: {chunk.id}")
            print(f"🔗 Fuente (URL): {chunk.url}")
            print(f"📦 Metadatos: {chunk.chunk_metadata}")
            print(f"🕒 Creado: {chunk.created_at}")
            print(f"📝 Contenido (primeros 150 caracteres):")
            print(f"   {chunk.content[:150]}...")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(inspect_knowledge())
