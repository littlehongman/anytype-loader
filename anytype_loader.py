from typing import AsyncIterator, Dict, Generator, Iterator, List, Optional, Tuple
import asyncio
import logging
import httpx
import requests


try: 
    # LangChain v1.x
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
except ImportError:
    # LangChain v0.x
    from langchain.document_loaders.base import BaseLoader
    from langchain.schema import Document

log = logging.getLogger(__name__)


class AnytypeLoader(BaseLoader):
    """Community loader for Anytype spaces.

    The loader pulls all objects from a given space, following pagination,
    then fetches each object's markdown content.
    """

    def __init__(self, url: str, api_key: str, space_id: str, page_size: int = 100) -> None:
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.space_id = space_id
        self.page_size = page_size
        self.timeout = 30

        # Async settings
        self.max_concurrency = 10
        self._async_client = None

    def lazy_load(self) -> Iterator[Document]:
        for object_id in self._iter_object_ids():
            fetched = self._fetch_object(object_id)
            if fetched is None:
                continue

            markdown, metadata = fetched
            yield Document(
                page_content=markdown,
                metadata=metadata,
            )

    async def alazy_load(self) -> AsyncIterator[Document]:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        async def fetch_with_limit(oid):
            async with semaphore: 
                return await self._afetch_object(oid) 
        
        tasks = []
        async for object_id in self._aiter_object_ids():
            task = asyncio.create_task(fetch_with_limit(object_id))
            tasks.append(task)
       
        for coro in asyncio.as_completed(tasks):
            fetched = await coro
            if fetched:
                markdown, metadata = fetched
                yield Document(page_content=markdown, metadata=metadata)

    def _iter_object_ids(self) -> Generator[str, None, None]:
        offset = 0
        while True:
            object_ids, has_more = self._list_objects(limit=self.page_size, offset=offset)

            for object_id in object_ids:
                yield str(object_id)
            
            offset += len(object_ids)
            
            if not has_more:
                break

    async def _aiter_object_ids(self) -> AsyncIterator[str]:
        offset = 0
        while True:
            object_ids, has_more = await self._alist_objects(limit=self.page_size, offset=offset)

            for object_id in object_ids:
                yield str(object_id)

            offset += len(object_ids)

            if not has_more:
                break

    def _list_objects(self, limit: int, offset: int) -> Tuple[List[str], bool]:
        url = f"{self.base_url}/v1/spaces/{self.space_id}/objects"
        response = requests.get(
            url,
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
            timeout=self.timeout,
        )

        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            # Expected schema per docs: {"data": [objects...], "pagination": {...}}
            objects_section = data.get("data")
            pagination_info = data.get("pagination")

            if isinstance(objects_section, list):
                ids: List[str] = []
                for obj in objects_section:
                    try:
                        ids.append(str(obj["id"]))
                    except Exception:
                        log.warning("Skipping object without id: %s", obj)

                has_more = False
                if isinstance(pagination_info, dict):
                    has_more = bool(pagination_info.get("has_more"))

                return ids, has_more

        log.warning("Unexpected list response structure: %s", data)
        return ([], False)

    async def _alist_objects(self, limit: int, offset: int) -> Tuple[List[str], bool]:
        url = f"{self.base_url}/v1/spaces/{self.space_id}/objects"

        client = await self._get_client()
        response = await client.get(
            url,
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )

        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            # Expected schema per docs: {"data": [objects...], "pagination": {...}}
            objects_section = data.get("data")
            pagination_info = data.get("pagination")

            if isinstance(objects_section, list):
                ids: List[str] = []
                for obj in objects_section:
                    try:
                        ids.append(str(obj["id"]))
                    except Exception:
                        log.warning("Skipping object without id: %s", obj)

                has_more = False
                if isinstance(pagination_info, dict):
                    has_more = bool(pagination_info.get("has_more"))

                return ids, has_more

        log.warning("Unexpected list response structure: %s", data)
        return ([], False)

           

    def _fetch_object(self, object_id: str) -> Optional[Tuple[str, Dict]]:
        url = f"{self.base_url}/v1/spaces/{self.space_id}/objects/{object_id}"
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        # Expected schema per docs: {"object": {...}}
        obj = data.get("object") if isinstance(data, dict) else None

        if not isinstance(obj, dict):
            log.warning("Unexpected object response for %s: %s", object_id, data)
            return None

        markdown = obj.get("markdown")
        if markdown is None:
            log.warning("No markdown content for object %s", object_id)
            return None

        metadata: Dict = {
            "space_id": self.space_id,
            "object_id": object_id,
            "source": url,
        }

        # Keep simple scalar fields such as name.
        for key in ("name",):
            if key in obj:
                metadata[key] = obj[key]

        # Flatten properties into a dict keyed by property key.
        properties: List[Dict] = obj.get("properties")
        flattened_properties = self._extract_properties(properties)
        if flattened_properties:
            metadata["properties"] = flattened_properties

        return str(markdown), metadata

    async def _afetch_object(self, object_id: str) -> Optional[Tuple[str, Dict]]:
        url = f"{self.base_url}/v1/spaces/{self.space_id}/objects/{object_id}"

        client = await self._get_client()
        response = await client.get(
            url,
            headers=self._headers(),
        )

        response.raise_for_status()
        data = response.json()

        obj = data.get("object") if isinstance(data, dict) else None

        if not isinstance(obj, dict):
            log.warning("Unexpected object response for %s: %s", object_id, data)
            return None

        markdown = obj.get("markdown")
        if markdown is None:
            log.warning("No markdown content for object %s", object_id)
            return None

        metadata: Dict = {
            "space_id": self.space_id,
            "object_id": object_id,
            "source": url,
        }

        for key in ("name",):
            if key in obj:
                metadata[key] = obj[key]

        properties: List[Dict] = obj.get("properties")
        flattened_properties = self._extract_properties(properties)
        if flattened_properties:
            metadata["properties"] = flattened_properties

        return str(markdown), metadata

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "anytype-loader",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self):
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=30)
        return self._async_client

    async def aclose(self):
        if self._async_client:
            await self._async_client.aclose()

    @staticmethod
    def _extract_properties(properties: Optional[List[Dict]]) -> Dict[str, object]:
        if not isinstance(properties, list):
            return {}

        extracted: Dict[str, object] = {}
        allowed_keys = {"last_opened_date", "last_modified_date", "created_date"}
        for prop in properties:
            if not isinstance(prop, dict):
                continue
            key = prop.get("key")
            if not key or key not in allowed_keys:
                continue

            # Prefer explicit value fields; fall back to any typed payload.
            value = None
            for candidate in ("value", "date", "number", "text", "bool"):
                if candidate in prop:
                    value = prop[candidate]
                    break

            extracted[str(key)] = value

        return extracted