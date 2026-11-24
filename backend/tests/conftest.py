import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.infra.config import get_settings
from app.infra.db import Base

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(get_settings().test_database_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def db(test_engine):
    # Los tests hacen commit, así que limpiamos filas entre casos para que
    # las aserciones de conteo y los `.one()` no vean datos de otros módulos.
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    testing_session = sessionmaker(bind=test_engine, expire_on_commit=False)
    with testing_session() as session:
        yield session
        session.rollback()
