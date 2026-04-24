import structlog
from django.conf import settings
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = structlog.get_logger(__name__)

COLLECTION = settings.QDRANT_COLLECTION


def _get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


async def _get_embedding(text: str) -> list[float]:
    openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await openai.embeddings.create(
        model="text-embedding-3-small",
        input=[text],
    )
    return response.data[0].embedding


async def search_knowledge(salon_id: int, query: str, top_k: int = 3) -> list[dict]:
    """Return top_k relevant chunks from the salon's knowledge base."""
    try:
        query_vector = await _get_embedding(query)
        qdrant = _get_qdrant()

        results = await qdrant.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="salon_id", match=MatchValue(value=salon_id))]
            ),
            limit=top_k,
            score_threshold=0.5,
        )

        logger.info("knowledge_search", salon_id=salon_id, query=query[:60], hits=len(results))

        return [
            {"text": r.payload["chunk_text"], "score": r.score, "doc_id": r.payload["document_id"]}
            for r in results
        ]
    except Exception as exc:
        logger.error("knowledge_search_error", error=str(exc), salon_id=salon_id)
        return []
