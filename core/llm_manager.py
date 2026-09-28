"""
大模型与多智能体统一管理模块 (LLM & Provider Manager)
支持 DeepSeek / 通义千问 (Qwen) / Google Gemini / OpenAI 兼容接口的统一调度、配置持久化与连通性测试。
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from dotenv import set_key, load_dotenv
from config.config import settings, BASE_DIR

ENV_PATH = BASE_DIR / ".env"

PROVIDER_PRESETS = {
    "deepseek": {
        "name": "DeepSeek (深度求索)",
        "desc": "高性价比、推理逻辑强，量化金融与代码分析首选",
        "default_base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "token_url": "https://platform.deepseek.com/api_keys"
    },
    "qwen": {
        "name": "通义千问 (Qwen / 阿里云百炼)",
        "desc": "中文商业与财报理解力极佳，官方兼容 OpenAI 接口",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen2.5-72b-instruct"],
        "token_url": "https://bailian.console.aliyun.com/"
    },
    "gemini": {
        "name": "Google Gemini",
        "desc": "超长上下文、极速响应与综合推理",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
        "token_url": "https://aistudio.google.com/apikey"
    },
    "openai": {
        "name": "OpenAI / 自定义兼容中转",
        "desc": "支持官方 OpenAI、月之暗面 Kimi、智谱 GLM、硅基流动或本地 Ollama",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "moonshot-v1-8k", "glm-4-flash"],
        "token_url": "https://platform.openai.com/api-keys"
    }
}

class LLMManager:
    """全平台统一大模型管理器"""

    def __init__(self):
        self._ensure_env_exists()

    def _ensure_env_exists(self):
        if not ENV_PATH.exists():
            try:
                ENV_PATH.touch()
            except Exception as e:
                print(f"[WARN] 无法创建 .env 文件: {e}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前系统的大模型配置状态（API Key 脱敏）"""
        active_provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek")
        
        # 探测当前哪个供应商有配置 Key
        providers_status = {}
        for p_key, p_info in PROVIDER_PRESETS.items():
            if p_key == "deepseek":
                key = os.getenv("DEEPSEEK_API_KEY", "")
                base_url = os.getenv("DEEPSEEK_BASE_URL", p_info["default_base_url"])
                model = os.getenv("DEEPSEEK_MODEL", p_info["default_model"])
            elif p_key == "qwen":
                key = os.getenv("QWEN_API_KEY", "")
                base_url = os.getenv("QWEN_BASE_URL", p_info["default_base_url"])
                model = os.getenv("QWEN_MODEL", p_info["default_model"])
            elif p_key == "gemini":
                key = os.getenv("GEMINI_API_KEY", "")
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                model = os.getenv("GEMINI_FLASH_MODEL", p_info["default_model"])
            else:
                key = os.getenv("OPENAI_API_KEY", "")
                base_url = os.getenv("OPENAI_BASE_URL", p_info["default_base_url"])
                model = os.getenv("OPENAI_MODEL", p_info["default_model"])

            masked_key = ""
            if key:
                if len(key) > 8:
                    masked_key = f"{key[:4]}****{key[-4:]}"
                else:
                    masked_key = "****"

            providers_status[p_key] = {
                "name": p_info["name"],
                "desc": p_info["desc"],
                "is_configured": bool(key),
                "masked_key": masked_key,
                "base_url": base_url,
                "model": model,
                "preset_models": p_info["models"],
                "token_url": p_info["token_url"]
            }

        # 检查当前激活的 Key 是否有效
        active_info = providers_status.get(active_provider, providers_status["deepseek"])

        return {
            "active_provider": active_provider,
            "is_ready": active_info["is_configured"],
            "providers": providers_status
        }

    def save_config(self, provider: str, api_key: str, base_url: str = "", model: str = "") -> Dict[str, Any]:
        """保存大模型配置并持久化写入 .env"""
        if provider not in PROVIDER_PRESETS:
            raise ValueError(f"不支持的供应商: {provider}")

        self._ensure_env_exists()
        preset = PROVIDER_PRESETS[provider]
        final_base_url = base_url.strip() if base_url.strip() else preset["default_base_url"]
        final_model = model.strip() if model.strip() else preset["default_model"]

        # 更新环境变量及 .env 文件
        set_key(str(ENV_PATH), "ACTIVE_LLM_PROVIDER", provider)
        os.environ["ACTIVE_LLM_PROVIDER"] = provider

        if provider == "deepseek":
            if api_key.strip():
                set_key(str(ENV_PATH), "DEEPSEEK_API_KEY", api_key.strip())
                os.environ["DEEPSEEK_API_KEY"] = api_key.strip()
                settings.DEEPSEEK_API_KEY = api_key.strip()
            set_key(str(ENV_PATH), "DEEPSEEK_BASE_URL", final_base_url)
            set_key(str(ENV_PATH), "DEEPSEEK_MODEL", final_model)
            os.environ["DEEPSEEK_BASE_URL"] = final_base_url
            os.environ["DEEPSEEK_MODEL"] = final_model
            settings.DEEPSEEK_BASE_URL = final_base_url
            settings.DEEPSEEK_MODEL = final_model

        elif provider == "qwen":
            if api_key.strip():
                set_key(str(ENV_PATH), "QWEN_API_KEY", api_key.strip())
                os.environ["QWEN_API_KEY"] = api_key.strip()
                settings.QWEN_API_KEY = api_key.strip()
            set_key(str(ENV_PATH), "QWEN_BASE_URL", final_base_url)
            set_key(str(ENV_PATH), "QWEN_MODEL", final_model)
            os.environ["QWEN_BASE_URL"] = final_base_url
            os.environ["QWEN_MODEL"] = final_model
            settings.QWEN_BASE_URL = final_base_url
            settings.QWEN_MODEL = final_model

        elif provider == "gemini":
            if api_key.strip():
                set_key(str(ENV_PATH), "GEMINI_API_KEY", api_key.strip())
                os.environ["GEMINI_API_KEY"] = api_key.strip()
                settings.GEMINI_API_KEY = api_key.strip()
            set_key(str(ENV_PATH), "GEMINI_FLASH_MODEL", final_model)
            set_key(str(ENV_PATH), "GEMINI_PRO_MODEL", final_model)
            os.environ["GEMINI_FLASH_MODEL"] = final_model
            os.environ["GEMINI_PRO_MODEL"] = final_model
            settings.GEMINI_FLASH_MODEL = final_model
            settings.GEMINI_PRO_MODEL = final_model

        elif provider == "openai":
            if api_key.strip():
                set_key(str(ENV_PATH), "OPENAI_API_KEY", api_key.strip())
                os.environ["OPENAI_API_KEY"] = api_key.strip()
            set_key(str(ENV_PATH), "OPENAI_BASE_URL", final_base_url)
            set_key(str(ENV_PATH), "OPENAI_MODEL", final_model)
            os.environ["OPENAI_BASE_URL"] = final_base_url
            os.environ["OPENAI_MODEL"] = final_model

        return {"success": True, "message": f"成功保存 {preset['name']} 配置", "config": self.get_config()}

    def test_connection(self, provider: str, api_key: str = "", base_url: str = "", model: str = "") -> Dict[str, Any]:
        """连通性实时测试：发送一条极简 ping 探测延迟与鉴权结果"""
        from openai import OpenAI
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["deepseek"])
        
        # 如果未传入 key 则从已有配置读取
        test_key = api_key.strip()
        if not test_key:
            if provider == "deepseek": test_key = os.getenv("DEEPSEEK_API_KEY", "")
            elif provider == "qwen": test_key = os.getenv("QWEN_API_KEY", "")
            elif provider == "gemini": test_key = os.getenv("GEMINI_API_KEY", "")
            elif provider == "openai": test_key = os.getenv("OPENAI_API_KEY", "")

        if not test_key:
            return {"success": False, "error": "请先输入 API Key / Token 后再测试连接"}

        test_base_url = base_url.strip() if base_url.strip() else preset["default_base_url"]
        test_model = model.strip() if model.strip() else preset["default_model"]

        t0 = time.time()
        try:
            client = OpenAI(
                api_key=test_key,
                base_url=test_base_url,
                timeout=12.0
            )
            # 发起测试请求
            resp = client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "请回答两个字：就绪"}],
                max_tokens=10,
                temperature=0.1
            )
            latency_ms = int((time.time() - t0) * 1000)
            reply = resp.choices[0].message.content.strip()
            return {
                "success": True,
                "latency_ms": latency_ms,
                "model": test_model,
                "reply": reply,
                "message": f"连接成功！模型 [{test_model}] 响应正常 (往返耗时 {latency_ms}ms)"
            }
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            err_msg = str(e)
            if "Authentication" in err_msg or "401" in err_msg or "invalid_api_key" in err_msg:
                friendly_err = "鉴权失败 (401)：API Key 无效或已被吊销，请检查输入的 Token"
            elif "Connection" in err_msg or "timeout" in err_msg.lower():
                friendly_err = f"网络连接超时：无法访问端点 {test_base_url}，请检查网络或是否需要代理"
            elif "404" in err_msg or "model_not_found" in err_msg:
                friendly_err = f"模型不存在 (404)：供应商端点未找到模型 [{test_model}]，请检查模型名称"
            else:
                friendly_err = f"测试请求失败: {err_msg[:120]}"

            return {
                "success": False,
                "latency_ms": latency_ms,
                "error": friendly_err
            }

    def get_client(self, preferred: Optional[str] = None) -> Tuple[Optional[Any], str]:
        """
        获取当前可用的大模型客户端与对应模型名称。
        全智能体自适应：若指定首选供应商有 Key，则优先使用；否则自动回退到任意已配置的供应商。
        :return: (OpenAI_client, model_name)
        """
        from openai import OpenAI
        active_provider = os.getenv("ACTIVE_LLM_PROVIDER", "deepseek")
        
        # 候选探测顺序
        check_order = [active_provider]
        if preferred and preferred not in check_order:
            check_order.insert(0, preferred)
        for p in ["deepseek", "qwen", "gemini", "openai"]:
            if p not in check_order:
                check_order.append(p)

        for p in check_order:
            preset = PROVIDER_PRESETS[p]
            key = ""
            base_url = preset["default_base_url"]
            model = preset["default_model"]

            if p == "deepseek":
                key = os.getenv("DEEPSEEK_API_KEY", "")
                base_url = os.getenv("DEEPSEEK_BASE_URL", base_url)
                model = os.getenv("DEEPSEEK_MODEL", model)
            elif p == "qwen":
                key = os.getenv("QWEN_API_KEY", "")
                base_url = os.getenv("QWEN_BASE_URL", base_url)
                model = os.getenv("QWEN_MODEL", model)
            elif p == "gemini":
                key = os.getenv("GEMINI_API_KEY", "")
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                model = os.getenv("GEMINI_FLASH_MODEL", model)
            elif p == "openai":
                key = os.getenv("OPENAI_API_KEY", "")
                base_url = os.getenv("OPENAI_BASE_URL", base_url)
                model = os.getenv("OPENAI_MODEL", model)

            if key and key.strip():
                try:
                    client = OpenAI(
                        api_key=key.strip(),
                        base_url=base_url,
                        timeout=30.0
                    )
                    return client, model
                except Exception as e:
                    print(f"[WARN] 构造 {p} LLM Client 失败: {e}")

        return None, ""

llm_manager = LLMManager()
