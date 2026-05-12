"""
ML 평가 통합 실행 (run_all_evaluation.py)
==========================================
역할:
  축 1~5를 순차 실행하고, 종합 리포트를 CSV로 저장한다.

입력: Phase 7-ML 출력 + Phase 7 stat 출력 + product_config
출력: tests/phase7_ml/results/ 아래 축별 CSV + 종합 리포트

위치: tests/phase7_ml/run_all_evaluation.py

실행 방법:
  python tests/phase7_ml/run_all_evaluation.py
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_common import log_eval
from test_axis1_esr import run_axis1
from test_axis2_separation import run_axis2
from test_axis3_auc import run_axis3
from test_axis4_sensitivity import run_axis4
from test_axis5_consensus import run_axis5


def run_all(data_dir, ml_dir, phase7_dir, output_dir):
    """5축 평가를 순차 실행하고 결과를 저장한다."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    log_eval("=" * 60)
    log_eval("ML 신뢰성 평가 시작 (5축)")
    log_eval("=" * 60)
    print()

    # --- 축 1: ESR ---
    esr_results, esr_weighted = run_axis1(data_dir, ml_dir)
    esr_df = pd.DataFrame([
        {k: v for k, v in r.items() if k != "shock_details"}
        for r in esr_results
    ])
    esr_df.to_csv(output / "axis1_esr.csv", index=False, encoding="utf-8-sig")
    print()

    # --- 축 2: 분리도 ---
    sep_results = run_axis2(data_dir, ml_dir)
    sep_df = pd.DataFrame(sep_results)
    sep_df.to_csv(output / "axis2_separation.csv", index=False, encoding="utf-8-sig")
    print()

    # --- 축 3: AUC ---
    auc_results = run_axis3(data_dir, ml_dir)
    auc_df = pd.DataFrame(auc_results)
    auc_df.to_csv(output / "axis3_auc.csv", index=False, encoding="utf-8-sig")
    print()

    # --- 축 4: 민감도 ---
    sens_results = run_axis4(data_dir, phase7_dir)
    # 민감도는 중첩 구조라서 요약 테이블 별도 구성
    sens_summary = []
    for r in sens_results:
        # contamination SR 평균 (기본값 제외)
        contam_srs = [
            c["stability_ratio"]
            for c in r["contamination_sensitivity"]
            if c["contamination"] != 0.10
            and c["stability_ratio"] is not None
            and not np.isnan(c["stability_ratio"])
        ]
        avg_contam = np.mean(contam_srs) if contam_srs else np.nan

        # k값 SR 평균 (기본값 제외)
        k_srs = [
            k["stability_ratio"]
            for k in r["lof_k_sensitivity"]
            if k["lof_k"] != 10
            and k["stability_ratio"] is not None
            and not np.isnan(k["stability_ratio"])
        ]
        avg_k = np.mean(k_srs) if k_srs else np.nan

        sens_summary.append({
            "commodity_id": r["commodity_id"],
            "segment": r["segment"],
            "n_base": r["n_base"],
            "avg_contam_sr": round(avg_contam, 4) if not np.isnan(avg_contam) else np.nan,
            "avg_k_sr": round(avg_k, 4) if not np.isnan(avg_k) else np.nan,
        })

    sens_df = pd.DataFrame(sens_summary)
    sens_df.to_csv(output / "axis4_sensitivity.csv", index=False, encoding="utf-8-sig")
    print()

    # --- 축 5: CTA + ASC ---
    cons_results = run_axis5(data_dir, ml_dir)
    cons_df = pd.DataFrame(cons_results)
    cons_df.to_csv(output / "axis5_consensus.csv", index=False, encoding="utf-8-sig")
    print()

    # --- 종합 리포트 ---
    log_eval("=" * 60)
    log_eval("종합 리포트")
    log_eval("=" * 60)

    print()
    print("=== 축 1: 외부 충격 회수율 (ESR) ===")
    print(f"전체 가중 ESR_ml: {esr_weighted:.4f}")
    print(esr_df[["commodity_id", "segment", "n_shocks", "esr_ml"]].to_string(index=False))

    print()
    print("=== 축 2: 이상 점수 분리도 ===")
    print(f"평균 SR: IF={sep_df['sr_if'].mean():.3f}, LOF={sep_df['sr_lof'].mean():.3f}, SVM={sep_df['sr_svm'].mean():.3f}")
    print(sep_df.to_string(index=False))

    print()
    print("=== 축 3: 통계-ML 일관성 AUC ===")
    print(f"평균 AUC: IF={auc_df['auc_if'].mean():.4f}, LOF={auc_df['auc_lof'].mean():.4f}, SVM={auc_df['auc_svm'].mean():.4f}, ensemble={auc_df['auc_ensemble'].mean():.4f}")
    print(auc_df.to_string(index=False))

    print()
    print("=== 축 4: 파라미터 민감도 ===")
    print(f"평균 contamination SR: {sens_df['avg_contam_sr'].mean():.4f}")
    print(f"평균 LOF k SR: {sens_df['avg_k_sr'].mean():.4f}")
    print(sens_df.to_string(index=False))

    print()
    print("=== 축 5: 합의 기반 지표 ===")
    valid_cons = cons_df[cons_df["hypothesis_holds"].notna()]
    n_holds = valid_cons["hypothesis_holds"].sum()
    n_valid = len(valid_cons)
    print(f"CTA 평균: {cons_df['cta'].mean():.4f}")
    print(f"ASC 평균: {cons_df['asc'].dropna().mean():.4f}")
    print(f"핵심 가설 (ASC > max(ESR)) 성립: {n_holds}/{n_valid} 구간")
    print(cons_df[["commodity_id", "segment", "cta", "asc", "esr_stat", "esr_ml", "hypothesis_holds"]].to_string(index=False))

    log_eval(f"결과 저장: {output}")


if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
    ML_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "phase7_ml")
    PHASE7_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed", "phase7")
    OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")

    run_all(DATA_DIR, ML_DIR, PHASE7_DIR, OUTPUT_DIR)
