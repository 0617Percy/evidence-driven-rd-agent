# -*- coding: utf-8 -*-
"""
AUTO-001 Y Runnable Handoff — Runtime verification (all checks).
Run by verify_y.ps1. Exit 0 = PASS, exit 1 = HOLD.
UTF-8 source: handles Chinese vault directory names natively.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = ROOT / "data" / "knowledge_vault" / "AUTO001_Y_V2"
TRUTH_SOURCE = ROOT / "data" / "truth_source" / "模拟数据集_v1.0"

failures = []


def check(name, ok, detail=""):
    if ok:
        print("[PASS] " + name)
    else:
        print("[HOLD] " + name + ("  " + detail if detail else ""))
        failures.append(name)


# ---- core files / dirs ----
check("app.py", (ROOT / "app.py").is_file())
check("src/", (ROOT / "src").is_dir())
check("RC1 corpus", (ROOT / "data" / "derived" / "rag_chunks_auto001_rc1.jsonl").is_file())
check("Governed Knowledge Vault", VAULT.is_dir())
check("Truth Source (模拟数据集_v1.0)", TRUTH_SOURCE.is_dir())
check("05_已审核派生知识", (VAULT / "05_已审核派生知识").is_dir())
check("Manifest", (VAULT / "05_已审核派生知识" / "00_Approved_Knowledge_Manifest.jsonl").is_file())
# Qdrant is a rebuildable runtime index and is intentionally NOT shipped in the
# public release, so its absence is reported as INFO instead of HOLD.
QDRANT_COLLECTION = (
    ROOT / "outputs" / "qdrant_v1_2" / "collection" / "rag_chunks_auto001_rc2_2"
)
if QDRANT_COLLECTION.is_dir():
    print("[PASS] Qdrant collection rag_chunks_auto001_rc2_2 (frozen index present)")
else:
    print("[INFO] Qdrant index absent - rebuild with: python src/eval_gold_rc2_2.py")
check(
    "Frozen Demo JSON",
    (ROOT / "outputs" / "auto001_main_demo_structured_output_A1_v1_3_1.json").is_file(),
)
check("knowledge_feedback", (ROOT / "outputs" / "knowledge_feedback").is_dir())
check(
    "knowledge_supersession_relations.jsonl",
    (ROOT / "outputs" / "knowledge_feedback" / "knowledge_supersession_relations.jsonl").is_file(),
)

# ---- core packages import ----
try:
    import streamlit  # noqa: F401
    import pandas  # noqa: F401
    import openpyxl  # noqa: F401
    import dotenv  # noqa: F401
    import openai  # noqa: F401
    import qdrant_client  # noqa: F401
    import fastembed  # noqa: F401
    check("core packages import", True)
except Exception as exc:  # pragma: no cover
    check("core packages import", False, repr(exc))

# ---- RC1 chunk count ----
rc1 = ROOT / "data" / "derived" / "rag_chunks_auto001_rc1.jsonl"
if rc1.is_file():
    n = sum(1 for line in rc1.open(encoding="utf-8") if line.strip())
    check("RC1 chunk count = 170", n == 170, "actual=" + str(n))
else:
    check("RC1 chunk count = 170", False, "corpus missing")

# ---- supersession relations ----
rel = ROOT / "outputs" / "knowledge_feedback" / "knowledge_supersession_relations.jsonl"
if rel.is_file():
    rows = [json.loads(x) for x in rel.open(encoding="utf-8") if x.strip()]
    pairs = set(
        (r.get("old_knowledge_record_id"), r.get("new_knowledge_record_id"))
        for r in rows
    )
    p1 = ("AK-51bc951a799242a4adfbe80ae635e448", "AK-fc31f218c2a14ef48389b761ec210b6b")
    p2 = ("AK-c444740cec87424a903b2767f3aa7dfb", "AK-fc31f218c2a14ef48389b761ec210b6b")
    check("supersession AK-51bc -> AK-fc31", p1 in pairs)
    check("supersession AK-c444 -> AK-fc31", p2 in pairs)
    check("relation count = 2", len(rows) == 2, "actual=" + str(len(rows)))
else:
    check("supersession relations", False, "file missing")

print()
if failures:
    print("Y_RUNTIME_VERIFICATION = HOLD (" + str(len(failures)) + " failure(s))")
    sys.exit(1)

print("Y_RUNTIME_VERIFICATION = PASS")
sys.exit(0)
