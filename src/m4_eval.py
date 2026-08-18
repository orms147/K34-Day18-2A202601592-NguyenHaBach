from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json, re
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TEST_SET_PATH


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tokens(text: str) -> set[str]:
    """Tokenize text for the offline fallback without requiring an LLM."""
    return set(re.findall(r"\w+", (text or "").lower(), flags=re.UNICODE))


def _coverage(needles: set[str], haystack: set[str]) -> float:
    if not needles:
        return 0.0
    return len(needles & haystack) / len(needles)


def _evaluate_local(questions: list[str], answers: list[str],
                    contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Provide deterministic proxy metrics when RAGAS or an API is unavailable."""
    rows = []
    for question, answer, row_contexts, ground_truth in zip(
        questions, answers, contexts, ground_truths
    ):
        answer_tokens = _tokens(answer)
        question_tokens = _tokens(question)
        truth_tokens = _tokens(ground_truth)
        context_tokens = [_tokens(context) for context in row_contexts]
        joined_context = set().union(*context_tokens) if context_tokens else set()

        faithfulness = _coverage(answer_tokens, joined_context)
        answer_relevancy = _coverage(question_tokens, answer_tokens)
        relevance_by_rank = [
            _coverage(truth_tokens, context_tokens[i])
            for i in range(len(context_tokens))
        ]
        weights = [1.0 / (i + 1) for i in range(len(relevance_by_rank))]
        context_precision = (
            sum(score * weight for score, weight in zip(relevance_by_rank, weights))
            / sum(weights)
            if weights else 0.0
        )
        context_recall = _coverage(truth_tokens, joined_context)
        rows.append(EvalResult(
            question=question,
            answer=answer,
            contexts=row_contexts,
            ground_truth=ground_truth,
            faithfulness=float(faithfulness),
            answer_relevancy=float(answer_relevancy),
            context_precision=float(context_precision),
            context_recall=float(context_recall),
        ))

    metric_names = ["faithfulness", "answer_relevancy",
                    "context_precision", "context_recall"]
    return {
        name: (
            sum(getattr(row, name) for row in rows) / len(rows)
            if rows else 0.0
        )
        for name in metric_names
    } | {"per_question": rows}


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation."""
    try:
        from ragas import evaluate
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
        from datasets import Dataset

        dataset = Dataset.from_dict({
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        })
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                            context_precision, context_recall])
        df = result.to_pandas()
        per_question = [
            EvalResult(
                question=row["question"],
                answer=row["answer"],
                contexts=row["contexts"],
                ground_truth=row["ground_truth"],
                faithfulness=float(row.get("faithfulness", 0.0) if row.get("faithfulness") is not None else 0.0),
                answer_relevancy=float(row.get("answer_relevancy", 0.0) if row.get("answer_relevancy") is not None else 0.0),
                context_precision=float(row.get("context_precision", 0.0) if row.get("context_precision") is not None else 0.0),
                context_recall=float(row.get("context_recall", 0.0) if row.get("context_recall") is not None else 0.0)
            )
            for _, row in df.iterrows()
        ]

        agg = {k: v for k, v in result.items()}
        return {
            "faithfulness": float(agg.get("faithfulness", 0.0)),
            "answer_relevancy": float(agg.get("answer_relevancy", 0.0)),
            "context_precision": float(agg.get("context_precision", 0.0)),
            "context_recall": float(agg.get("context_recall", 0.0)),
            "per_question": per_question
        }
    except Exception as e:
        print(f"  ⚠️  RAGAS evaluation failed; using local fallback: {e}")
        return _evaluate_local(questions, answers, contexts, ground_truths)


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    }

    analyzed = []
    for res in eval_results:
        metrics = {
            "faithfulness": res.faithfulness,
            "context_recall": res.context_recall,
            "context_precision": res.context_precision,
            "answer_relevancy": res.answer_relevancy
        }
        avg = sum(metrics.values()) / 4.0
        worst_metric = min(metrics, key=metrics.get)
        worst_score = metrics[worst_metric]
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]

        analyzed.append({
            "question": res.question,
            "worst_metric": worst_metric,
            "score": float(worst_score),
            "avg_score": float(avg),
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix
        })

    analyzed.sort(key=lambda x: x["avg_score"])

    return [
        {
            "question": x["question"],
            "worst_metric": x["worst_metric"],
            "score": x["score"],
            "diagnosis": x["diagnosis"],
            "suggested_fix": x["suggested_fix"]
        }
        for x in analyzed[:bottom_n]
    ]


def save_report(results: dict, failures: list[dict], path: str = "ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    per_question = results.get("per_question", [])
    serialized = [
        {key: value for key, value in vars(item).items()}
        if isinstance(item, EvalResult) else item
        for item in per_question
    ]
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(per_question),
        "per_question": serialized,
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
