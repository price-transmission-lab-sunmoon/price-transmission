# Phase 8 — 결과 종합 및 로버스트니스 체크

> **작성일**: 2026-05-22  
> **목적**: Phase 7(통계 탐지)과 Phase 7-ML(ML 보조 교차검증) 산출물을 종합하여 신뢰도 등급별 이상 시점을 확정하고, 3종 로버스트니스 체크 및 품목 간 이상 동조성 분석(Phase 8.5)을 수행한다.

---

## 1. 개요

Phase 8은 새로운 탐지를 수행하지 않는다. Phase 7/7-ML의 산출물을 **집계·비교·대조**하여, 분석 결과의 신뢰성을 검증하고 논문에 삽입할 핵심 테이블/수치를 생산하는 단계이다.

3개 하위 모듈로 구성된다:

| 모듈 | 역할 | 출력물 |
|------|------|--------|
| 결과 종합 (S1~S5) | 신뢰도 집계, 일치율, 횡단 비교, 도매 비교, 외부 충격 대조 | CSV 7개 |
| 로버스트니스 (R1~R3) | 롤링 윈도우, 계절 조정, contamination 민감도 | CSV 3개 + JSON 1개 |
| 동조성 분석 (T1~T6) | 히트맵, 동시 탐지, 케이스 A/B/C, ML reference | CSV 6개 |

전체 출력물: 18개 파일 (CSV 16개 + JSON 2개), 총 약 280 KB.

---

## 2. 코드 구조

```
src/preprocessing/phase8/
    phase8_common.py           공통 모듈 (데이터 로딩, 충격 윈도우, Jaccard, Cohen Kappa)
    phase8_summary.py          결과 종합 S1~S5
    phase8_robustness.py       로버스트니스 R1~R3
    phase8_5_synchrony.py      동조성 분석 T1~T6
    phase8_run.py              통합 실행 진입점
```

`phase8_run.py`가 S1~S5 → R1~R3 → T1~T6 → meta JSON 순서로 전체를 실행한다.

---

## 3. 실행 방법

```bash
python src/preprocessing/phase8/phase8_run.py
```

소요 시간: 약 15~30초. 의존성: pandas, numpy, scikit-learn.

---

## 4. 입력 파일

### Phase 7 산출물 (통계 탐지)

| 파일 | 경로 | 파일 수 | 용도 |
|------|------|---------|------|
| phase7_summary.csv | phase7/ | 1 | 통계 탐지 이벤트 2,266건 |
| {cid}_{seg}_pattern1.csv | phase7/pattern1/ | 33 | 패턴 1 상세 (방향 역전 + 시차 이탈) |
| {cid}_{seg}_pattern2_zscore.csv | phase7/pattern2/ | 20 | 패턴 2 상세 (Z-score + IQR) |
| {cid}_{seg}_pattern2_asymmetry.csv | phase7/pattern2/ | 20 | 비대칭 검정 |
| {cid}_{seg}_pattern3.csv | phase7/pattern3/ | 10 | 패턴 3 상세 (스프레드 누적) |
| {cid}_{seg}_robustness_W{36,60}.csv | phase7/robustness/ | 40 | 롤링 윈도우 민감도 (R1 입력) |
| {cid}_{seg}_stat_timeseries.csv | phase7/stat_timeseries/ | 33 | 전 시점 시계열 (R3 피처 추출) |

### Phase 7-ML 산출물 (ML 보조 교차검증)

| 파일 | 경로 | 파일 수 | 용도 |
|------|------|---------|------|
| phase7_ml_summary.csv | phase7_ml/ | 1 | ML 20유닛 요약 |
| {cid}_{seg}_ml_predictions.csv | phase7_ml/predictions/ | 20 | 3종 모델 판정 + 앙상블 |
| {cid}_{seg}_cross_val.csv | phase7_ml/cross_validation/ | 20 | 통계-ML 교차 대조 |
| {cid}_{seg}_grades.csv | phase7_ml/confidence_grades/ | 20 | 신뢰도 등급 (high/medium/reference) |

### 기준선·구조 변화

| 파일 | 경로 | 파일 수 | 용도 |
|------|------|---------|------|
| {cid}_{seg}_baseline.json | phase4/baseline/ | 33 | warmup_end, 정상 시차 (R2 입력) |
| {cid}_{seg}_breakpoints.json | phase6/breakpoints/ | 33 | 구조 변화, Chow Test |

### Phase 1 로버스트니스 (R2 입력)

| 파일 | 경로 | 파일 수 | 용도 |
|------|------|---------|------|
| {cid}_changes.csv | phase1/changes/ | 10 | STL 기반 변화율 |
| {cid}_dummy_changes.csv | phase1/robustness/ | 10 | 계절 더미 기반 변화율 |

### 설정

| 파일 | 경로 | 용도 |
|------|------|------|
| product_config.json | data/processed/ | 품목·구간 설정 |

---

## 5. 출력 파일

```
data/processed/phase8/
├── summary/
│   ├── confidence_summary.csv              S1: 신뢰도 등급 집계
│   ├── agreement_analysis.csv              S2: 통계-ML 일치율
│   ├── cross_commodity_comparison.csv      S3: 품목 간 횡단 비교
│   ├── wholesale_comparison.csv            S4: 도매 그룹 비교
│   ├── wholesale_downstream_analysis.csv   S4: 도매 하류 전달
│   ├── shock_correspondence.csv            S5: 외부 충격 요약
│   └── shock_detail.csv                    S5: 외부 충격 상세
├── robustness/
│   ├── rolling_window_sensitivity.csv      R1: 롤링 윈도우 민감도
│   ├── seasonal_method_comparison.csv      R2: 계절 조정 방식 비교
│   ├── contamination_sensitivity.csv       R3: contamination 민감도
│   └── robustness_summary.json             R1~R3 전체 요약
├── synchrony/
│   ├── heatmap_data.csv                    T1: 히트맵 데이터
│   ├── monthly_co_detection.csv            T2: 월별 동시 탐지
│   ├── case_A_ukraine.csv                  T3: 케이스 A
│   ├── case_B_russia_drought.csv           T4: 케이스 B
│   ├── case_C_feed_livestock.csv           T5: 케이스 C
│   └── ml_reference_co_occurrence.csv      T6: ML reference 동시 발생
└── phase8_meta.json                        전체 실행 메타 정보
```

---

## 6. 파라미터 및 설계 결정

### 6.1 파라미터

| 파라미터 | 값 | 용도 |
|----------|-----|------|
| Jaccard 안정 기준 | ≥ 0.7 | stable 판정 |
| Jaccard 보통 기준 | 0.4 ~ 0.7 | moderate 판정 |
| Jaccard 민감 기준 | < 0.4 | sensitive 판정 |
| R2 롤링 윈도우 | W=48 | 계절 더미 비교 시 패턴 2 재산출 윈도우 |
| R2 Z-score 경고 | ±2.0 | 패턴 2 재산출 임계값 |
| R2 IQR 배수 | 1.5 | 패턴 2 재산출 Tukey 기준 |
| R3 contamination 값 | 0.05, 0.08, 0.10, 0.12, 0.15 | ML 재실행 (0.08이 기본값) |
| R3 앙상블 기준 | ≥ 2/3 | ML consensus threshold |
| T5 반응 윈도우 | 1, 3, 6개월 | 사료→축산물 시차 확인 범위 |
| T6 동시 발생 기준 | k ≥ 3 | ML reference 동시 발생 최소 품목 수 |

### 6.2 외부 충격 윈도우 (eval_common.py 기준)

| ID | 이벤트 | 시작 | 종료 | 대상 품목 수 |
|----|--------|------|------|-------------|
| E1 | 2008 글로벌 금융위기 | 2008-07 | 2009-01 | 10 (전체) |
| E6 | 2010 러시아 가뭄·수출 금지 | 2010-08 | 2011-06 | 7 |
| E9 | 2015-16 역대급 엘니뇨 | 2015-09 | 2016-06 | 6 |
| E2 | 2020 COVID-19 팬데믹 | 2020-02 | 2020-06 | 10 (전체) |
| E4 | 2022 우크라이나 전쟁 | 2022-02 | 2022-10 | 4 |

### 6.3 설계 결정

**(1) 계절 더미 비교 범위 (R2)**  
Phase 1의 dummy_changes CSV가 이미 존재하므로 Phase 1 재실행은 불필요. Phase 2~6은 재실행하지 않고 STL 기반 결과를 공유한다. 즉, 공적분 검정·VAR/VECM 모형·ECT는 STL 기반과 동일하며, 변화율 → 전이율 → Z-score/IQR 단계만 계절 더미로 재산출하여 비교한다. 이 가정은 논문에 명시한다.

**(2) contamination 재실행 범위 (R3)**  
기존 실험(experiment_comparison.md)의 0.08/0.10/0.12 결과는 run_meta.json 파라미터 로깅 불일치가 확인되어, 0.05/0.08/0.10/0.12/0.15 전수를 Phase 8 내에서 재실행한다. stat_timeseries에서 6종 피처를 추출하고 동일한 StandardScaler + 3종 모델을 적용한다.

**(3) 케이스 B 변경**  
원래 브라질 서리(2021~22)로 계획했으나, eval_common.py v2에서 E3(브라질 서리)이 삭제됨(E3-E4 윈도우 겹침). 대신 E6(2010 러시아 가뭄)으로 교체. 케이스 A(우크라이나)와 둘 다 곡물 공급 충격이지만 시기가 12년 차이나서, 동조 패턴의 시간적 일관성 비교가 가능.

**(4) 전체 기간 vs 하위 기간 비교**  
구조 변화가 있는 구간이 5개(beef B, maize D', palmoil D', sugar D', wheat D')뿐이고, ML 적용 구간(A·B)은 beef B 1개뿐이라 별도 분석 테이블 대신 서술적 비교로 충분하다고 판단.

---

## 7. 결과 종합 (S1~S5)

### 7.1 S1: 신뢰도 등급 집계

**confidence_summary.csv** — 20개 유닛(A·B) + ALL 합계 행.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id | str | 품목 (ALL = 전체 합계) |
| segment | str | A / B / ALL |
| total_anomalies | int | 이상 이벤트 총수 (high + medium + reference) |
| high | int | 고신뢰: 통계 + ML 동시 탐지 |
| medium | int | 중신뢰: 통계만 탐지 |
| reference | int | 참고: ML만 탐지 |
| high_pct | float | high / total_anomalies × 100 |
| stat_only | int | = medium |
| ml_only | int | = reference |

**전체 결과:**

| 등급 | 건수 | 비율 | 의미 |
|------|------|------|------|
| high | 189 | 11.0% | 통계·ML 모두 이상 판정. 가장 신뢰할 수 있는 이상. |
| medium | 1,334 | 77.9% | 통계만 탐지. 패턴 규칙은 위반했으나 ML 분포에서는 정상 범주. |
| reference | 189 | 11.0% | ML만 탐지. 통계 규칙은 안 걸렸으나 6종 피처 결합에서 이상. |
| **합계** | **1,712** | **100%** | |

**품목별 해석:**

- **sugar B (high 21.2%)**: high 비율 1위. 정제당(PPI)은 원당 수입가에 강하게 연동되어, 전달 이상이 발생하면 통계·ML 모두 일관되게 포착한다. 가격 전달 구조가 명확한 품목에서 두 방법의 합의가 높다.
- **palmoil B (17.9%)**, **maize B (15.8%)**: B 구간(수입단가→PPI) 상위권. PPI 품목(유지, 전분)이 수입가에 직접 연동되는 가공 구조를 반영.
- **banana (A 9.2%, B 7.6%)**: 이벤트 총량은 최다(A 141건, B 131건)지만 high 비율은 하위. 바나나는 국제가 변동성이 워낙 커서 통계가 많이 잡지만, ML이 이 높은 변동성을 "정상 범주"로 학습하여 걸러낸다.
- **coffee B (4.3%)**: high 비율 최저. 관측 기간이 75개월(2019-12~2026-02)으로 짧아 ML 학습 데이터가 부족하다. warmup 후 탐지 가능 기간이 약 26개월뿐.

**구간 비교:**  
구간 A(국제가→수입단가)에서 이벤트 총량이 더 많지만(970 vs 742), 구간 B(수입단가→PPI)에서 high 비율이 더 높다(12.7% vs 10.6%). B 구간에서 통계와 ML이 더 일관되게 같은 시점을 이상으로 판정한다.

---

### 7.2 S2: 통계-ML 일치율 분석

**agreement_analysis.csv** — 20개 유닛.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id | str | 품목 |
| segment | str | A / B |
| total_months | int | 전체 관측 월 수 (결측 제거 후) |
| both_detected | int | 통계 ✓ + ML ✓ |
| stat_only | int | 통계 ✓ + ML ✗ |
| ml_only | int | 통계 ✗ + ML ✓ |
| both_normal | int | 통계 ✗ + ML ✗ |
| agreement_rate | float | (both_detected + both_normal) / total × 100 |
| cohen_kappa | float | Cohen's Kappa 계수 |

**전체 결과:**

| 지표 | 값 |
|------|-----|
| 평균 일치율 | 68.4% |
| 평균 Cohen's Kappa | 0.093 |
| 4분류 합계 | both=189, stat_only=1,334, ml_only=189, normal=3,101 (총 4,813개월) |

**Kappa 해석 (Landis & Koch, 1977):**  
0.093은 "약간 일치(slight)" 수준이다. 그러나 이것은 문제가 아니라 설계 의도와 부합한다. 통계 이상 비율(31.6%)과 ML 이상 비율(7.9%)의 기저율 차이가 크기 때문에, 우연 일치를 보정하면 실질적 일치가 낮게 산출된다. ML(contamination=0.08)은 통계와 동일한 결과를 내는 것이 목적이 아니라, 독립적 보조 검증 역할이다.

**주목할 유닛:**

- **sugar B (Kappa 0.28)**: 가장 높은 일치도. 정제당의 가격 전달 구조가 명확하여 통계와 ML이 비교적 같은 시점을 이상으로 판정한다.
- **coffee B (Kappa -0.04)**: 음수 = 우연보다 못한 불일치. 데이터 부족(66개월)으로 ML이 제대로 학습하지 못한 결과.
- 구간 B(평균 Kappa 0.12)가 A(0.07)보다 높음. B 구간에서 통계·ML 탐지 패턴이 더 일관적.

---

### 7.3 S3: 품목 간 횡단 비교

**cross_commodity_comparison.csv** — 20개 유닛.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id | str | 품목 |
| segment | str | A / B |
| total_obs | int | 전체 관측 수 |
| p1_count / p1_rate | int / float | 패턴 1 건수 / 탐지율(%) |
| p2_count / p2_rate | int / float | 패턴 2 건수 / 탐지율(%) |
| p3_count / p3_rate | int / float | 패턴 3 건수 / 탐지율(%) (B만, A는 0) |
| total_stat / total_stat_rate | int / float | 통계 탐지 총 건수 / 탐지율(%) |
| ml_detected | int | ML 탐지 건수 |
| high_count | int | 고신뢰 건수 |
| has_wholesale | bool | 도매 단계 유무 |

**구간 A (국제가 → 수입단가) 탐지율 순위:**

| 품목 | 관측 | P1 | P2 | 전체 | ML | high |
|------|------|-----|-----|------|-----|------|
| banana | 314 | 41.1% | 4.5% | 44.3% | 21 | 13 |
| orange | 314 | 36.9% | 3.2% | 39.2% | 25 | 12 |
| soybean | 314 | 31.2% | 4.1% | 34.1% | 21 | 12 |
| sugar | 314 | 28.3% | 5.4% | 33.1% | 21 | 13 |
| beef | 314 | 29.9% | 3.8% | 31.8% | 18 | 13 |
| groundnuts | 99 | 30.3% | 2.0% | 31.3% | 7 | 4 |
| wheat | 314 | 28.0% | 2.2% | 29.3% | 22 | 10 |
| palmoil | 314 | 26.4% | 2.5% | 29.0% | 23 | 9 |
| maize | 314 | 23.6% | 3.8% | 26.8% | 24 | 10 |
| coffee | 75 | 26.7% | 0.0% | 26.7% | 7 | 3 |

**구간 B (수입단가 → PPI) 탐지율 순위:**

| 품목 | 관측 | P1 | P2 | P3 | 전체 | ML | high |
|------|------|-----|-----|-----|------|-----|------|
| banana | 314 | 30.6% | 3.5% | 7.3% | 38.5% | 21 | 10 |
| beef | 314 | 28.0% | 1.9% | 8.9% | 35.7% | 23 | 13 |
| orange | 314 | 28.7% | 3.2% | 2.5% | 33.4% | 22 | 11 |
| groundnuts | 99 | 29.3% | 2.0% | 0.0% | 29.3% | 6 | 4 |
| coffee | 75 | 18.7% | 1.3% | 8.0% | 26.7% | 5 | 1 |
| soybean | 314 | 20.1% | 4.1% | 1.6% | 25.2% | 22 | 10 |
| palmoil | 314 | 9.6% | 3.5% | 5.7% | 17.8% | 24 | 12 |
| wheat | 314 | 9.9% | 3.5% | 2.5% | 15.6% | 25 | 9 |
| maize | 314 | 4.5% | 3.8% | 8.6% | 15.6% | 19 | 9 |
| sugar | 314 | 5.7% | 3.2% | 5.1% | 13.4% | 22 | 11 |

**핵심 발견:**

- 구간 A 탐지율이 B보다 전반적으로 높다 — 국제가→수입단가 전달 과정에서 이상이 더 빈번하다.
- banana, orange가 최상위 — 과일류는 국제가 변동성이 크고 수입 경로가 단순하여 충격이 불안정하게 전달된다.
- 패턴 1(방향 역전/시차 이탈)이 대부분의 탐지를 주도하며, 패턴 2(전이율 Z-score)는 2~5% 수준으로 보조적이다.
- 패턴 3(스프레드 누적)은 B 구간에서만 적용되며, beef(8.9%), maize(8.6%), coffee(8.0%)가 상위 — 이 품목들은 수입단가→PPI 장기 균형 관계에서 스프레드가 누적 확대되는 구조적 이상을 보인다.

---

### 7.4 S4: 도매 단계 비교 분석

**wholesale_comparison.csv** — 2행 (3구간 vs 4구간).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| group | str | '3seg' / '4seg' |
| n_commodities | int | 품목 수 |
| avg_p1_rate_A / avg_p1_rate_B | float | 구간 A/B 평균 패턴 1 탐지율 |
| avg_p2_rate_A / avg_p2_rate_B | float | 구간 A/B 평균 패턴 2 탐지율 |
| avg_stat_rate_A / avg_stat_rate_B | float | 구간 A/B 평균 전체 탐지율 |
| avg_high_pct | float | 평균 고신뢰 비율 |

**그룹 비교:**

| 지표 | 3구간 (7종) | 4구간 (3종) | 차이 |
|------|-----------|-----------|------|
| 패턴1 A | 27.7% | 36.1% | +8.4%p |
| 패턴1 B | 13.8% | 29.5% | +15.7%p |
| 전체 A | 30.1% | 38.3% | +8.2%p |
| 전체 B | 21.4% | 33.7% | +12.3%p |
| high 비율 | 13.4% | 9.9% | -3.5%p |

4구간 품목(banana, orange, groundnuts)이 A·B 모두에서 탐지율이 높다. 과일류는 수입 의존도가 높고 국제가 변동성이 커서 충격이 빈번하게 발생한다. 반면 high 비율은 3구간이 더 높은데, 이는 과일류의 높은 변동성을 ML이 "정상 범주"로 학습하여 걸러내기 때문이다.

**wholesale_downstream_analysis.csv** — 6행 (3품목 × 2쌍).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id | str | 품목 |
| seg_pair | str | 'A→C' / 'B→D' |
| upstream_count / downstream_count | int | 상류/하류 탐지 건수 |
| co_occurrence | int | 동월 동시 탐지 건수 |
| co_occurrence_rate | float | 동시 탐지율 (%) |
| downstream_follows_1m / downstream_follows_3m | int | 상류 후 1/3개월 내 하류 탐지 |

**품목별 해석:**

- **banana A→C**: 동시 탐지 33.8%. 바나나 유통 구조(산지 직수입→도매시장)가 중간 단계 없이 빠르게 작동하여 국제가→도매가 전달이 동시적이거나 1개월 내 일어난다.
- **groundnuts B→D**: 상류(B) 29건인데 하류(D)가 3건뿐, 동시 탐지 0건. 도매→소매 구간에서 이상이 거의 흡수되며, 유통 마진이 완충 역할을 한다.
- A→C 동시 탐지율(29~34%)이 B→D(0~32%)보다 전반적으로 높다. 국제가 충격이 도매까지 빠르게 전달되지만, 도매→소매 전달은 품목에 따라 크게 다르다.

---

### 7.5 S5: 외부 충격 시점 대조

**shock_correspondence.csv** — 5행 (충격 5개).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| shock_id | str | E1~E9 |
| shock_name | str | 이벤트명 |
| shock_start / shock_end | str | 윈도우 시작/종료 |
| n_applicable_segments | int | 적용 가능 유닛 수 |
| stat_hits / stat_recall | int / float | 통계 탐지 유닛 수 / 회수율 |
| ml_hits / ml_recall | int / float | ML 탐지 유닛 수 / 회수율 |
| high_hits | int | 고신뢰 탐지 유닛 수 |
| total_stat_events_in_window / total_ml_events_in_window | int | 윈도우 내 이벤트 총 건수 |

**shock_detail.csv** — 74행 (충격×유닛).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| shock_id | str | 이벤트 ID |
| commodity_id / segment | str | 품목 / 구간 |
| stat_detected_in_window / ml_detected_in_window | bool | 통계/ML 탐지 존재 여부 |
| high_in_window | bool | 고신뢰 탐지 존재 여부 |
| stat_event_count / ml_event_count | int | 이벤트 건수 |
| pattern_types | str | 탐지된 패턴 유형 |

**충격별 회수율:**

| ID | 이벤트 | 유닛 | stat 회수율 | ML 회수율 | high |
|----|--------|------|-----------|----------|------|
| E4 | 2022 우크라이나 | 8 | 100% | 75% | 6 |
| E6 | 2010 러시아 가뭄 | 14 | 85.7% | 50% | 3 |
| E2 | 2020 COVID-19 | 20 | 75% | 10% | 2 |
| E9 | 2015-16 엘니뇨 | 12 | 75% | 8.3% | 1 |
| E1 | 2008 금융위기 | 20 | 70% | 80% | 11 |

**충격별 해석:**

- **E4 (우크라이나)**: stat 100%, ML 75%. 가장 강한 충격으로 통계가 전 유닛에서 포착. soybean A·B만 ML이 못 잡음 — 대두는 우크라이나 직접 수출 품목이 아니라 간접 영향(대체재 효과)이라 피처 결합에서 이상 패턴이 약한 것으로 해석된다.
- **E1 (금융위기)**: ML 80% > stat 70%. ML이 통계보다 회수율이 높은 **유일한 이벤트**. 금융위기는 환율·국제가·전이율이 동시에 극단적으로 변동하는 다차원 충격이라, 단일 지표를 보는 통계보다 6종 피처 결합을 보는 ML이 유리하다.
- **E2 (COVID)**: stat 75% vs ML 10%. COVID 윈도우가 5개월로 매우 짧아, 전체 기간 학습(transductive) ML에서 단기 충격이 유의미한 이상으로 잡히기 어렵다. 통계(패턴 1)는 매월 독립 판정이라 단기 충격도 포착 가능.
- **E9 (엘니뇨)**: ML 8.3%. 기후 현상은 수개월에 걸쳐 서서히 가격에 영향을 미쳐 ML의 이상 탐지에 불리하다.

---

## 8. 로버스트니스 체크 (R1~R3)

### 8.1 R1: 롤링 윈도우 민감도 — **STABLE**

**rolling_window_sensitivity.csv** — 20개 유닛.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id / segment | str | 품목 / 구간 |
| w36_flags / w48_flags / w60_flags | int | 각 윈도우 탐지 건수 |
| w36_w48_overlap / w48_w60_overlap | int | 겹치는 탐지 건수 |
| w36_w48_jaccard / w48_w60_jaccard | float | Jaccard 유사도 |
| stability_verdict | str | stable / moderate / sensitive |

**결과:**

| 지표 | 값 |
|------|-----|
| 평균 Jaccard (W36↔W48) | 0.789 |
| 평균 Jaccard (W48↔W60) | 0.812 |
| 판정 분포 | 15 stable, 5 moderate, 0 sensitive |

롤링 윈도우 크기 변경에 대해 패턴 2 탐지가 안정적이다. W=48 기본값의 타당성이 검증되었다.

**예시:**

- sugar A: W36=17, W48=17, W60=15. J(36-48)=0.89, J(48-60)=0.88 → stable. 3개 윈도우에서 거의 동일한 시점을 탐지한다.
- wheat A: W48↔W60은 J=1.00(완전 동일)이나, W36에서 4건 추가 탐지 → 짧은 윈도우가 노이즈에 약간 더 민감함을 보여준다.

---

### 8.2 R2: 계절 조정 방식 비교 — **SENSITIVE**

**seasonal_method_comparison.csv** — 20개 유닛.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id / segment | str | 품목 / 구간 |
| stl_flags / dummy_flags | int | STL / 계절 더미 기반 탐지 건수 |
| overlap | int | 동시 탐지 건수 |
| jaccard | float | Jaccard 유사도 |
| stl_only / dummy_only | int | 각 방식에서만 탐지된 건수 |
| stability_verdict | str | stable / moderate / sensitive |

**결과:**

| 지표 | 값 |
|------|-----|
| 평균 Jaccard | 0.178 |
| 판정 분포 | 1 stable, 1 moderate, 18 sensitive |

계절 조정 방식 변경이 패턴 2 탐지에 매우 민감하게 영향을 미친다.

**예시:**

- palmoil A: STL=8건, Dummy=17건, overlap=0건, J=0.000 — 겹치는 시점이 한 건도 없다. STL의 비선형 계절 추정과 더미의 선형 추정이 팜유의 변화율 수준에서 크게 달라지기 때문이다.
- coffee A: STL=0건, Dummy=0건, J=1.000 — 유일한 stable. 관측 기간이 짧아(75개월) 두 방식 모두 탐지 자체가 없다.

**원인**: 패턴 2는 전이율(하류 변화율 / 상류 변화율)의 롤링 Z-score + IQR로 판정한다. 계절 조정 방식이 바뀌면 분모·분자 모두 변하므로 전이율이 상당히 달라지며, 특히 분모가 0에 가까울 때 전이율이 폭발하는 경계에서 STL과 더미가 서로 다른 값을 산출한다.

**논문 시사점**: "계절 조정 방법 선택이 가격 전달 이상 탐지의 가장 민감한 방법론적 결정"이라는 발견 자체가 논문 기여가 될 수 있다.

---

### 8.3 R3: ML contamination 민감도 — **MODERATE**

**contamination_sensitivity.csv** — 20개 유닛.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| commodity_id / segment | str | 품목 / 구간 |
| c005_detected ~ c015_detected | int | 각 contamination에서의 탐지 건수 |
| c005_c008_jaccard ~ c015_c008_jaccard | float | 기본값(0.08) 대비 Jaccard |
| stability_verdict | str | stable / moderate / sensitive |

**결과:**

| contamination | 총 탐지 건수 | 기본값(0.08) 대비 Jaccard |
|--------------|-------------|------------------------|
| 0.05 | 243 | 0.529 |
| 0.08 (기본) | 378 | — |
| 0.10 | 474 | 0.670 |
| 0.12 | 575 | 0.607 |
| 0.15 | 697 | 0.523 |

전체 평균 Jaccard: 0.582 → MODERATE. 20/20 유닛이 moderate.

0.08↔0.10 간 Jaccard가 0.67로 가장 안정적(인접한 값)이고, 0.08↔0.15는 0.52로 가장 민감하다. contamination이 커질수록 기본값과의 괴리가 커지는 것은 자연스러운 현상이다.

**robustness_summary.json** — R1~R3 전체 요약.

```json
{
  "rolling_window": {"avg_jaccard_w36_w48": 0.789, "verdict": "stable"},
  "seasonal_method": {"avg_jaccard": 0.178, "verdict": "sensitive"},
  "contamination": {"overall_avg_jaccard": 0.582, "verdict": "moderate"}
}
```

---

## 9. 동조성 분석 (T1~T6)

### 9.1 T1~T2: 히트맵 데이터 및 월별 동시 탐지

**heatmap_data.csv** — 5,372행 (월 × 품목 × 구간).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | date | 월 (YYYY-MM-01) |
| commodity_id / segment | str | 품목 / 구간 |
| pattern_type | str | pattern1 / pattern2 / pattern3 / none |
| confidence_grade | str | high / medium / reference / none |
| stat_detected / ml_detected | bool | 통계 / ML 탐지 여부 |

**monthly_co_detection.csv** — 구간별 월 단위 동시 탐지 집계.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | date | 월 |
| segment | str | A / B |
| n_commodities_stat / n_commodities_ml / n_commodities_high | int | 동시 탐지 품목 수 |
| commodity_list_stat | str | 탐지 품목 목록 |
| in_shock_window | bool | 외부 충격 윈도우 내 여부 |
| shock_id | str | 해당 충격 ID |

최대 동시 탐지: 구간 A에서 8품목 (2009-02, 금융위기 직후). 대부분의 고동시 탐지 월이 외부 충격 윈도우 내 또는 직후에 발생한다.

---

### 9.2 T3: 케이스 A — 2022 우크라이나 전쟁

**case_A_ukraine.csv** — 9행 (2022-02 ~ 2022-10, wheat/maize/soybean 구간 A).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | date | 월 |
| {cid}_A_detected | bool | 해당 품목 구간 A 탐지 여부 |
| {cid}_A_pattern | str | 패턴 유형 |
| {cid}_A_grade | str | 신뢰도 등급 |
| n_simultaneous | int | 동시 탐지 품목 수 (0~3) |

**월별 타임라인:**

| 월 | 밀 | 옥수수 | 대두 | 동시 |
|----|-----|--------|------|------|
| 2022-02 | · | · | · | 0 |
| 2022-03 | · | ✓ pattern1/medium | ✓ pattern1/medium | 2 |
| 2022-04 | · | · | ✓ pattern1/medium | 1 |
| 2022-05 | · | · | · | 0 |
| 2022-06 | · | ✓ pattern2/medium | · | 1 |
| 2022-07 | ✓ pattern1/high | · | ✓ pattern1/medium | 2 |
| 2022-08 | ✓ pattern1/medium | · | · | 1 |
| 2022-09 | · | ✓ pattern1/high | · | 1 |
| 2022-10 | · | ✓ pattern1/high | · | 1 |

3품목 동시 탐지는 없지만 9개월 중 7개월에서 최소 1품목이 탐지된다. 전쟁 발발(2022-02) 직후에는 이상 미발현(시차 존재), 이후 옥수수·대두가 먼저 반응하고 밀이 7월에 뒤따르는 패턴을 보인다. 이는 우크라이나 충격이 품목별 수입 계약 시차를 두고 한국 가격에 전달되었음을 시사한다.

---

### 9.3 T4: 케이스 B — 2010 러시아 가뭄

**case_B_russia_drought.csv** — 11행 (2010-08 ~ 2011-06, 7품목 구간 A).

케이스 A(우크라이나)와 같은 구조. 7품목: wheat, maize, soybean, palmoil, sugar, coffee, beef.

**결과:**  
11개월 중 9개월에서 최소 1품목 탐지, 최대 동시 4품목(2010-10, 2011-03, 2011-06). 케이스 A보다 동조성이 강하며, 우크라이나가 밀·옥수수에 집중된 반면 러시아 가뭄은 팜유·설탕까지 파급되는 광범위한 충격이었음을 보여준다.

---

### 9.4 T5: 케이스 C — 사료→축산물 시차

**case_C_feed_livestock.csv** — 191행 (maize/soybean A 탐지 이벤트).

| 컬럼 | 타입 | 설명 |
|------|------|------|
| trigger_date | date | 트리거 날짜 (maize/soybean A 탐지 월) |
| trigger_commodity | str | maize / soybean |
| beef_A_response_1m / 3m / 6m | bool | 1/3/6개월 내 소고기 A 탐지 여부 |
| beef_A_first_response_lag | float | 최초 반응 시차 (개월, NaN=미반응) |

**결과:**

| 지표 | 값 |
|------|-----|
| 총 트리거 | 191건 (maize 84건 + soybean 107건) |
| 1개월 내 반응 | 66건 (34.6%) |
| 3개월 내 반응 | 125건 (65.4%) |
| 6개월 내 반응 | 176건 (92.1%) |
| 평균 최초 반응 시차 | 2.5개월 (중앙값 2개월) |
| 미반응 | 15건 (7.9%) |

**시차 분포:**

| 시차 | 건수 |
|------|------|
| 1개월 | 66 |
| 2개월 | 37 |
| 3개월 | 22 |
| 4개월 | 27 |
| 5개월 | 13 |
| 6개월 | 11 |

곡물(사료) 가격 이상이 소고기 가격 이상으로 시차 전파되는 경제학적 메커니즘이 데이터에서 관찰된다. 평균 2.5개월 시차는 사료 재고 소진 기간(1~2개월) + 축산물 출하 주기(1~3개월)와 일치하며, 6개월 내 반응률 92%는 곡물→축산물 가격 전달이 거의 필연적임을 시사한다.

---

### 9.5 T6: ML reference 동시 발생

**ml_reference_co_occurrence.csv** — k≥3인 월만 기록.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| date | date | 월 |
| segment | str | A / B |
| n_reference | int | reference 등급 품목 수 |
| commodity_list | str | 해당 품목 목록 |
| in_shock_window | bool | 외부 충격 윈도우 내 여부 |
| shock_id | str | 해당 충격 ID |

**결과:** 9건, 이 중 4건(44%)이 외부 충격 윈도우 내.

핵심 사례 — 2008-10 구간 A에서 7품목 동시 reference (banana, maize, orange, palmoil, soybean, sugar, wheat). 금융위기(E1) 한복판으로, 리먼브라더스 파산 직후 전 세계 원자재 가격이 급락하면서 통계 패턴 규칙은 이 시점을 안 잡았지만 ML이 6종 피처 결합 이상으로 탐지했다. 7품목 동시 reference는 우연이 아니라 실제 거시 충격의 증거이며, 비지도 ML이 경제적으로 유의미한 이상을 독립적으로 포착할 수 있음을 시사한다.

---

## 10. 설계 변경 이력

| 일자 | 변경 사항 | 사유 |
|------|----------|------|
| 2026-05-22 | contamination 0.10/0.12 기존 실험 결과 폐기, 전수 재실행 | run_meta.json 파라미터 로깅 불일치 확인 (전부 0.10으로 기록) |
| 2026-05-22 | 케이스 B: 브라질 서리 → 러시아 가뭄(E6)으로 교체 | eval_common.py v2에서 E3 삭제 (E3-E4 윈도우 겹침) |
| 2026-05-22 | 계절 더미 비교: Phase 1만 변경, Phase 2~6 미재실행 | Phase 1 dummy_changes가 이미 존재하여 재실행 불필요. 공적분·VAR/VECM 공유 가정은 논문에 명시. |
| 2026-05-22 | c_key 버그 수정: 0.10 → c01 → c010 | str(0.10).replace('.','') = '01' 문제. int(c*100):03d 방식으로 수정. |
| 2026-05-22 | str.contains()에 na=False 추가 | NaN 방어 코드 (코드 리뷰 피드백 반영) |
| 2026-05-22 | 변수명 jaccard_cols → jaccard_values | 가독성 개선 (코드 리뷰 피드백 반영) |

---

## 11. 주의사항 및 한계

1. **coffee 관측 기간 제약**: 75개월(2019-12~2026-02), warmup 후 탐지 가능 26개월. 품목 간 비교에서 동일선상에 놓기 어려우며, 별도 주석이 필요하다.

2. **계절 더미 비교(R2)에서 Phase 2~6 미재실행**: ECT·IRF·구조 변화 결과는 STL 기반을 공유한다. 엄밀한 전체 파이프라인 재실행이 아님을 논문에 명시해야 한다.

3. **ML transductive 한계**: 전체 기간 단일 fit 방식이라 단기 충격(COVID 5개월)이나 점진적 충격(엘니뇨)에 불리하다. 이는 ML 방법론 자체의 한계이지 구현의 문제가 아니다.

4. **Kappa 해석**: 낮은 Kappa는 설계 의도(독립적 보조 검증)와 부합하지만, 논문에서 이 맥락을 명확히 설명하지 않으면 방법론 비판으로 이어질 수 있다.

5. **T5 사료→축산물 시차**: 탐색적 분석으로, 곡물·소고기 이상의 동시 발생이 인과관계를 의미하지는 않는다. 전달 시차에 대한 엄밀한 Granger 인과 검정은 이 프로젝트 범위 밖이다.

6. **I(2) 시계열**: 땅콩 wholesale_price, 오렌지 intl_price_krw 2건이 I(2)이나 I(1)로 간주하고 진행하였다. Phase 8 결과 해석 시 이 품목의 구간에서 비정상적 탐지가 관찰되면 I(2) 한계를 고려해야 한다.

---

## 12. 다음 단계

- 논문 작성: Phase 8 결과 테이블/차트를 논문에 삽입. 시각화는 필요 시 별도 스크립트로 생성.
- 웹 대시보드: Phase 8 출력물을 DB에 적재하여 대시보드에서 조회 가능하도록 연동.
