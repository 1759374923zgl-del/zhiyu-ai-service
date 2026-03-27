"""测试PDF文本提取效果"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fitz  # PyMuPDF
from config import Config

upload_dir = Config.UPLOAD_FOLDER
files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
print(f"上传目录: {upload_dir}")
print(f"PDF文件: {files}")

for fname in files:
    fpath = os.path.join(upload_dir, fname)
    print(f"\n=== 提取: {fname} ===")
    doc = fitz.open(fpath)
    print(f"页数: {doc.page_count}")
    
    # 方法1: 默认 get_text()
    page0 = doc[0]
    text_default = page0.get_text()
    print(f"[方法1-默认] 前200字: {repr(text_default[:200])}")
    
    # 方法2: get_text("text") with flags
    text_flags = page0.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    print(f"[方法2-preserve_ws] 前200字: {repr(text_flags[:200])}")
    
    # 方法3: blocks方式
    blocks = page0.get_text("blocks")
    print(f"[方法3-blocks] 共{len(blocks)}个块, 第1块: {repr(str(blocks[0])[:200]) if blocks else '空'}")
    
    # 方法4: dict方式，检查字体信息
    text_dict = page0.get_text("dict")
    first_span = None
    for block in text_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    first_span = span
                    break
            if first_span:
                break
        if first_span:
            break
    if first_span:
        print(f"[方法4-dict] 第一个span: text={repr(first_span['text'][:50])}, font={first_span.get('font','?')}, flags={first_span.get('flags','?')}")
    
    doc.close()

print("\nDone.")
