"""
Simple usage examples for AnytypeLoader.

This script demonstrates both sync and async loading. Replace the placeholder
values with your own API endpoint, key, and space ID before running.
"""

import asyncio
from anytype_loader import AnytypeLoader

API_URL = "http://127.0.0.1:31009"
API_KEY = "<API_KEY>"
SPACE_NAMES = ["Space 1", "Space 2"]


def run_sync():
    loader = AnytypeLoader(
        url=API_URL,
        api_key=API_KEY,
        space_names=SPACE_NAMES,
        page_size=20,
        # query="project",  # uncomment to use space search instead of list
    )

    docs = loader.load()

    for doc in docs[:3]:
        print(f"- {doc.metadata.get('name')} ({doc.metadata.get('object_id')})")


async def run_async():
    loader = AnytypeLoader(
        url=API_URL,
        api_key=API_KEY,
        space_names=SPACE_NAMES,
        page_size=20,
        # query="project",  # uncomment to use space search instead of list
    )

    docs = await loader.aload()

    for doc in docs[:3]:
        print(f"- {doc.metadata.get('name')} ({doc.metadata.get('object_id')})")

    await loader.aclose()


if __name__ == "__main__":
    run_sync()
    asyncio.run(run_async())
