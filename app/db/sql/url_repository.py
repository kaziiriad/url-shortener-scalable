import logging
import random
import string
from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.sql.models import URL
from sqlalchemy.sql import func, text

logger = logging.getLogger(__name__)

class URLKeyRepository:

    @staticmethod
    def _generate_key():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    
    @staticmethod
    async def get_unused_key(session: AsyncSession):
        """
        Atomically acquire an unused key using SELECT FOR UPDATE SKIP LOCKED.
        This prevents race conditions in distributed systems.
        """
        try:
            result = await session.execute(
                select(URL)
                .where(~URL.is_used)
                .limit(1)
                .with_for_update(skip_locked=True)  # Key fix for race conditions!
            )
            url = result.scalars().first()

            if url is not None:
                # Mark the key as used
                await session.execute(
                    update(URL)
                    .where(URL.id == url.id)
                    .values(is_used=True)
                )
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
    
    @staticmethod
    async def get_unused_key_raw(session: AsyncSession) -> dict | None:
        """
        Raw SQL version - use if ORM becomes a bottleneck.
        Benchmark before switching!
        """

        result = await session.execute(
            text("""
                UPDATE urls 
                SET is_used = true 
                WHERE id = (
                    SELECT id FROM urls 
                    WHERE is_used = false 
                    LIMIT 1 
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, key
            """)
        )
        row = result.first()
        
        if row:
            await session.commit()
            return {"id": row[0], "key": row[1]}
        return None


    @staticmethod
    async def pre_populate_keys(session: AsyncSession, count: int = 100000):
        """
        Pre-populate the database with unused keys.
        Uses efficient bulk insertion with raw SQL.
        
        Args:
            session: AsyncSession - The database session
            count: int - Number of keys to pre-populate (default: 100000)
        
        Returns:
            int: Number of keys successfully inserted
        """
        try:
            # Generate unique keys to avoid duplicates
            existing_keys = set()
            new_keys = []

            # Check existing keys to avoid duplicates
            result = await session.execute(select(URL.key))
            existing_keys = {row[0] for row in result.all()}

            while len(new_keys) < count:
                key = URLKeyRepository._generate_key()
                if key not in existing_keys and key not in new_keys:
                    new_keys.append(key)

            # Use bulk insert with raw SQL in batches
            batch_size = 1000
            inserted_count = 0

            for i in range(0, len(new_keys), batch_size):
                batch = new_keys[i:i + batch_size]
                inserted = await URLKeyRepository._bulk_insert_keys(session, batch)
                inserted_count += inserted

            logger.info(f"Pre-populated {inserted_count} keys")
            return inserted_count

        except Exception as e:
            await session.rollback()
            logger.error(f"Error pre-populating keys: {e}")
            raise

    @staticmethod
    async def _bulk_insert_keys(session: AsyncSession, keys: list[str]) -> int:
        """
        Bulk insert with raw SQL for better performance.
        This IS worth optimizing with raw SQL.
        """
        if not keys:
            return 0
        
        # Use raw SQL for bulk insert - much faster than ORM
        values = ", ".join([f"('{key}', false)" for key in keys])
        query = text(f"""
            INSERT INTO urls (key, is_used) 
            VALUES {values}
            ON CONFLICT (key) DO NOTHING
        """)
        
        result = await session.execute(query)
        await session.commit()
        
        return result.rowcount  # type: ignore[attr-defined]

    @staticmethod
    async def get_available_key_count(session: AsyncSession) -> int:
        """Get count of available unused keys."""
        try:
            result = await session.execute(
                select(func.count(URL.id)).where(~URL.is_used)
            )
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error getting available key count: {e}")
            return 0
