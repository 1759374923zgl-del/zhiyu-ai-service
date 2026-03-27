import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT配置（从环境变量读取，未设置则使用默认值）
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "zhiyu-ai-customer-service-secret-2024")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}

    # 智谱AI配置（从环境变量读取，不硬编码敏感密钥）
    ZHIPUAI_API_KEY = os.environ.get("ZHIPUAI_API_KEY", "")
    ZHIPUAI_MODEL = "glm-4-flash"  # GLM-4.7-Flash 对应的 API model name
    ZHIPUAI_EMBEDDING_MODEL = "embedding-3"

    # ChromaDB 配置
    CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

    # RAG配置
    CHUNK_SIZE = 500        # 每个文档分块大小（字符数）
    CHUNK_OVERLAP = 50      # 分块重叠大小
    TOP_K = 5              # 检索Top-K个结果
    SIMILARITY_THRESHOLD = 0.3  # 相似度阈值（cosine: 1-dist/2, 范围[0,1]，0.3约等于原始距离1.4）
