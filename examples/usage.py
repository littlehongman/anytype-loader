"""
Simple usage examples for AnytypeLoader.

This script demonstrates both sync and async loading. Replace the placeholder
values with your own API endpoint, key, and space ID before running.
"""

import time
import asyncio
from anytype_loader import AnytypeLoader

API_URL = "http://127.0.0.1:31009"
API_KEY = "<API_KEY>"
SPACE_NAMES = ["Space 1", "Space 2"]


def run_sync():
    start = time.time()
    loader = AnytypeLoader(
        url=API_URL,
        api_key=API_KEY,
        space_names=SPACE_NAMES,
        page_size=20,
        query="Pattern - Availability",
        # query="project",  # uncomment to use space search instead of list
    )
    docs = list(loader.lazy_load())
    print(f"sync loaded docs: {len(docs)}")
    for doc in docs[:3]:
        print(f"- {doc.metadata.get('name', 'unnamed')} ({doc.metadata.get('object_id')})")

    print(doc.metadata)
    print("Time Spent: ", (time.time() - start))


async def run_async():
    start = time.time()
    loader = AnytypeLoader(
        url=API_URL,
        api_key=API_KEY,
        space_names=SPACE_NAMES,
        page_size=20,
        query="Pattern - Availability",  # uncomment to use space search instead of list
    )
    docs = [doc async for doc in loader.alazy_load()]
    print(f"async loaded docs: {len(docs)}")
    for doc in docs[:3]:
        print(f"- {doc.metadata.get('name', 'unnamed')} ({doc.metadata.get('object_id')})")
    await loader.aclose()

    print(doc.metadata)

    print("Time Spent: ", (time.time() - start))


if __name__ == "__main__":
    # run_sync()
    asyncio.run(run_async())
