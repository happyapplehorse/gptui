import uuid
import logging
from logging import Logger

from qdrant_client import QdrantClient
from semantic_kernel.connectors.memory.qdrant.qdrant_memory_store import QdrantMemoryStore
from semantic_kernel.memory.memory_record import MemoryRecord
from semantic_kernel.utils.null_logger import NullLogger
from qdrant_client import models as qdrant_models


gptui_logger = logging.getLogger("gptui_logger")


class QdrantVector(QdrantMemoryStore):
    
    def __init__(
        self,
        vector_size: int,
        url: str | None = None,
        port: int | None = 6333,
        logger: Logger | None = None,
        local: bool | None = False,
    ) -> None:
        """Initializes a new instance of the QdrantMemoryStore class.

        Arguments:
            logger {Optional[Logger]} -- The logger to use. (default: {None})
        """
        if local:
            if url:
                try:
                    self._qdrantclient = QdrantClient(path=url)
                except KeyError as e:
                    gptui_logger.error(
                        f"An error occurred while initializing the local vector database. Database path: {url}. Error: {repr(e)} "
                        "Warning: Rebuilding of the vector database may be required."
                    )
            else:
                self._qdrantclient = QdrantClient(location=":memory:")
        else:
            self._qdrantclient = QdrantClient(url=url, port=port)

        self._logger = logger or NullLogger()
        self._default_vector_size = vector_size

    async def _convert_from_memory_record_async(
        self, collection_name: str, record: MemoryRecord
    ) -> qdrant_models.PointStruct:
        if record._key is not None and record._key != "":
            pointId = record._key

        else:
            existing_record = await self._get_existing_record_by_payload_id_async(
                collection_name=collection_name,
                payload_id=record._id,
            )

            if existing_record:
                pointId = str(existing_record.id)
            else:
                pointId = str(uuid.uuid4())

        payload = record.__dict__.copy()
        payload["storage_status"] = "unsaved"
        embedding = payload.pop("_embedding")

        return qdrant_models.PointStruct(
            id=pointId, vector=embedding.tolist(), payload=payload
        )

    async def collection_save(self, collection_name: str) -> qdrant_models.UpdateResult:
        filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="storage_status",
                    match=qdrant_models.MatchAny(any=["unsaved", "cached"]),
                )
            ]
        )

        update_result = self._qdrantclient.set_payload(
            collection_name=str(collection_name),
            payload={"storage_status": "saved"},
            points=filter,
        )

        return update_result

    async def collection_cache(self, collection_name: str) -> qdrant_models.UpdateResult:
        filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="storage_status",
                    match=qdrant_models.MatchValue(value="unsaved"),
                )
            ]
        )
        
        update_result = self._qdrantclient.set_payload(
            collection_name=str(collection_name),
            payload={"storage_status": "cached"},
            points=filter,
        )

        return update_result
    
    async def collection_clean(self, collection_name: str) -> qdrant_models.UpdateResult:
        filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="storage_status",
                    match=qdrant_models.MatchAny(any=["unsaved", "cached"]),
                )
            ]
        )

        update_result = self._qdrantclient.delete(
            collection_name=collection_name,
            points_selector=qdrant_models.FilterSelector(filter=filter),
        )
        
        return update_result

    async def collection_count(self, collection_name: str) -> tuple[int, int, int]:
        def make_filter(storage_status: str):
            filter = qdrant_models.Filter(
                must=[
                    qdrant_models.FieldCondition(
                        key="storage_status",
                        match=qdrant_models.MatchValue(value=storage_status),
                    )
                ]
            )
            return filter

        count_saved = self._qdrantclient.count(
            collection_name=collection_name,
            count_filter=make_filter("saved"),
            exact=True,
        )

        count_cached = self._qdrantclient.count(
            collection_name=collection_name,
            count_filter=make_filter("cached"),
            exact=True,
        )

        count_unsaved = self._qdrantclient.count(
            collection_name=collection_name,
            count_filter=make_filter("unsaved"),
            exact=True,
        )

        return count_saved.count, count_cached.count, count_unsaved.count
