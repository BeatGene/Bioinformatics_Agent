"""
应用配置管理，从 .env 文件读取环境变量。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """全局配置单例"""

    # DeepSeek API
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # PubMed
    PUBMED_EMAIL: str = os.getenv("PUBMED_EMAIL", "")
    PUBMED_API_KEY: str = os.getenv("PUBMED_API_KEY", "")

    # App
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "7860"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # 数据路径
    DATA_DIR: Path = PROJECT_ROOT / "data"
    DB_PATH: Path = DATA_DIR / "bioinformatics_agent.db"

    @classmethod
    def ensure_dirs(cls):
        """确保数据目录存在"""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> bool:
        """验证必要配置是否完整"""
        if not cls.DEEPSEEK_API_KEY or "your-deepseek-api-key" in cls.DEEPSEEK_API_KEY:
            raise ValueError(
                "请在 .env 文件中设置有效的 DEEPSEEK_API_KEY。\n"
                "复制 .env.example 为 .env 并填入你的 API Key。"
            )
        return True


config = Config()
