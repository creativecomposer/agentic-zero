from datetime import datetime
import hashlib
import uuid
import httpx
from pathlib import Path
from typing import List
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, SparseVectorParams,  VectorParams


# Run qdrant server
# docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant:latest
qdrant_client = QdrantClient(url="http://127.0.0.1:6333")

# Run llama.cpp with an embedding model
# ./build/bin/llama-server --model /home/anthony/.cache/llama.cpp/nomic-embed-text-v1.5.Q8_0.gguf --port 8081 --host 0.0.0.0 --embedding --pooling cls -ub 8192
embed_client = httpx.Client(base_url="http://127.0.0.1:8081/v1", timeout=None)
COLLECTION_NAME = "second_brain"

if not qdrant_client.collection_exists(COLLECTION_NAME):
    qdrant_client.create_collection(collection_name=COLLECTION_NAME, vectors_config=VectorParams(
        size=768, distance=Distance.COSINE), sparse_vectors_config={"text": SparseVectorParams()})


def get_rfc_3339_datetime():
    utc_datetime = datetime.utcnow()
    return utc_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')


def get_embedding(text: str):
    resp = embed_client.post(
        "/embeddings", json={"input": [text], "model": "nomic"})
    return resp.json()["data"][0]["embedding"] or ""


def chunk_document(content: str, source_path: str, metadata: dict) -> List[dict]:
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    chunks = []
    current = []
    current_tokens = 0
    for line in lines:
        tokens = len(line.split()) + 10  # rough
        if current_tokens + tokens > 800 and current:
            chunks.append(" ".join(current))
            current = [line]
            current_tokens = tokens
        else:
            current.append(line)
            current_tokens += tokens
    if current:
        chunks.append(" ".join(current))
    # Add metadata to every chunk
    return [{"text": c, "source": source_path, "metadata": metadata} for c in chunks]


def ingest_file(file_path: str):
    print(f"Ingesting {file_path}...")
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    modified_time = get_rfc_3339_datetime()
    chunks = chunk_document(
        text, str(path), {"type": "text", "modified": modified_time})

    points = []
    files_info_record = retrieve_files_info()
    if len(files_info_record) == 0:
        print("Files info does not exist. Create new files info point...")
        files_info_point = create_files_info_point(str(path))
        points.append(files_info_point)
    else:
        # files_info = points[0].model_dump()["payload"]
        files_info = files_info_record[0].payload or {}
        if str(path) in files_info:
            print(f"The file was already ingested at {
                  files_info[str(path)]}. Ingesting it again...")
        files_info[str(path)] = modified_time
        points.append(PointStruct(
            id=1, vector=files_info_record[0].vector, payload=files_info))

    i = 0
    for c in chunks:
        vector = get_embedding(c["text"])
        chunk_id = hashlib.sha256(f"{str(path)}_{i}".encode("utf-8"))
        point_id = uuid.UUID(chunk_id.hexdigest()[::2])
        points.append(PointStruct(id=point_id, vector=vector, payload=c))
        i += 1

    qdrant_client.upsert(collection_name=COLLECTION_NAME,
                         wait=True, points=points)
    print(f"Ingested {path} -> {len(chunks)} chunks")


# The file info point is stored with id 1, and vector as embedding of the text "TheFilesList"
def create_files_info_point(file_path: str):
    vector = get_embedding("TheFilesList")
    return PointStruct(id=1, vector=vector, payload={file_path: get_rfc_3339_datetime()})


def retrieve_files_info():
    return qdrant_client.retrieve(collection_name=COLLECTION_NAME, ids=[1], with_payload=True, with_vectors=True)


def retrieve(query: str, limit: int = 4):
    print(f"Retrieving relevant results for {query}...")
    vector = get_embedding(query)
    search_results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME, query=vector, with_payload=True, limit=limit)
    formatted = []
    for hit in search_results.points:
        payload = hit.model_dump()["payload"]
        # snippet = payload["text"][:800] + "..." if len(payload["text"]) > 800 else payload["text"]
        snippet = payload["text"]
        formatted.append(f"Source: {payload["source"]}\n{snippet}\n")
    return "\n\n".join(formatted)
