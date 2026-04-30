# Phase 5~6 — 인과 방향 확정 및 구조 변화 탐지

> **작성일**: 2026-04-30  
> **목적**: Phase 5(Granger 인과 방향 확정)와 Phase 6(Bai-Perron 구조 변화 탐지 + Chow Test 교차 확인 + 하위 기간 분할·재추정)의 목적, 코드 역할, 실행 방법, 결과 해석을 정리

---

## 1. 개요

Phase 5는 4구간 품목(땅콩·바나나·오렌지) 구간 C(PPI↔도매가)에서 양방향 Granger 인과 검정을 수행하여 분석 방향을 확정하는 단계이다. Phase 6는 전 품목·전 구간의 전이율 시계열에서 구조 변화 시점을 탐지하고, 하위 기간별 VAR/VECM을 재추정하여 기간별 기준선을 산출하는 단계이다.

```
Phase 4 산출물 (baseline, model_routing.json)
Phase 1 산출물 (changes, seasonal_adjusted)
    │
    ▼
[Phase 5] Granger 인과 방향 확정
    ├─ 4구간 품목 구간 C: 양방향 Granger 인과 검정
    ├─ 3구간 품목: PL-P5-001 INFO 로그 후 PHASE_SKIP
    └─ granger_direction.json 생성
    │
    ▼
[Phase 6] 구조 변화 탐지 및 기간 분할
    ├─ 전이율 산출 (안정 구간 필터 적용)
    ├─ Bai-Perron (Dynp + BIC): 데이터 주도 변화 시점 탐지
    ├─ Chow Test (2008·2020·2022): 교차 확인
    ├─ 하위 기간 분할 (MIN_SUBPERIOD_OBS=60 미만 시 병합)
    └─ 하위 기간별 VAR/VECM 재추정 (Phase 4 함수 재사용)
    │
    ▼
Phase 7 (이상 패턴 탐지) 입력
```

---

## 2. 실행 방법

### 전제 조건

Phase 1~4가 완료되어 다음 파일이 존재해야 한다:
- `data/processed/product_config.json`
- `data/processed/phase1/changes/{cid}_changes.csv` (10개)
- `data/processed/phase1/seasonal_adjusted/{cid}_sa.csv` (10개)
- `data/processed/phase3/model_routing.json`
- `data/processed/phase4/baseline/{cid}_{seg}_baseline.json` (33개)

### Phase 5 실행

```bash
python src/preprocessing/phase5_granger_causality.py
```

### Phase 6 실행

```bash
python src/preprocessing/phase6_structural_breaks.py
```

Phase 5 → Phase 6 순서로 실행한다. Phase 6는 Phase 5 산출물에 직접 의존하지 않지만, 두 단계 모두 Phase 7의 입력이므로 순차 실행을 권장한다.

---

## 3. Phase 5 — Granger 인과 방향 확정

### 3.1 목적

구간 C(PPI↔도매가)는 유통 체계상 PPI와 도매가가 거의 동일한 단계에 위치하여 인과 방향이 이론적으로 불명확하다. 다른 구간(A, B, D, D')은 상류→하류 방향이 경제 이론으로 확립되어 있어 검정이 불필요하다. Phase 5는 구간 C에 대해서만 양방향 Granger 인과 검정을 수행하여 분석 방향을 실증적으로 확정한다.

### 3.2 적용 대상

| 품목 유형 | 품목 수 | 처리 |
| --- | --- | --- |
| 4구간 (has_wholesale=true) | 3종 (groundnuts, banana, orange) | 구간 C Granger 검정 수행 |
| 3구간 (has_wholesale=false) | 7종 | PL-P5-001 INFO 로그 후 PHASE_SKIP |

### 3.3 검정 방법

- 함수: `statsmodels.tsa.stattools.grangercausalitytests`
- 유의수준: 5%
- 최대 시차: `model_routing.json`의 해당 구간 `var_lag_aic`
- 입력: `{cid}_changes.csv`의 `ppi_pct`, `wholesale_price_pct` 컬럼

statsmodels 규약: `grangercausalitytests(data, maxlag)`에서 `data[:, 0]`이 종속변수, `data[:, 1]`이 독립변수(원인 후보). 귀무가설은 "독립변수가 종속변수를 Granger-인과하지 않는다". 시차 1~max_lag 각각에 대해 F검정을 수행하고, p값이 가장 작은 시차의 결과를 채택한다.

### 3.4 `confirmed_direction` 판정 로직

| PPI→도매가 | 도매가→PPI | confirmed_direction | 예외 코드 | Phase 7 적용 범위 |
| --- | --- | --- | --- | --- |
| ✔ 유의 | ✗ 비유의 | `ppi_to_wholesale` | — | 패턴 1·2·3 모두 |
| ✗ 비유의 | ✔ 유의 | `wholesale_to_ppi` | — | 패턴 1·2·3 모두 |
| ✔ 유의 | ✔ 유의 | `bidirectional` | PL-P5-003 | 패턴 1·2·3 모두 (PPI→도매가 기본 방향 유지) |
| ✗ 비유의 | ✗ 비유의 | `none` | PL-P5-002 | 패턴 1만 |

### 3.5 검정 결과

| 품목 | 관측치 | max_lag | PPI→도매가 F (p) | 도매가→PPI F (p) | 확정 방향 |
| --- | --- | --- | --- | --- | --- |
| 땅콩 | 98 | 3 | 8.7422 (0.0039) ✔ | 7.3939 (0.0011) ✔ | **bidirectional** |
| 바나나 | 313 | 3 | 0.3858 (0.5350) ✗ | 2.0790 (0.1268) ✗ | none |
| 오렌지 | 313 | 3 | 0.0388 (0.8439) ✗ | 1.9136 (0.1676) ✗ | none |

### 3.6 결과 해석

**땅콩** — 이전(84관측치, max_lag=2)에서는 양방향 비유의(`none`)였으나, 14개월 데이터 확장(98관측치)과 max_lag 변경(2→3)으로 양방향 유의(`bidirectional`)로 전환되었다. PPI(견과가공품)와 도매가(가락시장 땅콩)가 상호 영향을 주고받는 구조가 확인된 것이다. Phase 7에서 구간 C에 패턴 1·2·3 모두 적용 가능해졌다.

**바나나·오렌지** — 여전히 양방향 비유의(`none`). PPI가 '과실류' 합산이라 개별 품목 도매가와의 Granger 인과가 포착되지 않는 구조적 원인이 유지되고 있다. 다만 바나나의 도매가→PPI 방향은 p=0.41→0.13으로 크게 내려갔고, 데이터 추가 축적 시 유의 전환 가능성이 있다.

---

## 4. Phase 6 — 구조 변화 탐지 및 기간 분할

### 4.1 목적

가격 전달 구조는 25년(2000~2026) 전체 기간 동안 일정하지 않을 수 있다. 금융위기(2008), COVID-19(2020), 러시아-우크라이나 전쟁(2022) 등 외부 충격이 전달 구조 자체를 변화시켰을 가능성이 있다. Phase 6는 이 구조 변화를 데이터 주도 방식으로 탐지하고, 하위 기간별로 모형을 재추정하여 기간별 기준선을 산출한다. 이 기준선은 Phase 7에서 각 기간에 맞는 정상 전달 시차와 탄력성을 적용하는 데 사용된다.

### 4.2 전이율 산출

검정 대상 시계열은 전이율(= 하류 변화율 ÷ 상류 변화율)이다. 전이율은 상류→하류 전달의 크기를 직접 측정하는 지표로, "전이율이 변했다 = 전달 구조가 변했다"라는 해석이 가능하다.

안정 구간 필터: 상류 변화율의 절대값이 3%(STABILITY_THRESHOLD × 100) 미만인 월은 전이율을 NaN으로 처리한다. 이 임계치는 Phase 7 패턴 3의 국제가 안정 구간 정의(±3%)와 동일하다. NaN은 forward-fill 후 남은 선두 NaN은 backward-fill로 처리하고, 극단값은 ±10 범위로 클리핑한다.

### 4.3 Bai-Perron (Dynp + BIC)

ruptures 라이브러리의 `Dynp`(동적 프로그래밍)를 사용하여, 변화점 수 k=0~5 각각에 대해 전역 최적 분할을 구한 후, BIC가 최소인 k를 채택한다.

| 파라미터 | 값 | 근거 |
| --- | --- | --- |
| model | `normal` | 세그먼트별 평균 변화를 탐지 |
| min_size | 60 (MIN_SUBPERIOD_OBS) | 하위 기간 최소 관측치 — VAR/VECM 재추정에 필요한 최소 표본 |
| max_breakpoints | 5 | 25년 데이터에서 5개 이상의 구조 변화는 과적합 위험 |

BIC 산출: `BIC = n × ln(RSS/n) + k × ln(n)` (k = 2 × 세그먼트 수 + 변화점 수)

### 4.4 Chow Test

Bai-Perron의 교차 확인용으로, 경제적 사건에 대응하는 3개 고정 시점에서 구조 변화를 검정한다.

| 시점 | 경제적 사건 |
| --- | --- |
| 2008-01 | 글로벌 금융위기 + 곡물 가격 급등 |
| 2020-01 | COVID-19 팬데믹 |
| 2022-01 | 러시아-우크라이나 전쟁 |

H0: 두 기간의 회귀 계수(상수 + 시간 추세)가 동일하다. F검정으로 판정하며, 분석 범위 밖이거나 양분 구간의 관측치가 10개 미만이면 검정을 수행하지 않는다 (PL-P6-002).

### 4.5 하위 기간 분할 및 병합

Bai-Perron이 탐지한 변화 시점을 기준으로 하위 기간을 분할한다. `n_obs` < 60(MIN_SUBPERIOD_OBS)인 기간은 직전 기간에 병합하고, `merged_with` 필드에 병합 대상 ID를 기록한다. 모든 하위 기간이 60 미만이면 단일 기간으로 유지한다 (PL-P6-003).

### 4.6 하위 기간 재추정

2개 이상 독립 하위 기간이 있을 때만 수행한다. Phase 4의 `estimate_vecm()`/`estimate_var()` 함수를 재사용하며, 전체 기간의 `model_routing.json` 모형 유형(VECM/VAR)을 하위 기간에도 동일 적용한다(옵션 C 방식).

시차 축소: 하위 기간이 짧을 경우 `effective_lag = min(original_lag, n_obs // 10 - 1)`로 시차를 축소한다.

### 4.7 경계 사례 플래그

Phase 3에서 공적분 Trace가 임계값 근처이거나, 데이터 확장으로 모형이 전환됐거나, I(2) 플래그가 붙은 구간에 `borderline_cointegration: true`를 부착한다.

| 구간 | 사유 |
| --- | --- |
| groundnuts D | Trace=15.55 vs 임계값 15.49 (차이 0.06) |
| maize D' | 14개월 추가로 VECM→VAR 전환 |
| coffee B | Trace=14.73 (임계값 대비 95%) |
| coffee A | VAR→VECM 전환 + I(2) 플래그 |
| groundnuts B | I(2) 플래그 (땅콩 PPI) |
| groundnuts C | I(2) 플래그 (땅콩 PPI) |

---

## 5. Phase 6 검정 결과

### 5.1 Bai-Perron 구조 변화 탐지 요약

총 33개 구간 중 5개 구간에서 변화점이 탐지되었다 (15.2%).

| 품목 | 구간 | 변화 시점 | 하위기간 수 | 경계⚠ |
| --- | --- | --- | --- | --- |
| 밀 | D' | 2013-05, 2020-11 | 3 | |
| 옥수수 | D' | 2017-02 | 2 | ⚠ |
| 팜유 | D' | 2010-06, 2020-11 | 3 | |
| 설탕 | D' | 2011-09 | 2 | |
| 쇠고기 | B | 2005-01 | 2 | |

나머지 28개 구간은 변화점 없음 (단일 기간 유지).

### 5.2 구간별 패턴

**구간 A (국제가→수입단가)**: 10개 품목 전부 변화점 없음. 소국 개방경제의 국제 가격 수용 메커니즘이 25년간 안정적이다.

**구간 B (수입단가→PPI)**: 쇠고기만 2005-01에 변화점. 미국 BSE 사태(2003.12) 이후 수입 구조 전환과 일치한다.

**구간 C (PPI↔도매가)**: 3개 품목 전부 변화점 없음. Chow 2020에서 땅콩(F=49.2)과 바나나(F=8.6)가 유의하지만 BIC 기준으로 분할이 정당화되지 않는다.

**구간 D/D' (도매가/PPI→CPI)**: 4개 품목에서 변화점 탐지. 소비자 가격 단계에서 구조 변화가 집중되는 패턴이다. 유통 마진·소매 경쟁·가격 규제 등 통제 불가 요인이 개입하는 구간의 특성을 반영한다.

### 5.3 Chow Test 유의성 집계

| 시점 | 유의 / 검정 가능 | 비율 | 비고 |
| --- | --- | --- | --- |
| 2008-01 | 15 / 26 | 57.7% | 커피·땅콩은 범위 밖 |
| 2020-01 | 13 / 30 | 43.3% | 커피 2020-01은 관측치 부족 |
| 2022-01 | 12 / 33 | 36.4% | 전 품목 검정 가능 |

2008 금융위기의 구조 변화 영향이 가장 광범위하고, 2022 러시아-우크라이나 전쟁의 영향은 상대적으로 제한적이다.

### 5.4 하위 기간 재추정 결과

총 12개 하위 기간 모형이 재추정되었다.

| 품목 | 구간 | 기간 | n_obs | 모형 | 시차 | 피크 | 탄력성 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 밀 | D' | 2000-01~2013-04 | 160 | VECM | 3 | 24개월 | 1.129 |
| 밀 | D' | 2013-05~2020-10 | 90 | VECM | 3 | 24개월 | 0.677 |
| 밀 | D' | 2020-11~2026-02 | 64 | VECM | 3 | 1개월 | -0.311 |
| 옥수수 | D' ⚠ | 2000-01~2017-01 | 202 | VAR | 2 | 1개월 | 0.119 |
| 옥수수 | D' ⚠ | 2017-02~2026-02 | 107 | VAR | 2 | 2개월 | 0.358 |
| 팜유 | D' | 2000-01~2010-05 | 120 | VAR | 4 | 4개월 | 0.168 |
| 팜유 | D' | 2010-06~2020-10 | 121 | VAR | 4 | 4개월 | 0.615 |
| 팜유 | D' | 2020-11~2026-02 | 60 | VAR | 4 | 3개월 | 0.741 |
| 설탕 | D' | 2000-01~2011-08 | 135 | VAR | 4 | 1개월 | 0.311 |
| 설탕 | D' | 2011-09~2026-02 | 170 | VAR | 4 | 2개월 | 0.309 |
| 쇠고기 | B | 2000-01~2004-12 | 55 | VAR | 4 | 2개월 | 0.178 |
| 쇠고기 | B | 2005-01~2026-02 | 250 | VAR | 4 | 3개월 | -0.151 |

### 5.5 주요 발견

**밀 D' — COVID 이후 전달 구조 역전**: 2020-11 변화점 이후 탄력성이 +1.129 → -0.311으로 부호가 역전되고, 피크가 24개월 → 1개월로 급변했다. PPI(밀가루) 상승이 CPI(밀가루)를 빠르게 끌어올리지만 방향이 반대인 이례적 패턴이다.

**팜유 D' — 전달 강화 추세**: 2000~2010 탄력성 0.168 → 2010~2020 탄력성 0.615 → 2020~2026 탄력성 0.741로 지속적으로 강화되고 있다. 식용유 시장의 가격 투명성 향상과 일치한다.

**쇠고기 B — BSE 이후 방향 역전**: 2005-01 변화점 전후로 탄력성이 +0.178 → -0.151로 역전. BSE 이후 수입 구조(원산지 다변화, 검역 강화)가 근본적으로 변한 증거이다.

**옥수수 D' ⚠ — 경계 사례**: VECM→VAR 모형 전환된 구간으로 경계 플래그가 부착되어 있다. 하위 기간 재추정 결과는 모형 선택 불안정성의 영향을 받을 수 있다.

---

## 6. 산출물 구조

### 6.1 Phase 5 산출물

```
data/processed/phase5/
├── granger_results.csv         ← Granger 검정 결과 (6행: 3품목 × 2방향)
└── granger_direction.json      ← 품목별 확정 방향 (후속 Phase 참조용)
```

### 6.2 Phase 6 산출물

```
data/processed/phase6/
├── breakpoints/                        ← 33개 JSON
│   └── {cid}_{seg}_breakpoints.json
├── chow_results/                       ← 33개 CSV
│   └── {cid}_{seg}_chow.csv
├── subperiod_models/                   ← 12개 JSON (변화점 있는 구간만)
│   └── {cid}_{seg}_subperiod_{n}_model.json
└── phase6_summary.csv                  ← 전 구간 요약 (33행)
```

---

## 7. CSV 및 JSON 컬럼 설명

### 7.1 granger_results.csv

| 컬럼 | 설명 |
| --- | --- |
| commodity_id | 품목 식별자 (4구간 3종만) |
| segment | 분석 구간 (C 고정) |
| direction | 검정 방향 (`ppi_to_wholesale` \| `wholesale_to_ppi`) |
| max_lag | 검정에 사용된 최대 시차 |
| best_lag | p값 최소가 되는 최적 시차 |
| f_stat | F 통계량 |
| pvalue | p값 |
| significant | 유의 여부 (p < 0.05) |
| confirmed_direction | 최종 확정 방향 (`ppi_to_wholesale` \| `wholesale_to_ppi` \| `bidirectional` \| `none`) |

### 7.2 granger_direction.json

```json
{
  "groundnuts": { "segment": "C", "confirmed_direction": "bidirectional" },
  "banana":     { "segment": "C", "confirmed_direction": "none" },
  "orange":     { "segment": "C", "confirmed_direction": "none" }
}
```

### 7.3 phase6_summary.csv

| 컬럼 | 설명 |
| --- | --- |
| commodity_id | 품목 식별자 |
| segment | 분석 구간 |
| n_obs | 전이율 유효 관측치 수 |
| n_breakpoints | Bai-Perron 탐지 변화점 수 |
| bp_dates | 변화 시점 목록 |
| n_subperiods | 독립 하위 기간 수 |
| borderline | 경계 사례 플래그 |
| chow_2008_sig | Chow 2008 유의 여부 (범위 밖이면 빈값) |
| chow_2020_sig | Chow 2020 유의 여부 (범위 밖이면 빈값) |
| chow_2022_sig | Chow 2022 유의 여부 (범위 밖이면 빈값) |
| reestimation_count | 하위 기간 재추정 성공 수 |

---

## 8. 데이터 리니지

Phase 0~6의 데이터 변환 단계:

```
[원시 데이터]  raw levels
    │
    ▼  Phase 0: 수집·정제·병합
[merged CSV]  monthly levels
    │
    ▼  Phase 1: STL → 계절 조정
[_sa]  계절 조정 수준 데이터
    │
    ├──▶  Phase 3 (Johansen): 수준 데이터
    ├──▶  Phase 4 (VECM 추정): 수준 데이터
    └──▶  Phase 6 (하위 기간 재추정): 수준 데이터 슬라이싱
    │
    ▼  Phase 1: 변화율 산출
[_pct]  전월 대비 변화율 (%)
    │
    ├──▶  Phase 4 (VAR 추정): 변화율 데이터
    ├──▶  Phase 5 (Granger): ppi_pct, wholesale_price_pct
    ├──▶  Phase 6 (전이율 산출): 하류_pct / 상류_pct
    └──▶  Phase 7 (패턴 1): 방향 비교 (부호)
    │
    ▼  Phase 4: 모형 추정
[baseline]  IRF 피크, 전이탄력성, ECT
    │
    ├──▶  Phase 6 (참조): estimation_period 확인
    └──▶  Phase 7 (판정 기준): 정상 전달 시차, 탄력성
    │
    ▼  Phase 5: Granger 검정
[granger_direction]  구간 C 확정 방향
    │
    └──▶  Phase 7: 구간 C 패턴 적용 범위 결정
    │
    ▼  Phase 6: 구조 변화 탐지
[breakpoints]  변화 시점, 하위 기간
[subperiod_models]  기간별 IRF 피크, 탄력성
    │
    └──▶  Phase 7: 기간별 기준선 적용
```

---

## 9. 다음 단계

Phase 5~6 완료 후 **Phase 7 (이상 패턴 탐지)**로 진행:

- Phase 4 기준선(또는 Phase 6 하위 기간 기준선)을 기반으로 패턴 1·2·3 탐지
- Phase 5 `granger_direction.json`으로 구간 C 패턴 적용 범위 결정
- Phase 6 `breakpoints.json`으로 기간별 다른 기준선(정상 전달 시차, 탄력성) 적용
- ML 3종 앙상블(Phase 7-ML)의 피처 생성
