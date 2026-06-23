from __future__ import annotations
import asyncio
import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


async def _download(url: str, dest_path: Path) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    dest_path.write_bytes(response.content)
    logger.info("Downloaded %d bytes → %s", len(response.content), dest_path)
    return dest_path


def resolve_pdf(url: str, local_path: Path) -> Path:
    """
    Resolve the PDF file path.

    Priority:
      1. Local file exists → use it directly (fastest, no network).
      2. URL is set → download to local_path, then use it.
      3. Neither → raise FileNotFoundError.
    """
    if local_path.exists():
        logger.info("Using local PDF: %s", local_path)
        return local_path

    if url:
        logger.info("Local PDF not found — downloading from %s", url)
        try:
            return asyncio.run(_download(url, local_path))
        except Exception as exc:
            raise FileNotFoundError(
                f"Download from {url!r} failed: {exc}. "
                f"No local file found at {local_path!r} either."
            ) from exc

    raise FileNotFoundError(
        f"No local PDF at {local_path!r} and PDF_URL is not configured. "
        "Set PDF_URL or PDF_LOCAL_PATH in your .env file."
    )
