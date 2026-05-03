
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def add_enum_value():
    async with engine.connect() as conn:
        print("Checking and adding 'ticket_updated' to notification_type enum...")
        try:
            # PostgreSQL requires ALTER TYPE ADD VALUE to run outside of a transaction in some versions.
            # Using execute() on the connection object.
            await conn.execute(text("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'ticket_updated'"))
            await conn.commit()
            print("Successfully added 'ticket_updated' to notification_type.")
        except Exception as e:
            print(f"Error (maybe it already exists?): {e}")

if __name__ == "__main__":
    asyncio.run(add_enum_value())
