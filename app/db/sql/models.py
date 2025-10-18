import random
import string

from sqlalchemy.sql import func
from app.db.sql.connection import Base
from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    is_used = Column(Boolean, default=False)

    def __repr__(self):
        return f"<URL(id={self.id}, key={self.key}, is_used={self.is_used})>"
    @staticmethod
    def generate_key():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=7))

    @classmethod
    async def get_unused_key(cls, session):
        """
        Atomically acquire an unused key using SELECT FOR UPDATE SKIP LOCKED.
        This prevents race conditions in distributed systems.
        """
        try:         
            result = await session.execute(
                select(cls)
                .where(cls.is_used == False)
                .limit(1)
                .with_for_update(skip_locked=True)  # Key fix for race conditions!
            )
            url = result.scalars().first()

            if url is not None:
                # Mark the key as used
                url.is_used = True
                session.add(url)
                await session.commit()
                logger.info(f"Acquired key: {url.key}")
                return url
            else:
                logger.warning("No unused keys available")
                return None
                
        except Exception as e:
            await session.rollback()
            logger.error(f"Error acquiring unused key: {e}")
            raise


    @classmethod
    async def pre_populate_keys(cls, session: AsyncSession, count: int = 100000):
        """
        Pre-populate the database with unused keys.
        Uses batch insertion with conflict resolution.
        """
        try:
            # Generate unique keys to avoid duplicates
            existing_keys = set()
            new_keys = []
            
            # Check existing keys to avoid duplicates
            result = await session.execute(select(cls.key))
            existing_keys = {row[0] for row in result.all()}

            while len(new_keys) < count:
                key = cls.generate_key()
                if key not in existing_keys and key not in new_keys:
                    new_keys.append(key)
            
            # Batch insert with smaller batches to avoid overwhelming the connection
            batch_size = 1000  # Increased from 100 for efficiency
            inserted_count = 0

            # Add in smaller batches to avoid overwhelming the connection
            for i in range(0, len(new_keys), batch_size):
                batch = new_keys[i:i + batch_size]
                
                # Use bulk insert for better performance
                objects = [cls(key=key, is_used=False) for key in batch]
                session.add_all(objects)
                
                try:
                    await session.flush()
                    inserted_count += len(batch)
                except Exception as e:
                    # Handle unique constraint violations
                    logger.warning(f"Some keys in batch already exist: {e}")
                    await session.rollback()
                    # Insert one by one for this batch
                    for obj in objects:
                        try:
                            session.add(obj)
                            await session.flush()
                            inserted_count += 1
                        except Exception:
                            await session.rollback()
            
            await session.commit()
            logger.info(f"Pre-populated {inserted_count} keys")
            return inserted_count

        except Exception as e:
            await session.rollback()
            logger.error(f"Error pre-populating keys: {e}")
            raise e

    @classmethod
    async def get_available_key_count(cls, session: AsyncSession) -> int:
        """Get count of available unused keys."""
        try:
            result = await session.execute(
                select(func.count(cls.id)).where(cls.is_used == False)
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error getting available key count: {e}")
            return 0

