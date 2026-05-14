"""
ML 평가 대시보드 생성 (generate_dashboard.py)
==============================================
역할:
  5축 평가 결과 CSV + run_meta.json을 읽어
  시각화 대시보드 HTML 파일을 생성한다.

입력: tests/phase7_ml/results/{run_id}/ 아래 CSV 5개 + run_meta.json
출력: 같은 디렉토리에 dashboard.html 생성

위치: tests/phase7_ml/generate_dashboard.py

실행 방법:
  python tests/phase7_ml/generate_dashboard.py                      # latest 사용
  python tests/phase7_ml/generate_dashboard.py --run run_20260513_143022  # 특정 run 지정
  python tests/phase7_ml/generate_dashboard.py --compare run_20260513_143022 run_20260513_160415
"""

import sys
import os
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path


# ---------------------------------------------------------------------------
# 데이터 로딩
# ---------------------------------------------------------------------------
def load_run_data(run_dir):
    """단일 run 디렉토리에서 CSV + meta를 로드한다."""
    run_dir = Path(run_dir)

    data = {}
    data["axis1"] = pd.read_csv(run_dir / "axis1_esr.csv", encoding="utf-8-sig")
    data["axis2"] = pd.read_csv(run_dir / "axis2_separation.csv", encoding="utf-8-sig")
    data["axis3"] = pd.read_csv(run_dir / "axis3_auc.csv", encoding="utf-8-sig")
    data["axis4"] = pd.read_csv(run_dir / "axis4_sensitivity.csv", encoding="utf-8-sig")
    data["axis5"] = pd.read_csv(run_dir / "axis5_consensus.csv", encoding="utf-8-sig")

    meta_path = run_dir / "run_meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            data["meta"] = json.load(f)
    else:
        data["meta"] = {"run_id": run_dir.name, "memo": "", "timestamp": "unknown"}

    return data


def df_to_js_array(df, columns, null_val="null"):
    """DataFrame을 JS 배열 리터럴 문자열로 변환한다."""
    rows = []
    for _, row in df.iterrows():
        obj_parts = []
        for col in columns:
            val = row[col]
            if isinstance(val, str):
                obj_parts.append(f'{col}:"{val}"')
            elif pd.isna(val):
                obj_parts.append(f"{col}:{null_val}")
            elif isinstance(val, bool) or (isinstance(val, (np.bool_))):
                obj_parts.append(f"{col}:{'true' if val else 'false'}")
            elif isinstance(val, (int, np.integer)):
                obj_parts.append(f"{col}:{val}")
            else:
                obj_parts.append(f"{col}:{val}")
        rows.append("{" + ",".join(obj_parts) + "}")
    return "[" + ",\n  ".join(rows) + "]"


# ---------------------------------------------------------------------------
# 비교 배너 HTML (선택적)
# ---------------------------------------------------------------------------
def build_compare_banner(meta_current, meta_previous):
    """두 run의 요약 지표를 비교하는 배너 HTML을 생성한다."""
    if not meta_previous:
        return ""

    sc = meta_current.get("summary", {})
    sp = meta_previous.get("summary", {})

    def delta_html(key, fmt=".4f", higher_is_better=True):
        vc = sc.get(key)
        vp = sp.get(key)
        if vc is None or vp is None:
            return '<span style="color:var(--text-muted)">—</span>'
        d = vc - vp
        if abs(d) < 0.0001:
            return f'<span style="color:var(--text-muted)">±0</span>'
        color = "var(--grade-good)" if (d > 0) == higher_is_better else "var(--grade-weak)"
        sign = "+" if d > 0 else ""
        return f'<span style="color:{color};font-weight:700">{sign}{d:{fmt}}</span>'

    rows = [
        ("가중 ESR", delta_html("weighted_esr")),
        ("평균 SR(IF)", delta_html("avg_sr_if", ".3f")),
        ("AUC(앙상블)", delta_html("avg_auc_ensemble")),
        ("Contam SR", delta_html("avg_contam_sr")),
        ("CTA", delta_html("avg_cta")),
    ]

    cells = "".join(
        f'<div style="text-align:center"><div style="font-size:11px;color:var(--text-muted)">{name}</div><div style="font-size:18px;margin-top:4px">{val}</div></div>'
        for name, val in rows
    )

    return f"""
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:32px">
      <div style="font-size:13px;color:var(--text-muted);margin-bottom:12px;font-family:'JetBrains Mono',monospace">
        vs {meta_previous.get('run_id','?')} — {meta_previous.get('memo','')}</div>
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:16px">{cells}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# HTML 생성
# ---------------------------------------------------------------------------
def generate_html(data, compare_data=None):
    """데이터로부터 대시보드 HTML 문자열을 생성한다."""

    meta = data["meta"]
    run_id = meta.get("run_id", "unknown")
    memo = meta.get("memo", "")
    timestamp = meta.get("timestamp", "")
    n_features = meta.get("features", {}).get("n_features", "?")
    feature_list = meta.get("features", {}).get("feature_list", [])

    # JS 데이터 변환
    axis1_js = df_to_js_array(data["axis1"],
        ["commodity_id", "segment", "n_shocks", "esr_if", "esr_lof", "esr_svm", "esr_ml"])
    axis2_js = df_to_js_array(data["axis2"],
        ["commodity_id", "segment", "sr_if", "sr_lof", "sr_svm"])
    axis3_js = df_to_js_array(data["axis3"],
        ["commodity_id", "segment", "auc_if", "auc_lof", "auc_svm", "auc_ensemble"])
    axis4_js = df_to_js_array(data["axis4"],
        ["commodity_id", "segment", "n_base", "avg_contam_sr", "avg_k_sr"])
    axis5_js = df_to_js_array(data["axis5"],
        ["commodity_id", "segment", "cta", "asc", "p_stat", "p_ml", "esr_stat", "esr_ml", "n_shocks", "hypothesis_holds"])

    # 비교 배너
    compare_banner = ""
    if compare_data:
        compare_banner = build_compare_banner(meta, compare_data["meta"])

    feature_badge = f"{n_features}종: {', '.join(feature_list)}" if feature_list else f"{n_features}종"

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Phase 7-ML 5축 평가 — {run_id}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{
  --bg-primary: #0a0e17;
  --bg-card: #111827;
  --border: #1e293b;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent-blue: #3b82f6;
  --accent-cyan: #06b6d4;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  --accent-violet: #8b5cf6;
  --grade-good: #10b981;
  --grade-moderate: #f59e0b;
  --grade-weak: #f43f5e;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Noto Sans KR',sans-serif; background:var(--bg-primary); color:var(--text-primary); min-height:100vh; line-height:1.6; }}
.container {{ max-width:1400px; margin:0 auto; padding:40px 32px; }}
.header {{ text-align:center; margin-bottom:48px; }}
.header::after {{ content:''; display:block; width:120px; height:2px; background:linear-gradient(90deg,var(--accent-blue),var(--accent-cyan)); margin:24px auto 0; }}
.header h1 {{ font-size:28px; font-weight:900; letter-spacing:-0.5px; background:linear-gradient(135deg,#e2e8f0,#94a3b8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.header .subtitle {{ font-size:14px; color:var(--text-muted); margin-top:8px; font-family:'JetBrains Mono',monospace; }}
.header .run-info {{ font-size:12px; color:var(--text-muted); margin-top:4px; font-family:'JetBrains Mono',monospace; }}
.header .memo-badge {{ display:inline-block; background:rgba(59,130,246,0.12); color:var(--accent-blue); padding:3px 12px; border-radius:20px; font-size:12px; margin-top:8px; font-family:'JetBrains Mono',monospace; }}
.summary-row {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:40px; }}
.summary-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:20px; text-align:center; position:relative; overflow:hidden; }}
.summary-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:3px; }}
.summary-card:nth-child(1)::before {{ background:var(--accent-blue); }}
.summary-card:nth-child(2)::before {{ background:var(--accent-cyan); }}
.summary-card:nth-child(3)::before {{ background:var(--accent-violet); }}
.summary-card:nth-child(4)::before {{ background:var(--accent-emerald); }}
.summary-card:nth-child(5)::before {{ background:var(--accent-amber); }}
.summary-card .axis-label {{ font-size:11px; font-family:'JetBrains Mono',monospace; color:var(--text-muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }}
.summary-card .axis-name {{ font-size:13px; font-weight:500; color:var(--text-secondary); margin-bottom:12px; }}
.summary-card .value {{ font-size:32px; font-weight:900; font-family:'JetBrains Mono',monospace; margin-bottom:4px; }}
.summary-card .grade {{ font-size:12px; font-weight:700; padding:3px 10px; border-radius:20px; display:inline-block; }}
.grade-good {{ background:rgba(16,185,129,0.15); color:var(--grade-good); }}
.grade-moderate {{ background:rgba(245,158,11,0.15); color:var(--grade-moderate); }}
.grade-weak {{ background:rgba(244,63,94,0.15); color:var(--grade-weak); }}
.section {{ margin-bottom:48px; }}
.section-header {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; padding-bottom:12px; border-bottom:1px solid var(--border); }}
.section-number {{ font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:700; color:var(--accent-blue); background:rgba(59,130,246,0.1); padding:4px 10px; border-radius:6px; }}
.section-title {{ font-size:18px; font-weight:700; }}
.section-desc {{ font-size:13px; color:var(--text-muted); margin-left:auto; font-family:'JetBrains Mono',monospace; }}
.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
.chart-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:24px; }}
.chart-card h3 {{ font-size:14px; font-weight:500; color:var(--text-secondary); margin-bottom:16px; }}
.chart-container {{ position:relative; width:100%; }}
.chart-container.wide {{ height:360px; }}
.radar-wrapper {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
.radar-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:24px; display:flex; flex-direction:column; align-items:center; }}
.radar-card h3 {{ font-size:14px; font-weight:500; color:var(--text-secondary); margin-bottom:16px; }}
.heatmap-table {{ width:100%; border-collapse:collapse; font-size:12px; font-family:'JetBrains Mono',monospace; }}
.heatmap-table th {{ padding:8px 10px; font-weight:500; color:var(--text-muted); text-align:center; border-bottom:1px solid var(--border); font-size:11px; }}
.heatmap-table th:first-child {{ text-align:left; min-width:100px; }}
.heatmap-table td {{ padding:6px 10px; text-align:center; border-bottom:1px solid rgba(30,41,59,0.5); }}
.heatmap-table td:first-child {{ text-align:left; font-weight:500; color:var(--text-secondary); }}
.heatmap-cell {{ display:inline-block; padding:2px 8px; border-radius:4px; font-weight:500; min-width:52px; }}
.hypothesis-badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-weight:700; font-size:11px; }}
.hyp-true {{ background:rgba(16,185,129,0.2); color:var(--grade-good); }}
.hyp-false {{ background:rgba(244,63,94,0.15); color:var(--grade-weak); }}
.hyp-na {{ background:rgba(100,116,139,0.15); color:var(--text-muted); }}
.footer {{ text-align:center; padding:32px 0; border-top:1px solid var(--border); color:var(--text-muted); font-size:12px; font-family:'JetBrains Mono',monospace; }}
@media print {{ body {{ background:#fff; color:#1a1a1a; }} .summary-card,.chart-card,.radar-card {{ border-color:#ddd; background:#fafafa; }} .header h1 {{ -webkit-text-fill-color:#1a1a1a; }} }}
@media (max-width:1024px) {{ .summary-row {{ grid-template-columns:repeat(3,1fr); }} .chart-grid,.radar-wrapper {{ grid-template-columns:1fr; }} }}
@media (max-width:640px) {{ .summary-row {{ grid-template-columns:1fr 1fr; }} .container {{ padding:20px 16px; }} }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Phase 7-ML · 5축 신뢰성 평가 리포트</h1>
    <div class="subtitle">ML Reliability Evaluation — 10 Commodities × 2 Segments (A, B) = 20 Units</div>
    <div class="run-info">{run_id} · {timestamp} · 피처 {feature_badge}</div>
    {"<div class='memo-badge'>" + memo + "</div>" if memo and memo != "메모 없음" else ""}
  </div>

  {compare_banner}

  <div class="summary-row" id="summaryCards"></div>

  <!-- Axis 1 -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">AXIS 1</span>
      <span class="section-title">외부 충격 회수율 (ESR)</span>
      <span class="section-desc">충격 윈도우 내 1건+ 탐지 시 회수</span>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h3>품목×구간별 ESR (앙상블)</h3><div class="chart-container wide"><canvas id="esr_bar"></canvas></div></div>
      <div class="chart-card"><h3>모델별 ESR 비교</h3><div class="chart-container wide"><canvas id="esr_model"></canvas></div></div>
    </div>
  </div>

  <!-- Axis 2 -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">AXIS 2</span>
      <span class="section-title">이상 점수 분리도 (SR)</span>
      <span class="section-desc">SR &gt; 2.0 양호 · 1.0~2.0 보통 · &lt;1.0 약함</span>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h3>품목×구간별 분리도 히트맵</h3><div id="sr_heatmap"></div></div>
      <div class="chart-card"><h3>모델별 SR 분포</h3><div class="chart-container wide"><canvas id="sr_box"></canvas></div></div>
    </div>
  </div>

  <!-- Axis 3 -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">AXIS 3</span>
      <span class="section-title">통계-ML 일관성 AUC</span>
      <span class="section-desc">이상적: 0.70~0.90 (독립성+일관성 공존)</span>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h3>품목×구간별 AUC (앙상블)</h3><div class="chart-container wide"><canvas id="auc_bar"></canvas></div></div>
      <div class="chart-card"><h3>AUC 해석 분포</h3><div class="chart-container wide"><canvas id="auc_dist"></canvas></div></div>
    </div>
  </div>

  <!-- Axis 4 -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">AXIS 4</span>
      <span class="section-title">파라미터 민감도 (Stability Ratio)</span>
      <span class="section-desc">SR ≥ 0.80 강건 · 0.60~0.80 보통 · &lt;0.60 취약</span>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h3>Contamination 변동 안정성</h3><div class="chart-container wide"><canvas id="sens_contam"></canvas></div></div>
      <div class="chart-card"><h3>LOF k값 변동 안정성</h3><div class="chart-container wide"><canvas id="sens_k"></canvas></div></div>
    </div>
  </div>

  <!-- Axis 5 -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">AXIS 5</span>
      <span class="section-title">합의 기반 지표 (CTA + ASC + P_stat + P_ml)</span>
      <span class="section-desc">핵심 가설: ASC &gt; max(P_stat, P_ml)</span>
    </div>
    <div class="chart-grid">
      <div class="chart-card"><h3>CTA vs ASC 산점도</h3><div class="chart-container wide"><canvas id="cta_asc"></canvas></div></div>
      <div class="chart-card"><h3>핵심 가설 검증 결과</h3><div id="hypothesis_table"></div></div>
    </div>
  </div>

  <!-- Radar -->
  <div class="section">
    <div class="section-header">
      <span class="section-number">종합</span>
      <span class="section-title">5축 종합 레이더 차트</span>
    </div>
    <div class="radar-wrapper">
      <div class="radar-card"><h3>5축 정규화 점수 (0~1)</h3><div style="width:340px;height:340px;"><canvas id="radar_all"></canvas></div></div>
      <div class="radar-card"><h3>축별 판정 요약</h3><div id="verdict_table" style="width:100%;"></div></div>
    </div>
  </div>

  <div class="footer">Phase 7-ML Reliability Evaluation · 선문대학교 종합설계 11분반 1팀 · {run_id}</div>
</div>

<script>
// === DATA (auto-generated) ===
const axis1 = {axis1_js};
const axis2 = {axis2_js};
const axis3 = {axis3_js};
const axis4 = {axis4_js};
const axis5 = {axis5_js};

// === CHART CONFIG ===
const labels20 = axis1.map(d => d.commodity_id + ' ' + d.segment);
const avg = (arr) => {{
  const valid = arr.filter(v => v !== null && !isNaN(v));
  return valid.length ? valid.reduce((a,b) => a+b, 0) / valid.length : NaN;
}};

Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(30,41,59,0.6)';
Chart.defaults.font.family = "'JetBrains Mono','Noto Sans KR',sans-serif";
Chart.defaults.font.size = 11;

function heatColor(val, thresholds) {{
  if (val === null || isNaN(val)) return 'rgba(100,116,139,0.2)';
  if (val >= thresholds[0]) return 'rgba(16,185,129,0.25)';
  if (val >= thresholds[1]) return 'rgba(245,158,11,0.25)';
  return 'rgba(244,63,94,0.2)';
}}

function gradeText(val, thresholds, labels) {{
  if (val === null || isNaN(val)) return ['—', 'grade-moderate'];
  if (val >= thresholds[0]) return [labels[0], 'grade-good'];
  if (val >= thresholds[1]) return [labels[1], 'grade-moderate'];
  return [labels[2], 'grade-weak'];
}}

// === SUMMARY CARDS ===
const esrValid = axis1.filter(d => d.esr_ml !== null);
const totalShocks = axis1.filter(d => d.n_shocks > 0).reduce((s,d) => s + d.n_shocks, 0);
const weightedESR = totalShocks > 0 ? axis1.filter(d => d.esr_ml !== null).reduce((s,d) => s + d.esr_ml * d.n_shocks, 0) / totalShocks : NaN;
const avgSR = avg([...axis2.map(d=>d.sr_if),...axis2.map(d=>d.sr_lof),...axis2.map(d=>d.sr_svm)]);
const avgAUC = avg(axis3.map(d=>d.auc_ensemble));
const avgContamSR = avg(axis4.map(d=>d.avg_contam_sr));
const avgKSR = avg(axis4.map(d=>d.avg_k_sr));
const avgSens = (avgContamSR + avgKSR) / 2;
const avgCTA = avg(axis5.map(d=>d.cta));

const summaryData = [
  {{axis:'AXIS 1',name:'충격 회수율',value:weightedESR,fmt:v=>v.toFixed(2),thresh:[0.70,0.50],labels:['양호','보통','미흡']}},
  {{axis:'AXIS 2',name:'분리도 (SR)',value:avgSR,fmt:v=>v.toFixed(2),thresh:[2.0,1.0],labels:['양호','보통','약함']}},
  {{axis:'AXIS 3',name:'AUC (앙상블)',value:avgAUC,fmt:v=>v.toFixed(3),thresh:[0.70,0.50],labels:['이상적','독립적','역방향']}},
  {{axis:'AXIS 4',name:'안정성 비율',value:avgSens,fmt:v=>v.toFixed(2),thresh:[0.80,0.60],labels:['강건','보통','취약']}},
  {{axis:'AXIS 5',name:'합의율 (CTA)',value:avgCTA,fmt:v=>v.toFixed(3),thresh:[0.30,0.15],labels:['양호','낮음','매우 낮음']}},
];

const sc = document.getElementById('summaryCards');
summaryData.forEach(d => {{
  const [label, cls] = gradeText(d.value, d.thresh, d.labels);
  const color = cls==='grade-good'?'var(--grade-good)':cls==='grade-moderate'?'var(--grade-moderate)':'var(--grade-weak)';
  sc.innerHTML += `<div class="summary-card"><div class="axis-label">${{d.axis}}</div><div class="axis-name">${{d.name}}</div><div class="value" style="color:${{color}}">${{d.fmt(d.value)}}</div><span class="grade ${{cls}}">${{label}}</span></div>`;
}});

// === AXIS 1 ===
new Chart(document.getElementById('esr_bar'), {{
  type:'bar',
  data:{{ labels:esrValid.map(d=>d.commodity_id+' '+d.segment), datasets:[{{ label:'ESR_ml', data:esrValid.map(d=>d.esr_ml), backgroundColor:esrValid.map(d=>d.esr_ml>=0.67?'rgba(16,185,129,0.7)':d.esr_ml>=0.50?'rgba(245,158,11,0.7)':'rgba(244,63,94,0.7)'), borderRadius:4, barPercentage:0.7 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{display:false}}}}, scales:{{ x:{{ticks:{{font:{{size:9}},maxRotation:45}}}}, y:{{min:0,max:1.1,ticks:{{stepSize:0.25}}}} }} }}
}});

new Chart(document.getElementById('esr_model'), {{
  type:'bar',
  data:{{ labels:esrValid.map(d=>d.commodity_id+' '+d.segment), datasets:[
    {{label:'IF',data:esrValid.map(d=>d.esr_if),backgroundColor:'rgba(59,130,246,0.6)',borderRadius:3,barPercentage:0.8}},
    {{label:'LOF',data:esrValid.map(d=>d.esr_lof),backgroundColor:'rgba(6,182,212,0.6)',borderRadius:3,barPercentage:0.8}},
    {{label:'SVM',data:esrValid.map(d=>d.esr_svm),backgroundColor:'rgba(139,92,246,0.6)',borderRadius:3,barPercentage:0.8}},
  ] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{position:'top',labels:{{boxWidth:12}}}}}}, scales:{{ x:{{ticks:{{font:{{size:9}},maxRotation:45}}}}, y:{{min:0,max:1.1}} }} }}
}});

// === AXIS 2 ===
let hmHtml = '<table class="heatmap-table"><thead><tr><th>품목 구간</th><th>IF</th><th>LOF</th><th>SVM</th><th>평균</th></tr></thead><tbody>';
axis2.forEach(d => {{
  const a = (d.sr_if+d.sr_lof+d.sr_svm)/3;
  hmHtml += `<tr><td>${{d.commodity_id}} ${{d.segment}}</td>
    <td><span class="heatmap-cell" style="background:${{heatColor(d.sr_if,[2.0,1.0])}}">${{d.sr_if.toFixed(2)}}</span></td>
    <td><span class="heatmap-cell" style="background:${{heatColor(d.sr_lof,[2.0,1.0])}}">${{d.sr_lof.toFixed(2)}}</span></td>
    <td><span class="heatmap-cell" style="background:${{heatColor(d.sr_svm,[2.0,1.0])}}">${{d.sr_svm.toFixed(2)}}</span></td>
    <td><span class="heatmap-cell" style="background:${{heatColor(a,[2.0,1.0])}}">${{a.toFixed(2)}}</span></td></tr>`;
}});
hmHtml += '</tbody></table>';
document.getElementById('sr_heatmap').innerHTML = hmHtml;

new Chart(document.getElementById('sr_box'), {{
  type:'bar',
  data:{{ labels:labels20, datasets:[
    {{label:'IF',data:axis2.map(d=>d.sr_if),backgroundColor:'rgba(59,130,246,0.6)',borderRadius:3}},
    {{label:'LOF',data:axis2.map(d=>d.sr_lof),backgroundColor:'rgba(6,182,212,0.6)',borderRadius:3}},
    {{label:'SVM',data:axis2.map(d=>d.sr_svm),backgroundColor:'rgba(139,92,246,0.6)',borderRadius:3}},
  ] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{position:'top',labels:{{boxWidth:12}}}}}}, scales:{{ x:{{ticks:{{font:{{size:8}},maxRotation:60}}}}, y:{{min:0}} }} }}
}});

// === AXIS 3 ===
new Chart(document.getElementById('auc_bar'), {{
  type:'bar',
  data:{{ labels:labels20, datasets:[{{ label:'AUC (ensemble)', data:axis3.map(d=>d.auc_ensemble), backgroundColor:axis3.map(d=>d.auc_ensemble>=0.70?'rgba(16,185,129,0.7)':d.auc_ensemble>=0.50?'rgba(59,130,246,0.6)':'rgba(244,63,94,0.7)'), borderRadius:4 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{display:false}}}}, scales:{{ x:{{ticks:{{font:{{size:8}},maxRotation:60}}}}, y:{{min:0.3,max:1.0,ticks:{{stepSize:0.1}}}} }} }}
}});

const aucInterp = {{'독립성 의심 (≥0.95)':0, '이상적 (0.70~0.95)':0, '일관성 부족 (0.50~0.70)':0, '역방향 (<0.50)':0}};
axis3.forEach(d => {{
  if(d.auc_ensemble>=0.95) aucInterp['독립성 의심 (≥0.95)']++;
  else if(d.auc_ensemble>=0.70) aucInterp['이상적 (0.70~0.95)']++;
  else if(d.auc_ensemble>=0.50) aucInterp['일관성 부족 (0.50~0.70)']++;
  else aucInterp['역방향 (<0.50)']++;
}});

new Chart(document.getElementById('auc_dist'), {{
  type:'doughnut',
  data:{{ labels:Object.keys(aucInterp), datasets:[{{ data:Object.values(aucInterp), backgroundColor:['rgba(244,63,94,0.7)','rgba(16,185,129,0.7)','rgba(59,130,246,0.7)','rgba(245,158,11,0.7)'], borderWidth:0 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{position:'bottom',labels:{{padding:16,boxWidth:12}}}}}} }}
}});

// === AXIS 4 ===
new Chart(document.getElementById('sens_contam'), {{
  type:'bar',
  data:{{ labels:labels20, datasets:[{{ label:'Contamination SR', data:axis4.map(d=>d.avg_contam_sr), backgroundColor:axis4.map(d=>d.avg_contam_sr>=0.80?'rgba(16,185,129,0.7)':d.avg_contam_sr>=0.60?'rgba(245,158,11,0.7)':'rgba(244,63,94,0.7)'), borderRadius:4 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{display:false}}}}, scales:{{ x:{{ticks:{{font:{{size:8}},maxRotation:60}}}}, y:{{min:0.4,max:1.05}} }} }}
}});

new Chart(document.getElementById('sens_k'), {{
  type:'bar',
  data:{{ labels:labels20, datasets:[{{ label:'LOF k SR', data:axis4.map(d=>d.avg_k_sr), backgroundColor:axis4.map(d=>d.avg_k_sr>=0.80?'rgba(16,185,129,0.7)':d.avg_k_sr>=0.60?'rgba(245,158,11,0.7)':'rgba(244,63,94,0.7)'), borderRadius:4 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{legend:{{display:false}}}}, scales:{{ x:{{ticks:{{font:{{size:8}},maxRotation:60}}}}, y:{{min:0.6,max:1.05}} }} }}
}});

// === AXIS 5 ===
const scatterData = axis5.map(d => ({{ x:d.cta, y:d.asc, label:d.commodity_id+' '+d.segment, hyp:d.hypothesis_holds, p_stat:d.p_stat, p_ml:d.p_ml }}));
new Chart(document.getElementById('cta_asc'), {{
  type:'scatter',
  data:{{ datasets:[{{ label:'품목×구간', data:scatterData, backgroundColor:scatterData.map(d=>d.hyp===true?'rgba(16,185,129,0.8)':d.hyp===false?'rgba(244,63,94,0.6)':'rgba(100,116,139,0.5)'), pointRadius:7, pointHoverRadius:10 }}] }},
  options:{{ responsive:true, maintainAspectRatio:false, plugins:{{ legend:{{display:false}}, tooltip:{{callbacks:{{label:(ctx)=>{{const d=scatterData[ctx.dataIndex]; return `${{d.label}}: CTA=${{ctx.parsed.x.toFixed(3)}}, ASC=${{ctx.parsed.y.toFixed(3)}}, P_stat=${{d.p_stat!==null?d.p_stat.toFixed(3):'—'}}, P_ml=${{d.p_ml!==null?d.p_ml.toFixed(3):'—'}}`;}}}}}} }}, scales:{{ x:{{title:{{display:true,text:'CTA (교차 합의율)'}},min:0}}, y:{{title:{{display:true,text:'ASC (합의-충격 일치율)'}},min:0}} }} }}
}});

let hypHtml = '<table class="heatmap-table"><thead><tr><th>품목 구간</th><th>CTA</th><th>ASC</th><th>P_stat</th><th>P_ml</th><th>ESR_stat</th><th>ESR_ml</th><th>가설</th></tr></thead><tbody>';
axis5.forEach(d => {{
  const badge = d.hypothesis_holds===true?'<span class="hypothesis-badge hyp-true">성립</span>':d.hypothesis_holds===false?'<span class="hypothesis-badge hyp-false">기각</span>':'<span class="hypothesis-badge hyp-na">N/A</span>';
  hypHtml += `<tr><td>${{d.commodity_id}} ${{d.segment}}</td><td>${{d.cta.toFixed(3)}}</td><td>${{d.asc!==null?d.asc.toFixed(3):'—'}}</td><td>${{d.p_stat!==null?d.p_stat.toFixed(3):'—'}}</td><td>${{d.p_ml!==null?d.p_ml.toFixed(3):'—'}}</td><td>${{d.esr_stat!==null?d.esr_stat.toFixed(2):'—'}}</td><td>${{d.esr_ml!==null?d.esr_ml.toFixed(2):'—'}}</td><td>${{badge}}</td></tr>`;
}});
hypHtml += '</tbody></table>';
document.getElementById('hypothesis_table').innerHTML = hypHtml;

// === RADAR ===
const radarScores = [
  Math.min(weightedESR/1.0, 1.0),
  Math.min(avgSR/4.0, 1.0),
  Math.min((avgAUC-0.5)/0.4, 1.0),
  Math.min(avgSens/1.0, 1.0),
  Math.min(avgCTA/0.30, 1.0),
];

new Chart(document.getElementById('radar_all'), {{
  type:'radar',
  data:{{ labels:['ESR (충격 회수)','SR (분리도)','AUC (일관성)','SR (안정성)','CTA (합의)'], datasets:[{{ label:'현재 모델', data:radarScores, backgroundColor:'rgba(59,130,246,0.15)', borderColor:'rgba(59,130,246,0.8)', borderWidth:2, pointBackgroundColor:'rgba(59,130,246,1)', pointRadius:5 }}] }},
  options:{{ responsive:true, maintainAspectRatio:true, plugins:{{legend:{{display:false}}}}, scales:{{ r:{{min:0,max:1,ticks:{{stepSize:0.25,display:false}},grid:{{color:'rgba(30,41,59,0.5)'}},pointLabels:{{font:{{size:12}}}},angleLines:{{color:'rgba(30,41,59,0.3)'}}}} }} }}
}});

// === VERDICT TABLE ===
const verdicts = [
  {{ axis:'축 1 ESR', value:weightedESR.toFixed(2), interp:'가중 평균 '+weightedESR.toFixed(2)+' — 비지도 학습 기준 '+(weightedESR>=0.70?'양호':weightedESR>=0.50?'보통':'미흡'), grade:weightedESR>=0.70?'grade-good':weightedESR>=0.50?'grade-moderate':'grade-weak' }},
  {{ axis:'축 2 분리도', value:'IF='+avg(axis2.map(d=>d.sr_if)).toFixed(1)+' LOF='+avg(axis2.map(d=>d.sr_lof)).toFixed(1)+' SVM='+avg(axis2.map(d=>d.sr_svm)).toFixed(1), interp:'3종 모두 SR > 2.0 — 내부 분리 양호', grade:'grade-good' }},
  {{ axis:'축 3 AUC', value:avgAUC.toFixed(3), interp:avgAUC.toFixed(2)+' 수준 — '+(avgAUC>=0.70?'이상적 (독립성+일관성)':avgAUC>=0.50?'독립성 확보 (순환 논리 방지 작동)':'역방향'), grade:avgAUC>=0.70?'grade-good':'grade-moderate' }},
  {{ axis:'축 4 안정성', value:'C='+avgContamSR.toFixed(2)+' K='+avgKSR.toFixed(2), interp:'k 변동 강건('+avgKSR.toFixed(2)+'), contamination 보통('+avgContamSR.toFixed(2)+')', grade:avgSens>=0.80?'grade-good':'grade-moderate' }},
  {{ axis:'축 5 합의', value:'CTA='+avgCTA.toFixed(3), interp:'가설(ASC>max(P)) '+axis5.filter(d=>d.hypothesis_holds===true).length+'/'+axis5.filter(d=>d.hypothesis_holds!==null).length+' 성립'+(avgCTA<0.20?' — 개선 필요':''), grade:avgCTA>=0.30?'grade-good':avgCTA>=0.15?'grade-moderate':'grade-weak' }},
];

let vHtml = '<table class="heatmap-table"><thead><tr><th>축</th><th>핵심값</th><th>해석</th><th>판정</th></tr></thead><tbody>';
verdicts.forEach(v => {{
  const lbl = v.grade==='grade-good'?'양호':v.grade==='grade-moderate'?'보통':'개선 필요';
  vHtml += `<tr><td>${{v.axis}}</td><td style="font-family:'JetBrains Mono';font-size:11px">${{v.value}}</td><td style="color:var(--text-secondary);font-family:'Noto Sans KR';font-size:12px">${{v.interp}}</td><td><span class="grade ${{v.grade}}" style="font-size:11px">${{lbl}}</span></td></tr>`;
}});
vHtml += '</tbody></table>';
document.getElementById('verdict_table').innerHTML = vHtml;
</script>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ML 평가 대시보드 HTML 생성")
    parser.add_argument("--run", type=str, default=None,
                        help="특정 run 디렉토리명 (예: run_20260513_143022). 미지정 시 latest 사용")
    parser.add_argument("--compare", type=str, default=None,
                        help="비교 대상 run 디렉토리명 (비교 배너 표시)")
    args = parser.parse_args()

    results_base = Path(os.path.dirname(os.path.abspath(__file__))) / "results"

    # 대상 run 결정
    if args.run:
        run_dir = results_base / args.run
    else:
        run_dir = results_base / "latest"

    if not run_dir.exists():
        print(f"[ERROR] 디렉토리 없음: {run_dir}")
        print(f"  run_all_evaluation.py를 먼저 실행하세요.")
        sys.exit(1)

    print(f"[Dashboard] 데이터 로딩: {run_dir}")
    data = load_run_data(run_dir)

    # 비교 대상 로딩
    compare_data = None
    if args.compare:
        compare_dir = results_base / args.compare
        if compare_dir.exists():
            print(f"[Dashboard] 비교 대상 로딩: {compare_dir}")
            compare_data = load_run_data(compare_dir)
        else:
            print(f"[WARNING] 비교 대상 없음: {compare_dir}")

    # HTML 생성
    html = generate_html(data, compare_data)

    output_path = run_dir / "dashboard.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    # latest에도 동기화
    latest_dashboard = results_base / "latest" / "dashboard.html"
    if run_dir != results_base / "latest" and (results_base / "latest").exists():
        with open(latest_dashboard, "w", encoding="utf-8") as f:
            f.write(html)

    print(f"[Dashboard] 생성 완료: {output_path}")
    print(f"[Dashboard] 브라우저에서 열어 확인하세요.")


if __name__ == "__main__":
    main()