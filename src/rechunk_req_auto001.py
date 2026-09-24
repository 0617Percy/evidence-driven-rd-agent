import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRUTH_SOURCE_DIR = (
    PROJECT_ROOT / "data" / "truth_source" / "模拟数据集_v1.0"
)

RAW_RAG = TRUTH_SOURCE_DIR / "12_AI训练语料" / "rag_chunks.jsonl"

RAW_SOURCE = TRUTH_SOURCE_DIR / "03_客户需求" / "需求说明书样例_汽车革客户.md"

OUT_DIR = Path("data") / "derived"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CORPUS = OUT_DIR / "rag_chunks_auto001_rc1.jsonl"
OUT_MANIFEST = Path("outputs") / "auto001_req_rechunk_manifest_v0_1.json"

NEW_CHUNK_ID = "CK-AUTO001-REQ-RC-001"
SOURCE_ID = "REQ-AUTO-001"
SOURCE_REL = "03_客户需求/需求说明书样例_汽车革客户.md"


def main():
    if not RAW_RAG.exists():
        raise FileNotFoundError(RAW_RAG)

    if not RAW_SOURCE.exists():
        raise FileNotFoundError(RAW_SOURCE)

    raw_text = RAW_SOURCE.read_text(
        encoding="utf-8-sig"
    ).strip()

    lines = raw_text.splitlines()

    # --------------------------------------------------
    # 前置事实核验
    # --------------------------------------------------

    checks = {
        "contains_HD_S303_surface":
            "HD-S303面层" in raw_text,
        "contains_minus30":
            "-30℃" in raw_text,
        "contains_50000":
            "5万次" in raw_text,
        "contains_auto_scene":
            (
                "汽车内饰" in raw_text
                or "仪表板包覆革" in raw_text
            ),
    }

    print("SOURCE_CHECK:", checks)

    if not all(checks.values()):
        raise RuntimeError(
            "SOURCE_FACT_CHECK_FAILED"
        )

    # --------------------------------------------------
    # 读取原始169 chunks
    # --------------------------------------------------

    chunks = []

    with RAW_RAG.open(
        "r",
        encoding="utf-8-sig",
    ) as f:
        for line in f:
            if line.strip():
                chunks.append(
                    json.loads(line)
                )

    print(
        "ORIGINAL_CORPUS_SIZE:",
        len(chunks),
    )

    if any(
        x.get("chunk_id") == NEW_CHUNK_ID
        for x in chunks
    ):
        raise RuntimeError(
            "NEW_CHUNK_ID_ALREADY_EXISTS"
        )

    # --------------------------------------------------
    # 合法 re-chunk
    #
    # 规则：
    # 原文件很短，且全文属于同一当前客户需求上下文，
    # 因此使用整篇文档作为一个语义完整chunk。
    #
    # 不摘取散句，不拼固定答案。
    # --------------------------------------------------

    new_chunk = {
        "chunk_id": NEW_CHUNK_ID,
        "doc_type": "客户需求",
        "title": (
            "客户需求说明书(样例)："
            "汽车内饰革水性化｜完整需求与对接上下文"
        ),
        "text": raw_text,
        "tags": [
            "AUTO-001",
            "汽车内饰革",
            "HD-S303",
            "低温耐折",
            "-30℃",
            "客户需求",
        ],
        "source": SOURCE_REL,
        "rechunk_meta": {
            "stable_source_id": SOURCE_ID,
            "source_range": (
                f"全文，第1-{len(lines)}行"
            ),
            "chunk_rule": (
                "源文件篇幅短且全文属于同一当前客户需求/"
                "对接上下文，因此按完整文档作为单一语义chunk；"
                "未抽取或拼接散落句子。"
            ),
            "derived_from_original_source": True,
            "original_source_modified": False,
            "previous_related_chunks": [
                "CK-0168",
                "CK-0169",
            ],
        },
    }

    derived_chunks = chunks + [
        new_chunk
    ]

    with OUT_CORPUS.open(
        "w",
        encoding="utf-8",
    ) as f:
        for item in derived_chunks:
            f.write(
                json.dumps(
                    item,
                    ensure_ascii=False,
                )
                + "\n"
            )

    manifest = {
        "stable_source_id": SOURCE_ID,
        "new_chunk_id": NEW_CHUNK_ID,
        "source": SOURCE_REL,
        "source_relative_path":
            RAW_SOURCE.relative_to(PROJECT_ROOT).as_posix(),
        "source_range":
            f"全文，第1-{len(lines)}行",
        "chunk_rule":
            new_chunk["rechunk_meta"][
                "chunk_rule"
            ],
        "fact_checks": checks,
        "original_corpus_size":
            len(chunks),
        "derived_corpus_size":
            len(derived_chunks),
        "original_source_modified":
            False,
    }

    OUT_MANIFEST.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # 最终验证
    # --------------------------------------------------

    assert len(derived_chunks) == len(chunks) + 1
    assert "HD-S303面层" in new_chunk["text"]
    assert "-30℃" in new_chunk["text"]
    assert "5万次" in new_chunk["text"]
    assert (
        new_chunk["source"]
        == SOURCE_REL
    )

    print(
        "NEW_CHUNK_ID:",
        NEW_CHUNK_ID,
    )
    print(
        "SOURCE_RANGE:",
        manifest["source_range"],
    )
    print(
        "DERIVED_CORPUS_SIZE:",
        len(derived_chunks),
    )
    print(
        "DERIVED_CORPUS:",
        OUT_CORPUS,
    )
    print(
        "MANIFEST:",
        OUT_MANIFEST,
    )
    print(
        "REQ_AUTO001_RECHUNK_PASS"
    )


if __name__ == "__main__":
    main()
