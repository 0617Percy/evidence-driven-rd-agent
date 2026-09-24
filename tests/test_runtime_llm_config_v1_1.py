# -*- coding: utf-8 -*-
"""
Runtime LLM Config V1.1 离线测试。

原则：
- 不调用真实 LLM / Retriever。
- 不修改 os.environ（resolve 只读）。
- 测试写入临时目录，不污染正式 JSONL。
- 使用假 Key sk-test-DO-NOT-LEAK-123456 验证不泄漏。
"""

import json
import os
import shutil
import sys
from pathlib import Path
from unittest import mock
from uuid import uuid4


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import runtime_llm_config_v1_1 as rc  # noqa: E402


FAKE_KEY = "sk-test-DO-NOT-LEAK-123456"

ENV_FULL = {
    "LLM_PROVIDER": "",
    "LLM_MODEL": "env-model",
    "LLM_BASE_URL": "https://api.env.example",
    "LLM_API_KEY": "env-key",
}


def make_tmp():
    root = ROOT / "outputs" / "knowledge_feedback" / "test"
    root.mkdir(parents=True, exist_ok=True)
    p = root / ("rc_" + uuid4().hex)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ------------------------------------------------------------
# Runtime Config core
# ------------------------------------------------------------

def test_rc01_env_only():
    cfg = rc.resolve_runtime_llm_config(env=dict(ENV_FULL))

    assert cfg.model == "env-model"
    assert cfg.base_url == "https://api.env.example"
    assert cfg.api_key == "env-key"
    assert cfg.config_source == "ENV"


def test_rc02_session_override_model_only():
    cfg = rc.resolve_runtime_llm_config(
        session_overrides={"model": "session-model"},
        env=dict(ENV_FULL),
    )

    assert cfg.model == "session-model"
    assert cfg.base_url == "https://api.env.example"  # fallback env
    assert cfg.api_key == "env-key"  # fallback env
    assert cfg.config_source == "SESSION"


def test_rc03_session_own_api_key():
    cfg = rc.resolve_runtime_llm_config(
        session_overrides={"api_key": "session-key"},
        env=dict(ENV_FULL),
    )

    assert cfg.api_key == "session-key"


def test_rc04_key_not_in_repr_str_public():
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="m",
        base_url="https://x",
        api_key=FAKE_KEY,
    )

    assert FAKE_KEY not in repr(cfg)
    assert FAKE_KEY not in str(cfg)
    assert FAKE_KEY not in json.dumps(
        cfg.to_public_dict(),
        ensure_ascii=False,
    )
    assert FAKE_KEY not in json.dumps(
        rc.public_runtime_summary(cfg),
        ensure_ascii=False,
    )
    # public dict 只给 api_key_available，不给 key
    d = cfg.to_public_dict()
    assert "api_key" not in d
    assert d["api_key_available"] is True


def test_rc05_no_api_key_hold():
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="m",
        base_url="https://x",
        api_key="",
    )

    errors = rc.validate_runtime_llm_config(cfg)
    assert any("API Key" in e for e in errors)


def test_rc06_invalid_base_url_hold():
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="m",
        base_url="ftp://bad",
        api_key="k",
    )

    errors = rc.validate_runtime_llm_config(cfg)
    assert any("http" in e for e in errors)


def test_rc07_valid_deepseek_pass():
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key="k",
    )

    assert rc.validate_runtime_llm_config(cfg) == []


def test_rc08_custom_openai_compatible_pass():
    cfg = rc.RuntimeLLMConfig(
        provider="Custom OpenAI-compatible",
        model="gpt-4o-mini",
        base_url="https://api.custom.example/v1",
        api_key="k",
    )

    assert rc.validate_runtime_llm_config(cfg) == []


def test_rc09_restore_env_clears_override():
    # 模拟：应用 override -> 恢复（清空 override）
    applied = rc.resolve_runtime_llm_config(
        session_overrides={"model": "session-model"},
        env=dict(ENV_FULL),
    )

    assert applied.config_source == "SESSION"

    restored = rc.resolve_runtime_llm_config(
        session_overrides=None,
        env=dict(ENV_FULL),
    )

    assert restored.config_source == "ENV"
    assert restored.model == "env-model"


def test_rc10_no_os_environ_mutation():
    keys = ["LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_PROVIDER"]
    before = {k: os.environ.get(k) for k in keys}

    cfg = rc.resolve_runtime_llm_config(
        session_overrides={
            "model": "session-model",
            "api_key": "session-key",
        },
        env=dict(ENV_FULL),
    )

    after = {k: os.environ.get(k) for k in keys}

    assert before == after
    assert cfg.api_key == "session-key"  # 只在对象内存，不在 env


# ------------------------------------------------------------
# Answer compatibility（mock，不真实调用 LLM / Retriever）
# ------------------------------------------------------------

def test_answer_compat():
    import live_answer_service_v1 as svc

    captured = {}

    class _Completions:
        def create(self, **kwargs):
            captured["model"] = kwargs.get("model")
            raise RuntimeError("SENTINEL_STOP")

    class _Chat:
        completions = _Completions()

    class _LLM:
        def __init__(self, **kwargs):
            captured["api_key"] = kwargs.get("api_key")
            captured["base_url"] = kwargs.get("base_url")

        chat = _Chat()

    class _Qdrant:
        def __init__(self, **kwargs):
            pass

        def close(self):
            pass

    class _Embedder:
        def __init__(self, **kwargs):
            pass

    svc.OpenAI = _LLM
    svc.QdrantClient = _Qdrant
    svc.TextEmbedding = _Embedder
    svc.retriever.DB_PATH = "fake"
    svc.retriever.MODEL_NAME = "fake"
    svc.retriever.search = lambda *a, **k: []

    # 1) 旧方式：run_live(query) 使用 env
    with mock.patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "env-key",
            "LLM_BASE_URL": "https://env.example",
            "LLM_MODEL": "env-model",
        },
    ):
        try:
            svc.run_live("汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次")
        except RuntimeError as exc:
            assert "SENTINEL_STOP" in str(exc)

        assert captured["api_key"] == "env-key"
        assert captured["base_url"] == "https://env.example"
        assert captured["model"] == "env-model"

    # 2) 新方式：run_live(query, runtime_config=config) 使用传入 config
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="cfg-model",
        base_url="https://cfg.example",
        api_key="cfg-key",
    )

    try:
        svc.run_live("汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次", runtime_config=cfg)
    except RuntimeError as exc:
        assert "SENTINEL_STOP" in str(exc)

    assert captured["api_key"] == "cfg-key"
    assert captured["base_url"] == "https://cfg.example"
    assert captured["model"] == "cfg-model"


# ------------------------------------------------------------
# Curator compatibility（mock，不真实调用 LLM）
# ------------------------------------------------------------

def test_curator_compat(tmp_path):
    import knowledge_curator_v0_2 as kc

    captured = {}

    def _fake_call(curator_input, client, model):
        captured["model"] = model
        raise RuntimeError("SENTINEL_STOP")

    kc._call_curator_llm = _fake_call
    kc._build_client_from_env = lambda: ("fake-client", "env-model")
    kc._build_client_from_config = lambda c: ("fake-client", c.model)

    result = {
        "query": "测试问题",
        "evidence": [
            {
                "chunk_id": "CK-0062",
                "title": "测试",
                "source": "08_问题案例/cases.csv",
                "doc_type": "问题案例",
                "text": "测试文本",
            }
        ],
        "structured_output": {
            "risk_summary": "r",
            "condition_gap": [],
            "evidence_gap": {"statement": "gap", "source_refs": ["CK-0062"]},
            "evidence_level": [],
            "recommended_validation": [],
        },
        "safety": {
            "status": "PASS",
            "citation_correctness": "PASS",
            "unsupported_claim_count": 0,
        },
    }

    # 1) 旧方式：run_knowledge_curator(result) -> env
    kc.run_knowledge_curator(result, base_dir=tmp_path)
    assert captured["model"] == "env-model"

    # 2) 新方式：runtime_config -> 使用 config.model
    cfg = rc.RuntimeLLMConfig(
        provider="DeepSeek",
        model="cfg-model",
        base_url="https://cfg.example",
        api_key="cfg-key",
    )

    kc.run_knowledge_curator(
        result,
        base_dir=tmp_path,
        runtime_config=cfg,
    )
    assert captured["model"] == "cfg-model"


# ------------------------------------------------------------
# Secret leakage（假 Key 不得出现在正式 runtime JSONL）
# ------------------------------------------------------------

def test_secret_leakage():
    feedback = ROOT / "outputs" / "knowledge_feedback"

    for name in ["query_traces.jsonl", "kb_update_candidates.jsonl"]:
        p = feedback / name

        if p.exists():
            content = p.read_text(encoding="utf-8")
            assert FAKE_KEY not in content


def run_all():
    tmp_path = make_tmp()

    try:
        tests = [
            test_rc01_env_only,
            test_rc02_session_override_model_only,
            test_rc03_session_own_api_key,
            test_rc04_key_not_in_repr_str_public,
            test_rc05_no_api_key_hold,
            test_rc06_invalid_base_url_hold,
            test_rc07_valid_deepseek_pass,
            test_rc08_custom_openai_compatible_pass,
            test_rc09_restore_env_clears_override,
            test_rc10_no_os_environ_mutation,
            test_answer_compat,
            test_curator_compat,
            test_secret_leakage,
        ]

        for test in tests:
            try:
                if test is test_curator_compat:
                    test(tmp_path)

                else:
                    test()

                print("PASS", test.__name__)

            except Exception as exc:
                print("FAIL", test.__name__, "->", repr(exc))
                raise

    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    run_all()
    print("ALL_RUNTIME_CONFIG_TESTS_PASS")
