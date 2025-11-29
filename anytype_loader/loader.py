from typing import AsyncIterator, Dict, Generator, Iterator, List, Optional, Tuple
import asyncio
import time
import warnings

import httpx
import requests
from .exceptions import AnytypeAPIError, AnytypeAuthError

try:
    # LangChain v1.x
    from langchain_core.document_loaders import BaseLoader
    from langchain_core.documents import Document
except ImportError:
    # LangChain v0.x
    from langchain.document_loaders.base import BaseLoader
    from langchain.schema import Document


class AnytypeLoader(BaseLoader):
    """Community loader for Anytype spaces.

    The loader pulls all objects from a given space, following pagination,
    then fetches each object's markdown content.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        space_names: List[str],
        page_size: int = 100,
        query: Optional[str] = None,
        max_concurrency: int = 10,
    ) -> None:
        if not url or not api_key:
            raise ValueError("url and api_key are required")
        if not space_names:
            raise ValueError("At least one space name is required")
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.page_size = page_size
        self.query = query
        self.timeout = 30

        # Async settings
        self.max_concurrency = max_concurrency
        self.max_retries = 3
        self.retry_backoff = 1.0
        self._async_client = None

        # Space info
        self.space_name_map: Dict[str, str] = {}
        self.space_ids = self._resolve_space_ids(space_names)

    def _resolve_space_ids(
        self,
        space_names: List[str],
    ) -> List[str]:
        spaces = self._list_spaces()
        wanted = set(space_names)

        for space in spaces:
            if not isinstance(space, dict):
                continue
            sid = space.get("id")
            sname = space.get("name")

            if sname in wanted and sid:
                self.space_name_map[sid] = str(sname)

        unique_ids = self.space_name_map.keys()
        missing_names = wanted - set(self.space_name_map.values())

        if missing_names:
            warnings.warn(f"Skipping unknown spaces: {', '.join(missing_names)}")

        if not unique_ids:
            raise ValueError("At least one space name must resolve to an id")

        return unique_ids

    def lazy_load(self) -> Iterator[Document]:
        for space_id in self.space_ids:
            for object_id in self._iter_object_ids(space_id):
                fetched = self._fetch_object(space_id, object_id)
                if fetched is None:
                    continue

                markdown, metadata = fetched
                yield Document(
                    page_content=markdown,
                    metadata=metadata,
                )

    async def alazy_load(self) -> AsyncIterator[Document]:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def fetch_with_limit(space: str, oid: str):
            async with semaphore:
                return await self._afetch_object(space, oid)

        tasks = []
        for space_id in self.space_ids:
            async for object_id in self._aiter_object_ids(space_id):
                tasks.append(asyncio.create_task(fetch_with_limit(space_id, object_id)))

        for coro in asyncio.as_completed(tasks):
            fetched = await coro
            if fetched:
                markdown, metadata = fetched
                yield Document(page_content=markdown, metadata=metadata)

    def _iter_object_ids(self, space_id: str) -> Generator[str, None, None]:
        offset = 0
        while True:
            object_ids, has_more = self._list_objects(
                space_id=space_id, limit=self.page_size, offset=offset
            )
            if offset == 0 and not object_ids:
                warnings.warn(f"No objects returned for space {space_id} (offset=0)")

            for object_id in object_ids:
                yield str(object_id)

            offset += len(object_ids)

            if not has_more:
                break

    async def _aiter_object_ids(self, space_id: str) -> AsyncIterator[str]:
        offset = 0
        while True:
            object_ids, has_more = await self._alist_objects(
                space_id=space_id, limit=self.page_size, offset=offset
            )
            if offset == 0 and not object_ids:
                warnings.warn(f"No objects returned for space {space_id} (offset=0)")

            for object_id in object_ids:
                yield str(object_id)

            offset += len(object_ids)

            if not has_more:
                break

    def _list_objects(self, space_id: str, limit: int, offset: int) -> Tuple[List[str], bool]:
        endpoint = "search" if self.query else "objects"
        url = f"{self.base_url}/v1/spaces/{space_id}/{endpoint}"

        kwargs = {
            "headers": self._headers(),
            "params": {"limit": limit, "offset": offset},
            "timeout": self.timeout,
        }

        if self.query:
            kwargs["json"] = {"query": self.query}
            response = self._request_with_retries("post", url, **kwargs)
        else:
            response = self._request_with_retries("get", url, **kwargs)

        return self._parse_objects_response(response.json())

    async def _alist_objects(
        self, space_id: str, limit: int, offset: int
    ) -> Tuple[List[str], bool]:
        client = await self._get_client()

        endpoint = "search" if self.query else "objects"
        url = f"{self.base_url}/v1/spaces/{space_id}/{endpoint}"

        kwargs = {
            "headers": self._headers(),
            "params": {"limit": limit, "offset": offset},
            "timeout": self.timeout,
        }

        if self.query:
            kwargs["json"] = {"query": self.query}
            response = await self._arequest_with_retries(client.post, url, **kwargs)
        else:
            response = await self._arequest_with_retries(client.get, url, **kwargs)

        return self._parse_objects_response(response.json())

    def _list_spaces(self) -> List[Dict]:
        """Fetch spaces to resolve names to ids."""
        url = f"{self.base_url}/v1/spaces"
        response = self._request_with_retries(
            "get",
            url,
            headers=self._headers(),
            params={"limit": 100, "offset": 0},
            timeout=self.timeout,
        )
        data = response.json()
        spaces = data.get("data") if isinstance(data, dict) else None
        if isinstance(spaces, list):
            return spaces  # type: ignore[return-value]
        warnings.warn("Unexpected list spaces response structure; no spaces returned")
        return []

    @staticmethod
    def _parse_objects_response(data: object) -> Tuple[List[str], bool]:
        if isinstance(data, dict):
            objects_section = data.get("data")
            pagination_info = data.get("pagination")

            if isinstance(objects_section, list):
                ids: List[str] = []
                for obj in objects_section:
                    ids.append(obj["id"])

                has_more = False
                if isinstance(pagination_info, dict):
                    has_more = bool(pagination_info.get("has_more"))

                return ids, has_more

        warnings.warn("Unexpected list response structure; treating as empty result")
        return ([], False)

    def _fetch_object(self, space_id: str, object_id: str) -> Optional[Tuple[str, Dict]]:
        url = f"{self.base_url}/v1/spaces/{space_id}/objects/{object_id}"
        response = self._request_with_retries("get", url, headers=self._headers(), timeout=30)
        data = response.json()

        # Expected schema per docs: {"object": {...}}
        obj = data.get("object") if isinstance(data, dict) else None

        if not isinstance(obj, dict):
            raise AnytypeAPIError(f"Malformed object response for {object_id}: {data}")

        markdown = obj.get("markdown")
        if markdown is None:
            warnings.warn(f"No markdown content for object {object_id}; skipping")
            return None

        obj_type = None
        if isinstance(obj.get("type"), dict):
            obj_type = obj["type"].get("name")
        if obj_type is None:
            warnings.warn(f"Missing type for object {object_id}; using 'unknown'")
            obj_type = "unknown"

        name = obj.get("name") or "untitled"
        if obj.get("name") is None:
            warnings.warn(f"Missing name for object {object_id}; using 'untitled'")

        metadata: Dict = {
            "space_id": space_id,
            "space_name": self.space_name_map.get(space_id),
            "object_id": object_id,
            "id": object_id,
            "name": name,
            "archived": bool(obj.get("archived")),
            "type": obj_type,
        }

        # Flatten properties into a dict keyed by property key.
        properties: List[Dict] = obj.get("properties")
        flattened_properties = self._extract_properties(properties)
        if flattened_properties:
            metadata.update(flattened_properties)

        return str(markdown), metadata

    async def _afetch_object(self, space_id: str, object_id: str) -> Optional[Tuple[str, Dict]]:
        url = f"{self.base_url}/v1/spaces/{space_id}/objects/{object_id}"

        client = await self._get_client()
        response = await self._arequest_with_retries(
            client.get,
            url,
            headers=self._headers(),
        )
        data = response.json()

        obj = data.get("object") if isinstance(data, dict) else None

        if not isinstance(obj, dict):
            raise AnytypeAPIError(f"Malformed object response for {object_id}: {data}")

        markdown = obj.get("markdown")
        if markdown is None:
            warnings.warn(f"No markdown content for object {object_id}; skipping")
            return None

        obj_type = None
        if isinstance(obj.get("type"), dict):
            obj_type = obj["type"].get("name")
        if obj_type is None:
            warnings.warn(f"Missing type for object {object_id}; using 'unknown'")
            obj_type = "unknown"

        name = obj.get("name") or "untitled"
        if obj.get("name") is None:
            warnings.warn(f"Missing name for object {object_id}; using 'untitled'")

        metadata: Dict = {
            "space_id": space_id,
            "space_name": self.space_name_map.get(space_id),
            "object_id": object_id,
            "id": object_id,
            "name": name,
            "archived": bool(obj.get("archived")),
            "type": obj_type,
        }

        properties: List[Dict] = obj.get("properties")
        flattened_properties = self._extract_properties(properties)
        if flattened_properties:
            metadata.update(flattened_properties)

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
            self._async_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    @staticmethod
    def _extract_properties(properties: Optional[List[Dict]]) -> Dict[str, object]:
        if not isinstance(properties, list):
            return {}

        extracted: Dict[str, object] = {}
        allowed_keys = {
            "tag",
            "description",
            "last_opened_date",
            "last_modified_date",
            "created_date",
        }
        rename_map = {
            "created_date": "created_at",
            "last_modified_date": "updated_at",
            "last_opened_date": "last_opened_at",
        }

        for prop in properties:
            key = prop.get("key")

            if key not in allowed_keys:
                continue

            if key == "tag":
                items = prop.get("multi_select")
                if not isinstance(items, list):
                    continue
                names: List[str] = []
                for tag in items:
                    if isinstance(tag, dict) and tag.get("name"):
                        names.append(str(tag["name"]))
                if names:
                    extracted["tags"] = names
                continue

            fmt = prop.get("format")
            if fmt in ["date", "text"]:
                if key in rename_map:
                    key = rename_map[key]

                extracted[key] = prop.get(fmt)

            else:
                # "format": "objects" is not supported for now
                continue

        return extracted

    def _request_with_retries(self, method: str, url: str, **kwargs):
        attempt = 0
        while True:
            try:
                response = requests.request(method, url, **kwargs)
            except requests.RequestException as exc:
                raise AnytypeAPIError(f"Request to {url} failed: {exc}") from exc
            if response.status_code in {429, 503} and attempt < self.max_retries:
                warnings.warn(
                    f"Rate limited ({response.status_code}); retrying {attempt + 1}/{self.max_retries}"
                )
                attempt += 1
                time.sleep(self.retry_backoff * attempt)
                continue
            self._raise_for_status(response, url)
            return response

    async def _arequest_with_retries(self, func, url: str, **kwargs):
        attempt = 0
        while True:
            try:
                response = await func(url, **kwargs)
            except httpx.HTTPError as exc:
                raise AnytypeAPIError(f"Request to {url} failed: {exc}") from exc
            if response.status_code in {429, 503} and attempt < self.max_retries:
                warnings.warn(
                    f"Rate limited ({response.status_code}); retrying {attempt + 1}/{self.max_retries}"
                )
                attempt += 1
                await asyncio.sleep(self.retry_backoff * attempt)
                continue
            self._raise_for_status(response, url)
            return response

    def _raise_for_status(self, response, url: str):
        if response.status_code < 400:
            return

        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = payload.get("message") or payload.get("error") or ""
        except Exception:
            detail = response.text[:200] if hasattr(response, "text") else ""

        if response.status_code in {401, 403}:
            raise AnytypeAuthError(
                f"Authentication failed for {url}: {detail or response.status_code}"
            )

        raise AnytypeAPIError(
            f"Request failed ({response.status_code}) for {url}: {detail or 'no detail'}"
        )
