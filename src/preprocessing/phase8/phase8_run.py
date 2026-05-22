"""
Phase 8 통합 실행 진입점 (phase8_run.py)
=========================================
역할:
  Phase 8 전체 파이프라인을 순차 실행한다.
  (1) 결과 종합 (S1~S5) — phase8_summary.py
  (2) 로버스트니스 체크 (R1~R3) — phase8_robustness.py
  (3) 동조성 분석 (T1~T6) — phase8_5_synchrony.py
  (4) 전체 메타 정보 저장 — phase8_meta.json

입력 파일:
  Phase 7/7-ML 산출물 전체, Phase 1 로버스트니스, Phase 4/6 기준선

출력 파일:
  data/processed/phase8/summary/         ← S1~S5 (7개 CSV)
  data/processed/phase8/robustness/      ← R1~R3 (3개 CSV + 1개 JSON)
  data/processed/phase8/synchrony/       ← T1~T6 (6개 CSV)
  data/processed/phase8/phase8_meta.json ← 전체 실행 메타

코드 위치:
  src/preprocessing/phase8/phase8_run.py

실행 방법:
  python src/preprocessing/phase8/phase8_run.py
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase8_common import (
    Phase8Paths,
    load_product_config,
    ensure_phase8_dirs,
    log8,
)
from phase8_summary import run_summary
from phase8_robustness import run_robustness
from phase8_5_synchrony import run_synchrony


# ═══════════════════════════════════════════════════════════════════
# 전체 메타 정보 생성
# ═══════════════════════════════════════════════════════════════════
def build_phase8_meta(summary_results, robustness_results, synchrony_results,
                      elapsed_seconds):
    """
    Phase 8 전체 실행 결과를 메타 JSON으로 구성한다.
    """
    meta = {
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(elapsed_seconds, 1),
        "modules": {
            "summary": {
                "outputs": [
                    "confidence_summary.csv",
                    "agreement_analysis.csv",
                    "cross_commodity_comparison.csv",
                    "wholesale_comparison.csv",
                    "wholesale_downstream_analysis.csv",
                    "shock_correspondence.csv",
                    "shock_detail.csv",
                ],
            },
            "robustness": {
                "outputs": [
                    "rolling_window_sensitivity.csv",
                    "seasonal_method_comparison.csv",
                    "contamination_sensitivity.csv",
                    "robustness_summary.json",
                ],
            },
            "synchrony": {
                "outputs": [
                    "heatmap_data.csv",
                    "monthly_co_detection.csv",
                    "case_A_ukraine.csv",
                    "case_B_russia_drought.csv",
                    "case_C_feed_livestock.csv",
                    "ml_reference_co_occurrence.csv",
                ],
            },
        },
        "key_findings": {},
    }

    # S1 요약
    conf = summary_results.get("confidence_summary")
    if conf is not None:
        total_row = conf[conf["commodity_id"] == "ALL"]
        if len(total_row) > 0:
            t = total_row.iloc[0]
            meta["key_findings"]["confidence"] = {
                "total_anomalies": int(t["total_anomalies"]),
                "high": int(t["high"]),
                "medium": int(t["medium"]),
                "reference": int(t["reference"]),
                "high_pct": float(t["high_pct"]),
            }

    # S2 요약
    agree = summary_results.get("agreement_analysis")
    if agree is not None:
        meta["key_findings"]["agreement"] = {
            "avg_agreement_rate": round(float(agree["agreement_rate"].mean()), 1),
            "avg_cohen_kappa": round(float(agree["cohen_kappa"].mean()), 4),
        }

    # S5 요약
    shock = summary_results.get("shock_correspondence")
    if shock is not None:
        meta["key_findings"]["shock_recall"] = {
            row["shock_id"]: {
                "stat_recall": float(row["stat_recall"]),
                "ml_recall": float(row["ml_recall"]),
            }
            for _, row in shock.iterrows()
        }

    # R1~R3 요약
    rob_summary = robustness_results.get("robustness_summary")
    if rob_summary:
        meta["key_findings"]["robustness"] = rob_summary

    # T5 요약
    case_c = synchrony_results.get("case_C_feed_livestock")
    if case_c is not None and len(case_c) > 0:
        meta["key_findings"]["feed_livestock_lag"] = {
            "n_triggers": len(case_c),
            "response_3m_pct": round(
                float(case_c["beef_A_response_3m"].mean()) * 100, 1
            ),
            "response_6m_pct": round(
                float(case_c["beef_A_response_6m"].mean()) * 100, 1
            ),
            "avg_first_lag_months": round(
                float(case_c["beef_A_first_response_lag"].mean()), 1
            ),
        }

    # T6 요약
    ref_co = synchrony_results.get("ml_reference_co_occurrence")
    if ref_co is not None:
        meta["key_findings"]["ml_reference_co_occurrence"] = {
            "k3_plus_months": len(ref_co),
            "in_shock_window": int(ref_co["in_shock_window"].sum())
            if len(ref_co) > 0 else 0,
        }

    return meta


# ═══════════════════════════════════════════════════════════════════
# 메인 실행
# ═══════════════════════════════════════════════════════════════════
def run_phase8(data_dir, phase7_dir, ml_dir, output_dir,
               phase1_changes_dir=None, phase1_dummy_dir=None):
    """
    Phase 8 전체 파이프라인을 실행한다.

    Args:
        data_dir: 데이터 루트 디렉토리 (product_config.json 위치)
        phase7_dir: Phase 7 stat 출력 디렉토리
        ml_dir: Phase 7-ML 출력 디렉토리
        output_dir: Phase 8 출력 디렉토리
        phase1_changes_dir: Phase 1 STL changes 디렉토리 (None이면 기본 경로)
        phase1_dummy_dir: Phase 1 계절 더미 디렉토리 (None이면 기본 경로)

    Returns:
        phase8_meta dict
    """
    start_time = time.time()

    paths = Phase8Paths(
        data_dir=data_dir,
        phase7_dir=phase7_dir,
        ml_dir=ml_dir,
        output_dir=output_dir,
        phase1_changes_dir=phase1_changes_dir,
        phase1_dummy_dir=phase1_dummy_dir,
    )

    config = load_product_config(paths)
    output_base = ensure_phase8_dirs(output_dir)

    log8("╔" + "═" * 50 + "╗")
    log8("║   Phase 8 — 결과 종합 및 로버스트니스 체크      ║")
    log8("╚" + "═" * 50 + "╝")
    log8("")

    # (1) 결과 종합 (S1~S5)
    summary_results = run_summary(paths, config)
    log8("")

    # (2) 로버스트니스 체크 (R1~R3)
    robustness_results = run_robustness(paths, config)
    log8("")

    # (3) 동조성 분석 (T1~T6)
    synchrony_results = run_synchrony(paths, config)
    log8("")

    # (4) 전체 메타 정보 저장
    elapsed = time.time() - start_time
    meta = build_phase8_meta(
        summary_results, robustness_results, synchrony_results, elapsed
    )

    meta_path = output_base / "phase8_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    log8("╔" + "═" * 50 + "╗")
    log8("║   Phase 8 전체 완료                             ║")
    log8("╚" + "═" * 50 + "╝")
    log8(f"  소요 시간: {elapsed:.1f}초")
    log8(f"  메타 정보: {meta_path}")
    log8("")

    # 출력물 목록 출력
    log8("=== 출력물 목록 ===")
    for dirpath, dirnames, filenames in os.walk(output_base):
        for fn in sorted(filenames):
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, output_base)
            size = os.path.getsize(fp)
            log8(f"  {rel}: {size:,} bytes")

    return meta


# ═══════════════════════════════════════════════════════════════════
# 엔트리포인트
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # 프로젝트 루트 기준 경로 설정
    BASE_DIR = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
    )
    DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
    PHASE7_DIR = os.path.join(DATA_DIR, "phase7")
    ML_DIR = os.path.join(DATA_DIR, "phase7_ml")
    OUTPUT_DIR = os.path.join(DATA_DIR, "phase8")
    PHASE1_CHANGES_DIR = os.path.join(DATA_DIR, "phase1", "changes")
    PHASE1_DUMMY_DIR = os.path.join(DATA_DIR, "phase1", "robustness")

    meta = run_phase8(
        data_dir=DATA_DIR,
        phase7_dir=PHASE7_DIR,
        ml_dir=ML_DIR,
        output_dir=OUTPUT_DIR,
        phase1_changes_dir=PHASE1_CHANGES_DIR,
        phase1_dummy_dir=PHASE1_DUMMY_DIR,
    )

    print()
    print("=== Phase 8 Key Findings ===")
    print(json.dumps(meta["key_findings"], indent=2, ensure_ascii=False))
