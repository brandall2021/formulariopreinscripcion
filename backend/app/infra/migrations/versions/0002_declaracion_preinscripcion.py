"""Registrar la aceptación de la declaración de preinscripción."""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("solicitudes", sa.Column("declaracion_aceptada_en", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("solicitudes", "declaracion_aceptada_en")
