from sqlalchemy import Table, Column, Integer, DateTime, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from auth.db import Base

links = Table(
    "links",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("original_url", String, nullable=False),
    Column("short_code", String, nullable=False, unique=True), # Не link, тк без домена
    Column("created_at", DateTime, nullable=False),
    Column("last_used_at", DateTime, nullable=True),
    Column("expires_at", DateTime, nullable=True),
    Column("owner_id", UUID, ForeignKey("user.id"), nullable=True), # Ссылки могут создавать неавторизованные/незарегистрированные пользователи
    Column("num_of_clicks", Integer, nullable=False, default=0)
)

metadata = Base.metadata

