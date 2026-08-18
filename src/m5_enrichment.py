from __future__ import annotations

"""
Module 5: Enrichment Pipeline
==============================
Làm giàu chunks TRƯỚC khi embed: Summarize, HyQA, Contextual Prepend, Auto Metadata.

Test: pytest tests/test_m5.py
"""

import os, sys
from dataclasses import dataclass, field

from config import OPENAI_API_KEY

import requests

_OPENROUTER_UNAVAILABLE = False


def _call_openrouter(messages: list[dict], max_tokens: int) -> str:
    global _OPENROUTER_UNAVAILABLE
    if _OPENROUTER_UNAVAILABLE:
        raise RuntimeError("OpenRouter is unavailable; using local fallback")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": messages,
        "max_tokens": max_tokens
    }
    resp = requests.post(url, headers=headers, json=data, timeout=30)
    if resp.status_code in {401, 402, 403}:
        _OPENROUTER_UNAVAILABLE = True
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _local_summary(text: str) -> str:
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
    return ". ".join(sentences[:2]) + "." if sentences else text


def _local_questions(text: str, n_questions: int) -> list[str]:
    import re
    sentences = [s.strip() for s in re.split(r'[.!?\n]', text) if len(s.strip()) > 10]
    return [f"{s.rstrip('.')}?" for s in sentences[:n_questions]]


def _local_metadata() -> dict:
    return {"topic": "general", "entities": [], "category": "policy", "language": "vi"}


def _local_enrichment(text: str, source: str) -> dict:
    prefix = f"Trích từ {source}. " if source else ""
    return {
        "summary": _local_summary(text),
        "questions": _local_questions(text, 3),
        "context": prefix.strip(),
        "metadata": _local_metadata(),
    }


@dataclass
class EnrichedChunk:
    """Chunk đã được làm giàu."""
    original_text: str
    enriched_text: str
    summary: str
    hypothesis_questions: list[str]
    auto_metadata: dict
    method: str  # "contextual", "summary", "hyqa", "full"


# ─── Technique 1: Chunk Summarization ────────────────────


def summarize_chunk(text: str) -> str:
    """
    Tạo summary ngắn cho chunk.
    Embed summary thay vì (hoặc cùng với) raw chunk → giảm noise.
    """
    if OPENAI_API_KEY and not _OPENROUTER_UNAVAILABLE:
        try:
            content = _call_openrouter([
                {"role": "system", "content": "Tóm tắt đoạn văn sau trong 2-3 câu ngắn gọn bằng tiếng Việt."},
                {"role": "user", "content": text},
            ], max_tokens=150)
            return content
        except Exception as e:
            print(f"  ⚠️  OpenRouter summarize failed: {e}")

    return _local_summary(text)


# ─── Technique 2: Hypothesis Question-Answer (HyQA) ─────


def generate_hypothesis_questions(text: str, n_questions: int = 3) -> list[str]:
    """
    Generate câu hỏi mà chunk có thể trả lời.
    Index cả questions lẫn chunk → query match tốt hơn (bridge vocabulary gap).
    """
    if OPENAI_API_KEY and not _OPENROUTER_UNAVAILABLE:
        try:
            content = _call_openrouter([
                {"role": "system", "content": f"Dựa trên đoạn văn, tạo {n_questions} câu hỏi mà đoạn văn có thể trả lời. Trả về mỗi câu hỏi trên 1 dòng."},
                {"role": "user", "content": text},
            ], max_tokens=200)
            questions = content.split("\n")
            return [q.strip().lstrip("0123456789.-) ") for q in questions if q.strip()][:n_questions]
        except Exception as e:
            print(f"  ⚠️  OpenRouter HyQA failed: {e}")

    return _local_questions(text, n_questions)


# ─── Technique 3: Contextual Prepend (Anthropic style) ──


def contextual_prepend(text: str, document_title: str = "") -> str:
    """
    Prepend context giải thích chunk nằm ở đâu trong document.
    Anthropic benchmark: giảm 49% retrieval failure (alone).
    """
    if OPENAI_API_KEY and not _OPENROUTER_UNAVAILABLE:
        try:
            content = _call_openrouter([
                {"role": "system", "content": "Viết 1 câu ngắn mô tả đoạn văn này nằm ở đâu trong tài liệu và nói về chủ đề gì. Chỉ trả về 1 câu."},
                {"role": "user", "content": f"Tài liệu: {document_title}\n\nĐoạn văn:\n{text}"},
            ], max_tokens=80)
            return f"{content}\n\n{text}"
        except Exception as e:
            print(f"  ⚠️  OpenRouter contextual failed: {e}")

    prefix = f"Trích từ {document_title}. " if document_title else ""
    return f"{prefix}{text}"


# ─── Technique 4: Auto Metadata Extraction ──────────────


def extract_metadata(text: str) -> dict:
    """
    LLM extract metadata tự động: topic, entities, date_range, category.
    """
    if OPENAI_API_KEY and not _OPENROUTER_UNAVAILABLE:
        try:
            import json as _json
            content = _call_openrouter([
                {"role": "system", "content": 'Trích xuất metadata từ đoạn văn. Trả về JSON: {"topic": "...", "entities": ["..."], "category": "policy|hr|it|finance", "language": "vi|en"}'},
                {"role": "user", "content": text},
            ], max_tokens=150)
            return _json.loads(content.replace("```json", "").replace("```", "").strip())
        except Exception as e:
            print(f"  ⚠️  OpenRouter metadata failed: {e}")

    return _local_metadata()


# ─── Combined Single-Call Mode ───────────────────────────


def _enrich_single_call(text: str, source: str) -> dict:
    """Single LLM call to get summary + questions + context + metadata.

    ⚠️ Cost optimization: 1 API call thay vì 4 calls riêng lẻ.
    """
    if OPENAI_API_KEY and not _OPENROUTER_UNAVAILABLE:
        try:
            import json as _json
            content = _call_openrouter([
                {"role": "system", "content": """Phân tích đoạn văn và trả về JSON:
    {
      "summary": "tóm tắt 2-3 câu",
      "questions": ["câu hỏi 1", "câu hỏi 2", "câu hỏi 3"],
      "context": "1 câu mô tả đoạn văn nằm ở đâu trong tài liệu",
      "metadata": {"topic": "...", "entities": ["..."], "category": "policy|hr|it|finance", "language": "vi|en"}
    }"""},
                {"role": "user", "content": f"Tài liệu: {source}\n\nĐoạn văn:\n{text}"},
            ], max_tokens=400)
            return _json.loads(content.replace("```json", "").replace("```", "").strip())
        except Exception as e:
            print(f"  ⚠️  Enrichment API failed: {e}")

    return _local_enrichment(text, source)


# ─── Full Enrichment Pipeline ────────────────────────────


def enrich_chunks(
    chunks: list[dict],
    methods: list[str] | None = None,
) -> list[EnrichedChunk]:
    """
    Chạy enrichment pipeline trên danh sách chunks. (Đã implement sẵn — dùng functions ở trên)

    Có 2 chế độ:
    - methods cụ thể (["summary"], ["contextual"]...): gọi từng function riêng (tốt cho học/debug)
    - methods=["combined"] hoặc None: 1 API call duy nhất cho tất cả (tốt cho production)

    Args:
        chunks: List of {"text": str, "metadata": dict}
        methods: Default None → combined mode (1 call/chunk).
                 Options: "summary", "hyqa", "contextual", "metadata", "combined"
    """
    if methods is None:
        methods = ["combined"]

    use_combined = "combined" in methods

    enriched = []
    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        source = chunk.get("metadata", {}).get("source", "")

        if use_combined:
            result = _enrich_single_call(text, source)
            summary = result.get("summary", "")
            questions = result.get("questions", [])
            context_line = result.get("context", "")
            enriched_text = f"{context_line}\n\n{text}" if context_line else text
            auto_meta = result.get("metadata", {})
        else:
            summary = summarize_chunk(text) if "summary" in methods else ""
            questions = generate_hypothesis_questions(text) if "hyqa" in methods else []
            enriched_text = contextual_prepend(text, source) if "contextual" in methods else text
            auto_meta = extract_metadata(text) if "metadata" in methods else {}

        enriched.append(EnrichedChunk(
            original_text=text,
            enriched_text=enriched_text,
            summary=summary,
            hypothesis_questions=questions,
            # The original source is evidence for version conflicts and must win.
            auto_metadata={**auto_meta, **chunk.get("metadata", {})},
            method="+".join(methods),
        ))

        if (i + 1) % 10 == 0 or (i + 1) == len(chunks):
            print(f"  Enriched {i + 1}/{len(chunks)} chunks...", flush=True)

    return enriched


# ─── Main ────────────────────────────────────────────────

if __name__ == "__main__":
    sample = "Nhân viên chính thức được nghỉ phép năm 12 ngày làm việc mỗi năm. Số ngày nghỉ phép tăng thêm 1 ngày cho mỗi 5 năm thâm niên công tác."

    print("=== Enrichment Pipeline Demo ===\n")
    print(f"Original: {sample}\n")

    s = summarize_chunk(sample)
    print(f"Summary: {s}\n")

    qs = generate_hypothesis_questions(sample)
    print(f"HyQA questions: {qs}\n")

    ctx = contextual_prepend(sample, "Sổ tay nhân viên VinUni 2024")
    print(f"Contextual: {ctx}\n")

    meta = extract_metadata(sample)
    print(f"Auto metadata: {meta}")
