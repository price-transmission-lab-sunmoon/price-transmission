"""
축 5 -- 합의 기반 지표 (CTA + ASC)
====================================
역할:
  통계-ML 트랙의 탐지 합의를 정량화한다.
  CTA = |통계 교집합 ML| / |통계 합집합 ML|
  ASC = |합의 시점 중 충격 윈도우 내| / |합의 시점 총|

  핵심 가설: ASC > max(ESR_stat, ESR_ml)

입력 파일:
  - data/processed/phase7_ml/cross_validation/{cid}_{seg}_cross_val.csv
  - data/processed/phase7_ml/predictions/{cid}_{seg}_ml_predictions.csv
  - data/processed/phase4/baseline/{cid}_{seg}_baseline.json
  - data/processed/product_config.json

출력: CTA, ASC 결과 dict

위치: tests/phase7_ml/test_axis5_consensus.py
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_common import (
    EXTERNAL_SHOCKS,
    get_applicable_shocks,
    load_cross_val,
    load_predictions,
    get_ml_segments,
    log_eval,
)


def compute_cta(cv_df):
    """
    Cross-Track Agreement를 산출한다.
    CTA = |stat 교집합 ml| / |stat 합집합 ml|
    """
    stat = cv_df["stat_detected"].values
    ml = cv_df["ml_detected"].values

    intersection = (stat & ml).sum()
    union = (stat | ml).sum()

    if union == 0:
        return np.nan
    return intersection / union


def compute_asc(cv_df, shocks):
    """
    Agreement-to-Shock Coincidence를 산출한다.
    ASC = |합의 시점 중 충격 윈도우 내| / |합의 시점 총|
    """
    # 합의 시점 = stat + ml 동시 탐지
    consensus = cv_df[cv_df["stat_detected"] & cv_df["ml_detected"]]
    n_consensus = len(consensus)

    if n_consensus == 0:
        return np.nan, 0

    # 충격 윈도우 내 합의 건수
    in_shock = 0
    for _, row in consensus.iterrows():
        date = row["date"]
        for shock in shocks:
            s_start = pd.Timestamp(shock["start"])
            s_end = pd.Timestamp(shock["end"])
            if s_start <= date <= s_end:
                in_shock += 1
                break  # 같은 날짜에 여러 충격이 겹쳐도 1건

    asc = in_shock / n_consensus
    return asc, n_consensus


def compute_esr_stat(cv_df, shocks):
    """통계 트랙의 ESR을 산출한다 (축 5 비교용)."""
    n_shocks = len(shocks)
    if n_shocks == 0:
        return np.nan

    recalled = 0
    for shock in shocks:
        s_start = pd.Timestamp(shock["start"])
        s_end = pd.Timestamp(shock["end"])
        window = cv_df[
            (cv_df["date"] >= s_start) & (cv_df["date"] <= s_end)
        ]
        if window["stat_detected"].any():
            recalled += 1

    return recalled / n_shocks


def run_axis5(data_dir, ml_dir):
    """전 20개 구간에 대해 CTA, ASC를 산출한다."""
    segments = get_ml_segments(data_dir)
    log_eval("축 5 (CTA + ASC) 시작")

    all_results = []

    for cid, seg in segments:
        cv = load_cross_val(ml_dir, cid, seg)
        shocks = get_applicable_shocks(data_dir, cid, seg)

        cta = compute_cta(cv)
        asc, n_consensus = compute_asc(cv, shocks)
        esr_stat = compute_esr_stat(cv, shocks)

        # ESR_ml (축 1에서도 산출하지만 비교용으로 여기서도 간이 산출)
        pred = load_predictions(ml_dir, cid, seg)
        n_shocks = len(shocks)
        if n_shocks > 0:
            ml_recalled = sum(
                1 for shock in shocks
                if pred[
                    (pred["date"] >= pd.Timestamp(shock["start"]))
                    & (pred["date"] <= pd.Timestamp(shock["end"]))
                ]["ml_detected"].any()
            )
            esr_ml = ml_recalled / n_shocks
        else:
            esr_ml = np.nan

        # 핵심 가설 검증: ASC > max(ESR_stat, ESR_ml)
        if not np.isnan(asc) and not np.isnan(esr_stat) and not np.isnan(esr_ml):
            hypothesis_holds = asc > max(esr_stat, esr_ml)
        else:
            hypothesis_holds = None

        result = {
            "commodity_id": cid,
            "segment": seg,
            "cta": round(cta, 4) if not np.isnan(cta) else np.nan,
            "asc": round(asc, 4) if not np.isnan(asc) else np.nan,
            "n_consensus": n_consensus,
            "esr_stat": round(esr_stat, 4) if not np.isnan(esr_stat) else np.nan,
            "esr_ml": round(esr_ml, 4) if not np.isnan(esr_ml) else np.nan,
            "n_shocks": n_shocks,
            "hypothesis_holds": hypothesis_holds,
        }
        all_results.append(result)

        hyp_str = "O" if hypothesis_holds else ("X" if hypothesis_holds is False else "-")
        log_eval(
            f"  {cid:12s} {seg}: "
            f"CTA={result['cta']}, ASC={result['asc']}, "
            f"ESR_stat={result['esr_stat']}, ESR_ml={result['esr_ml']}, "
            f"ASC>max(ESR)={hyp_str}"
        )

    log_eval("축 5 완료")
    return all_results


if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
    ML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "phase7_ml")
    run_axis5(DATA_DIR, ML_DIR)
