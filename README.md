# Anytype Loader
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Community loader for Anytype spaces. Supports sync and async loading.

## Installation

```bash
pip install anytype-loader            # defaults to langchain-core (1.x)
# pip install anytype-loader[langchain]  # add langchain 0.x support
```


## Basic usage (sync)

```python
from anytype_loader import AnytypeLoader

loader = AnytypeLoader(
    url="http://127.0.0.1:31009",
    api_key="YOUR_API_KEY",
    space_names=["Personal", "Work"],
    page_size=50,
    query="project",  # optional: use space search endpoint instead of full listing
)

docs = list(loader.lazy_load())
```

## Basic usage (async)

```python
import asyncio
from anytype_loader import AnytypeLoader

async def main():
    loader = AnytypeLoader(
        url="http://127.0.0.1:31009",
        api_key="YOUR_API_KEY",
        space_names=["Your Space"],
        page_size=50,
    )
    docs = [doc async for doc in loader.alazy_load()]
    print(len(docs))
    await loader.aclose()

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

### Notes

- Async path uses a pooled `httpx.AsyncClient` and bounded concurrency.
- For LangChain 0.x support, wrap imports to fall back to `langchain` modules if `langchain_core` is unavailable.
