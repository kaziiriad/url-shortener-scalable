
from common.db.sql.connection import Base
from sqlalchemy import Column, String, Boolean, Integer
import logging

logger = logging.getLogger(__name__)

class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    is_used = Column(Boolean, default=False)

    def __repr__(self):
        return f"<URL(id={self.id}, key={self.key}, is_used={self.is_used})>"

