"""
Phase 8 로버스트니스 체크 (phase8_robustness.py)
=================================================
역할:
  3가지 민감도 분석을 수행한다.

  R1. 롤링 윈도우 민감도 (W=36/48/60)
  R2. 계절 조정 방식 비교 (STL vs 계절 더미)
  R3. ML contamination 민감도 (0.05/0.08/0.10/0.12/0.15)

출력 파일:
  data/processed/phase8/robustness/rolling_window_sensitivity.csv
  data/processed/phase8/robustness/seasonal_method_comparison.csv
  data/processed/phase8/robustness/contamination_sensitivity.csv
  data/processed/phase8/robustness/robustness_summary.json
"""

import sys
import os
import json
import pandas as pd
import numpy as np
from pathlib import Path

from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase8_common import (
    Phase8Paths,
    ML_SEGMENTS,
    load_product_config,
    load_pattern2,
    load_robustness_csv,
    load_stl_changes,
    load_dummy_changes,
    load_baseline,
    load_stat_timeseries,
    iter_ml_segments,
    iter_pattern2_segments,
    jaccard_similarity,
    stability_verdict,
    ensure_phase8_dirs,
    log8,
)


# ═══════════════════════════════════════════════════════════════════
# 파라미터
# ═══════════════════════════════════════════════════════════════════
# R1 롤링 윈도우
ROLLING_WINDOWS = [36, 48, 60]

# R2 계절 더미 비교: 전이율 산출 파라미터 (phase7_common 기준)
TRANSMISSION_RATE_MIN_UPSTREAM = 0.5
ROLLING_WINDOW_DEFAULT = 48
ZSCORE_WARNING = 2.0
ZSCORE_ALERT = 2.5
IQR_MULTIPLIER = 1.5

# R3 contamination 민감도
CONTAMINATION_VALUES = [0.05, 0.08, 0.10, 0.12, 0.15]
CONTAMINATION_BASELINE = 0.08
ML_CONSENSUS_THRESHOLD = 2
RANDOM_STATE = 42

# ML 피처 (phase7_ml_common 기준)
FEATURE_COLUMNS = [
    "transmission_rate",
    "upstream_pct",
    "downstream_pct",
    "ect_or_spread",
    "exchange_rate_pct",
    "intl_price_usd_pct",
]


# ═══════════════════════════════════════════════════════════════════
# R1. 롤링 윈도우 민감도 (W=36/48/60)
# ═══════════════════════════════════════════════════════════════════
def build_rolling_window_sensitivity(paths, config):
    """
    W=36/48/60 패턴 2 탐지 결과를 비교한다.

    W48은 pattern2 기본 결과에서, W36/W60은 robustness CSV에서 가져온다.
    """
    log8("R1: 롤링 윈도우 민감도")
    rows = []

    for cid, seg in iter_pattern2_segments(config):
        # W48 (기본): pattern2_zscore CSV
        p2 = load_pattern2(paths, cid, seg)
        w48_dates = set(
            pd.to_datetime(p2[p2["pattern2_flag"] == True]["date"])
        )

        # W36, W60: robustness CSV
        rob36 = load_robustness_csv(paths, cid, seg, 36)
        w36_dates = set(
            pd.to_datetime(rob36[rob36["pattern2_flag"] == True]["date"])
        )

        rob60 = load_robustness_csv(paths, cid, seg, 60)
        w60_dates = set(
            pd.to_datetime(rob60[rob60["pattern2_flag"] == True]["date"])
        )

        # Jaccard 유사도
        j_36_48 = jaccard_similarity(w36_dates, w48_dates)
        j_48_60 = jaccard_similarity(w48_dates, w60_dates)

        # 평균 Jaccard로 안정성 판정
        avg_j = (j_36_48 + j_48_60) / 2

        rows.append({
            "commodity_id": cid,
            "segment": seg,
            "w36_flags": len(w36_dates),
            "w48_flags": len(w48_dates),
            "w60_flags": len(w60_dates),
            "w36_w48_overlap": len(w36_dates & w48_dates),
            "w48_w60_overlap": len(w48_dates & w60_dates),
            "w36_w48_jaccard": round(j_36_48, 4),
            "w48_w60_jaccard": round(j_48_60, 4),
            "stability_verdict": stability_verdict(avg_j),
        })

        log8(f"  {cid:12s} {seg}: "
             f"W36={len(w36_dates):3d}, W48={len(w48_dates):3d}, "
             f"W60={len(w60_dates):3d} | "
             f"J(36-48)={j_36_48:.3f}, J(48-60)={j_48_60:.3f}")

    df = pd.DataFrame(rows)
    return df


# ═══════════════════════════════════════════════════════════════════
# R2. 계절 조정 방식 비교 (STL vs 계절 더미)
# ═══════════════════════════════════════════════════════════════════
def _compute_transmission_rate(upstream_pct, downstream_pct,
                               min_upstream=TRANSMISSION_RATE_MIN_UPSTREAM):
    """전이율 산출 (phase7_common.compute_transmission_rate 재현)."""
    tr = pd.Series(np.nan, index=upstream_pct.index, dtype=float)
    valid = (
        upstream_pct.notna()
        & downstream_pct.notna()
        & (upstream_pct.abs() >= min_upstream)
    )
    tr[valid] = downstream_pct[valid] / upstream_pct[valid]
    return tr


def _compute_rolling_zscore_flags(tr_series, warmup_end, window=ROLLING_WINDOW_DEFAULT):
    """
    전이율에 대해 롤링 Z-score + IQR 기반 패턴 2 flag를 산출한다.
    phase7_pattern2.py의 로직을 재현한다.
    """
    n = len(tr_series)
    dates = tr_series.index
    vals = tr_series.values

    flags = pd.Series(False, index=dates, dtype=bool)

    for i in range(n):
        if dates[i] <= warmup_end:
            continue
        if pd.isna(vals[i]):
            continue

        # 롤링 윈도우: i-window ~ i-1
        start_idx = max(0, i - window)
        end_idx = i
        window_vals = vals[start_idx:end_idx]
        window_vals = window_vals[~np.isnan(window_vals)]

        if len(window_vals) < 10:
            continue

        # Z-score
        mean = np.mean(window_vals)
        std = np.std(window_vals, ddof=1)
        if std == 0:
            continue
        zscore = (vals[i] - mean) / std

        # IQR
        q1 = np.percentile(window_vals, 25)
        q3 = np.percentile(window_vals, 75)
        iqr = q3 - q1
        iqr_lower = q1 - IQR_MULTIPLIER * iqr
        iqr_upper = q3 + IQR_MULTIPLIER * iqr
        iqr_outlier = (vals[i] < iqr_lower) or (vals[i] > iqr_upper)

        # 패턴 2 판정: (Z-score ≥ warning OR Z-score ≤ -warning) AND IQR outlier
        zscore_flag = abs(zscore) >= ZSCORE_WARNING
        if zscore_flag and iqr_outlier:
            flags.iloc[i] = True

    return flags


def _get_pct_columns(config, cid, seg):
    """segment_pairs에서 상류/하류 _pct 컬럼명을 반환한다."""
    pair = config[cid]["segment_pairs"][seg]
    return pair[0] + "_pct", pair[1] + "_pct"


def build_seasonal_method_comparison(paths, config):
    """
    STL 기반 패턴 2 결과와 계절 더미 기반 패턴 2 결과를 비교한다.

    dummy_changes CSV에서 변화율을 가져와 전이율 → Z-score/IQR을
    재산출하고, STL 기반 결과와 Jaccard 유사도를 산출한다.
    """
    log8("R2: 계절 조정 방식 비교")
    rows = []

    for cid, seg in iter_pattern2_segments(config):
        # STL 기반 결과
        p2 = load_pattern2(paths, cid, seg)
        p2["date"] = pd.to_datetime(p2["date"])
        stl_flag_dates = set(p2[p2["pattern2_flag"] == True]["date"])

        # warmup_end
        baseline = load_baseline(paths, cid, seg)
        warmup_end = pd.Timestamp(baseline["warmup_end"] + "-01")

        # 계절 더미 기반 변화율 로드
        dummy_df = load_dummy_changes(paths, cid)
        up_col, dn_col = _get_pct_columns(config, cid, seg)

        # 전이율 산출
        dummy_tr = _compute_transmission_rate(dummy_df[up_col], dummy_df[dn_col])

        # 패턴 2 flag 재산출
        dummy_flags = _compute_rolling_zscore_flags(dummy_tr, warmup_end)
        dummy_flag_dates = set(dummy_flags[dummy_flags].index)

        # Jaccard 유사도
        j = jaccard_similarity(stl_flag_dates, dummy_flag_dates)

        rows.append({
            "commodity_id": cid,
            "segment": seg,
            "stl_flags": len(stl_flag_dates),
            "dummy_flags": len(dummy_flag_dates),
            "overlap": len(stl_flag_dates & dummy_flag_dates),
            "jaccard": round(j, 4),
            "stl_only": len(stl_flag_dates - dummy_flag_dates),
            "dummy_only": len(dummy_flag_dates - stl_flag_dates),
            "stability_verdict": stability_verdict(j),
        })

        log8(f"  {cid:12s} {seg}: "
             f"STL={len(stl_flag_dates):3d}, "
             f"Dummy={len(dummy_flag_dates):3d}, "
             f"overlap={len(stl_flag_dates & dummy_flag_dates):3d} | "
             f"J={j:.3f}")

    df = pd.DataFrame(rows)
    return df


# ═══════════════════════════════════════════════════════════════════
# R3. ML contamination 민감도
# ═══════════════════════════════════════════════════════════════════
def _run_ml_with_contamination(X_scaled, contamination):
    """
    특정 contamination으로 3종 모델을 실행하고 ml_detected를 반환한다.
    phase7_ml_models.py 로직을 재현한다.
    """
    # Isolation Forest
    if_model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=RANDOM_STATE,
    )
    if_model.fit(X_scaled)
    if_anomaly = if_model.predict(X_scaled) == -1

    # LOF
    lof_model = LocalOutlierFactor(
        n_neighbors=10,
        contamination=contamination,
        novelty=False,
    )
    lof_labels = lof_model.fit_predict(X_scaled)
    lof_anomaly = lof_labels == -1

    # One-Class SVM
    svm_model = OneClassSVM(
        kernel="rbf",
        nu=contamination,
        gamma="scale",
    )
    svm_model.fit(X_scaled)
    svm_anomaly = svm_model.predict(X_scaled) == -1

    # 앙상블
    consensus = if_anomaly.astype(int) + lof_anomaly.astype(int) + svm_anomaly.astype(int)
    ml_detected = consensus >= ML_CONSENSUS_THRESHOLD

    return ml_detected


def build_contamination_sensitivity(paths, config):
    """
    contamination 0.05/0.08/0.10/0.12/0.15로 ML을 재실행하고
    기본값(0.08) 대비 Jaccard 유사도를 산출한다.

    stat_timeseries에서 6종 피처를 추출하여 동일한 전처리를 적용한다.
    """
    log8("R3: ML contamination 민감도")
    rows = []

    for cid, seg in iter_ml_segments(config):
        # 피처 추출 (stat_timeseries에서)
        st = load_stat_timeseries(paths, cid, seg)
        features = st[FEATURE_COLUMNS].copy()
        features.index = pd.to_datetime(st["period"])

        # 결측 제거
        features_valid = features.dropna()
        valid_index = features_valid.index

        if len(features_valid) < 20:
            log8(f"  {cid:12s} {seg}: 유효 데이터 부족 ({len(features_valid)}), 건너뜀")
            continue

        # StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(features_valid.values)

        # 각 contamination으로 실행
        results_by_c = {}
        for c in CONTAMINATION_VALUES:
            ml_detected = _run_ml_with_contamination(X_scaled, c)
            detected_dates = set(valid_index[ml_detected])
            results_by_c[c] = detected_dates

        # 기본값 대비 Jaccard
        baseline_dates = results_by_c[CONTAMINATION_BASELINE]

        c_key = lambda c: f"c{int(c * 100):03d}"

        row = {
            "commodity_id": cid,
            "segment": seg,
        }

        for c in CONTAMINATION_VALUES:
            row[f"{c_key(c)}_detected"] = len(results_by_c[c])

        for c in CONTAMINATION_VALUES:
            if c == CONTAMINATION_BASELINE:
                continue
            j = jaccard_similarity(baseline_dates, results_by_c[c])
            row[f"{c_key(c)}_{c_key(CONTAMINATION_BASELINE)}_jaccard"] = round(j, 4)

        # 전체 Jaccard 평균으로 안정성 판정
        jaccard_values = [v for k, v in row.items() if "jaccard" in str(k)]
        avg_j = np.mean(jaccard_values) if jaccard_values else 0.0
        row["stability_verdict"] = stability_verdict(avg_j)

        rows.append(row)

        log8(f"  {cid:12s} {seg}: "
             f"c005={len(results_by_c[0.05]):3d}, "
             f"c008={len(results_by_c[0.08]):3d}, "
             f"c010={len(results_by_c[0.10]):3d}, "
             f"c012={len(results_by_c[0.12]):3d}, "
             f"c015={len(results_by_c[0.15]):3d}")

    df = pd.DataFrame(rows)
    return df


# ═══════════════════════════════════════════════════════════════════
# 로버스트니스 요약 JSON
# ═══════════════════════════════════════════════════════════════════
def build_robustness_summary_json(r1_df, r2_df, r3_df):
    """R1~R3 전체 요약을 JSON으로 구성한다."""
    summary = {}

    # R1 요약
    if len(r1_df) > 0:
        avg_j_36_48 = r1_df["w36_w48_jaccard"].mean()
        avg_j_48_60 = r1_df["w48_w60_jaccard"].mean()
        summary["rolling_window"] = {
            "avg_jaccard_w36_w48": round(avg_j_36_48, 4),
            "avg_jaccard_w48_w60": round(avg_j_48_60, 4),
            "verdict": stability_verdict((avg_j_36_48 + avg_j_48_60) / 2),
            "n_stable": int((r1_df["stability_verdict"] == "stable").sum()),
            "n_moderate": int((r1_df["stability_verdict"] == "moderate").sum()),
            "n_sensitive": int((r1_df["stability_verdict"] == "sensitive").sum()),
        }

    # R2 요약
    if len(r2_df) > 0:
        avg_j = r2_df["jaccard"].mean()
        summary["seasonal_method"] = {
            "avg_jaccard": round(avg_j, 4),
            "verdict": stability_verdict(avg_j),
            "n_stable": int((r2_df["stability_verdict"] == "stable").sum()),
            "n_moderate": int((r2_df["stability_verdict"] == "moderate").sum()),
            "n_sensitive": int((r2_df["stability_verdict"] == "sensitive").sum()),
        }

    # R3 요약
    if len(r3_df) > 0:
        jaccard_cols = [c for c in r3_df.columns if "jaccard" in c]
        if jaccard_cols:
            avg_jaccards = {}
            for c in jaccard_cols:
                avg_jaccards[c] = round(r3_df[c].mean(), 4)
            overall_avg = np.mean(list(avg_jaccards.values()))
            summary["contamination"] = {
                "per_pair_avg_jaccard": avg_jaccards,
                "overall_avg_jaccard": round(overall_avg, 4),
                "verdict": stability_verdict(overall_avg),
                "n_stable": int((r3_df["stability_verdict"] == "stable").sum()),
                "n_moderate": int((r3_df["stability_verdict"] == "moderate").sum()),
                "n_sensitive": int((r3_df["stability_verdict"] == "sensitive").sum()),
            }

    return summary


# ═══════════════════════════════════════════════════════════════════
# 통합 실행
# ═══════════════════════════════════════════════════════════════════
def run_robustness(paths, config):
    """
    Phase 8 로버스트니스 체크 R1~R3을 실행하고 CSV/JSON으로 저장한다.

    Args:
        paths: Phase8Paths 인스턴스
        config: product_config dict

    Returns:
        dict of DataFrames + summary JSON dict
    """
    output_dir = ensure_phase8_dirs(paths.output_dir)
    rob_dir = output_dir / "robustness"

    log8("=" * 50)
    log8("Phase 8 로버스트니스 체크 시작")
    log8("=" * 50)

    results = {}

    # R1: 롤링 윈도우 민감도
    r1 = build_rolling_window_sensitivity(paths, config)
    r1.to_csv(
        rob_dir / "rolling_window_sensitivity.csv",
        index=False, encoding="utf-8-sig",
    )
    results["rolling_window_sensitivity"] = r1

    # R2: 계절 조정 방식 비교
    r2 = build_seasonal_method_comparison(paths, config)
    r2.to_csv(
        rob_dir / "seasonal_method_comparison.csv",
        index=False, encoding="utf-8-sig",
    )
    results["seasonal_method_comparison"] = r2

    # R3: contamination 민감도
    r3 = build_contamination_sensitivity(paths, config)
    r3.to_csv(
        rob_dir / "contamination_sensitivity.csv",
        index=False, encoding="utf-8-sig",
    )
    results["contamination_sensitivity"] = r3

    # 요약 JSON
    rob_summary = build_robustness_summary_json(r1, r2, r3)
    with open(rob_dir / "robustness_summary.json", "w", encoding="utf-8") as f:
        json.dump(rob_summary, f, indent=2, ensure_ascii=False)
    results["robustness_summary"] = rob_summary

    log8("=" * 50)
    log8("Phase 8 로버스트니스 체크 완료")
    log8(f"  출력: {rob_dir}")
    log8("=" * 50)

    return results