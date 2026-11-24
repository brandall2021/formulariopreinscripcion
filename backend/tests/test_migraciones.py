import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import inspect, text
from app.infra.config import get_settings
from app.infra.db import Base

TABLAS = {
    "alumnos", "auditorias", "consentimientos", "convocatorias", "carreras",
    "documento_versiones", "documentos", "historial_estados", "notificaciones",
    "observaciones", "otp_codigos", "requisitos_documentales", "solicitudes",
    "tipos_documentos", "usuarios",
}


def test_migracion_crea_todas_las_tablas(test_engine):
    Base.metadata.drop_all(test_engine)
    with test_engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    alembic = Path(sys.executable).with_name("alembic")
    subprocess.run(
        [str(alembic), "upgrade", "head"],
        cwd=".", check=True,
        env={**os.environ, "DATABASE_URL": get_settings().test_database_url},
        capture_output=True,
    )
    tablas = set(inspect(test_engine).get_table_names())
    assert TABLAS <= tablas
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT 1 FROM alembic_version")).scalar() is not None
