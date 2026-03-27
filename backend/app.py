import os
from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
from models import db, User, KnowledgeBase

def create_app():
    app = Flask(__name__, static_folder="../frontend", static_url_path="")
    app.config.from_object(Config)

    # 初始化扩展
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 注册蓝图
    from auth import auth_bp
    from admin import admin_bp
    from chat import chat_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")

    # 静态文件路由
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/admin.html")
    def admin_page():
        return send_from_directory(app.static_folder, "admin.html")

    @app.route("/chat.html")
    def chat_page():
        return send_from_directory(app.static_folder, "chat.html")

    # 健康检查
    @app.route("/api/health")
    def health():
        return {"code": 200, "message": "服务运行正常"}

    # 初始化数据库和默认数据
    with app.app_context():
        db.create_all()
        _init_default_data()

    return app


def _init_default_data():
    """初始化默认管理员账号和知识库"""
    # 创建默认管理员
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        print("[INFO] 已创建默认管理员账号: admin / admin123")

    # 创建默认知识库
    default_kbs = ["销售核心库", "技术支持库", "行政管理库", "售后服务库"]
    for kb_name in default_kbs:
        if not KnowledgeBase.query.filter_by(name=kb_name).first():
            kb = KnowledgeBase(name=kb_name, description=f"{kb_name}相关文档")
            db.session.add(kb)

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    port = int(os.environ.get("PORT", 5000))
    print("[INFO] 智语AI客服平台启动中...")
    print(f"[INFO] 访问地址: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
