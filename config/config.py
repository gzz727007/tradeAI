import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class SystemConfig:
    # 路径配置
    PROJECT_ROOT: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    
    # 数据库配置 (默认本地 SQLite 事务数据库，支持无缝配置为 PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'data' / 'trade_ai.db').as_posix()}"
    )
    
    # LLM API 配置
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    GEMINI_FLASH_MODEL: str = os.getenv("GEMINI_FLASH_MODEL", "gemini-2.5-flash")
    GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
    
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen2.5-72b-instruct")
    
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # 消息通知
    FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")
    SERVERCHAN_KEY: str = os.getenv("SERVERCHAN_KEY", "")
    
    # 可转债量化默认参数
    DEFAULT_DOUBLE_LOW_WEIGHT: float = 1.0  # 双低 = 价格 + 溢价率 * 100 * weight
    MAX_PRICE: float = 130.0                # 高价保护上限 (超过 130 强赎与估值风险大)
    MIN_PRICE: float = 90.0                 # 极低价地板 (低于 90 需严防退市违约)
    MAX_REMAINING_SCALE: float = 8.0        # 剩余规模上限 (8亿以下弹性较好)
    PORTFOLIO_TOP_N: int = 15               # 组合持仓标的数 (建议 10~15 只做分散)
    
    # 交易摩擦
    COMMISSION_RATE: float = 0.00005        # 券商佣金 万0.5
    SLIPPAGE_RATE: float = 0.001            # 滑点 0.1%

settings = SystemConfig()
