import os
import threading
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, User, KnowledgeBase, Document
import rag

admin_bp = Blueprint("admin", __name__)


def admin_required(fn):
    """管理员权限装饰器"""
    from functools import wraps
    from flask_jwt_extended import verify_jwt_in_request
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user or user.role != "admin":
            return jsonify({"code": 403, "message": "需要管理员权限"}), 403
        return fn(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    from config import Config
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in Config.ALLOWED_EXTENSIONS


def get_file_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return "PDF"
    elif ext in ("docx", "doc"):
        return "Word"
    return "Unknown"


# ==================== 知识库管理 ====================

@admin_bp.route("/knowledge-bases", methods=["GET"])
@admin_required
def list_knowledge_bases():
    kbs = KnowledgeBase.query.order_by(KnowledgeBase.created_at.desc()).all()
    return jsonify({"code": 200, "data": [kb.to_dict() for kb in kbs]})


@admin_bp.route("/knowledge-bases", methods=["POST"])
@admin_required
def create_knowledge_base():
    data = request.get_json()
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return jsonify({"code": 400, "message": "知识库名称不能为空"}), 400

    if KnowledgeBase.query.filter_by(name=name).first():
        return jsonify({"code": 400, "message": "知识库名称已存在"}), 400

    kb = KnowledgeBase(name=name, description=description)
    db.session.add(kb)
    db.session.commit()

    return jsonify({"code": 200, "message": "知识库创建成功", "data": kb.to_dict()})


@admin_bp.route("/knowledge-bases/<int:kb_id>", methods=["DELETE"])
@admin_required
def delete_knowledge_base(kb_id):
    kb = KnowledgeBase.query.get(kb_id)
    if not kb:
        return jsonify({"code": 404, "message": "知识库不存在"}), 404

    # 删除关联文档的向量索引
    for doc in kb.documents:
        rag.delete_document_index(doc.id)
        # 删除文件
        try:
            if os.path.exists(doc.filename):
                os.remove(doc.filename)
        except:
            pass

    db.session.delete(kb)
    db.session.commit()

    return jsonify({"code": 200, "message": "知识库删除成功"})


# ==================== 文档管理 ====================

@admin_bp.route("/documents", methods=["GET"])
@admin_required
def list_documents():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    status = request.args.get("status", "")
    keyword = request.args.get("keyword", "").strip()

    query = Document.query
    if status:
        query = query.filter_by(status=status)
    if keyword:
        query = query.filter(Document.original_filename.contains(keyword))
    kb_id_filter = request.args.get("kb_id", type=int)
    if kb_id_filter:
        query = query.filter_by(kb_id=kb_id_filter)

    pagination = query.order_by(Document.upload_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "code": 200,
        "data": {
            "items": [doc.to_dict() for doc in pagination.items],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages
        }
    })


@admin_bp.route("/documents/stats", methods=["GET"])
@admin_required
def get_document_stats():
    total = Document.query.count()
    success = Document.query.filter_by(status="success").count()
    indexing = Document.query.filter_by(status="indexing").count()
    failed = Document.query.filter_by(status="failed").count()
    return jsonify({
        "code": 200,
        "data": {
            "total": total,
            "success": success,
            "indexing": indexing,
            "failed": failed
        }
    })


@admin_bp.route("/documents/upload", methods=["POST"])
@admin_required
def upload_document():
    from config import Config

    if "file" not in request.files:
        return jsonify({"code": 400, "message": "未找到上传文件"}), 400

    file = request.files["file"]
    kb_id = request.form.get("kb_id", type=int)

    if not file or not file.filename:
        return jsonify({"code": 400, "message": "文件名不能为空"}), 400

    if not allowed_file(file.filename):
        return jsonify({"code": 400, "message": "不支持的文件格式，仅支持 PDF 和 Word 文档"}), 400

    if not kb_id:
        return jsonify({"code": 400, "message": "请选择所属知识库"}), 400

    kb = KnowledgeBase.query.get(kb_id)
    if not kb:
        return jsonify({"code": 404, "message": "所选知识库不存在"}), 404

    # 查重：同一知识库内不允许上传文件名完全相同的文档
    original_filename = file.filename
    existing = Document.query.filter_by(
        kb_id=kb_id,
        original_filename=original_filename
    ).first()
    if existing:
        return jsonify({
            "code": 400,
            "message": f"该知识库中已存在同名文档『{original_filename}』，请勿重复上传"
        }), 400

    # 保存文件
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    safe_name = secure_filename(file.filename)
    # 避免文件名冲突
    import uuid
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
    file.save(file_path)

    file_type = get_file_type(original_filename)

    # 创建文档记录
    doc = Document(
        kb_id=kb_id,
        filename=file_path,
        original_filename=original_filename,
        file_type=file_type,
        status="indexing"
    )
    db.session.add(doc)
    db.session.commit()
    doc_id = doc.id

    # 后台异步处理索引
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_async_index_document,
        args=(app, doc_id, file_path, file_type, kb.name)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        "code": 200,
        "message": "文件上传成功，正在后台建立索引",
        "data": doc.to_dict()
    })


def _async_index_document(app, doc_id, file_path, file_type, kb_name):
    """后台线程：对文档进行索引处理"""
    with app.app_context():
        doc = Document.query.get(doc_id)
        if not doc:
            return
        try:
            chunk_count = rag.index_document(doc_id, file_path, file_type, kb_name)
            doc.status = "success"
            doc.chunk_count = chunk_count
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
        db.session.commit()


@admin_bp.route("/documents/<int:doc_id>", methods=["DELETE"])
@admin_required
def delete_document(doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"code": 404, "message": "文档不存在"}), 404

    # 删除向量索引
    rag.delete_document_index(doc_id)

    # 删除文件
    try:
        if os.path.exists(doc.filename):
            os.remove(doc.filename)
    except:
        pass

    db.session.delete(doc)
    db.session.commit()

    return jsonify({"code": 200, "message": "文档删除成功"})


@admin_bp.route("/documents/<int:doc_id>/retry", methods=["POST"])
@admin_required
def retry_document(doc_id):
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"code": 404, "message": "文档不存在"}), 404

    if not os.path.exists(doc.filename):
        return jsonify({"code": 400, "message": "原始文件不存在，无法重试"}), 400

    doc.status = "indexing"
    doc.error_message = ""
    doc.chunk_count = 0
    db.session.commit()

    app = current_app._get_current_object()
    kb_name = doc.knowledge_base.name if doc.knowledge_base else ""
    thread = threading.Thread(
        target=_async_index_document,
        args=(app, doc_id, doc.filename, doc.file_type, kb_name)
    )
    thread.daemon = True
    thread.start()

    return jsonify({"code": 200, "message": "已重新提交索引任务"})


@admin_bp.route("/documents/<int:doc_id>/file", methods=["GET"])
def view_document_file(doc_id):
    """通过 token 查询参数验证权限后，返回文档文件内容（PDF内联预览，Word下载）"""
    from flask import send_file
    from flask_jwt_extended import decode_token

    token = request.args.get("token", "")
    if not token:
        return jsonify({"code": 401, "message": "缺少认证 Token"}), 401

    try:
        decoded = decode_token(token)
        user_id = int(decoded["sub"])
        user = User.query.get(user_id)
        if not user or user.role != "admin":
            return jsonify({"code": 403, "message": "需要管理员权限"}), 403
    except Exception:
        return jsonify({"code": 401, "message": "Token 无效或已过期"}), 401

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"code": 404, "message": "文档不存在"}), 404

    if not os.path.exists(doc.filename):
        return jsonify({"code": 404, "message": "文件不存在（可能已被删除）"}), 404

    # PDF：内联预览；Word：触发下载
    is_pdf = doc.file_type == "PDF"
    return send_file(
        doc.filename,
        download_name=doc.original_filename,
        as_attachment=not is_pdf,
        mimetype="application/pdf" if is_pdf else "application/octet-stream"
    )


# ==================== 普通用户文档查看接口（引用标注跳转使用）====================

@admin_bp.route("/public/documents/<int:doc_id>/file", methods=["GET"])
def view_document_file_public(doc_id):
    """
    普通已登录用户可访问的文档查看接口（用于引用标注点击跳转）
    通过 token 查询参数验证已登录身份（不要求管理员权限）
    """
    from flask import send_file
    from flask_jwt_extended import decode_token

    token = request.args.get("token", "")
    if not token:
        return jsonify({"code": 401, "message": "缺少认证 Token"}), 401

    try:
        decoded = decode_token(token)
        user_id = int(decoded["sub"])
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 401, "message": "用户不存在或 Token 无效"}), 401
    except Exception:
        return jsonify({"code": 401, "message": "Token 无效或已过期"}), 401

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"code": 404, "message": "文档不存在"}), 404

    if not os.path.exists(doc.filename):
        return jsonify({"code": 404, "message": "文件不存在（可能已被删除）"}), 404

    # PDF：内联预览（浏览器支持 #page=N 锚点跳转）；Word：触发下载
    is_pdf = doc.file_type == "PDF"
    return send_file(
        doc.filename,
        download_name=doc.original_filename,
        as_attachment=not is_pdf,
        mimetype="application/pdf" if is_pdf else "application/octet-stream"
    )

