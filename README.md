## Anytype Loader

Lightweight community loader for Anytype spaces built on `langchain-core`.

### Usage

```python
from anytype_loader import AnytypeLoader

loader = AnytypeLoader(
    url="http://127.0.0.1:31009",
    api_key="YOUR_API_KEY",
    space_id="YOUR_SPACE_ID",
)

docs = loader.load()
```

The loader will:
- List objects via `/v1/spaces/:space_id/objects` using pagination with `limit` and `offset`.
- Fetch each object via `/v1/spaces/:space_id/objects/:object_id`.
- Return a `Document` containing the object's `markdown` field.
