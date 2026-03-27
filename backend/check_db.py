"""检查数据库中Document的实际状态"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Document, KnowledgeBase

app = create_app()
with app.app_context():
    docs = Document.query.all()
    print(f"共 {len(docs)} 个文档记录:")
    for d in docs:
        print(f"  id={d.id}, kb_id={d.kb_id}, original_filename={d.original_filename}")
        print(f"    status={d.status!r}, chunk_count={d.chunk_count}")
        print(f"    error_message={d.error_message!r}")

    print("\n知识库列表:")
    kbs = KnowledgeBase.query.all()
    for kb in kbs:
        print(f"  id={kb.id}, name={kb.name!r}, doc_count={len(kb.documents)}")
