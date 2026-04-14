import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Conversation, Message
import rag

chat_bp = Blueprint("chat", __name__)


# ==================== 对话管理 ====================

@chat_bp.route("/conversations", methods=["GET"])
@jwt_required()
def list_conversations():
    user_id = int(get_jwt_identity())
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    pagination = (
        Conversation.query
        .filter_by(user_id=user_id)
        .order_by(Conversation.updated_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "code": 200,
        "data": {
            "items": [c.to_dict() for c in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages
        }
    })


@chat_bp.route("/conversations", methods=["POST"])
@jwt_required()
def create_conversation():
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    title = data.get("title", "新对话").strip() or "新对话"

    conv = Conversation(user_id=user_id, title=title)
    db.session.add(conv)
    db.session.commit()

    return jsonify({"code": 200, "data": conv.to_dict()})


@chat_bp.route("/conversations/<int:conv_id>", methods=["DELETE"])
@jwt_required()
def delete_conversation(conv_id):
    user_id = int(get_jwt_identity())
    conv = Conversation.query.get(conv_id)
    if not conv or conv.user_id != user_id:
        return jsonify({"code": 404, "message": "对话不存在"}), 404

    db.session.delete(conv)
    db.session.commit()
    return jsonify({"code": 200, "message": "对话已删除"})


@chat_bp.route("/conversations/<int:conv_id>/messages", methods=["GET"])
@jwt_required()
def get_messages(conv_id):
    user_id = int(get_jwt_identity())
    conv = Conversation.query.get(conv_id)
    if not conv or conv.user_id != user_id:
        return jsonify({"code": 404, "message": "对话不存在"}), 404

    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
    return jsonify({
        "code": 200,
        "data": [msg.to_dict() for msg in messages]
    })


@chat_bp.route("/conversations/<int:conv_id>/messages", methods=["POST"])
@jwt_required()
def send_message(conv_id):
    user_id = int(get_jwt_identity())
    conv = Conversation.query.get(conv_id)
    if not conv or conv.user_id != user_id:
        return jsonify({"code": 404, "message": "对话不存在"}), 404

    data = request.get_json()
    user_content = data.get("content", "").strip()
    if not user_content:
        return jsonify({"code": 400, "message": "消息内容不能为空"}), 400

    # 保存用户消息
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=user_content
    )
    db.session.add(user_msg)
    db.session.flush()

    # 更新对话标题（仅第一条消息时）
    msg_count = Message.query.filter_by(conversation_id=conv_id).count()
    if msg_count <= 1:
        title = user_content[:30] + ("..." if len(user_content) > 30 else "")
        conv.title = title

    # 获取历史对话（用于上下文）
    history_messages = (
        Message.query
        .filter_by(conversation_id=conv_id)
        .filter(Message.id != user_msg.id)
        .order_by(Message.created_at)
        .all()
    )
    conversation_history = [
        {"role": m.role, "content": m.content}
        for m in history_messages
    ]

    # RAG检索
    context_items = []
    try:
        context_items = rag.search_knowledge(user_content)
        # 调试日志：打印检索结果
        if context_items:
            print(f"[RAG] 查询: {user_content!r}, 检索到 {len(context_items)} 条结果:")
            for item in context_items:
                print(f"  - 分数:{item['score']}, KB:{item['kb_name']}, 内容前50字: {item['content'][:50]!r}")
        else:
            print(f"[RAG] 查询: {user_content!r}, 无相关结果（阈值过滤后）")

        # 二次过滤：只有极短的问候语（<=4字，如"你好""谢谢"）才不使用知识库
        # 避免"Coze是什么"(7字)、"Coze核心能力"(9字)等有效问题被误判为闲聊
        question_length = len(user_content.strip())
        is_chitchat = question_length <= 4
        if is_chitchat and context_items:
            print(f"[RAG] 问题字数={question_length}，判定为闲聊，忽略检索结果")
            context_items = []
    except Exception as e:
        print(f"WARNING: RAG search failed: {e}")

    # 生成AI回答
    try:
        answer = rag.generate_answer(user_content, context_items, conversation_history)
    except Exception as e:
        answer = f"抱歉，AI服务暂时不可用，请稍后再试。错误信息：{str(e)}"

    # 查询每个 context_item 对应的文档原始名称
    def get_doc_filename(doc_id_str):
        try:
            from models import Document
            doc_obj = Document.query.get(int(doc_id_str))
            return doc_obj.original_filename if doc_obj else ""
        except:
            return ""

    # 构造完整 source 信息（含页码和文件名）
    full_sources = []
    for item in context_items:
        full_sources.append({
            "kb_name": item["kb_name"],
            "doc_id": item.get("doc_id", ""),
            "page_num": item.get("page_num", 1),
            "filename": get_doc_filename(item.get("doc_id", "")),
            "content_preview": item["content"][:100],
            "score": item["score"]
        })

    # 保存AI消息
    sources_json = json.dumps(full_sources, ensure_ascii=False)

    ai_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=answer,
        sources=sources_json
    )
    db.session.add(ai_msg)

    # 更新对话更新时间
    from datetime import datetime
    conv.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "code": 200,
        "data": {
            "user_message": user_msg.to_dict(),
            "assistant_message": ai_msg.to_dict(),
            "has_knowledge": len(context_items) > 0,
            "sources": full_sources
        }
    })
