"""links id autoincrement

Revision ID: 0001_links_id
Revises: 0b4e1b13c62a
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_links_id"
down_revision: Union[str, None] = "0b4e1b13c62a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем sequence и default для id, чтобы новые строки получали id автоматически
    op.execute("CREATE SEQUENCE IF NOT EXISTS links_id_seq")
    op.execute(
        "SELECT setval('links_id_seq', COALESCE((SELECT MAX(id) FROM links), 1))"
    )
    op.alter_column(
        "links",
        "id",
        server_default=sa.text("nextval('links_id_seq'::regclass)"),
    )


def downgrade() -> None:
    op.alter_column("links", "id", server_default=None)
    op.execute("DROP SEQUENCE IF EXISTS links_id_seq")
