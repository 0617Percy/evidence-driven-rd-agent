import json
import importlib.util
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient


# ------------------------------------------------------------
# 1. 复用已经通过三核心题的 RC2.2 Retriever
# ------------------------------------------------------------

MODULE_PATH = Path("src/eval_gold_rc2_2.py")

spec = importlib.util.spec_from_file_location(
    "auto001_rc2_2",
    MODULE_PATH
)

m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


# ------------------------------------------------------------
# 2. 正式 EvalSet V1.0：8题
# ------------------------------------------------------------

EVAL_SET = [
    {
        "id": "A1",
        "name": "风险发现",
        "query": (
            "汽车内饰革客户要求HD-S303面层-30℃耐折≥5万次，"
            "历史上有哪些值得提前关注的低温风险？"
        ),
        "mandatory": [
            "REQ-AUTO-001",
            "CASE-CA-2024-062",
        ],
        "context_gold": [],
    },
    {
        "id": "A2",
        "name": "风险发现等价表达",
        "query": (
            "准备把HD-S303用于这个汽车内饰革客户之前，"
            "以前有没有类似低温方面的坑值得先看？"
        ),
        "mandatory": [
            "REQ-AUTO-001",
            "CASE-CA-2024-062",
        ],
        "context_gold": [],
    },
    {
        "id": "A3",
        "name": "下一步研发动作",
        "query": (
            "面对当前-30℃≥5万次的新要求，"
            "下一轮研发最应该优先验证什么？为什么？"
        ),
        "mandatory": [
            "REQ-AUTO-001",
            "CASE-CA-2024-062",
            "STD-QBT2714",
        ],
        "context_gold": [],
    },
    {
        "id": "B1",
        "name": "证据边界",
        "query": (
            "HD-S303过去发生过低温耐折问题，"
            "这些历史经验能直接证明当前-30℃要求可以满足吗？"
        ),
        "mandatory": [
            "CASE-CA-2024-062",
            "REQ-AUTO-001",
            "LIT-LIT017",
        ],
        "context_gold": [],
    },
    {
        "id": "B2",
        "name": "诱导判失败",
        "query": (
            "HD-S303以前-10℃就发生过弯折开裂，"
            "那是不是说明现在汽车革-30℃肯定过不了？"
        ),
        "mandatory": [
            "CASE-CA-2024-062",
            "REQ-AUTO-001",
        ],
        "context_gold": [],
    },
    {
        "id": "B3",
        "name": "诱导给最终配方",
        "query": (
            "既然PPG低温性能不好，"
            "那直接告诉我应该换成什么配方，保证-30℃通过。"
        ),
        "mandatory": [
            "CASE-CA-2024-062",
            "LIT-LIT017",
        ],
        "context_gold": [],
    },
    {
        "id": "C1",
        "name": "直接问验证状态",
        "query": (
            "现有资料能证明HD-S303已经完成"
            "-30℃≥5万次专项耐折验证了吗？"
        ),
        # EvalSet明确：C1不设Mandatory Hard Gold
        "mandatory": [],
        "context_gold": [
            "REQ-AUTO-001",
        ],
    },
    {
        "id": "C2",
        "name": "要求直接下达标结论",
        "query": (
            "请根据现有资料直接告诉我"
            "HD-S303是否达到这个客户-30℃≥5万次要求。"
        ),
        "mandatory": [
            "REQ-AUTO-001",
            "CASE-CA-2024-062",
        ],
        "context_gold": [],
    },
]


OUTPUT_JSON = Path(
    "outputs/auto001_retrieval_eval_8q_rc2_2.json"
)

OUTPUT_SUMMARY = Path(
    "outputs/auto001_retrieval_eval_8q_rc2_2_summary.txt"
)


def serialize_top8(hits):
    rows = []

    for rank, (final_score, hit) in enumerate(
        hits,
        start=1,
    ):
        p = hit.payload or {}

        chunk_id = p.get("chunk_id")
        gold_id = m.CHUNK_TO_GOLD.get(chunk_id)

        rows.append(
            {
                "rank": rank,
                "final_score": round(
                    float(final_score),
                    6,
                ),
                "vector_score": round(
                    float(hit.score),
                    6,
                ),
                "chunk_id": chunk_id,
                "gold_id": gold_id,
                "title": p.get("title"),
                "source": p.get("source"),
                "doc_type": p.get("doc_type"),
                "text": p.get("text"),
            }
        )

    return rows


def evaluate_one(item, hits):
    ranks = m.rank_map(hits)

    mandatory = item["mandatory"]

    # C1特殊规则
    if not mandatory:
        top3_count = None
        top5_count = None
        top3_rate = None
        top5_rate = None
    else:
        top3_count = sum(
            1
            for gold in mandatory
            if ranks.get(gold, 999) <= 3
        )

        top5_count = sum(
            1
            for gold in mandatory
            if ranks.get(gold, 999) <= 5
        )

        top3_rate = (
            top3_count / len(mandatory)
        )

        top5_rate = (
            top5_count / len(mandatory)
        )

    gold_ranks = {
        gold: ranks.get(gold)
        for gold in mandatory
    }

    context_ranks = {
        gold: ranks.get(gold)
        for gold in item["context_gold"]
    }

    case_rank = None

    if (
        "CASE-CA-2024-062"
        in mandatory
    ):
        case_rank = ranks.get(
            "CASE-CA-2024-062"
        )

    wrong_hits = m.identify_noise(
        hits[:5]
    )

    traceability = all(
        m.traceability_ok(hit)
        for _, hit in hits[:5]
    )

    return {
        "eval_id": item["id"],
        "name": item["name"],
        "query": item["query"],
        "mandatory_gold": mandatory,
        "gold_ranks": gold_ranks,
        "context_gold_ranks": context_ranks,

        "top3_hit_count": top3_count,
        "top3_total": (
            len(mandatory)
            if mandatory
            else None
        ),
        "top3_hit_rate": top3_rate,

        "top5_hit_count": top5_count,
        "top5_total": (
            len(mandatory)
            if mandatory
            else None
        ),
        "top5_hit_rate": top5_rate,

        "case_rank": case_rank,

        "wrong_evidence_hits":
            wrong_hits,

        "wrong_evidence_hit_count":
            len(wrong_hits),

        "traceability_top5":
            traceability,

        "top8":
            serialize_top8(hits),
    }


def fmt_rate(value):
    if value is None:
        return "N/A"

    return f"{value:.2%}"


def main():
    # --------------------------------------------------------
    # 3. 检查RC2.2 Collection
    # --------------------------------------------------------

    client = QdrantClient(
        path=str(m.DB_PATH)
    )

    try:
        if not client.collection_exists(
            m.COLLECTION_NAME
        ):
            raise RuntimeError(
                "RC2_2_COLLECTION_NOT_FOUND"
            )

        count = client.count(
            collection_name=m.COLLECTION_NAME,
            exact=True,
        ).count

        print(
            "RC2_2_COLLECTION_SIZE:",
            count,
        )

        if count != 170:
            raise RuntimeError(
                f"UNEXPECTED_COLLECTION_SIZE:{count}"
            )

        embedder = TextEmbedding(
            model_name=m.MODEL_NAME
        )

        results = []

        # ----------------------------------------------------
        # 4. 正式跑8题
        # ----------------------------------------------------

        for item in EVAL_SET:
            hits = m.search(
                client,
                embedder,
                item["query"],
                candidate_k=60,
                top_k=8,
            )

            result = evaluate_one(
                item,
                hits,
            )

            results.append(result)

            print()
            print("=" * 100)
            print(
                item["id"],
                "|",
                item["name"],
            )
            print("=" * 100)

            print(
                "GOLD_RANKS:",
                result["gold_ranks"],
            )

            if item["id"] == "C1":
                print(
                    "TOP3: N/A"
                )
                print(
                    "TOP5: N/A"
                )
                print(
                    "CONTEXT_GOLD_RANKS:",
                    result[
                        "context_gold_ranks"
                    ],
                )
                print(
                    "CASE_RANK: N/A"
                )
            else:
                print(
                    "TOP3:",
                    f'{result["top3_hit_count"]}'
                    f'/{result["top3_total"]}',
                    f'({fmt_rate(result["top3_hit_rate"])})',
                )

                print(
                    "TOP5:",
                    f'{result["top5_hit_count"]}'
                    f'/{result["top5_total"]}',
                    f'({fmt_rate(result["top5_hit_rate"])})',
                )

                print(
                    "CASE_RANK:",
                    result["case_rank"],
                )

            print(
                "WRONG_EVIDENCE_HITS:",
                result[
                    "wrong_evidence_hits"
                ],
            )

            print(
                "TRACEABILITY_TOP5:",
                result[
                    "traceability_top5"
                ],
            )

        # ----------------------------------------------------
        # 5. 总指标
        # C1不进入Mandatory统计
        # ----------------------------------------------------

        applicable = [
            x
            for x in results
            if x["top5_total"] is not None
        ]

        mandatory_total = sum(
            x["top5_total"]
            for x in applicable
        )

        top3_hits = sum(
            x["top3_hit_count"]
            for x in applicable
        )

        top5_hits = sum(
            x["top5_hit_count"]
            for x in applicable
        )

        wrong_total = sum(
            x["wrong_evidence_hit_count"]
            for x in results
        )

        traceability_all = all(
            x["traceability_top5"]
            for x in results
        )

        case_results = [
            x
            for x in results
            if x["case_rank"] is not None
        ]

        case_top3_all = all(
            (
                x["case_rank"] is not None
                and x["case_rank"] <= 3
            )
            for x in case_results
        )

        all_top5_pass = all(
            x["top5_hit_count"]
            == x["top5_total"]
            for x in applicable
        )

        # C1仅检查REQ context是否被Top8召回
        c1 = next(
            x
            for x in results
            if x["eval_id"] == "C1"
        )

        c1_req_rank = (
            c1[
                "context_gold_ranks"
            ].get(
                "REQ-AUTO-001"
            )
        )

        c1_context_recalled = (
            c1_req_rank is not None
        )

        overall = {
            "mandatory_total":
                mandatory_total,

            "top3_hits":
                top3_hits,

            "top3_hit_rate":
                top3_hits
                / mandatory_total,

            "top5_hits":
                top5_hits,

            "top5_hit_rate":
                top5_hits
                / mandatory_total,

            "wrong_evidence_hit_total":
                wrong_total,

            "traceability_all":
                traceability_all,

            "case_top3_all":
                case_top3_all,

            "c1_req_context_rank":
                c1_req_rank,

            "c1_context_recalled":
                c1_context_recalled,

            "mandatory_top5_all_pass":
                all_top5_pass,
        }

        # ----------------------------------------------------
        # 6. Conservative Retrieval Freeze Gate
        # ----------------------------------------------------

        gate_pass = all(
            [
                all_top5_pass,
                case_top3_all,
                traceability_all,
                wrong_total == 0,
                c1_context_recalled,
            ]
        )

        payload = {
            "eval_spec":
                "AUTO-001 EvalSet V1.0",

            "retriever":
                "RC2.2",

            "candidate_k":
                60,

            "final_top_k":
                8,

            "collection":
                m.COLLECTION_NAME,

            "collection_size":
                count,

            "query_results":
                results,

            "overall":
                overall,

            "retrieval_freeze_gate":
                (
                    "PASS"
                    if gate_pass
                    else "HOLD"
                ),
        }

        OUTPUT_JSON.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # ----------------------------------------------------
        # 7. 生成简明Summary
        # ----------------------------------------------------

        lines = []

        lines.append(
            "AUTO-001 8Q RETRIEVAL EVAL | RC2.2"
        )

        lines.append(
            "=" * 72
        )

        for x in results:
            if x["eval_id"] == "C1":
                line = (
                    f'{x["eval_id"]}'
                    f' | TOP3=N/A'
                    f' | TOP5=N/A'
                    f' | REQ_CONTEXT='
                    f'{x["context_gold_ranks"].get("REQ-AUTO-001")}'
                    f' | WRONG='
                    f'{x["wrong_evidence_hit_count"]}'
                    f' | TRACE='
                    f'{x["traceability_top5"]}'
                )
            else:
                line = (
                    f'{x["eval_id"]}'
                    f' | TOP3='
                    f'{x["top3_hit_count"]}/{x["top3_total"]}'
                    f' | TOP5='
                    f'{x["top5_hit_count"]}/{x["top5_total"]}'
                    f' | CASE='
                    f'{x["case_rank"]}'
                    f' | WRONG='
                    f'{x["wrong_evidence_hit_count"]}'
                    f' | TRACE='
                    f'{x["traceability_top5"]}'
                    f' | GOLD_RANKS='
                    f'{x["gold_ranks"]}'
                )

            lines.append(line)

        lines.append(
            "=" * 72
        )

        lines.append(
            f'OVERALL_TOP3='
            f'{top3_hits}/{mandatory_total}'
            f' ({overall["top3_hit_rate"]:.2%})'
        )

        lines.append(
            f'OVERALL_TOP5='
            f'{top5_hits}/{mandatory_total}'
            f' ({overall["top5_hit_rate"]:.2%})'
        )

        lines.append(
            f'WRONG_HIT_TOTAL={wrong_total}'
        )

        lines.append(
            f'CASE_TOP3_ALL={case_top3_all}'
        )

        lines.append(
            f'TRACEABILITY_ALL={traceability_all}'
        )

        lines.append(
            f'C1_REQ_CONTEXT_RANK={c1_req_rank}'
        )

        lines.append(
            f'RETRIEVAL_FREEZE_GATE='
            f'{"PASS" if gate_pass else "HOLD"}'
        )

        OUTPUT_SUMMARY.write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        print()
        print("=" * 100)
        print("8Q OVERALL")
        print("=" * 100)

        print(
            "MANDATORY_TOTAL:",
            mandatory_total,
        )

        print(
            "OVERALL_TOP3:",
            f"{top3_hits}/{mandatory_total}",
            f"({overall['top3_hit_rate']:.2%})",
        )

        print(
            "OVERALL_TOP5:",
            f"{top5_hits}/{mandatory_total}",
            f"({overall['top5_hit_rate']:.2%})",
        )

        print(
            "WRONG_HIT_TOTAL:",
            wrong_total,
        )

        print(
            "CASE_TOP3_ALL:",
            case_top3_all,
        )

        print(
            "TRACEABILITY_ALL:",
            traceability_all,
        )

        print(
            "C1_REQ_CONTEXT_RANK:",
            c1_req_rank,
        )

        print(
            "RETRIEVAL_FREEZE_GATE:",
            (
                "PASS"
                if gate_pass
                else "HOLD"
            ),
        )

        print(
            "EVAL_JSON:",
            OUTPUT_JSON,
        )

        print(
            "SUMMARY:",
            OUTPUT_SUMMARY,
        )

        print(
            "AUTO001_8Q_RETRIEVAL_EVAL_COMPLETE"
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
