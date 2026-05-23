"""
Phase 8 공통 모듈 (phase8_common.py)
=====================================
역할:
  Phase 8 전체에서 공유하는 데이터 로딩, 외부 충격 윈도우 정의,
  품목 분류, 집계 유틸리티를 제공한다.

입력 파일:
  - data/processed/product_config.json
  - data/processed/phase7/phase7_summary.csv
  - data/processed/phase7_ml/phase7_ml_summary.csv
  - data/processed/phase7_ml/predictions/*.csv
  - data/processed/phase7_ml/cross_validation/*.csv
  - data/processed/phase7_ml/confidence_grades/*.csv
  - data/processed/phase7/pattern1/*.csv
  - data/processed/phase7/pattern2/*.csv
  - data/processed/phase7/pattern3/*.csv
  - data/processed/phase7/robustness/*.csv
  - data/processed/phase7/stat_timeseries/*.csv
  - data/processed/phase4/baseline/*.json
  - data/processed/phase6/breakpoints/*.json
  - data/processed/phase1/changes/*.csv
  - data/processed/phase1/robustness/*_dummy_changes.csv

출력 파일:
  없음 (라이브러리 모듈)
"""

import json
import os
import pandas as pd
import numpy as np
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# 외부 충격 사건 정의 (eval_common.py 기준, 시간순)
# ═══════════════════════════════════════════════════════════════════
EXTERNAL_SHOCKS = [
    {
        "id": "E1",
        "name": "2008 글로벌 금융위기",
        "start": "2008-07-01",
        "end": "2009-01-01",
        "commodities": [
            "wheat", "maize", "soybean", "palmoil", "sugar",
            "coffee", "beef", "groundnuts", "banana", "orange",
        ],
    },
    {
        "id": "E6",
        "name": "2010 러시아 가뭄·수출 금지",
        "start": "2010-08-01",
        "end": "2011-06-01",
        "commodities": [
            "wheat", "maize", "soybean", "palmoil", "sugar",
            "coffee", "beef",
        ],
    },
    {
        "id": "E9",
        "name": "2015-16 역대급 엘니뇨",
        "start": "2015-09-01",
        "end": "2016-06-01",
        "commodities": [
            "maize", "soybean", "palmoil", "sugar", "coffee", "beef",
        ],
    },
    {
        "id": "E2",
        "name": "2020 COVID-19 팬데믹",
        "start": "2020-02-01",
        "end": "2020-06-01",
        "commodities": [
            "wheat", "maize", "soybean", "palmoil", "sugar",
            "coffee", "beef", "groundnuts", "banana", "orange",
        ],
    },
    {
        "id": "E4",
        "name": "2022 우크라이나 전쟁",
        "start": "2022-02-01",
        "end": "2022-10-01",
        "commodities": ["wheat", "maize", "soybean", "palmoil"],
    },
]


# ═══════════════════════════════════════════════════════════════════
# 품목 분류
# ═══════════════════════════════════════════════════════════════════
THREE_SEG_COMMODITIES = [
    "wheat", "maize", "soybean", "palmoil", "sugar", "coffee", "beef",
]
FOUR_SEG_COMMODITIES = ["groundnuts", "banana", "orange"]

ALL_COMMODITIES = THREE_SEG_COMMODITIES + FOUR_SEG_COMMODITIES

ML_SEGMENTS = ["A", "B"]
ALL_SEGMENTS = ["A", "B", "C", "D", "D_prime"]


# ═══════════════════════════════════════════════════════════════════
# 데이터 경로 관리
# ═══════════════════════════════════════════════════════════════════
class Phase8Paths:
    """Phase 8에서 사용하는 모든 입출력 경로를 관리한다."""

    def __init__(self, data_dir, phase7_dir, ml_dir, output_dir,
                 phase1_changes_dir=None, phase1_dummy_dir=None):
        self.data_dir = Path(data_dir)
        self.phase7_dir = Path(phase7_dir)
        self.ml_dir = Path(ml_dir)
        self.output_dir = Path(output_dir)

        # Phase 1 경로 (계절 더미 로버스트니스용)
        self.phase1_changes_dir = (
            Path(phase1_changes_dir) if phase1_changes_dir
            else self.data_dir / "phase1" / "changes"
        )
        self.phase1_dummy_dir = (
            Path(phase1_dummy_dir) if phase1_dummy_dir
            else self.data_dir / "phase1" / "robustness"
        )

        # 설정
        self.product_config_path = self.data_dir / "product_config.json"

        # Phase 4/6
        self.baseline_dir = self.data_dir / "phase4" / "baseline"
        self.breakpoints_dir = self.data_dir / "phase6" / "breakpoints"

        # Phase 7 하위 디렉토리
        self.pattern1_dir = self.phase7_dir / "pattern1"
        self.pattern2_dir = self.phase7_dir / "pattern2"
        self.pattern3_dir = self.phase7_dir / "pattern3"
        self.robustness_dir = self.phase7_dir / "robustness"
        self.stat_timeseries_dir = self.phase7_dir / "stat_timeseries"

        # Phase 7-ML 하위 디렉토리
        self.predictions_dir = self.ml_dir / "predictions"
        self.cross_val_dir = self.ml_dir / "cross_validation"
        self.grades_dir = self.ml_dir / "confidence_grades"


# ═══════════════════════════════════════════════════════════════════
# 설정 로딩
# ═══════════════════════════════════════════════════════════════════
def load_product_config(paths):
    """product_config.json을 로드한다."""
    with open(paths.product_config_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# Phase 7 데이터 로딩
# ═══════════════════════════════════════════════════════════════════
def load_phase7_summary(paths):
    """phase7_summary.csv를 로드한다."""
    df = pd.read_csv(
        paths.phase7_dir / "phase7_summary.csv", encoding="utf-8-sig"
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_pattern1(paths, cid, seg):
    """패턴 1 결과 CSV를 로드한다."""
    fp = paths.pattern1_dir / f"{cid}_{seg}_pattern1.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_pattern2(paths, cid, seg):
    """패턴 2 Z-score 결과 CSV를 로드한다."""
    fp = paths.pattern2_dir / f"{cid}_{seg}_pattern2_zscore.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_pattern3(paths, cid, seg):
    """패턴 3 결과 CSV를 로드한다."""
    fp = paths.pattern3_dir / f"{cid}_{seg}_pattern3.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_robustness_csv(paths, cid, seg, window):
    """로버스트니스 CSV를 로드한다. window = 36 또는 60."""
    fp = paths.robustness_dir / f"{cid}_{seg}_robustness_W{window}.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_stat_timeseries(paths, cid, seg):
    """stat_timeseries CSV를 로드한다."""
    fp = paths.stat_timeseries_dir / f"{cid}_{seg}_stat_timeseries.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["period"] = pd.to_datetime(df["period"])
    return df


# ═══════════════════════════════════════════════════════════════════
# Phase 7-ML 데이터 로딩
# ═══════════════════════════════════════════════════════════════════
def load_ml_summary(paths):
    """phase7_ml_summary.csv를 로드한다."""
    return pd.read_csv(
        paths.ml_dir / "phase7_ml_summary.csv", encoding="utf-8-sig"
    )


def load_predictions(paths, cid, seg):
    """ML predictions CSV를 로드한다."""
    fp = paths.predictions_dir / f"{cid}_{seg}_ml_predictions.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_cross_val(paths, cid, seg):
    """cross_validation CSV를 로드한다."""
    fp = paths.cross_val_dir / f"{cid}_{seg}_cross_val.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_grades(paths, cid, seg):
    """confidence_grades CSV를 로드한다."""
    fp = paths.grades_dir / f"{cid}_{seg}_grades.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    return df


# ═══════════════════════════════════════════════════════════════════
# 기준선·구조 변화 로딩
# ═══════════════════════════════════════════════════════════════════
def load_baseline(paths, cid, seg):
    """Phase 4 baseline JSON을 로드한다."""
    fp = paths.baseline_dir / f"{cid}_{seg}_baseline.json"
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def load_breakpoints(paths, cid, seg):
    """Phase 6 breakpoints JSON을 로드한다."""
    fp = paths.breakpoints_dir / f"{cid}_{seg}_breakpoints.json"
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════
# Phase 1 데이터 로딩 (계절 더미 로버스트니스용)
# ═══════════════════════════════════════════════════════════════════
def load_stl_changes(paths, cid):
    """Phase 1 STL 기반 changes CSV를 로드한다."""
    fp = paths.phase1_changes_dir / f"{cid}_changes.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


def load_dummy_changes(paths, cid):
    """Phase 1 계절 더미 기반 changes CSV를 로드한다."""
    fp = paths.phase1_dummy_dir / f"{cid}_dummy_changes.csv"
    df = pd.read_csv(fp, encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df


# ═══════════════════════════════════════════════════════════════════
# 외부 충격 유틸리티
# ═══════════════════════════════════════════════════════════════════
def get_applicable_shocks(cid):
    """
    품목에 적용 가능한 외부 충격 목록을 반환한다.

    Args:
        cid: 품목 ID

    Returns:
        list of shock dicts
    """
    return [s for s in EXTERNAL_SHOCKS if cid in s["commodities"]]


def is_date_in_shock_window(date, shocks):
    """
    특정 날짜가 주어진 충격 목록의 윈도우 중 하나에 포함되는지 확인한다.

    Args:
        date: 확인할 날짜 (Timestamp)
        shocks: 충격 목록

    Returns:
        (bool, str or None) — (포함 여부, 해당 충격 ID)
    """
    if isinstance(date, str):
        date = pd.Timestamp(date)
    for shock in shocks:
        s_start = pd.Timestamp(shock["start"])
        s_end = pd.Timestamp(shock["end"])
        if s_start <= date <= s_end:
            return True, shock["id"]
    return False, None


def get_shock_window_dates(shock):
    """충격의 시작·종료 Timestamp를 반환한다."""
    return pd.Timestamp(shock["start"]), pd.Timestamp(shock["end"])


# ═══════════════════════════════════════════════════════════════════
# 구간 순회 유틸리티
# ═══════════════════════════════════════════════════════════════════
def iter_ml_segments(config):
    """ML 적용 구간(A, B) 품목×구간 조합을 순회한다."""
    for cid in config:
        for seg in config[cid]["segments"]:
            if seg in ML_SEGMENTS:
                yield cid, seg


def iter_all_segments(config):
    """전 품목×구간 조합을 순회한다."""
    for cid in config:
        for seg in config[cid]["segments"]:
            yield cid, seg


def iter_pattern2_segments(config):
    """패턴 2 적용 구간(A, B)을 순회한다."""
    return iter_ml_segments(config)


def iter_pattern3_segments(config):
    """패턴 3 적용 구간(B만)을 순회한다."""
    for cid in config:
        for seg in config[cid]["segments"]:
            if seg == "B":
                yield cid, seg


# ═══════════════════════════════════════════════════════════════════
# 집계 유틸리티
# ═══════════════════════════════════════════════════════════════════
def jaccard_similarity(set_a, set_b):
    """
    두 집합의 Jaccard 유사도를 산출한다.

    J(A, B) = |A ∩ B| / |A ∪ B|
    둘 다 비어 있으면 1.0 (동일).

    Args:
        set_a: set of dates (or any hashable)
        set_b: set of dates

    Returns:
        float (0.0 ~ 1.0)
    """
    set_a = set(set_a)
    set_b = set(set_b)
    if len(set_a) == 0 and len(set_b) == 0:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def stability_verdict(jaccard_value):
    """
    Jaccard 유사도 기반 안정성 판정.

    ≥ 0.7 → 'stable'
    0.4 ~ 0.7 → 'moderate'
    < 0.4 → 'sensitive'
    """
    if jaccard_value >= 0.7:
        return "stable"
    elif jaccard_value >= 0.4:
        return "moderate"
    else:
        return "sensitive"


def cohen_kappa(y1, y2):
    """
    두 이진 판정 간 Cohen's Kappa 계수를 산출한다.

    Args:
        y1, y2: bool 또는 0/1 array-like (동일 길이)

    Returns:
        float (Kappa 값, -1 ~ 1)
    """
    y1 = np.asarray(y1, dtype=bool)
    y2 = np.asarray(y2, dtype=bool)
    n = len(y1)
    if n == 0:
        return np.nan

    # 관찰 일치율
    agree = np.sum(y1 == y2)
    p_o = agree / n

    # 기대 일치율
    p1 = np.sum(y1) / n
    p2 = np.sum(y2) / n
    p_e = p1 * p2 + (1 - p1) * (1 - p2)

    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


# ═══════════════════════════════════════════════════════════════════
# 출력 디렉토리 생성
# ═══════════════════════════════════════════════════════════════════
def ensure_phase8_dirs(output_dir):
    """Phase 8 출력 디렉토리 구조를 생성한다."""
    output_dir = Path(output_dir)
    dirs = [
        "summary",
        "robustness",
        "synchrony",
    ]
    for d in dirs:
        (output_dir / d).mkdir(parents=True, exist_ok=True)
    return output_dir


# ═══════════════════════════════════════════════════════════════════
# 로깅
# ═══════════════════════════════════════════════════════════════════
def log8(msg):
    """Phase 8 로그 출력."""
    print(f"[Phase8] {msg}")
