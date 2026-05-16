from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.config import settings


class AzureBackupDisabled(RuntimeError):
    pass


class AzureBlobBackup:
    @property
    def enabled(self) -> bool:
        return bool(settings.azure_storage_connection_string)

    async def upload_json(self, blob_name: str, payload: dict[str, Any]) -> str:
        if not self.enabled:
            raise AzureBackupDisabled("Azure Blob backup is not configured.")

        record = {
            "created_at": datetime.now(UTC).isoformat(),
            "service": "biber-api",
            "payload": payload,
        }
        body = json.dumps(record, indent=2, sort_keys=True).encode("utf-8")

        def _upload() -> str:
            from azure.storage.blob import BlobServiceClient

            service = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string or ""
            )
            container = service.get_container_client(settings.azure_blob_container)
            if not container.exists():
                container.create_container()
            blob = container.get_blob_client(blob_name)
            blob.upload_blob(body, overwrite=True, content_type="application/json")
            return blob.url

        return await asyncio.to_thread(_upload)
