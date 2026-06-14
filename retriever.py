from typing import Any

from config import TOP_K
from ingest import _chroma_client, _embedding_function, collection_name_for_creator


def retrieve_chunks(question: str, creator_name: str, top_k: int = TOP_K) -> list[dict[str, Any]]:
    client = _chroma_client()
    collection = client.get_collection(
        name=collection_name_for_creator(creator_name),
        embedding_function=_embedding_function(),
    )
    results = collection.query(query_texts=[question], n_results=top_k)

    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    chunks: list[dict[str, Any]] = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        chunks.append(
            {
                "chunk_text": document,
                "video_title": metadata.get("video_title", "Untitled video"),
                "video_url": metadata.get("video_url", ""),
                "video_id": metadata.get("video_id", ""),
                "similarity_score": None if distance is None else 1 / (1 + distance),
            }
        )
    return chunks

