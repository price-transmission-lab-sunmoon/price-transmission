"""
SHAP 분석 — Local Outlier Factor (run_shap_lof.py)
===================================================
역할:
  학습된 LOF 모델에 대해 SHAP(KernelExplainer)를 실행하고,
  전체 관측치의 피처별 기여도를 CSV로 저장한다.

Explainer: shap.KernelExplainer (전체 배경 데이터, 품목당 5~15분)

주의:
  LOF(novelty=False)는 새 데이터에 score를 호출할 수 없으므로,
  동일 파라미터로 novelty=True LOF를 재학습하는 래퍼를 사용한다.

실행:
  python tests/shap/run_shap_lof.py
  python tests/shap/run_shap_lof.py --run-date 20260519_0945
  python tests/shap/run_shap_lof.py --output-dir tests/shap/results/20260519_2000_LOF  (이어하기)
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
from sklearn.neighbors import LocalOutlierFactor

warnings.filterwarnings("ignore", category=FutureWarning)


FEATURE_COLUMNS = [
    "transmission_rate", "upstream_pct", "downstream_pct",
    "ect_or_spread", "exchange_rate_pct", "intl_price_usd_pct",
]
ML_SEGMENTS = ["A", "B"]
MODEL_NAME = "LOF"


def log_shap(msg):
    print(f"[SHAP-{MODEL_NAME}] {msg}")


def find_latest_run_date(models_dir):
    models_dir = Path(models_dir)
    run_dirs = sorted([d for d in models_dir.iterdir() if d.is_dir()], key=lambda d: d.name, reverse=True)
    if not run_dirs:
        raise FileNotFoundError(f"모델 폴더가 없습니다: {models_dir}")
    return run_dirs[0].name


def create_lof_score_fn(lof_model, X_train):
    lof_novelty = LocalOutlierFactor(
        n_neighbors=lof_model.n_neighbors,
        contamination=lof_model.contamination,
        novelty=True,
    )
    lof_novelty.fit(X_train)
    def score_fn(X):
        return -lof_novelty.score_samples(X)
    return score_fn


def compute_shap_segment(models_dir, features_dir, run_date, cid, seg):
    model_path = Path(models_dir) / run_date / f"{cid}_{seg}_lof_{run_date}.pkl"
    scaler_path = Path(models_dir) / run_date / f"{cid}_{seg}_scaler_{run_date}.pkl"
    if not model_path.exists():
        log_shap(f"  {cid} {seg}: 모델 없음 — 건너뜀")
        return None

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    features_path = Path(features_dir) / f"{cid}_{seg}_features.csv"
    features_df = pd.read_csv(features_path, encoding="utf-8-sig")
    dates = pd.to_datetime(features_df["date"])
    X_raw = features_df[FEATURE_COLUMNS].copy()
    valid_mask = X_raw.notna().all(axis=1)
    X_valid = X_raw[valid_mask]
    dates_valid = dates[valid_mask]
    X_scaled = scaler.transform(X_valid.values)

    score_fn = create_lof_score_fn(model, X_scaled)
    explainer = shap.KernelExplainer(score_fn, X_scaled)
    shap_values = explainer.shap_values(X_scaled, silent=True)

    shap_df = pd.DataFrame(shap_values, columns=FEATURE_COLUMNS)
    shap_df.insert(0, "date", dates_valid.values)
    shap_df.insert(1, "commodity_id", cid)
    shap_df.insert(2, "segment", seg)
    mean_abs = np.abs(shap_values).mean(axis=0)
    return shap_df, mean_abs


def run_shap_lof(data_dir, ml_dir, output_base, run_date=None, output_dir_override=None):
    models_dir = Path(ml_dir) / "models"
    features_dir = Path(ml_dir) / "features"

    if run_date is None:
        run_date = find_latest_run_date(models_dir)
        log_shap(f"최신 run_date 자동 탐지: {run_date}")
    else:
        log_shap(f"지정된 run_date: {run_date}")

    if output_dir_override:
        output_dir = Path(output_dir_override)
        log_shap(f"기존 출력 디렉토리 사용 (이어하기 모드): {output_dir}")
    else:
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
    skipped_count = 0

    for i, (cid, seg) in enumerate(segments):
        csv_path = output_dir / f"{cid}_{seg}_shap.csv"
        if csv_path.exists():
            log_shap(f"  [{i+1}/{len(segments)}] {cid} {seg}: 이미 존재 — 스킵")
            existing = pd.read_csv(csv_path, encoding="utf-8-sig")
            mean_abs = np.abs(existing[FEATURE_COLUMNS].values).mean(axis=0)
            importance = {"commodity_id": cid, "segment": seg}
            for j, col in enumerate(FEATURE_COLUMNS):
                importance[f"mean_abs_{col}"] = round(mean_abs[j], 6)
            top_idx = np.argmax(mean_abs)
            importance["top_feature"] = FEATURE_COLUMNS[top_idx]
            importance["top_importance"] = round(mean_abs[top_idx], 6)
            all_importance.append(importance)
            skipped_count += 1
            success_count += 1
            continue

        log_shap(f"  [{i+1}/{len(segments)}] {cid} {seg} 시작...")
        t_start = datetime.now()

        result = compute_shap_segment(models_dir, features_dir, run_date, cid, seg)
        if result is None:
            continue

        shap_df, mean_abs = result
        elapsed = (datetime.now() - t_start).total_seconds()

        shap_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        importance = {"commodity_id": cid, "segment": seg}
        for j, col in enumerate(FEATURE_COLUMNS):
            importance[f"mean_abs_{col}"] = round(mean_abs[j], 6)
        top_idx = np.argmax(mean_abs)
        importance["top_feature"] = FEATURE_COLUMNS[top_idx]
        importance["top_importance"] = round(mean_abs[top_idx], 6)
        all_importance.append(importance)

        log_shap(f"  [{i+1}/{len(segments)}] {cid:12s} {seg}: top={FEATURE_COLUMNS[top_idx]} ({mean_abs[top_idx]:.4f}), n={len(shap_df)}, {elapsed:.1f}s")
        success_count += 1

    summary_df = pd.DataFrame(all_importance)
    summary_df.to_csv(output_dir / "shap_summary.csv", index=False, encoding="utf-8-sig")

    global_importance = {}
    for col in FEATURE_COLUMNS:
        global_importance[col] = round(summary_df[f"mean_abs_{col}"].mean(), 6)

    status = "complete" if success_count == len(segments) else f"partial ({success_count}/{len(segments)})"

    meta = {
        "model": MODEL_NAME,
        "explainer": "KernelExplainer",
        "lof_wrapper": "novelty=True re-fit with same params",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_date_source": run_date,
        "output_dir": str(output_dir),
        "n_segments_total": len(segments),
        "n_segments_complete": success_count,
        "n_segments_skipped": skipped_count,
        "status": status,
        "feature_columns": FEATURE_COLUMNS,
        "background_data": "full (no subsampling)",
        "global_feature_importance": global_importance,
    }
    with open(output_dir / "run_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    log_shap(f"완료: {success_count}/{len(segments)} 구간 (스킵: {skipped_count})")
    log_shap(f"상태: {status}")
    log_shap(f"글로벌 피처 중요도:")
    for col, imp in sorted(global_importance.items(), key=lambda x: -x[1]):
        log_shap(f"  {col:25s}: {imp:.6f}")
    return summary_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SHAP — LOF")
    parser.add_argument("--run-date", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default=None, help="기존 출력 디렉토리 (이어하기)")
    args = parser.parse_args()

    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
    ML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "phase7_ml")
    OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "results")

    run_shap_lof(DATA_DIR, ML_DIR, OUTPUT_BASE, run_date=args.run_date, output_dir_override=args.output_dir)