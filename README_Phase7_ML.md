# Phase 7-ML: 비지도 ML 이상 탐지 파이프라인

> 역할: 통계 기반 이상 탐지(Phase 7)의 보조 교차검증 수단  
> 모델: Isolation Forest + Local Outlier Factor + One-Class SVM 앙상블  
> 적용 구간: A(국제가→수입단가), B(수입단가→PPI) — 전 10품목 × 2구간 = 20유닛

---

## 1. 개요

Phase 7-ML은 3종 비지도 이상 탐지 모델을 사용하여, Phase 7 통계 탐지와 독립적으로 이상 시점을 판별하고, 두 트랙의 교차 대조를 통해 신뢰도 3단계 등급을 부여하는 파이프라인이다.

ML은 단독 판정 수단이 아니라 **교차검증 수단**으로 역할이 제한된다. ML 단독 탐지(reference 등급)는 주 분석 결과에 포함하지 않으며, 통계 탐지와의 일치(high 등급)만이 최고 신뢰도로 인정된다.

---

## 2. 코드 구조

```
src/preprocessing/Phase7/
├── phase7_ml_common.py     ← 피처 행렬 구성, 전처리, stat_detected 조인
├── phase7_ml_models.py     ← 3종 모델 실행 + 앙상블 집계
├── phase7_ml_cross.py      ← 통계-ML 교차 대조 + 신뢰도 등급화
└── phase7_ml_run.py        ← 전체 파이프라인 진입점 (20유닛 순차 실행)

tests/phase7_ml/
├── eval_common.py          ← 평가 공통 (외부 충격 목록, 유틸)
├── test_axis1_esr.py       ← 축 1: 외부 충격 회수율
├── test_axis2_separation.py← 축 2: 이상 점수 분리도
├── test_axis3_auc.py       ← 축 3: 통계-ML 일관성 AUC + ROC curve
├── test_axis4_sensitivity.py← 축 4: 파라미터 민감도
├── test_axis5_consensus.py ← 축 5: 합의 기반 지표
├── run_all_evaluation.py   ← 5축 통합 실행 + 타임스탬프 저장
├── generate_dashboard.py   ← 5축 평가 대시보드 HTML 생성
└── results/                ← 평가 결과 (run별 디렉토리)

tests/shap/
├── run_shap_if.py          ← IF SHAP 분석 (TreeExplainer)
├── run_shap_lof.py         ← LOF SHAP 분석 (KernelExplainer)
├── run_shap_svm.py         ← SVM SHAP 분석 (KernelExplainer)
├── generate_shap_dashboard.py ← SHAP 대시보드 HTML + Beeswarm PNG 생성
└── results/                ← SHAP 결과 (모델별 타임스탬프 디렉토리)
```

---

## 3. 실행 방법

### 3.1 ML 파이프라인 실행

```bash
python src/preprocessing/Phase7/phase7_ml_run.py
```

20유닛에 대해 피처 구성 → 전처리 → 3종 모델 → 앙상블 → 교차 대조 → 등급화를 순차 실행한다.

### 3.2 5축 평가 실행

```bash
python tests/phase7_ml/run_all_evaluation.py --memo "최종 확정: 6종 + c=0.08"
python tests/phase7_ml/generate_dashboard.py
```

타임스탬프 디렉토리(`results/run_YYYYMMDD_HHMMSS/`)에 축별 CSV + `run_meta.json`을 저장하고, `latest/`에 복사본을 갱신한다.

### 3.3 SHAP 분석 실행

```bash
python tests/shap/run_shap_if.py                    # IF (수 초)
python tests/shap/run_shap_lof.py                   # LOF (~5분)
python tests/shap/run_shap_svm.py                   # SVM (~4분)
python tests/shap/generate_shap_dashboard.py \
  --if-dir 20260519_1910_IF \
  --lof-dir 20260519_2033_LOF \
  --svm-dir 20260519_2041_SVM
```

SHAP 코드는 `--output-dir` 인자로 기존 폴더를 지정하면 이미 완료된 유닛은 스킵하고 이어서 실행한다.

---

## 4. 입력 파일

| 파일                              | 위치                                     | 설명                                                 |
| --------------------------------- | ---------------------------------------- | ---------------------------------------------------- |
| `{cid}_{seg}_stat_timeseries.csv` | `data/processed/phase7/stat_timeseries/` | Phase 4 산출물. 6종 피처의 원시 데이터               |
| `phase7_summary.csv`              | `data/processed/phase7/`                 | Phase 7 통계 탐지 결과 (stat_detected, pattern_type) |
| `product_config.json`             | `data/processed/`                        | 품목별 구간 목록                                     |

---

## 5. 출력 파일

### 5.1 ML 파이프라인 출력 (`data/processed/phase7_ml/`)

| 디렉토리             | 파일 패턴                            | 설명                               |
| -------------------- | ------------------------------------ | ---------------------------------- |
| `features/`          | `{cid}_{seg}_features.csv`           | 스케일링 전 원시 6종 피처 (20개)   |
| `predictions/`       | `{cid}_{seg}_ml_predictions.csv`     | 3종 모델 판정 + 앙상블 결과 (20개) |
| `cross_validation/`  | `{cid}_{seg}_cross_val.csv`          | 통계-ML 교차 대조 (전 시점) (20개) |
| `confidence_grades/` | `{cid}_{seg}_grades.csv`             | 신뢰도 등급 (이상 시점만) (20개)   |
| `models/{run_date}/` | `{cid}_{seg}_{model}_{run_date}.pkl` | 학습된 모델 + 스케일러 (80개)      |
| (루트)               | `phase7_ml_summary.csv`              | 전체 20유닛 요약 통계              |

### 5.2 predictions CSV 컬럼

| 컬럼                 | 타입   | 설명                             |
| -------------------- | ------ | -------------------------------- |
| `date`               | date   | 관측 월 (YYYY-MM-DD)             |
| `commodity_id`       | string | 품목 ID                          |
| `segment`            | string | 구간 (A 또는 B)                  |
| `if_anomaly`         | bool   | Isolation Forest 이상 판정       |
| `if_score`           | float  | IF 이상 점수 (낮을수록 이상)     |
| `lof_anomaly`        | bool   | LOF 이상 판정                    |
| `lof_score`          | float  | LOF 이상 점수 (낮을수록 이상)    |
| `svm_anomaly`        | bool   | One-Class SVM 이상 판정          |
| `svm_score`          | float  | SVM 이상 점수 (음수=이상)        |
| `ml_consensus_count` | int    | 이상 판정 모델 수 (0~3)          |
| `ml_detected`        | bool   | 앙상블 최종 판정 (consensus ≥ 2) |

### 5.3 grades CSV 컬럼

| 컬럼                 | 타입   | 설명                                |
| -------------------- | ------ | ----------------------------------- |
| `date`               | date   | 관측 월                             |
| `commodity_id`       | string | 품목 ID                             |
| `segment`            | string | 구간                                |
| `ml_detected`        | bool   | ML 앙상블 판정                      |
| `ml_consensus_count` | int    | 이상 판정 모델 수                   |
| `stat_detected`      | bool   | 통계 탐지 여부                      |
| `pattern_type`       | string | 통계 탐지 패턴 (pattern1/2/3)       |
| `agreement`          | bool   | 통계-ML 일치 여부                   |
| `confidence_grade`   | string | 신뢰도 등급 (high/medium/reference) |

정상 월(confidence_grade=None)은 grades CSV에서 제외된다.

---

## 6. 피처 정의 (6종)

| #   | 피처명               | 설명                   | 산출                                     |
| --- | -------------------- | ---------------------- | ---------------------------------------- |
| F1  | `transmission_rate`  | 월별 전이율            | downstream_pct ÷ upstream_pct            |
| F2  | `upstream_pct`       | 상류 가격 변화율 (%)   | 해당 구간 상류 시계열의 전월 대비 변화율 |
| F3  | `downstream_pct`     | 하류 가격 변화율 (%)   | 해당 구간 하류 시계열의 전월 대비 변화율 |
| F4  | `ect_or_spread`      | ECT 또는 로그 스프레드 | 공적분 여부에 따라 분기                  |
| F5  | `exchange_rate_pct`  | 환율 변동률 (%)        | 원/달러 환율의 전월 대비 변화율          |
| F6  | `intl_price_usd_pct` | 달러 국제가 변동률 (%) | 달러 기준 국제 원자재 가격 변화율        |

순환 논리 방지: Phase 7 통계 판정 결과(zscore, pattern_flag 등)는 피처에서 완전 제외한다. 8회 피처 실험을 통해 6종이 최적임을 확인하였다.

---

## 7. 모델 파라미터 (최종 확정)

| 모델                 | 파라미터            | 값                                     |
| -------------------- | ------------------- | -------------------------------------- |
| Isolation Forest     | n_estimators        | 100                                    |
|                      | contamination       | 0.08                                   |
|                      | random_state        | 42                                     |
| Local Outlier Factor | n_neighbors         | 10                                     |
|                      | contamination       | 0.08                                   |
|                      | novelty             | False                                  |
| One-Class SVM        | kernel              | rbf                                    |
|                      | nu                  | 0.08                                   |
|                      | gamma               | scale                                  |
| 전처리               | scaler              | StandardScaler                         |
| 앙상블               | consensus_threshold | 2 (3종 중 2개 이상 → ml_detected=True) |

---

## 8. 신뢰도 등급 체계

| 등급          | 조건                                      | 의미                             | DB 적재 |
| ------------- | ----------------------------------------- | -------------------------------- | ------- |
| **high**      | stat_detected=True AND ml_detected=True   | 통계 + ML 동시 탐지. 최고 신뢰도 | ✔       |
| **medium**    | stat_detected=True AND ml_detected=False  | 통계만 탐지. ML 미확인           | ✔       |
| **reference** | stat_detected=False AND ml_detected=True  | ML만 탐지. 참고용                | ✔       |
| (None)        | stat_detected=False AND ml_detected=False | 정상 월                          | ✖       |

---

## 9. 5축 평가 프레임워크

ML 모델에 라벨이 없으므로 전통적 정확도/재현율을 산출할 수 없다. 대신 5개 독립 축으로 신뢰성을 다면 평가한다.

### 축 1 — External Shock Recall (ESR)

알려진 외부 충격 윈도우(2008 금융위기, 2010 러시아 가뭄, 2015 엘니뇨, 2020 COVID, 2022 우크라이나) 내에서 ML이 최소 1건 이상 탐지했는지를 측정한다. 충격 건수 가중 평균으로 산출.

### 축 2 — Anomaly Score Separation Ratio (SR)

이상 판정 관측치와 정상 판정 관측치의 이상 점수 평균 차이를 정상 표준편차로 나눈 분리도. SR > 2.0이면 양호.

### 축 3 — Statistical-ML Consistency (AUC)

stat_detected를 pseudo-label로 사용하여 ROC AUC를 산출. 앙상블 스코어는 3종 모델의 원시 이상 점수를 Min-Max 정규화 후 평균한 연속형 값을 사용. 이상적 범위 0.70~0.90 (독립성 + 일관성).

### 축 4 — Hyperparameter Sensitivity (Stability Ratio)

contamination(0.05/0.10/0.15)과 LOF k(5/10/15/20) 변동 시 탐지 집합의 안정성. SR ≥ 0.80이면 robust.

### 축 5 — Consensus Indicators

CTA(Cross-Track Agreement), ASC(Agreement-Shock Coincidence), P_stat, P_ml 4개 지표. 핵심 가설: ASC > max(P_stat, P_ml) — 합의 시점의 충격 정밀도가 개별 트랙보다 높은지 검증.

### 최종 확정 결과 요약

| 축  | 지표                      | 값                 | 판정                 |
| --- | ------------------------- | ------------------ | -------------------- |
| 1   | 가중 ESR                  | 0.516              | Moderate             |
| 2   | 평균 SR (IF/LOF/SVM)      | 2.71 / 2.61 / 2.22 | Good (전 모델 > 2.0) |
| 3   | 평균 AUC (앙상블, 연속형) | 0.607              | Independent          |
| 4   | Contam SR / LOF k SR      | 0.725 / 0.924      | Moderate / Robust    |
| 5   | 가설 성립                 | 7/20               | 35% 성립             |

---

## 10. SHAP 피처 중요도 분석

3종 모델에 SHAP를 적용하여 각 모델이 이상 판정 시 어떤 피처에 의존하는지를 정량적으로 분석하였다.

| Explainer       | 적용 모델        | 정확도      | 속도      |
| --------------- | ---------------- | ----------- | --------- |
| TreeExplainer   | Isolation Forest | Exact       | 수 초     |
| KernelExplainer | LOF, SVM         | Approximate | ~5분/전체 |

### 글로벌 피처 중요도 (Mean |SHAP|, 정규화 비율)

| 피처                 | IF        | LOF       | SVM       |
| -------------------- | --------- | --------- | --------- |
| `intl_price_usd_pct` | **18.4%** | 13.5%     | 17.2%     |
| `exchange_rate_pct`  | 17.0%     | 15.7%     | 17.0%     |
| `transmission_rate`  | 16.9%     | **21.8%** | 16.0%     |
| `ect_or_spread`      | 16.4%     | 12.3%     | **19.6%** |
| `downstream_pct`     | 16.2%     | 20.9%     | 13.0%     |
| `upstream_pct`       | 15.8%     | 15.9%     | 16.5%     |

3종 모델이 각각 다른 피처를 1위로 선택하며(IF→국제가, LOF→전이율, SVM→ect_or_spread), 앙상블이 가격 전달 구조의 서로 다른 측면을 상호보완적으로 커버하고 있음을 실증한다.

### SHAP 시각화 산출물

| 산출물                            | 설명                                               |
| --------------------------------- | -------------------------------------------------- |
| Global Bar Plot (절대값 + 정규화) | 3종 모델 피처 중요도 비교                          |
| Per-Unit Top Feature Table        | 20유닛별 모델별 top 피처 + Share%                  |
| Heatmap (연도 집계 / 월별 상세)   | 시점×피처 SHAP 값, 이상치 필터·기간 선택·툴팁 지원 |
| Beeswarm Plot (PNG ×3)            | 전체 관측치 SHAP 분포, 점 색상=피처 원시값         |

---

## 11. 실험 이력

8회의 체계적 실험을 통해 최종 설정을 확정하였다.

| #   | 카테고리 | 변경 내용                   | 결과                             |
| --- | -------- | --------------------------- | -------------------------------- |
| 1   | Baseline | 6종, c=0.10, StandardScaler | ESR 0.629, 가설 5/20             |
| 2   | 피처     | 10종 (+lag1 +std3)          | ESR 하락, 가설 동일 → 실패       |
| 3   | 피처     | 8종 (+lag1만)               | ESR 하락, 가설 3/20 → 실패       |
| 4   | 파라미터 | c=0.08                      | **가설 7/20, P_ml 0.260** → 채택 |
| 5   | 파라미터 | c=0.12                      | ESR 최고(0.661)이나 가설 6/20    |
| 6   | 전처리   | RobustScaler                | 가설 4/20 → 실패                 |
| 7   | 측정     | 연속형 앙상블 AUC           | AUC 0.55→0.63 → 적용             |
| 8   | 피처     | 7종 (+positive_shock)       | 가설 3/20 → 실패                 |

확정 사항: 6종 피처, c=0.08, StandardScaler, 연속형 앙상블 AUC
유의 사항 : #7번 실험 전체 평균 AUC 0.607로 개선 (일부 유닛 최고 0.630 달성)

---

## 12. 디렉토리 구조 (출력물)

```
data/processed/phase7_ml/
├── features/                          ← 스케일링 전 원시 피처 (20개 CSV)
├── predictions/                       ← 3종 모델 판정 + 앙상블 (20개 CSV)
├── cross_validation/                  ← 통계-ML 교차 대조 (20개 CSV)
├── confidence_grades/                 ← 신뢰도 등급 (20개 CSV, 이상 시점만)
├── models/{YYYYMMDD_HHMM}/           ← 학습된 모델 pkl + run_log (80개 + 1개)
└── phase7_ml_summary.csv             ← 전체 요약

tests/phase7_ml/results/
├── run_{YYYYMMDD_HHMMSS}/            ← 5축 평가 결과 (축별 CSV + run_meta.json)
└── latest/                           ← 최신 결과 복사본

tests/shap/results/
├── {YYYYMMDD_HHMM}_IF/              ← IF SHAP (20개 CSV + summary + meta)
├── {YYYYMMDD_HHMM}_LOF/             ← LOF SHAP
├── {YYYYMMDD_HHMM}_SVM/             ← SVM SHAP
└── 대시보드_{YYYYMMDD_HHMM}/         ← SHAP 대시보드 HTML + Beeswarm PNG
```
