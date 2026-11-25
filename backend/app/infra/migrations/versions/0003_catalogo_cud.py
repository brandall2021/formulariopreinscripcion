"""Agregar el CUD al catálogo de documentos."""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO tipos_documentos (codigo, nombre, descripcion, formatos, tamano_maximo_bytes)
        VALUES ('cud', 'Certificado Único de Discapacidad (CUD)',
                'Adjuntá el certificado completo y legible.', 'pdf,jpg,png', 10485760)
        ON CONFLICT (codigo) DO NOTHING
    """)


def downgrade():
    # El tipo puede estar referenciado por legajos. Se conserva su registro.
    pass
