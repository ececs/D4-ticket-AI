
import asyncio
import logging
import uuid
from sqlalchemy import select
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.user import User

# Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
engine = create_async_engine(db_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

VIRTUAL_USERS = [
    ("Sara Martínez (Lead Developer)", "sara.dev@orbidi.test", "https://i.pravatar.cc/150?u=sara"),
    ("Carlos Ruiz (Senior Support)", "carlos.support@orbidi.test", "https://i.pravatar.cc/150?u=carlos"),
    ("Elena Gómez (UI/UX Designer)", "elena.ux@orbidi.test", "https://i.pravatar.cc/150?u=elena"),
    ("David León (DevOps Engineer)", "david.ops@orbidi.test", "https://i.pravatar.cc/150?u=david"),
    ("Lucía Sanz (QA Automation)", "lucia.qa@orbidi.test", "https://i.pravatar.cc/150?u=lucia"),
    ("Roberto Cano (Product Manager)", "roberto.pm@orbidi.test", "https://i.pravatar.cc/150?u=roberto"),
]

async def seed_users():
    async with AsyncSessionLocal() as db:
        try:
            logger.info("Iniciando carga de usuarios virtuales...")
            
            for name, email, avatar in VIRTUAL_USERS:
                # Check if exists
                res = await db.execute(select(User).where(User.email == email))
                existing = res.scalar_one_or_none()
                
                if existing:
                    logger.info(f"Usuario {email} ya existe. Saltando.")
                    continue
                
                user = User(
                    id=uuid.uuid4(),
                    name=name,
                    email=email,
                    avatar_url=avatar
                )
                db.add(user)
                logger.info(f"Creado: {name}")

            await db.commit()
            logger.info("✅ ÉXITO: Usuarios virtuales creados correctamente.")
            
        except Exception as e:
            logger.error(f"Error en seed de usuarios: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(seed_users())
