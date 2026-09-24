# -*- coding: utf-8 -*-
"""
Runtime LLM Config V1.1（独立模块）

统一 Answer LLM 与 Knowledge Curator LLM 的运行时配置。

支持两种来源：
    A. Environment Config（.env / environment variables）
    B. Session Runtime Override（页面本次会话临时配置）

优先级：Session 非空 Override > Environment Config。

安全约定：
    - 绝不写 os.environ（不把用户输入写回环境变量）
    - api_key 只存在于内存对象 + Streamlit session_state
    - repr / str / public dict 绝不含 api_key
    - 不把 api_key 写入磁盘 / 日志 / trace / candidate

V1.1 只支持 OpenAI-compatible client：
    - DeepSeek：OpenAI-compatible client + DeepSeek 配置
    - Custom OpenAI-compatible：同一 client + 自定义 model/base_url/api_key
"""

import os
from dataclasses import dataclass, field


PROVIDER_DEEPSEEK = "DeepSeek"
PROVIDER_CUSTOM = "Custom OpenAI-compatible"

PROVIDERS = [
    PROVIDER_DEEPSEEK,
    PROVIDER_CUSTOM,
]

# 环境变量名（只读，绝不回写）
ENV_PROVIDER = "LLM_PROVIDER"
ENV_MODEL = "LLM_MODEL"
ENV_BASE_URL = "LLM_BASE_URL"
ENV_API_KEY = "LLM_API_KEY"


@dataclass
class RuntimeLLMConfig:
    provider: str = PROVIDER_DEEPSEEK
    model: str = ""
    base_url: str = ""
    api_key: str = field(default="", repr=False)
    temperature: float = 0.0
    timeout: float = None
    config_source: str = "ENV"

    def to_public_dict(self):
        """公开字典：绝不包含 api_key。"""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "config_source": self.config_source,
            "api_key_available": bool(self.api_key),
        }

    def public_summary(self):
        d = self.to_public_dict()

        source = (
            "本次会话"
            if d["config_source"] == "SESSION"
            else "本机环境"
        )

        return (
            "Provider："
            + (d["provider"] or "（未配置）")
            + "｜Model："
            + (d["model"] or "（未配置）")
            + "｜Base URL："
            + (d["base_url"] or "（未配置）")
            + "｜API Key："
            + ("已配置" if d["api_key_available"] else "未配置")
            + "｜来源："
            + source
        )

    def __str__(self):
        return self.public_summary()


def _read_env(env=None):
    """读取环境配置。env 参数仅供测试注入，不写 os.environ。"""
    if env is not None:
        src = env

    else:
        try:
            from dotenv import load_dotenv

            load_dotenv()

        except Exception:
            pass

        src = os.environ

    return {
        "provider": (src.get(ENV_PROVIDER) or "").strip(),
        "model": (src.get(ENV_MODEL) or "").strip(),
        "base_url": (src.get(ENV_BASE_URL) or "").strip(),
        "api_key": (src.get(ENV_API_KEY) or "").strip(),
    }


def resolve_runtime_llm_config(
    session_overrides=None,
    env=None,
):
    """
    Session 非空 Override > Environment Config（field-level）。

    - 某个 Session 字段非空：使用 Session 值。
    - 某个 Session 字段为空：fallback 环境值。
    - 绝不写 os.environ。
    """
    e = _read_env(env)

    overrides = session_overrides or {}

    def pick(key):
        value = (overrides.get(key) or "").strip()

        if value:
            return value

        return e.get(key) or ""

    provider = pick("provider") or PROVIDER_DEEPSEEK
    model = pick("model")
    base_url = pick("base_url")
    api_key = pick("api_key")

    has_override = any(
        (overrides.get(k) or "").strip()
        for k in ["provider", "model", "base_url", "api_key"]
    )

    return RuntimeLLMConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        config_source="SESSION" if has_override else "ENV",
    )


def validate_runtime_llm_config(config):
    """
    轻量校验（不联网、不调用 API）。

    返回错误列表；空列表 = 通过。
    """
    errors = []

    if not (config.model or "").strip():
        errors.append("未配置模型（Model）。")

    base_url = (config.base_url or "").strip()

    if not base_url:
        errors.append("未配置 Base URL。")

    elif not (
        base_url.startswith("http://")
        or base_url.startswith("https://")
    ):
        errors.append("Base URL 必须以 http:// 或 https:// 开头。")

    if not (config.api_key or "").strip():
        errors.append("未配置 API Key。")

    return errors


def public_runtime_summary(config):
    """公开摘要：绝不包含 api_key。"""
    return config.to_public_dict()
