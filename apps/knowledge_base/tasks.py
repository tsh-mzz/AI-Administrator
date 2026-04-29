import asyncio
from config.celery import app


@app.task
def index_document_task(document_id: int) -> None:
    from apps.knowledge_base.models import KnowledgeDocument
    from apps.knowledge_base.indexer import index_document

    async def _run():
        doc = await KnowledgeDocument.objects.select_related("salon").aget(pk=document_id)
        await index_document(doc)

    asyncio.run(_run())
