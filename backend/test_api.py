"""直接API测试：登录 + 发消息 + 查看是否有RAG检索"""
import requests, json

BASE = "http://localhost:5000"

# 1. 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"})
data = r.json()
print(f"Login: code={data.get('code')}")
token = data.get("access_token") or data.get("data", {}).get("token")
if not token:
    print(f"Login failed: {data}")
    exit(1)
print(f"Token: {token[:30]}...")

headers = {"Authorization": f"Bearer {token}"}

# 2. 创建对话
r = requests.post(f"{BASE}/api/chat/conversations", json={"title": "RAG测试"}, headers=headers)
conv = r.json()
conv_id = conv["data"]["id"]
print(f"Created conversation: id={conv_id}")

# 3. 发送问题
question = "Coze是什么？"
print(f"\n发送问题: {question!r}")
r = requests.post(
    f"{BASE}/api/chat/conversations/{conv_id}/messages",
    json={"content": question},
    headers=headers,
    timeout=60
)
resp = r.json()
print(f"Response code: {resp.get('code')}")
data = resp.get("data", {})
print(f"has_knowledge: {data.get('has_knowledge')}")
print(f"sources: {json.dumps(data.get('sources', []), ensure_ascii=False)}")
ai_msg = data.get("assistant_message", {})
print(f"AI回答前200字: {ai_msg.get('content', '')[:200]}")
