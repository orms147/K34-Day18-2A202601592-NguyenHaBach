# Group Report - Lab 18: Production RAG

**Nhom:** Ca nhan
**Ngay:** 2026-08-18
**So cau hoi:** 20

## Thanh vien & Phan cong

| Ten | Module | Hoan thanh | Tests pass |
|-----|--------|------------|------------|
| Ca nhan | M1: Chunking | Yes | 13/13 |
| Ca nhan | M2: Hybrid Search | Yes | 5/5 |
| Ca nhan | M3: Reranking | Yes | 5/5 |
| Ca nhan | M4: Evaluation | Yes | 4/4 |
| Ca nhan | M5: Enrichment | Yes | 10/10 |

## Ket qua danh gia

RAGAS khong the chay trong moi truong nay vi package `ragas` chua duoc cai va
OpenRouter tra HTTP 402. `m4_eval.py` dung local fallback deterministic de
giu contract bon metric va tao per-question failure analysis. Can chay lai
voi RAGAS that khi co dependency va quota API.

| Metric | Naive | Production | Delta |
|--------|------:|-----------:|------:|
| Faithfulness | 1.0000 | 1.0000 | +0.0000 |
| Answer Relevancy | 0.7183 | 0.7781 | +0.0598 |
| Context Precision | 0.5886 | 0.7600 | +0.1714 |
| Context Recall | 0.8467 | 0.8876 | +0.0409 |

## Key Findings

1. **Biggest improvement:** Hierarchical child retrieval plus parent context raised context precision from 0.5886 to 0.7600; hybrid BM25+dense and CrossEncoder helped keep policy evidence together.
2. **Biggest challenge:** Corpus has old/new versions. A keyword match can return v2023 or password v1 even when v2024/v2 is current, so source and effective-date metadata must affect ranking.
3. **Surprise finding:** The fallback answer can be faithful by returning context verbatim but still fail answer relevancy because it does not calculate numeric answers or compress long parents.

## Presentation Notes (5 phut)

1. RAGAS scores: show the table and clearly label them as local proxy scores, not real RAGAS.
2. Biggest win: parent context after child retrieval improved evidence completeness.
3. Case study: Senior 9 nam - leave evidence found, salary facet missing; fix with query decomposition.
4. Next optimization: version-aware filters, numeric calculator, and real RAGAS with a funded/working OpenRouter model.
