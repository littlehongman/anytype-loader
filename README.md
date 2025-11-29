# Anytype Loader
[![PyPI version](https://img.shields.io/pypi/v/anytype-loader.svg)](https://pypi.org/project/anytype-loader/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python loader for [Anytype](https://anytype.io) spaces. Load documents into LangChain format for RAG pipelines and AI applications. Supports both sync and async operations.

## Installation

```bash
pip install anytype-loader
```
Supports `langchain-core` 1.x by default. For LangChain 0.x, install with `pip install anytype-loader[langchain]`.

## Prerequisites

- Anytype desktop app running locally
- API key from Anytype settings
- Space names you want to load

## What it does

The loader retrieves documents from your Anytype spaces and converts them to LangChain `Document` objects:

- Resolves space names to IDs via `/v1/spaces`
- Lists objects with pagination via `/v1/spaces/:space_id/objects` (or `/v1/spaces/:space_id/search` with `query` parameter)
- Fetches full content for each object via `/v1/spaces/:space_id/objects/:object_id`
- Returns documents with markdown content and metadata including space info, timestamps, tags, and object properties

**Example metadata:**

```json
{
    "id": "<object_id>",
    "space_id": "<space_id>", 
    "space_name": "Personal",
    "name": "Project Notes", 
    "archived": false, 
    "type": "Page", 
    "created_at": "2024-11-02T21:20:00Z", 
    "updated_at": "2025-11-28T19:17:37Z",
    "last_opened_at": "2025-11-28T19:03:43Z",
    "tags": ["work", "urgent"], 
    "description": "Q4 planning document"
}
```

## Quickstart

### Sync

```python
from anytype_loader import AnytypeLoader

loader = AnytypeLoader(
    url="http://127.0.0.1:31009",
    api_key="YOUR_API_KEY",
    space_names=["Personal", "Work"],
    page_size=50,
    query="project",  # optional: search instead of listing all objects
)

docs = loader.load()
```

### Async

**Recommended: context manager (auto-cleanup)**

```python
import asyncio
from anytype_loader import AnytypeLoader

async def main():
    async with AnytypeLoader(
        url="http://127.0.0.1:31009",
        api_key="YOUR_API_KEY",
        space_names=["Personal", "Work"],
        page_size=50,
    ) as loader:
        docs = await loader.aload()

asyncio.run(main())
```

**Alternative: manual cleanup**

```python
async def main():
    loader = AnytypeLoader(
        url="http://127.0.0.1:31009",
        api_key="YOUR_API_KEY",
        space_names=["Personal", "Work"],
    )
    
    docs = await loader.aload()
    await loader.aclose()  # required for cleanup

asyncio.run(main())
```


## What it does

- Resolves provided `space_names` via `/v1/spaces` to get IDs.
- Lists objects via `/v1/spaces/:space_id/objects` (or `/v1/spaces/:space_id/search` when `query` is set) with pagination (`limit`/`offset`).
- Fetches each object via `/v1/spaces/:space_id/objects/:object_id`.
- Returns `Document` objects with `markdown` content and flattened metadata including: `space_id`, `space_name`, `object_id`, `name`, `archived`, `type`, tags (tag names), and selected dates (`created_at`, `updated_at`, `last_opened_at` when present).

Example metadata from one document:

```json
{
    "space_id": "<space_id>", 
    "space_name": "Johnson", 
    "object_id": "<object_id>", 
    "id": "<object_id>",
    "name": "Pattern - Availability", 
    "archived": false, 
    "type": "Page", 
    "created_at": "2024-11-02T21:20:00Z", 
    "tags": ["testTag"], 
    "updated_at": "2025-11-28T19:17:37Z", 
    "description": "Test Desc", 
    "last_opened_at": "2025-11-28T19:03:43Z"
}
```

## Implementation notes

- Async implementation uses pooled `httpx.AsyncClient` with bounded concurrency for efficient parallel fetching
- All timestamps are returned in ISO 8601 format
- Tag references are resolved to tag names in metadata
- Empty or missing fields are omitted from metadata