"""测试第二个PDF + 检查数据库doc_id分布"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz
from config import Config
import chromadb

# 测试第二个PDF
pdf2 = r"D:\E\AI编程\Antigravity\智能客服\backend\uploads\d1ee3aedf6f043d0bf0ddb20439b6a29_Coze.pdf"
print("=== 测试第二个PDF ===")
doc = fitz.open(pdf2)
print(f"页数: {doc.page_count}")
text = ""
for i, page in enumerate(doc):
    text += page.get_text() + "\n"
    if i >= 1:
        break
doc.close()
print(f"前500字符: {text[:500]!r}")

print("\n=== ChromaDB中的doc_id分布 ===")
client = chromadb.PersistentClient(path=Config.CHROMA_PATH)
col = client.get_collection("knowledge_docs")

# 获取所有元数据
all_data = col.get(include=["metadatas"])
doc_ids = {}
for meta in all_data["metadatas"]:
    did = meta.get("doc_id", "?")
    kb = meta.get("kb_name", "?")
    key = f"doc_id={did}, kb={kb}"
    doc_ids[key] = doc_ids.get(key, 0) + 1

print(f"共 {len(all_data['metadatas'])} 条记录:")
for k, v in doc_ids.items():
    print(f"  {k}: {v}条")

print("\n检查所有块的内容质量（前5个）:")
sample = col.get(limit=5, include=["documents", "metadatas"])
for i, (doc_text, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
    # 检查中文字符比例
    chinese_count = sum(1 for c in doc_text if '\u4e00' <= c <= '\u9fff')
    total = len(doc_text)
    ratio = chinese_count / total if total > 0 else 0
    print(f"  [{i+1}] doc_id={meta.get('doc_id')}, 总字符={total}, 中文字符={chinese_count}, 中文比例={ratio:.1%}")
    print(f"       前80字: {doc_text[:80]!r}")
