import logging
import os

import faiss
import numpy as np
from openai import OpenAI


logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def embed_texts(texts: list[str]) -> np.ndarray:
    logger.info("embed_texts: embedding %d texts", len(texts))
    response = _get_client().embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    embeddings = [item.embedding for item in response.data]
    return np.array(embeddings, dtype=np.float32)


def build_index(items: list[dict]) -> tuple[faiss.IndexFlatL2, list[dict]]:
    texts = [
        " ".join(filter(None, [
            item.get('name', ''),
            item.get('description') or '',
            item.get('category') or '',
            ", ".join(item.get('common_ingredients') or []),
        ])).strip()
        for item in items
    ]
    embeddings = embed_texts(texts)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    logger.info("build_index: indexed %d items", len(items))
    return index, items


def search_index(
    query: str,
    index: faiss.IndexFlatL2,
    items: list[dict],
    k: int = 5,
) -> list[dict]:
    query_embedding = embed_texts([query])
    distances, indices = index.search(query_embedding, k)

    matches = []
    for distance, item_index in zip(distances[0], indices[0]):
        if item_index == -1:
            continue

        match = dict(items[item_index])
        match["score"] = round(float(distance), 4)
        matches.append(match)

    top_name = matches[0].get("name") if matches else None
    logger.info("search_index: query=%s top_result=%s", query, top_name)
    return matches
