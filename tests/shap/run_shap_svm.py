"""
SHAP 분석 — One-Class SVM (run_shap_svm.py)
=============================================
역할:
  학습된 One-Class SVM 모델에 대해 SHAP(KernelExplainer)를 실행하고,
  전체 관측치의 피처별 기여도를 CSV로 저장한다.

입력:
  - data/processed/phase7_ml/models/{run_date}/{cid}_{seg}_svm_{run_date}.pkl
  - data/processed/phase7_ml/models/{run_date}/{cid}_{seg}_scaler_{run_date}.pkl
  - data/processed/phase7_ml/features/{cid}_{seg}_features.csv
  - data/processed/product_config.json

출력:
  - tests/shap/results/{YYYYMMDD_HHMM}_SVM/{cid}_{seg}_shap.csv  (20개)
  - tests/shap/results/{YYYYMMDD_HHMM}_SVM/shap_summary.csv      (전체 요약)
  - tests/shap/results/{YYYYMMDD_HHMM}_SVM/run_meta.json          (실행 메타)

Explainer: shap.KernelExplainer (전체 배경 데이터, 품목당 5~15분)

위치: tests/shap/run_shap_svm.py

실행 방법:
  python tests/shap/run_shap_svm.py
  python tests/shap/run_shap_svm.py --run-date 20260519_0945
"""

import sys
import os
import json
import argparse
import warnings
import pandas as pd
import numpy as np
import joblib
import shap
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
FEATURE_COLUMNS = [
    "transmission_rate",
    "upstream_pct",
    "downstream_pct",
    "ect_or_spread",
    "exchange_rate_pct",
    "intl_price_usd_pct",
]

ML_SEGMENTS = ["A", "B"]
MODEL_NAME = "SVM"


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------
def log_shap(msg):
    print(f"[SHAP-{MODEL_NAME}] {msg}")


def find_latest_run_date(models_dir):
    models_dir = Path(models_dir)
    run_dirs = sorted(
        [d for d in models_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not run_dirs:
        raise FileNotFoundError(f"모델 폴더가 없습니다: {models_dir}")
    return run_dirs[0].name


# ---------------------------------------------------------------------------
# SVM 스코어 함수 (KernelExplainer용)
# ---------------------------------------------------------------------------
def create_svm_score_fn(svm_model):
    """
    One-Class SVM의 decision_function을 부호 반전하여
    "높을수록 이상" 방향의 스코어 함수를 반환한다.

    Args:
        svm_model: 학습된 OneClassSVM 모델

    Returns:
        score_fn: X → anomaly scores (높을수록 이상)
    """
    def score_fn(X):
        # decision_function: 양수=정상, 음수=이상 → 부호 반전
        return -svm_model.decision_function(X)

    return score_fn


# ---------------------------------------------------------------------------
# 단일 구간 SHAP 산출
# ---------------------------------------------------------------------------
def compute_shap_segment(models_dir, features_dir, run_date, cid, seg):
    """
    단일 품목x구간에 대해 SVM SHAP 값을 산출한다.
    """
    model_path = Path(models_dir) / run_date / f"{cid}_{seg}_svm_{run_date}.pkl"
    scaler_path = Path(models_dir) / run_date / f"{cid}_{seg}_scaler_{run_date}.pkl"

    if not model_path.exists():
        log_shap(f"  {cid} {seg}: 모델 없음 — 건너뜀")
        return None

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    # 피처 로드
    features_path = Path(features_dir) / f"{cid}_{seg}_features.csv"
    features_df = pd.read_csv(features_path, encoding="utf-8-sig")

    dates = pd.to_datetime(features_df["date"])
    X_raw = features_df[FEATURE_COLUMNS].copy()

    valid_mask = X_raw.notna().all(axis=1)
    X_valid = X_raw[valid_mask]
    dates_valid = dates[valid_mask]

    X_scaled = scaler.transform(X_valid.values)

    # SVM 스코어 함수 생성
    score_fn = create_svm_score_fn(model)

    # SHAP KernelExplainer (전체 배경 데이터)
    explainer = shap.KernelExplainer(score_fn, X_scaled)
    shap_values = explainer.shap_values(X_scaled, silent=True)

    # SHAP DataFrame 구성
    shap_df = pd.DataFrame(shap_values, columns=FEATURE_COLUMNS)
    shap_df.insert(0, "date", dates_valid.values)
    shap_df.insert(1, "commodity_id", cid)
    shap_df.insert(2, "segment", seg)

    mean_abs = np.abs(shap_values).mean(axis=0)

    return shap_df, mean_abs


# ---------------------------------------------------------------------------
# 메인 실행
# ---------------------------------------------------------------------------
def run_shap_svm(data_dir, ml_dir, output_base, run_date=None):
    models_dir = Path(ml_dir) / "models"
    features_dir = Path(ml_dir) / "features"

    if run_date is None:
        run_date = find_latest_run_date(models_dir)
        log_shap(f"최신 run_date 자동 탐지: {run_date}")
    else:
        log_shap(f"지정된 run_date: {run_date}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = Path(output_base) / f"{timestamp}_{MODEL_NAME}"
    output_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(data_dir) / "product_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    segments = []
    for cid, cfg in config.items():
        for seg in cfg["segments"]:
            if seg in ML_SEGMENTS:
                segments.append((cid, seg))

    log_shap(f"SHAP 분석 시작: {len(segments)}개 구간, 모델={MODEL_NAME}")
    log_shap(f"주의: KernelExplainer — 품목당 5~15분 소요")
    log_shap(f"출력: {output_dir}")

    all_importance = []
    success_count = 0

    for i, (cid, seg) in enumerate(segments):
        log_shap(f"  [{i+1}/{len(segments)}] {cid} {seg} 시작...")
        t_start = datetime.now()

        result = compute_shap_segment(models_dir, features_dir, run_date, cid, seg)

        if result is None:
            continue

        shap_df, mean_abs = result

        elapsed = (datetime.now() - t_start).total_seconds()

        csv_path = output_dir / f"{cid}_{seg}_shap.csv"
        shap_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        importance = {"commodity_id": cid, "segment": seg}
        for j, col in enumerate(FEATURE_COLUMNS):
            importance[f"mean_abs_{col}"] = round(mean_abs[j], 6)
        top_idx = np.argmax(mean_abs)
        importance["top_feature"] = FEATURE_COLUMNS[top_idx]
        importance["top_importance"] = round(mean_abs[top_idx], 6)
        all_importance.append(importance)

        log_shap(
            f"  [{i+1}/{len(segments)}] {cid:12s} {seg}: "
            f"top={FEATURE_COLUMNS[top_idx]} ({mean_abs[top_idx]:.4f}), "
            f"n={len(shap_df)}, "
            f"{elapsed:.1f}s"
        )
        success_count += 1

    summary_df = pd.DataFrame(all_importance)
    summary_path = output_dir / "shap_summary.csv"
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    global_importance = {}
    for col in FEATURE_COLUMNS:
        key = f"mean_abs_{col}"
        global_importance[col] = round(summary_df[key].mean(), 6)

    meta = {
        "model": MODEL_NAME,
        "explainer": "KernelExplainer",
        "score_function": "-decision_function (negated, higher=more anomalous)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_date_source": run_date,
        "output_dir": str(output_dir),
        "n_segments": success_count,
        "feature_columns": FEATURE_COLUMNS,
        "background_data": "full (no subsampling)",
        "global_feature_importance": global_importance,
    }
    meta_path = output_dir / "run_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    log_shap(f"완료: {success_count}/{len(segments)} 구간")
    log_shap(f"글로벌 피처 중요도:")
    for col, imp in sorted(global_importance.items(), key=lambda x: -x[1]):
        log_shap(f"  {col:25s}: {imp:.6f}")

    return summary_df


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SHAP 분석 — One-Class SVM")
    parser.add_argument("--run-date", type=str, default=None, help="모델 run_date (미지정 시 최신)")
    args = parser.parse_args()

    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
    ML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "phase7_ml")
    OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "results")

    run_shap_svm(DATA_DIR, ML_DIR, OUTPUT_BASE, run_date=args.run_date)
