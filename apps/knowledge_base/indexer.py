import asyncio
from uuid import uuid4
from typing import Iterator

import structlog
from django.conf import settings
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

logger = structlog.get_logger(__name__)

COLLECTION = settings.QDRANT_COLLECTION
VECTOR_SIZE = 1536  # text-embedding-3-small


def _get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


def _get_openai() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return [c for c in chunks if c.strip()]


async def _ensure_collection(client: AsyncQdrantClient) -> None:
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if COLLECTION not in names:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("qdrant_collection_created", collection=COLLECTION)


async def _get_embeddings(texts: list[str]) -> list[list[float]]:
    openai = _get_openai()
    response = await openai.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


async def index_document(doc) -> None:
    """Chunk, embed and upsert a KnowledgeDocument into Qdrant."""
    qdrant = _get_qdrant()
    await _ensure_collection(qdrant)

    # Remove old chunks for this document
    if doc.qdrant_point_ids:
        await qdrant.delete(
            collection_name=COLLECTION,
            points_selector=doc.qdrant_point_ids,
        )

    if not doc.is_active or not doc.content.strip():
        await doc.__class__.objects.filter(pk=doc.pk).aupdate(qdrant_point_ids=[])
        return

    chunks = _chunk_text(doc.content)
    if not chunks:
        return

    embeddings = await _get_embeddings(chunks)

    points = []
    point_ids = []
    for chunk, vector in zip(chunks, embeddings):
        pid = str(uuid4())
        point_ids.append(pid)
        points.append(PointStruct(
            id=pid,
            vector=vector,
            payload={
                "salon_id": doc.salon_id,
                "document_id": doc.id,
                "document_type": doc.document_type,
                "chunk_text": chunk,
            },
        ))

    await qdrant.upsert(collection_name=COLLECTION, points=points)
    await doc.__class__.objects.filter(pk=doc.pk).aupdate(qdrant_point_ids=point_ids)

    logger.info(
        "document_indexed",
        document_id=doc.id,
        salon_id=doc.salon_id,
        chunks=len(chunks),
    )

