import asyncio
import datetime
import gzip
import io
import os

import structlog
from config.celery import app

logger = structlog.get_logger(__name__)


@app.task
def index_document_task(document_id: int) -> None:
    from apps.knowledge_base.models import KnowledgeDocument
    from apps.knowledge_base.indexer import index_document

    async def _run():
        doc = await KnowledgeDocument.objects.select_related("salon").aget(
            pk=document_id
        )
        await index_document(doc)

    asyncio.run(_run())


@app.task(name="apps.knowledge_base.tasks.backup_database_task")
def backup_database_task() -> dict:
    from django.core.management import call_command

    backup_dir = "/app/backups"
    os.makedirs(backup_dir, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    filename = f"{backup_dir}/db_{date_str}.json.gz"

    buf = io.StringIO()
    call_command("dumpdata", "--natural-foreign", "--natural-primary", stdout=buf)

    with gzip.open(filename, "wt", encoding="utf-8") as f:
        f.write(buf.getvalue())

    size_kb = os.path.getsize(filename) // 1024
    logger.info("backup_complete", file=filename, size_kb=size_kb)
    return {"file": filename, "size_kb": size_kb}
