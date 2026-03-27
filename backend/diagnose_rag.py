"""RAG diagnose script - ASCII output only"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from config import Config
import chromadb

print("=== ChromaDB Diagnose ===")
print(f"Path: {Config.CHROMA_PATH}")
print(f"SIMILARITY_THRESHOLD: {Config.SIMILARITY_THRESHOLD}")

client = chromadb.PersistentClient(path=Config.CHROMA_PATH)
col = client.get_collection("knowledge_docs")
count = col.count()
print(f"Total chunks in DB: {count}")

if count == 0:
    print("ERROR: Collection is EMPTY! Documents were never indexed.")
    sys.exit(1)

# Show sample
sample = col.get(limit=2, include=["documents", "metadatas"])
for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
    print(f"\nSample {i+1}:")
    print(f"  kb_name: {meta.get('kb_name','?')}")
    # Print first 80 chars safely
    safe_content = doc[:80].encode('ascii', errors='replace').decode('ascii')
    print(f"  content: {safe_content!r}")

# Test retrieval
print("\n=== RAG Search Test ===")
from zhipuai import ZhipuAI
ai_client = ZhipuAI(api_key=Config.ZHIPUAI_API_KEY)

queries = ["Coze", "Coze\u662f\u4ec0\u4e48"]  # "Coze" and "Coze是什么"
for query in queries:
    safe_q = query.encode('ascii', errors='replace').decode('ascii')
    print(f"\nQuery: {safe_q!r}")
    resp = ai_client.embeddings.create(model=Config.ZHIPUAI_EMBEDDING_MODEL, input=query)
    qvec = resp.data[0].embedding
    print(f"  Embedding dim: {len(qvec)}")
    
    chroma_col = chromadb.PersistentClient(path=Config.CHROMA_PATH).get_collection("knowledge_docs")
    results = chroma_col.query(
        query_embeddings=[qvec],
        n_results=min(5, count),
        include=["documents", "metadatas", "distances"]
    )
    
    if results["documents"] and results["documents"][0]:
        print(f"  Got {len(results['documents'][0])} results:")
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            sim_old = 1.0 - dist
            sim_new = 1.0 - dist / 2.0
            passes = sim_new >= Config.SIMILARITY_THRESHOLD
            safe_doc = doc[:50].encode('ascii', errors='replace').decode('ascii')
            print(f"  [{i+1}] dist={dist:.4f}, sim_old={sim_old:.4f}, sim_new={sim_new:.4f}, pass={passes}")
            print(f"       kb={meta.get('kb_name','?')}, doc={safe_doc!r}")
    else:
        print("  No results!")

print("\nDone.")
