FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY worker ./worker
# setuptools recientes rechazan el descubrimiento automático con varios paquetes planos.
RUN printf '[options]\npackages = find_namespace:\n' > setup.cfg
RUN pip install --no-cache-dir -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
