"""
Attachment Service Module.

Orchestrates file storage (via storage_service) and database metadata 
management for ticket attachments.

Architecture (Senior Pattern):
- Decoupling: Returns Pydantic schemas (`AttachmentOut`) instead of models.
- Resilience: Gracefully handles storage failures when retrieving presigned URLs.
"""

import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.attachment import Attachment
from app.models.ticket import Ticket
from app.schemas.attachment import AttachmentOut
from app.services import storage_service


async def list_attachments(
    db: AsyncSession, 
    ticket_id: uuid.UUID
) -> List[AttachmentOut]:
    """
    Retrieves all attachments for a ticket with fresh presigned URLs.
    """
    result = await db.execute(
        select(Attachment)
        .where(Attachment.ticket_id == ticket_id)
        .order_by(Attachment.created_at.asc())
    )
    attachments = result.scalars().all()

    items = []
    for att in attachments:
        try:
            url = await storage_service.get_presigned_url(att.storage_key)
        except Exception:
            url = None
        
        items.append(AttachmentOut(
            id=att.id,
            ticket_id=att.ticket_id,
            uploader_id=att.uploader_id,
            filename=att.filename,
            size_bytes=att.size_bytes,
            mime_type=att.mime_type,
            created_at=att.created_at,
            download_url=url,
        ))
    return items


async def create_attachment(
    db: AsyncSession,
    ticket_id: uuid.UUID,
    uploader_id: uuid.UUID,
    filename: str,
    content: bytes,
    mime_type: str,
) -> Optional[AttachmentOut]:
    """
    Uploads a file to storage and saves metadata to the database.
    """
    # 1. Verify ticket
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    if not ticket_result.scalar_one_or_none():
        return None

    # 2. Upload to storage (MinIO/R2)
    storage_key = await storage_service.upload_file(
        ticket_id=ticket_id,
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    # 3. Save metadata
    attachment = Attachment(
        ticket_id=ticket_id,
        uploader_id=uploader_id,
        filename=filename,
        storage_key=storage_key,
        size_bytes=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    # 4. Generate immediate URL
    download_url = await storage_service.get_presigned_url(storage_key)

    return AttachmentOut(
        id=attachment.id,
        ticket_id=attachment.ticket_id,
        uploader_id=attachment.uploader_id,
        filename=attachment.filename,
        size_bytes=attachment.size_bytes,
        mime_type=attachment.mime_type,
        created_at=attachment.created_at,
        download_url=download_url,
    )


async def delete_attachment(
    db: AsyncSession,
    attachment_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> bool:
    """
    Deletes an attachment from both storage and database.
    """
    result = await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    attachment = result.scalar_one_or_none()
    
    if not attachment or attachment.uploader_id != actor_id:
        return False

    # Delete from storage first
    try:
        await storage_service.delete_file(attachment.storage_key)
    except Exception:
        pass

    # Clean up DB
    await db.delete(attachment)
    await db.commit()
    return True
