# Individual Reflection - Lab 18

**Ten:** Sinh vien A202601592
**Module phu trach:** M1-M5 (ca nhan)

## 1. Dong gop ky thuat

- Module da implement: M1 semantic/hierarchical/structure-aware chunking; M2 BM25, dense Qdrant va RRF; M3 CrossEncoder reranking; M4 evaluation/failure analysis; M5 combined enrichment va local fallback.
- Cac ham/class chinh: `chunk_semantic`, `chunk_hierarchical`, `chunk_structure_aware`, `BM25Search`, `DenseSearch`, `reciprocal_rank_fusion`, `CrossEncoderReranker.rerank`, `evaluate_ragas`, `failure_analysis`, `enrich_chunks`.
- So tests pass: 37/37.
- Pipeline tao `reports/ragas_report.json` va `reports/naive_baseline_report.json` cho 20 cau hoi.

## 2. Kien thuc hoc duoc

- Khai niem moi nhat: RRF gop rank thay vi cong score BM25 va cosine; hierarchical retrieval cho phep tim child nhung tra parent; reranker nen dat sau retrieval.
- Dieu bat ngo nhat: Chunking dung van co the sai khi query co hai facet. Cau Senior 9 nam tim du phep nhung bo sot bang luong.
- Mapping concept -> code: M1 trong `src/m1_chunking.py`, M2 trong `src/m2_search.py`, M3 trong `src/m3_rerank.py`, M4 trong `src/m4_eval.py`, M5 trong `src/m5_enrichment.py`.

## 3. Kho khan & Cach giai quyet

- Kho khan lon nhat: OpenRouter tra `402 Client Error: Payment Required`, package RAGAS bao `No module named 'ragas'`, va console Windows bao `UnicodeEncodeError` voi emoji tren cp1252.
- Cach giai quyet: giu API fallback an toan, them local deterministic evaluation, dung `OPENROUTER_API_KEY` qua config, reconfigure stdout UTF-8, va tranh goi lap lai sau loi 402. Docker Desktop cung khong chay, nen DenseSearch dung Qdrant in-memory cho local run.
- Thoi gian debug: khoang 60 phut, gom chay test module, chay baseline, main pipeline va doc bottom-5.

## 4. Neu lam lai

- Se lam khac dieu gi: cai dependency va test API/RAGAS truoc khi chay full pipeline; them version-aware metadata ngay tu buoc load document.
- Module muon thu tiep: query decomposition cho cau hoi multi-hop va numeric answer verifier cho cac cau hoi luong/phi.

## 5. Tu danh gia

| Tieu chi | Tu cham (1-5) |
|----------|---------------:|
| Hieu bai giang | 4 |
| Code quality | 4 |
| Teamwork | 3 (bai ca nhan) |
| Problem solving | 5 |

## Action plan

1. Tuan 1: them version-aware retrieval va test 20 cau hoi co expected source.
2. Tuan 2: them calculator/exact-match evaluator cho so tien, phan tram va ngay.
3. Tuan 3: chay lai RAGAS that, luu latency breakdown va so sanh voi local proxy.
