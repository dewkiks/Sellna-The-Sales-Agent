"""Manual dev script — verifies that qdrant-client is installed and functional.

This is NOT a production module and NOT part of the scraping pipeline.
Run it directly (python test_qdrant.py) to confirm the Qdrant async client
can create an in-memory collection, upsert a vector point, and query it back.

What it checks:
  - qdrant-client package is importable.
  - AsyncQdrantClient works with the ':memory:' backend (no server needed).
  - create_collection, upsert, and query_points all succeed without error.

Expected output on success: "QUERY POINTS: 1"
Any exception is caught and printed as "ERROR: <message>".
"""

import asyncio
import qdrant_client
from qdrant_client import models


async def main():
    try:
        # ':memory:' creates an ephemeral in-process Qdrant instance — no server required.
        client = qdrant_client.AsyncQdrantClient(':memory:')

        # Create a minimal collection: 2-dimensional vectors, cosine similarity.
        await client.create_collection(
            'test',
            vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE)
        )

        # Insert one point with id=1 and a simple unit vector.
        await client.upsert('test', points=[models.PointStruct(id=1, vector=[0.5, 0.5])])

        # Query for the nearest neighbour of [0.5, 0.5] — should return id=1.
        res = await client.query_points('test', query=[0.5, 0.5])
        print("QUERY POINTS:", res.points[0].id)
    except Exception as e:
        print("ERROR:", e)


asyncio.run(main())
