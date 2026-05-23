"""
Phase 8.5 품목 간 이상 동조성 분석 (phase8_5_synchrony.py)
==========================================================
역할:
  10개 품목의 이상 시점을 횡단 대조하고 케이스 분석을 수행한다.

  T1. 히트맵 데이터 생성
  T2. 월별 동시 탐지 집계
  T3. 케이스 A — 2022 우크라이나 (E4)
  T4. 케이스 B — 2010 러시아 가뭄 (E6)
  T5. 케이스 C — 사료→축산물 시차 (탐색적)
  T6. ML reference 동시 발생 분석

출력 파일:
  data/processed/phase8/synchrony/heatmap_data.csv
  data/processed/phase8/synchrony/monthly_co_detection.csv
  data/processed/phase8/synchrony/case_A_ukraine.csv
  data/processed/phase8/synchrony/case_B_russia_drought.csv
  data/processed/phase8/synchrony/case_C_feed_livestock.csv
  data/processed/phase8/synchrony/ml_reference_co_occurrence.csv
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
    ALL_COMMODITIES,
    ML_SEGMENTS,
    load_product_config,
    load_phase7_summary,
    load_grades,
    load_predictions,
    get_applicable_shocks,
    is_date_in_shock_window,
    get_shock_window_dates,
    iter_ml_segments,
    ensure_phase8_dirs,
    log8,
)


# ═══════════════════════════════════════════════════════════════════
# T1. 히트맵 데이터 생성
# ═══════════════════════════════════════════════════════════════════
def build_heatmap_data(paths, config):
    """
    시간(월) × 품목×구간(A·B) 히트맵 데이터를 생성한다.
    각 셀은 패턴 유형과 신뢰도 등급을 포함한다.
    """
    log8("T1: 히트맵 데이터 생성")

    summary = load_phase7_summary(paths)
    summary_indexed = summary.set_index(["date", "commodity_id", "segment"])

    # 전체 grades 로드
    all_grades = []
    for cid, seg in iter_ml_segments(config):
        gr = load_grades(paths, cid, seg)
        all_grades.append(gr)
    grades_all = pd.concat(all_grades, ignore_index=True)
    grades_all["date"] = pd.to_datetime(grades_all["date"])
    grades_indexed = grades_all.set_index(["date", "commodity_id", "segment"])

    # 전체 날짜 범위 (모든 품목의 공통 범위 합집합)
    all_dates = set()
    for cid in config:
        start = pd.Timestamp(config[cid]["common_start"] + "-01")
        end = pd.Timestamp(config[cid]["common_end"] + "-01")
        dates = pd.date_range(start, end, freq="MS")
        all_dates.update(dates)
    all_dates = sorted(all_dates)

    rows = []
    for date in all_dates:
        for cid in config:
            cid_start = pd.Timestamp(config[cid]["common_start"] + "-01")
            cid_end = pd.Timestamp(config[cid]["common_end"] + "-01")
            if date < cid_start or date > cid_end:
                continue

            for seg in ML_SEGMENTS:
                if seg not in config[cid]["segments"]:
                    continue

                # 통계 탐지
                key = (date, cid, seg)
                if key in summary_indexed.index:
                    sm_row = summary_indexed.loc[key]
                    if isinstance(sm_row, pd.DataFrame):
                        sm_row = sm_row.iloc[0]
                    stat_detected = True
                    pattern_type = sm_row["pattern_type"]
                else:
                    stat_detected = False
                    pattern_type = "none"

                # ML 탐지 + 신뢰도
                if key in grades_indexed.index:
                    gr_row = grades_indexed.loc[key]
                    if isinstance(gr_row, pd.DataFrame):
                        gr_row = gr_row.iloc[0]
                    ml_detected = bool(gr_row["ml_detected"])
                    confidence_grade = gr_row["confidence_grade"]
                else:
                    ml_detected = False
                    confidence_grade = "none"

                rows.append({
                    "date": date,
                    "commodity_id": cid,
                    "segment": seg,
                    "pattern_type": pattern_type,
                    "confidence_grade": confidence_grade,
                    "stat_detected": stat_detected,
                    "ml_detected": ml_detected,
                })

    df = pd.DataFrame(rows)
    log8(f"  {len(df)} rows 생성 (날짜×품목×구간)")
    return df


# ═══════════════════════════════════════════════════════════════════
# T2. 월별 동시 탐지 집계
# ═══════════════════════════════════════════════════════════════════
def build_monthly_co_detection(heatmap_df):
    """
    월별로 몇 개 품목이 동시에 이상을 보이는지 집계한다.
    """
    log8("T2: 월별 동시 탐지 집계")

    rows = []
    for (date, seg), grp in heatmap_df.groupby(["date", "segment"]):
        stat_commodities = grp[grp["stat_detected"]]["commodity_id"].tolist()
        ml_commodities = grp[grp["ml_detected"]]["commodity_id"].tolist()
        high_commodities = grp[
            grp["confidence_grade"] == "high"
        ]["commodity_id"].tolist()

        # 충격 윈도우 확인
        in_shock, shock_id = is_date_in_shock_window(date, EXTERNAL_SHOCKS)

        rows.append({
            "date": date,
            "segment": seg,
            "n_commodities_stat": len(stat_commodities),
            "n_commodities_ml": len(ml_commodities),
            "n_commodities_high": len(high_commodities),
            "commodity_list_stat": ",".join(sorted(stat_commodities)),
            "in_shock_window": in_shock,
            "shock_id": shock_id if shock_id else "",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(["date", "segment"]).reset_index(drop=True)

    # 통계 요약
    max_stat = df["n_commodities_stat"].max()
    max_ml = df["n_commodities_ml"].max()
    log8(f"  최대 동시 탐지: stat={max_stat}품목, ml={max_ml}품목")

    return df


# ═══════════════════════════════════════════════════════════════════
# T3. 케이스 A — 2022 우크라이나 (E4)
# ═══════════════════════════════════════════════════════════════════
def build_case_A_ukraine(paths, config, heatmap_df):
    """
    E4(2022-02~2022-10) 윈도우 내에서 wheat, maize, soybean 구간 A의
    탐지 패턴을 분석한다.
    """
    log8("T3: 케이스 A — 2022 우크라이나")

    shock = next(s for s in EXTERNAL_SHOCKS if s["id"] == "E4")
    s_start, s_end = get_shock_window_dates(shock)
    target_cids = ["wheat", "maize", "soybean"]
    seg = "A"

    # 윈도우 내 월 생성
    window_dates = pd.date_range(s_start, s_end, freq="MS")

    rows = []
    for date in window_dates:
        row = {"date": date}
        n_detected = 0

        for cid in target_cids:
            match = heatmap_df[
                (heatmap_df["date"] == date)
                & (heatmap_df["commodity_id"] == cid)
                & (heatmap_df["segment"] == seg)
            ]

            if len(match) > 0:
                m = match.iloc[0]
                row[f"{cid}_A_detected"] = m["stat_detected"]
                row[f"{cid}_A_pattern"] = m["pattern_type"]
                row[f"{cid}_A_grade"] = m["confidence_grade"]
                if m["stat_detected"]:
                    n_detected += 1
            else:
                row[f"{cid}_A_detected"] = False
                row[f"{cid}_A_pattern"] = "none"
                row[f"{cid}_A_grade"] = "none"

        row["n_simultaneous"] = n_detected
        rows.append(row)

    df = pd.DataFrame(rows)

    # 요약
    n_all_3 = int((df["n_simultaneous"] == 3).sum())
    n_any = int((df["n_simultaneous"] >= 1).sum())
    log8(f"  윈도우 {len(window_dates)}개월: "
         f"3품목 동시={n_all_3}, 1개 이상={n_any}")

    return df


# ═══════════════════════════════════════════════════════════════════
# T4. 케이스 B — 2010 러시아 가뭄 (E6)
# ═══════════════════════════════════════════════════════════════════
def build_case_B_russia_drought(paths, config, heatmap_df):
    """
    E6(2010-08~2011-06) 윈도우 내에서 해당 품목 구간 A의
    탐지 패턴을 분석한다.
    """
    log8("T4: 케이스 B — 2010 러시아 가뭄")

    shock = next(s for s in EXTERNAL_SHOCKS if s["id"] == "E6")
    s_start, s_end = get_shock_window_dates(shock)
    target_cids = shock["commodities"]
    seg = "A"

    window_dates = pd.date_range(s_start, s_end, freq="MS")

    rows = []
    for date in window_dates:
        row = {"date": date}
        n_detected = 0

        for cid in target_cids:
            match = heatmap_df[
                (heatmap_df["date"] == date)
                & (heatmap_df["commodity_id"] == cid)
                & (heatmap_df["segment"] == seg)
            ]

            if len(match) > 0:
                m = match.iloc[0]
                row[f"{cid}_A_detected"] = m["stat_detected"]
                row[f"{cid}_A_pattern"] = m["pattern_type"]
                row[f"{cid}_A_grade"] = m["confidence_grade"]
                if m["stat_detected"]:
                    n_detected += 1
            else:
                row[f"{cid}_A_detected"] = False
                row[f"{cid}_A_pattern"] = "none"
                row[f"{cid}_A_grade"] = "none"

        row["n_simultaneous"] = n_detected
        rows.append(row)

    df = pd.DataFrame(rows)

    n_majority = int((df["n_simultaneous"] >= len(target_cids) // 2).sum())
    n_any = int((df["n_simultaneous"] >= 1).sum())
    log8(f"  윈도우 {len(window_dates)}개월 ({len(target_cids)}품목): "
         f"과반 동시={n_majority}, 1개 이상={n_any}")

    return df


# ═══════════════════════════════════════════════════════════════════
# T5. 케이스 C — 사료→축산물 시차 (탐색적)
# ═══════════════════════════════════════════════════════════════════
def build_case_C_feed_livestock(paths, config):
    """
    옥수수·대두 구간 A 탐지 후 소고기 구간 A에서 시차를 두고
    이상이 뒤따르는지 분석한다.
    """
    log8("T5: 케이스 C — 사료→축산물 시차")

    summary = load_phase7_summary(paths)

    # 트리거: maize A 또는 soybean A 탐지 날짜
    trigger_events = summary[
        (summary["commodity_id"].isin(["maize", "soybean"]))
        & (summary["segment"] == "A")
    ][["date", "commodity_id"]].copy()
    trigger_events["date"] = pd.to_datetime(trigger_events["date"])

    # 소고기 A 탐지 날짜 집합
    beef_a_dates = set(
        pd.to_datetime(
            summary[
                (summary["commodity_id"] == "beef")
                & (summary["segment"] == "A")
            ]["date"]
        )
    )

    rows = []
    for _, trig in trigger_events.iterrows():
        trig_date = trig["date"]
        trig_cid = trig["commodity_id"]

        # 1m, 3m, 6m 내 소고기 반응 확인
        resp_1m = False
        resp_3m = False
        resp_6m = False
        first_lag = np.nan

        for offset in range(1, 7):
            future = trig_date + pd.DateOffset(months=offset)
            if future in beef_a_dates:
                if offset <= 1:
                    resp_1m = True
                if offset <= 3:
                    resp_3m = True
                resp_6m = True
                if np.isnan(first_lag):
                    first_lag = offset

        rows.append({
            "trigger_date": trig_date,
            "trigger_commodity": trig_cid,
            "beef_A_response_1m": resp_1m,
            "beef_A_response_3m": resp_3m,
            "beef_A_response_6m": resp_6m,
            "beef_A_first_response_lag": first_lag if not np.isnan(first_lag) else np.nan,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("trigger_date").reset_index(drop=True)

    # 요약
    n_triggers = len(df)
    n_resp_3m = int(df["beef_A_response_3m"].sum())
    n_resp_6m = int(df["beef_A_response_6m"].sum())
    avg_lag = df["beef_A_first_response_lag"].mean()
    log8(f"  트리거 {n_triggers}건: "
         f"3m 내 반응={n_resp_3m} ({n_resp_3m/n_triggers*100:.0f}%), "
         f"6m 내 반응={n_resp_6m} ({n_resp_6m/n_triggers*100:.0f}%), "
         f"평균 시차={avg_lag:.1f}개월")

    return df


# ═══════════════════════════════════════════════════════════════════
# T6. ML reference 동시 발생 분석
# ═══════════════════════════════════════════════════════════════════
def build_ml_reference_co_occurrence(paths, config):
    """
    reference 등급(ML 단독 탐지)이 k≥3 품목에서 동시 발생하는 월을 추출한다.
    """
    log8("T6: ML reference 동시 발생")

    # 전체 grades 로드
    all_grades = []
    for cid, seg in iter_ml_segments(config):
        gr = load_grades(paths, cid, seg)
        all_grades.append(gr)
    grades_all = pd.concat(all_grades, ignore_index=True)
    grades_all["date"] = pd.to_datetime(grades_all["date"])

    # reference 등급만 필터
    ref = grades_all[grades_all["confidence_grade"] == "reference"]

    rows = []
    for (date, seg), grp in ref.groupby(["date", "segment"]):
        cids = sorted(grp["commodity_id"].unique().tolist())
        if len(cids) < 3:
            continue

        in_shock, shock_id = is_date_in_shock_window(date, EXTERNAL_SHOCKS)

        rows.append({
            "date": date,
            "segment": seg,
            "n_reference": len(cids),
            "commodity_list": ",".join(cids),
            "in_shock_window": in_shock,
            "shock_id": shock_id if shock_id else "",
        })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values(["date", "segment"]).reset_index(drop=True)

    log8(f"  k≥3 동시 발생 월: {len(df)}건")
    if len(df) > 0:
        n_in_shock = int(df["in_shock_window"].sum())
        log8(f"  이 중 충격 윈도우 내: {n_in_shock}건")

    return df


# ═══════════════════════════════════════════════════════════════════
# 통합 실행
# ═══════════════════════════════════════════════════════════════════
def run_synchrony(paths, config):
    """
    Phase 8.5 동조성 분석 T1~T6을 실행하고 CSV로 저장한다.

    Args:
        paths: Phase8Paths 인스턴스
        config: product_config dict

    Returns:
        dict of DataFrames
    """
    output_dir = ensure_phase8_dirs(paths.output_dir)
    sync_dir = output_dir / "synchrony"

    log8("=" * 50)
    log8("Phase 8.5 동조성 분석 시작")
    log8("=" * 50)

    results = {}

    # T1: 히트맵 데이터
    heatmap = build_heatmap_data(paths, config)
    heatmap.to_csv(
        sync_dir / "heatmap_data.csv",
        index=False, encoding="utf-8-sig",
    )
    results["heatmap_data"] = heatmap

    # T2: 월별 동시 탐지
    co_detect = build_monthly_co_detection(heatmap)
    co_detect.to_csv(
        sync_dir / "monthly_co_detection.csv",
        index=False, encoding="utf-8-sig",
    )
    results["monthly_co_detection"] = co_detect

    # T3: 케이스 A — 우크라이나
    case_a = build_case_A_ukraine(paths, config, heatmap)
    case_a.to_csv(
        sync_dir / "case_A_ukraine.csv",
        index=False, encoding="utf-8-sig",
    )
    results["case_A_ukraine"] = case_a

    # T4: 케이스 B — 러시아 가뭄
    case_b = build_case_B_russia_drought(paths, config, heatmap)
    case_b.to_csv(
        sync_dir / "case_B_russia_drought.csv",
        index=False, encoding="utf-8-sig",
    )
    results["case_B_russia_drought"] = case_b

    # T5: 케이스 C — 사료→축산물
    case_c = build_case_C_feed_livestock(paths, config)
    case_c.to_csv(
        sync_dir / "case_C_feed_livestock.csv",
        index=False, encoding="utf-8-sig",
    )
    results["case_C_feed_livestock"] = case_c

    # T6: ML reference 동시 발생
    ref_co = build_ml_reference_co_occurrence(paths, config)
    ref_co.to_csv(
        sync_dir / "ml_reference_co_occurrence.csv",
        index=False, encoding="utf-8-sig",
    )
    results["ml_reference_co_occurrence"] = ref_co

    log8("=" * 50)
    log8("Phase 8.5 동조성 분석 완료")
    log8(f"  출력: {sync_dir}")
    log8("=" * 50)

    return results
