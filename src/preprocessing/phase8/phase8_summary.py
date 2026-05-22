"""
Phase 8 결과 종합 (phase8_summary.py)
======================================
역할:
  Phase 7(통계)과 Phase 7-ML(ML 교차검증) 산출물을 종합하여
  5개 분석 테이블을 생성한다.

  S1. 신뢰도 등급 집계
  S2. 통계-ML 일치율 분석
  S3. 품목 간 횡단 비교 (공통 구간 A·B)
  S4. 도매 단계 비교 분석
  S5. 외부 충격 시점 대조

출력 파일:
  data/processed/phase8/summary/confidence_summary.csv
  data/processed/phase8/summary/agreement_analysis.csv
  data/processed/phase8/summary/cross_commodity_comparison.csv
  data/processed/phase8/summary/wholesale_comparison.csv
  data/processed/phase8/summary/wholesale_downstream_analysis.csv
  data/processed/phase8/summary/shock_correspondence.csv
  data/processed/phase8/summary/shock_detail.csv
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase8_common import (
    Phase8Paths,
    EXTERNAL_SHOCKS,
    THREE_SEG_COMMODITIES,
    FOUR_SEG_COMMODITIES,
    ML_SEGMENTS,
    load_product_config,
    load_phase7_summary,
    load_grades,
    load_cross_val,
    load_predictions,
    get_applicable_shocks,
    get_shock_window_dates,
    iter_ml_segments,
    iter_all_segments,
    cohen_kappa,
    ensure_phase8_dirs,
    log8,
)


# ═══════════════════════════════════════════════════════════════════
# S1. 신뢰도 등급 집계
# ═══════════════════════════════════════════════════════════════════
def build_confidence_summary(paths, config):
    """
    전 20개 유닛(A·B)의 confidence_grades를 통합하고
    등급별·품목별·구간별 건수를 집계한다.
    """
    log8("S1: 신뢰도 등급 집계")
    rows = []

    for cid, seg in iter_ml_segments(config):
        gr = load_grades(paths, cid, seg)

        n_high = int((gr["confidence_grade"] == "high").sum())
        n_medium = int((gr["confidence_grade"] == "medium").sum())
        n_reference = int((gr["confidence_grade"] == "reference").sum())
        total = n_high + n_medium + n_reference

        rows.append({
            "commodity_id": cid,
            "segment": seg,
            "total_anomalies": total,
            "high": n_high,
            "medium": n_medium,
            "reference": n_reference,
            "high_pct": round(n_high / total * 100, 1) if total > 0 else 0.0,
            "stat_only": n_medium,
            "ml_only": n_reference,
        })

    df = pd.DataFrame(rows)

    # 전체 합계 행
    totals = df[["total_anomalies", "high", "medium", "reference",
                 "stat_only", "ml_only"]].sum()
    total_row = {
        "commodity_id": "ALL",
        "segment": "ALL",
        "total_anomalies": int(totals["total_anomalies"]),
        "high": int(totals["high"]),
        "medium": int(totals["medium"]),
        "reference": int(totals["reference"]),
        "high_pct": round(
            totals["high"] / totals["total_anomalies"] * 100, 1
        ) if totals["total_anomalies"] > 0 else 0.0,
        "stat_only": int(totals["stat_only"]),
        "ml_only": int(totals["ml_only"]),
    }
    df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

    log8(f"  총 이상 이벤트: {int(totals['total_anomalies'])}")
    log8(f"  high={int(totals['high'])}, medium={int(totals['medium'])}, "
         f"reference={int(totals['reference'])}")

    return df


# ═══════════════════════════════════════════════════════════════════
# S2. 통계-ML 일치율 분석
# ═══════════════════════════════════════════════════════════════════
def build_agreement_analysis(paths, config):
    """
    cross_validation CSV 20개를 통합하여
    전 시점의 agreement 비율과 Cohen's Kappa를 산출한다.
    """
    log8("S2: 통계-ML 일치율 분석")
    rows = []

    for cid, seg in iter_ml_segments(config):
        cv = load_cross_val(paths, cid, seg)

        stat = cv["stat_detected"].astype(bool)
        ml = cv["ml_detected"].astype(bool)

        both_detected = int((stat & ml).sum())
        stat_only = int((stat & ~ml).sum())
        ml_only = int((~stat & ml).sum())
        both_normal = int((~stat & ~ml).sum())
        total = len(cv)

        agreement_rate = round(
            (both_detected + both_normal) / total * 100, 1
        ) if total > 0 else 0.0

        kappa = cohen_kappa(stat, ml)

        rows.append({
            "commodity_id": cid,
            "segment": seg,
            "total_months": total,
            "both_detected": both_detected,
            "stat_only": stat_only,
            "ml_only": ml_only,
            "both_normal": both_normal,
            "agreement_rate": agreement_rate,
            "cohen_kappa": round(kappa, 4) if not np.isnan(kappa) else np.nan,
        })

    df = pd.DataFrame(rows)

    avg_agree = df["agreement_rate"].mean()
    avg_kappa = df["cohen_kappa"].mean()
    log8(f"  평균 일치율: {avg_agree:.1f}%")
    log8(f"  평균 Cohen's Kappa: {avg_kappa:.4f}")

    return df


# ═══════════════════════════════════════════════════════════════════
# S3. 품목 간 횡단 비교 (공통 구간 A·B)
# ═══════════════════════════════════════════════════════════════════
def build_cross_commodity_comparison(paths, config):
    """
    10개 품목의 A·B 구간 탐지 결과를 횡단 비교한다.
    phase7_summary에서 패턴별 건수를, grades에서 신뢰도 건수를 추출한다.
    """
    log8("S3: 품목 간 횡단 비교")

    summary = load_phase7_summary(paths)
    rows = []

    for cid, seg in iter_ml_segments(config):
        cfg = config[cid]
        seg_summary = summary[
            (summary["commodity_id"] == cid) & (summary["segment"] == seg)
        ]

        total_obs = cfg["common_months"]

        # 패턴별 건수 (pattern_types_all에서 개별 패턴 포함 여부로 카운트)
        p1 = int(seg_summary["pattern_types_all"].str.contains("pattern1", na=False).sum())
        p2 = int(seg_summary["pattern_types_all"].str.contains("pattern2", na=False).sum())
        p3 = int(
            seg_summary["pattern_types_all"].str.contains("pattern3", na=False).sum()
        ) if seg == "B" else 0

        total_stat = len(seg_summary)

        # ML 탐지 및 고신뢰 건수
        gr = load_grades(paths, cid, seg)
        ml_detected = int(gr["ml_detected"].sum())
        high_count = int((gr["confidence_grade"] == "high").sum())

        rows.append({
            "commodity_id": cid,
            "segment": seg,
            "total_obs": total_obs,
            "p1_count": p1,
            "p1_rate": round(p1 / total_obs * 100, 1),
            "p2_count": p2,
            "p2_rate": round(p2 / total_obs * 100, 1),
            "p3_count": p3,
            "p3_rate": round(p3 / total_obs * 100, 1) if seg == "B" else 0.0,
            "total_stat": total_stat,
            "total_stat_rate": round(total_stat / total_obs * 100, 1),
            "ml_detected": ml_detected,
            "high_count": high_count,
            "has_wholesale": cfg["has_wholesale"],
        })

    df = pd.DataFrame(rows)
    log8(f"  {len(df)}개 유닛 비교 완료")

    return df


# ═══════════════════════════════════════════════════════════════════
# S4. 도매 단계 비교 분석
# ═══════════════════════════════════════════════════════════════════
def build_wholesale_comparison(cross_comp_df):
    """
    S3 결과를 기반으로 3구간 vs 4구간 그룹 비교를 수행한다.
    """
    log8("S4: 도매 단계 비교 (그룹 비교)")

    rows = []
    for group_name, cid_list in [
        ("3seg", THREE_SEG_COMMODITIES),
        ("4seg", FOUR_SEG_COMMODITIES),
    ]:
        grp = cross_comp_df[cross_comp_df["commodity_id"].isin(cid_list)]
        grp_a = grp[grp["segment"] == "A"]
        grp_b = grp[grp["segment"] == "B"]

        rows.append({
            "group": group_name,
            "n_commodities": len(cid_list),
            "avg_p1_rate_A": round(grp_a["p1_rate"].mean(), 1),
            "avg_p1_rate_B": round(grp_b["p1_rate"].mean(), 1),
            "avg_p2_rate_A": round(grp_a["p2_rate"].mean(), 1),
            "avg_p2_rate_B": round(grp_b["p2_rate"].mean(), 1),
            "avg_stat_rate_A": round(grp_a["total_stat_rate"].mean(), 1),
            "avg_stat_rate_B": round(grp_b["total_stat_rate"].mean(), 1),
            "avg_high_pct": round(
                grp["high_count"].sum()
                / grp["total_stat"].sum() * 100, 1
            ) if grp["total_stat"].sum() > 0 else 0.0,
        })

    df = pd.DataFrame(rows)
    log8(f"  3구간 vs 4구간 비교 완료")

    return df


def build_wholesale_downstream_analysis(paths, config):
    """
    4구간 품목(3종)에 대해 A·B 탐지와 C·D 탐지의 관계를 분석한다.
    동월 동시 탐지, 시차 전파(1m/3m) 여부를 산출한다.
    """
    log8("S4: 도매 하류 구간 분석")

    summary = load_phase7_summary(paths)
    rows = []

    seg_pairs = [("A", "C"), ("B", "D")]

    for cid in FOUR_SEG_COMMODITIES:
        for up_seg, dn_seg in seg_pairs:
            # 해당 구간이 존재하는지 확인
            if up_seg not in config[cid]["segments"]:
                continue
            if dn_seg not in config[cid]["segments"]:
                continue

            up_events = summary[
                (summary["commodity_id"] == cid)
                & (summary["segment"] == up_seg)
            ]
            dn_events = summary[
                (summary["commodity_id"] == cid)
                & (summary["segment"] == dn_seg)
            ]

            up_dates = set(up_events["date"])
            dn_dates = set(dn_events["date"])

            # 동월 동시 탐지
            co_occurrence = up_dates & dn_dates

            # 시차 전파: 상류 탐지 후 N개월 내 하류 탐지
            follows_1m = 0
            follows_3m = 0
            for up_date in up_dates:
                for offset in range(1, 4):
                    future = up_date + pd.DateOffset(months=offset)
                    if future in dn_dates:
                        if offset <= 1:
                            follows_1m += 1
                        follows_3m += 1
                        break  # 최초 반응만 카운트

            rows.append({
                "commodity_id": cid,
                "seg_pair": f"{up_seg}→{dn_seg}",
                "upstream_count": len(up_dates),
                "downstream_count": len(dn_dates),
                "co_occurrence": len(co_occurrence),
                "co_occurrence_rate": round(
                    len(co_occurrence) / len(up_dates) * 100, 1
                ) if len(up_dates) > 0 else 0.0,
                "downstream_follows_1m": follows_1m,
                "downstream_follows_3m": follows_3m,
            })

    df = pd.DataFrame(rows)
    log8(f"  {len(df)}개 구간 쌍 분석 완료")

    return df


# ═══════════════════════════════════════════════════════════════════
# S5. 외부 충격 시점 대조
# ═══════════════════════════════════════════════════════════════════
def build_shock_correspondence(paths, config):
    """
    외부 충격 5개 이벤트에 대해 통계·ML 탐지의 회수율을 산출한다.
    요약 테이블 + 상세 테이블을 반환한다.
    """
    log8("S5: 외부 충격 시점 대조")

    summary = load_phase7_summary(paths)
    corr_rows = []
    detail_rows = []

    for shock in EXTERNAL_SHOCKS:
        s_start, s_end = get_shock_window_dates(shock)

        stat_hits = 0
        ml_hits = 0
        high_hits = 0
        total_stat_events = 0
        total_ml_events = 0
        n_applicable = 0

        for cid in shock["commodities"]:
            for seg in ML_SEGMENTS:
                if seg not in config[cid]["segments"]:
                    continue

                n_applicable += 1

                # 통계 탐지: summary에서 윈도우 내 이벤트
                seg_stat = summary[
                    (summary["commodity_id"] == cid)
                    & (summary["segment"] == seg)
                    & (summary["date"] >= s_start)
                    & (summary["date"] <= s_end)
                ]
                stat_in_window = len(seg_stat) > 0
                stat_count = len(seg_stat)
                pattern_types = (
                    ",".join(sorted(seg_stat["pattern_type"].unique()))
                    if stat_count > 0 else ""
                )

                # ML 탐지: predictions에서 윈도우 내 이벤트
                try:
                    pred = load_predictions(paths, cid, seg)
                    window_pred = pred[
                        (pred["date"] >= s_start) & (pred["date"] <= s_end)
                    ]
                    ml_in_window = window_pred["ml_detected"].any()
                    ml_count = int(window_pred["ml_detected"].sum())
                except Exception:
                    ml_in_window = False
                    ml_count = 0

                # 고신뢰: grades에서 윈도우 내 high
                try:
                    gr = load_grades(paths, cid, seg)
                    window_gr = gr[
                        (gr["date"] >= s_start)
                        & (gr["date"] <= s_end)
                        & (gr["confidence_grade"] == "high")
                    ]
                    high_in_window = len(window_gr) > 0
                except Exception:
                    high_in_window = False

                if stat_in_window:
                    stat_hits += 1
                if ml_in_window:
                    ml_hits += 1
                if high_in_window:
                    high_hits += 1
                total_stat_events += stat_count
                total_ml_events += ml_count

                detail_rows.append({
                    "shock_id": shock["id"],
                    "commodity_id": cid,
                    "segment": seg,
                    "stat_detected_in_window": stat_in_window,
                    "ml_detected_in_window": ml_in_window,
                    "high_in_window": high_in_window,
                    "stat_event_count": stat_count,
                    "ml_event_count": ml_count,
                    "pattern_types": pattern_types,
                })

        corr_rows.append({
            "shock_id": shock["id"],
            "shock_name": shock["name"],
            "shock_start": shock["start"],
            "shock_end": shock["end"],
            "n_applicable_segments": n_applicable,
            "stat_hits": stat_hits,
            "stat_recall": round(
                stat_hits / n_applicable, 3
            ) if n_applicable > 0 else 0.0,
            "ml_hits": ml_hits,
            "ml_recall": round(
                ml_hits / n_applicable, 3
            ) if n_applicable > 0 else 0.0,
            "high_hits": high_hits,
            "total_stat_events_in_window": total_stat_events,
            "total_ml_events_in_window": total_ml_events,
        })

        log8(f"  {shock['id']} ({shock['name']}): "
             f"stat_recall={stat_hits}/{n_applicable}, "
             f"ml_recall={ml_hits}/{n_applicable}, "
             f"high={high_hits}")

    corr_df = pd.DataFrame(corr_rows)
    detail_df = pd.DataFrame(detail_rows)

    return corr_df, detail_df


# ═══════════════════════════════════════════════════════════════════
# 통합 실행
# ═══════════════════════════════════════════════════════════════════
def run_summary(paths, config):
    """
    Phase 8 결과 종합 S1~S5를 실행하고 CSV로 저장한다.

    Args:
        paths: Phase8Paths 인스턴스
        config: product_config dict

    Returns:
        dict of DataFrames
    """
    output_dir = ensure_phase8_dirs(paths.output_dir)
    summary_dir = output_dir / "summary"

    log8("=" * 50)
    log8("Phase 8 결과 종합 시작")
    log8("=" * 50)

    results = {}

    # S1: 신뢰도 등급 집계
    confidence = build_confidence_summary(paths, config)
    confidence.to_csv(
        summary_dir / "confidence_summary.csv",
        index=False, encoding="utf-8-sig",
    )
    results["confidence_summary"] = confidence

    # S2: 통계-ML 일치율 분석
    agreement = build_agreement_analysis(paths, config)
    agreement.to_csv(
        summary_dir / "agreement_analysis.csv",
        index=False, encoding="utf-8-sig",
    )
    results["agreement_analysis"] = agreement

    # S3: 품목 간 횡단 비교
    cross_comp = build_cross_commodity_comparison(paths, config)
    cross_comp.to_csv(
        summary_dir / "cross_commodity_comparison.csv",
        index=False, encoding="utf-8-sig",
    )
    results["cross_commodity_comparison"] = cross_comp

    # S4: 도매 단계 비교
    wholesale = build_wholesale_comparison(cross_comp)
    wholesale.to_csv(
        summary_dir / "wholesale_comparison.csv",
        index=False, encoding="utf-8-sig",
    )
    results["wholesale_comparison"] = wholesale

    downstream = build_wholesale_downstream_analysis(paths, config)
    downstream.to_csv(
        summary_dir / "wholesale_downstream_analysis.csv",
        index=False, encoding="utf-8-sig",
    )
    results["wholesale_downstream_analysis"] = downstream

    # S5: 외부 충격 시점 대조
    shock_corr, shock_detail = build_shock_correspondence(paths, config)
    shock_corr.to_csv(
        summary_dir / "shock_correspondence.csv",
        index=False, encoding="utf-8-sig",
    )
    shock_detail.to_csv(
        summary_dir / "shock_detail.csv",
        index=False, encoding="utf-8-sig",
    )
    results["shock_correspondence"] = shock_corr
    results["shock_detail"] = shock_detail

    log8("=" * 50)
    log8("Phase 8 결과 종합 완료")
    log8(f"  출력: {summary_dir}")
    log8("=" * 50)

    return results