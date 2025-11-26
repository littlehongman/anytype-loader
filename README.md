## Anytype Loader

Community loader for Anytype spaces. Supports sync and async loading.

### Installation

```bash
pip install anytype-loader
```

### Basic usage (sync)

```python
from anytype_loader import AnytypeLoader

loader = AnytypeLoader(
    url="http://127.0.0.1:31009",
    api_key="YOUR_API_KEY",
    space_id="YOUR_SPACE_ID",
    page_size=50,
)

docs = list(loader.lazy_load())
```

### Basic usage (async)

```python
import asyncio
from anytype_loader import AnytypeLoader

async def main():
    loader = AnytypeLoader(
        url="http://127.0.0.1:31009",
        api_key="YOUR_API_KEY",
        space_id="YOUR_SPACE_ID",
        page_size=50,
    )
    docs = [doc async for doc in loader.alazy_load()]
    print(len(docs))

asyncio.run(main())
```

### What it does

- Lists objects via `/v1/spaces/:space_id/objects` with pagination (`limit`/`offset`).
- Fetches each object via `/v1/spaces/:space_id/objects/:object_id`.
- Returns `Document` objects with the `markdown` field as content and metadata including `space_id`, `object_id`, `name`, and selected date properties (`last_opened_date`, `last_modified_date`, `created_date`).

### Notes

- Async path uses a pooled `httpx.AsyncClient` and bounded concurrency.
- For LangChain 0.x support, wrap imports to fall back to `langchain` modules if `langchain_core` is unavailable.
