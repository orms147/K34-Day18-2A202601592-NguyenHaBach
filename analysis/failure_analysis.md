# Failure Analysis - Lab 18: Production RAG

**Họ và Tên:** Nguyễn Hà Bách
**Mã Học Viên::** 2A202601592

## RAGAS Scores

The environment did not contain the `ragas` package and the OpenRouter key
returned HTTP 402. The report therefore uses the deterministic local fallback
in `src/m4_eval.py`, not model-based RAGAS scores. It still evaluates every
question and keeps the same four metric contracts.

| Metric | Naive Baseline | Production | Delta |
|--------|---------------:|-----------:|------:|
| Faithfulness | 1.0000 | 1.0000 | +0.0000 |
| Answer Relevancy | 0.7183 | 0.7781 | +0.0598 |
| Context Precision | 0.5886 | 0.7600 | +0.1714 |
| Context Recall | 0.8467 | 0.8876 | +0.0409 |

The production pipeline improved all three retrieval-sensitive metrics. The
local faithfulness proxy is 1.0 because the no-API fallback returns selected
context as the answer; this must not be interpreted as a real LLM faithfulness
measurement.

## Bottom-5 Failures

The list below follows `reports/ragas_report.json`, sorted by the lowest
per-question average score. Scores are from the local fallback described above.

### 1. Senior 9 nam: phep va luong

- **Question:** Mot nhan vien Senior co 9 nam tham nien duoc nghi bao nhieu ngay phep nam va luong trong khoang nao?
- **Expected:** 18 ngay phep theo v2024; luong Senior P3-P4 la 20-35 trieu VND/thang.
- **Got:** Context v2024 day du va tra ve 18 ngay, nhung khong co bang luong Senior.
- **Worst metric:** `context_precision` = 0.5072; `context_recall` = 0.6087.
- **Error Tree:** Output thieu luong -> context co bang luong khong? Khong -> retrieval co phu het hai y khong? Khong -> query la cau hoi hai phan.
- **Root cause:** Top-3 sau rerank tap trung vao policy nghi phep; child chunk luong khong vao context.
- **Suggested fix:** Tach query thanh hai facet (phep va luong), retrieve/rerank rieng, sau do merge; them filter theo `source`/section va test rieng cho cau hoi multi-hop.

### 2. Luong thu viec Junior

- **Question:** Luong thu viec cua nhan vien Junior muc cao nhat la bao nhieu?
- **Expected:** Junior toi da 20.000.000 VND; 85% la 17.000.000 VND/thang.
- **Got:** Context co bang luong 12-20 trieu va quy tac 85%, nhung fallback tra nguyen parent, khong tinh ra 17 trieu.
- **Worst metric:** `context_precision` = 0.5714.
- **Error Tree:** Output chua co phep tinh -> context co du dau vao? Co -> generation co lam phep tinh khong? Chua -> loi o answer step.
- **Root cause:** Khong co LLM do HTTP 402; fallback khong co answer synthesis/calculator.
- **Suggested fix:** Them answer prompt yeu cau trich xuat so lieu va tinh toan; dung calculator deterministic cho bieu thuc `85% x 20.000.000`, sau do chi cho phep LLM dien dat.

### 3. Mua laptop 30 trieu

- **Question:** Neu can mua laptop 30 trieu cho nhan vien moi, ai phe duyet va can gi tu phong CNTT?
- **Expected:** Director phe duyet, can xac nhan cau hinh CNTT va it nhat 3 bao gia.
- **Got:** Parent `mua_sam.md` co day du ca ba bang chung; fallback tra parent thay vi cau tra loi ngan gon.
- **Worst metric:** `answer_relevancy` = 0.5000.
- **Error Tree:** Output co bang chung nhung dai -> context co dung? Co -> query co dung? Co -> presentation/answer extraction chua toi uu.
- **Root cause:** Local lexical proxy phat hien it token trung cau hoi, trong khi semantic content cua context la dung.
- **Suggested fix:** Them prompt tra loi theo ba truong `approver`, `IT requirement`, `quotes`; rerank xong dung context compression de loai phan khong lien quan.

### 4. So ngay phep nam hien hanh

- **Question:** Nhan vien duoc nghi bao nhieu ngay phep nam?
- **Expected:** 15 ngay co luong theo v2024; v2023 12 ngay da bi thay the.
- **Got:** Context co ca v2024 va v2023, nhung fallback tra ca hai parent va khong tu viet cau ket luan ve phien ban hien hanh.
- **Worst metric:** `context_precision` = 0.6000.
- **Error Tree:** Output co evidence -> context co du? Co, nhung co xung dot version -> metadata/version filter co chua? Chua loc truoc generation.
- **Root cause:** Hai policy cung match tu khoa; source/version duoc giu nhung chua duoc dung de uu tien v2024.
- **Suggested fix:** Parse `effective_date`/version vao metadata, uu tien tai lieu moi nhat khi co xung dot, dong thoi giu tai lieu cu lam evidence phu.

### 5. Tam ung qua han 20 ngay

- **Question:** Nhan vien tam ung 15 trieu, sau 20 ngay moi thanh toan. Bi phat bao nhieu?
- **Expected:** Qua 5 ngay; 2%/thang tren 15 trieu = 300.000 VND/thang, pro-rata khoang 50.000 VND.
- **Got:** Context co 15 ngay va 2%/thang, nhung fallback chua tinh ra 300.000 va 50.000.
- **Worst metric:** `context_recall` = 0.7391.
- **Error Tree:** Output thieu con so cuoi -> context co du cong thuc? Co mot phan -> generator/calculator co tinh pro-rata? Chua.
- **Root cause:** Chunk co quy tac phi nhung khong co phep tinh cu the; khong co answer synthesis khi API khong kha dung.
- **Suggested fix:** Tach numeric facts trong M4 test, tinh `15,000,000 * 0.02` va `300,000 * 5/30` bang code, sau do evaluate exact numeric match.

## Case Study

**Question chon phan tich:** Cau hoi Senior 9 nam tham nien.

**Error Tree walkthrough:**
1. Output dung? -> Dung phan phep (18 ngay), thieu phan luong.
2. Context dung? -> Dung cho phep, thieu bang luong Senior.
3. Query rewrite OK? -> Chua; cau hoi co hai facet nhung chi dung mot lan retrieval.
4. Fix o buoc: M2 query decomposition, rerank theo facet va merge context truoc M3/M4.

**Neu co them 1 gio, se optimize:**
- Them version-aware metadata filter cho policy v2023/v2024 va mat_khau v1/v2.
- Them test numeric exact-match va test cau hoi multi-hop.
- Cai `ragas` va chay lai evaluation voi OpenRouter co quota de doi chieu voi local proxy.
