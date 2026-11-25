from datetime import timedelta
from minio import Minio
from app.infra.config import Settings

class ObjectStore:
    def __init__(self, settings: Settings):
        self.bucket = settings.minio_bucket
        self.client = Minio(settings.minio_endpoint,
                            access_key=settings.minio_access_key,
                            secret_key=settings.minio_secret_key, secure=False)
        # Región explícita: sin ella el SDK consultaría la ubicación del bucket
        # contra localhost:9000 desde dentro del contenedor, donde no escucha MinIO.
        self.public_client = Minio(settings.minio_public_endpoint,
                                   access_key=settings.minio_access_key,
                                   secret_key=settings.minio_secret_key, secure=False,
                                   region="us-east-1")
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
    def put_bytes(self, key: str, data: bytes) -> None:
        from io import BytesIO
        self.client.put_object(self.bucket, key, BytesIO(data), len(data))
    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False
    def presigned_put(self, key: str, content_type: str, expires: int) -> str:
        return self.public_client.presigned_put_object(self.bucket, key,
                                                       expires=timedelta(seconds=expires))
    def presigned_get(self, key: str, expires: int) -> str:
        return self.public_client.presigned_get_object(self.bucket, key,
                                                       expires=timedelta(seconds=expires))
