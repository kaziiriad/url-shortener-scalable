import random
import string
from app.db.sql.connection import Base
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

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
        # atomic operation
        try:         
            result = await session.execute(select(cls).where(cls.is_used == False).limit(1))
            url = result.scalars().first()
            if url is not None:
                # mark the key as used
                url.is_used = True
                session.add(url)
                await session.commit()
                return url
            else:
                return None
        except Exception as e:
            await session.rollback()
            raise e

    @classmethod
    async def pre_populate_keys(cls, session: AsyncSession, count: int = 100000):
        # atomic operation
        try:
            # Generate unique keys to avoid duplicates
            existing_keys = set()
            new_keys = []
            
            while len(new_keys) < count:
                key = cls.generate_key()
                if key not in existing_keys:
                    existing_keys.add(key)
                    new_keys.append(key)
            
            # Add in smaller batches to avoid overwhelming the connection
            batch_size = 100
            for i in range(0, len(new_keys), batch_size):
                batch = new_keys[i:i + batch_size]
                session.add_all([cls(key=key, is_used=False) for key in batch])
                await session.flush()  # Flush batch to DB
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise e