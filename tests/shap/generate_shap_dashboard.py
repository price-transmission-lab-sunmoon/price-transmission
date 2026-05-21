"""
SHAP 대시보드 생성 (generate_shap_dashboard.py) v2
===================================================
역할:
  3종 모델(IF/LOF/SVM)의 SHAP 결과를 읽어
  Bar Plot + Heatmap + Beeswarm 시각화 대시보드 HTML + PNG를 생성한다.

시각화 구성:
  Section 1: Global Feature Importance Bar Plot (3종 모델 비교)
  Section 2: Per-Unit Top Feature Table
  Section 3: SHAP Heatmap (시점 × 피처, percentile 클리핑 + 파랑-흰-빨강)
  Section 4: Beeswarm Plots (matplotlib PNG, 모델별)

출력:
  - tests/shap/results/대시보드_{YYYYMMDD_HHMM}/dashboard_shap.html
  - tests/shap/results/대시보드_{YYYYMMDD_HHMM}/beeswarm_IF.png
  - tests/shap/results/대시보드_{YYYYMMDD_HHMM}/beeswarm_LOF.png
  - tests/shap/results/대시보드_{YYYYMMDD_HHMM}/beeswarm_SVM.png

실행:
  python tests/shap/generate_shap_dashboard.py --if-dir 20260519_1910_IF --lof-dir 20260519_2033_LOF --svm-dir 20260519_2041_SVM
"""

import sys
import os
import json
import argparse
import base64
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pathlib import Path
from datetime import datetime


FEATURE_COLUMNS = [
    "transmission_rate", "upstream_pct", "downstream_pct",
    "ect_or_spread", "exchange_rate_pct", "intl_price_usd_pct",
]

FEATURE_LABELS = {
    "transmission_rate": "Transmission Rate",
    "upstream_pct": "Upstream Price Change (%)",
    "downstream_pct": "Downstream Price Change (%)",
    "ect_or_spread": "ECT / Log Spread",
    "exchange_rate_pct": "Exchange Rate Change (%)",
    "intl_price_usd_pct": "Intl. Price USD Change (%)",
}

FEATURE_LABELS_SHORT = {
    "transmission_rate": "Transmission Rate",
    "upstream_pct": "Upstream %",
    "downstream_pct": "Downstream %",
    "ect_or_spread": "ECT/Spread",
    "exchange_rate_pct": "Exchange Rate %",
    "intl_price_usd_pct": "Intl. Price USD %",
}


def load_model_data(results_base, dir_name):
    d = Path(results_base) / dir_name
    if not d.exists():
        raise FileNotFoundError(f"디렉토리 없음: {d}")

    summary = pd.read_csv(d / "shap_summary.csv", encoding="utf-8-sig")
    meta_path = d / "run_meta.json"
    meta = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    shap_all = []
    for csv_file in sorted(d.glob("*_shap.csv")):
        if csv_file.name == "shap_summary.csv":
            continue
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
        shap_all.append(df)

    shap_detail = pd.concat(shap_all, ignore_index=True) if shap_all else pd.DataFrame()
    return summary, meta, shap_detail


# ---------------------------------------------------------------------------
# Beeswarm PNG 생성
# ---------------------------------------------------------------------------
def generate_beeswarm_png(shap_detail, features_dir, model_name, output_path):
    """
    전체 유닛의 SHAP 값을 합쳐서 Beeswarm plot PNG를 생성한다.
    X축: SHAP value, Y축: 피처 (중요도 순 정렬)
    점 색상: 피처의 원시 값 (높으면 빨강, 낮으면 파랑)
    """
    if shap_detail.empty:
        return

    shap_vals = shap_detail[FEATURE_COLUMNS].values  # (N, 6)

    # 원시 피처값 로드 (색상용)
    raw_vals_all = []
    for (cid, seg), group in shap_detail.groupby(["commodity_id", "segment"]):
        feat_path = Path(features_dir) / f"{cid}_{seg}_features.csv"
        if feat_path.exists():
            feat_df = pd.read_csv(feat_path, encoding="utf-8-sig")
            feat_df["date"] = pd.to_datetime(feat_df["date"])
            group_dates = pd.to_datetime(group["date"])
            merged = pd.merge(
                pd.DataFrame({"date": group_dates}),
                feat_df[["date"] + FEATURE_COLUMNS],
                on="date", how="left"
            )
            raw_vals_all.append(merged[FEATURE_COLUMNS].values)
        else:
            raw_vals_all.append(np.full((len(group), len(FEATURE_COLUMNS)), np.nan))

    raw_vals = np.vstack(raw_vals_all)  # (N, 6)

    # 피처 중요도 순 정렬 (mean |SHAP| 내림차순)
    mean_abs = np.abs(shap_vals).mean(axis=0)
    order = np.argsort(mean_abs)  # 오름차순 (하단=가장 덜 중요, 상단=가장 중요)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0a0e17")
    ax.set_facecolor("#0a0e17")

    for i, feat_idx in enumerate(order):
        sv = shap_vals[:, feat_idx]
        rv = raw_vals[:, feat_idx]

        # raw 값 정규화 (0~1) — 색상용
        rv_min, rv_max = np.nanmin(rv), np.nanmax(rv)
        if rv_max - rv_min > 0:
            rv_norm = (rv - rv_min) / (rv_max - rv_min)
        else:
            rv_norm = np.full_like(rv, 0.5)
        rv_norm = np.clip(np.nan_to_num(rv_norm, nan=0.5), 0, 1)

        # jitter (겹침 방지)
        jitter = np.random.RandomState(42).uniform(-0.3, 0.3, len(sv))

        # 색상: 파랑(low) → 빨강(high)
        cmap = plt.cm.coolwarm
        colors = cmap(rv_norm)

        ax.scatter(sv, np.full_like(sv, i) + jitter, c=colors, s=3, alpha=0.6, linewidths=0)

    # Y축 라벨
    y_labels = [FEATURE_LABELS_SHORT[FEATURE_COLUMNS[idx]] for idx in order]
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(y_labels, fontsize=10, color="#e2e8f0")

    ax.axvline(0, color="#64748b", linewidth=0.5, linestyle="--")
    ax.set_xlabel("SHAP Value (impact on anomaly score)", fontsize=11, color="#94a3b8")
    ax.set_title(f"Beeswarm Plot — {model_name}", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)

    ax.tick_params(axis="x", colors="#94a3b8", labelsize=9)
    ax.tick_params(axis="y", colors="#e2e8f0")
    for spine in ax.spines.values():
        spine.set_color("#1e293b")

    # 컬러바
    sm = plt.cm.ScalarMappable(cmap=plt.cm.coolwarm, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.02, pad=0.04)
    cbar.set_label("Feature Value (normalized)", fontsize=9, color="#94a3b8")
    cbar.ax.tick_params(labelsize=8, colors="#94a3b8")
    cbar.outline.set_edgecolor("#1e293b")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor="#0a0e17", bbox_inches="tight")
    plt.close()
    print(f"  Beeswarm 저장: {output_path}")


# ---------------------------------------------------------------------------
# HTML 생성
# ---------------------------------------------------------------------------
def build_heatmap_data_js(shap_detail, predictions_dir=None):
    if shap_detail.empty:
        return "{}"
    units = shap_detail.groupby(["commodity_id", "segment"])
    heatmap_data = {}
    for (cid, seg), group in units:
        key = f"{cid}_{seg}"
        dates = pd.to_datetime(group["date"]).dt.strftime("%Y-%m").tolist()
        features_data = {}
        for col in FEATURE_COLUMNS:
            features_data[col] = [round(v, 6) for v in group[col].values.tolist()]

        # ml_detected 인덱스 (이상치 필터용)
        anomaly_indices = []
        if predictions_dir:
            pred_path = Path(predictions_dir) / f"{cid}_{seg}_ml_predictions.csv"
            if pred_path.exists():
                pred_df = pd.read_csv(pred_path, encoding="utf-8-sig")
                pred_df["date"] = pd.to_datetime(pred_df["date"]).dt.strftime("%Y-%m")
                group_dates_str = pd.to_datetime(group["date"]).dt.strftime("%Y-%m").tolist()
                detected_dates = set(pred_df[pred_df["ml_detected"] == True]["date"].tolist())
                anomaly_indices = [i for i, d in enumerate(group_dates_str) if d in detected_dates]

        heatmap_data[key] = {"dates": dates, "features": features_data, "anomaly": anomaly_indices}
    return json.dumps(heatmap_data)


def generate_html(if_summary, lof_summary, svm_summary,
                  if_meta, lof_meta, svm_meta,
                  if_detail, lof_detail, svm_detail,
                  if_dir, lof_dir, svm_dir,
                  beeswarm_exists, predictions_dir=None):

    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_global_importance(summary):
        return [round(summary[f"mean_abs_{c}"].mean(), 6) for c in FEATURE_COLUMNS]

    if_imp = get_global_importance(if_summary)
    lof_imp = get_global_importance(lof_summary)
    svm_imp = get_global_importance(svm_summary)

    feature_labels_js = json.dumps([FEATURE_LABELS[c] for c in FEATURE_COLUMNS])
    if_imp_js = json.dumps(if_imp)
    lof_imp_js = json.dumps(lof_imp)
    svm_imp_js = json.dumps(svm_imp)

    def unit_table_js(summary):
        rows = []
        for _, row in summary.iterrows():
            rows.append({"cid": row["commodity_id"], "seg": row["segment"],
                         "top": row["top_feature"], "imp": round(row["top_importance"], 4)})
        return json.dumps(rows)

    if_units_js = unit_table_js(if_summary)
    lof_units_js = unit_table_js(lof_summary)
    svm_units_js = unit_table_js(svm_summary)

    if_heatmap_js = build_heatmap_data_js(if_detail, predictions_dir)
    lof_heatmap_js = build_heatmap_data_js(lof_detail, predictions_dir)
    svm_heatmap_js = build_heatmap_data_js(svm_detail, predictions_dir)

    units_list = if_summary[["commodity_id", "segment"]].apply(lambda r: f"{r.commodity_id}_{r.segment}", axis=1).tolist()
    units_js = json.dumps(units_list)

    # Beeswarm section HTML
    beeswarm_html = ""
    if beeswarm_exists:
        beeswarm_html = """
<div class="section">
  <div class="section-header">
    <span class="section-number">4</span>
    <span class="section-title">Beeswarm Plots (All Units Combined)</span>
    <span class="section-desc">Each dot = one month of one commodity. Color = feature value (blue=low, red=high)</span>
  </div>
  <div class="chart-grid">
    <div class="chart-card"><h3>Isolation Forest</h3><img src="beeswarm_IF.png" style="width:100%;border-radius:8px;"></div>
    <div class="chart-card"><h3>Local Outlier Factor</h3><img src="beeswarm_LOF.png" style="width:100%;border-radius:8px;"></div>
  </div>
  <div style="margin-top:20px">
    <div class="chart-card full"><h3>One-Class SVM</h3><img src="beeswarm_SVM.png" style="width:100%;border-radius:8px;"></div>
  </div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SHAP Feature Importance Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root {{ --bg-primary:#0a0e17; --bg-card:#111827; --border:#1e293b; --text-primary:#e2e8f0; --text-secondary:#94a3b8; --text-muted:#64748b; --accent-blue:#3b82f6; --accent-cyan:#06b6d4; --accent-emerald:#10b981; --accent-amber:#f59e0b; --accent-rose:#f43f5e; --accent-violet:#8b5cf6; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Noto Sans KR',sans-serif; background:var(--bg-primary); color:var(--text-primary); min-height:100vh; line-height:1.6; }}
.container {{ max-width:1400px; margin:0 auto; padding:40px 32px; }}
.header {{ text-align:center; margin-bottom:48px; }}
.header::after {{ content:''; display:block; width:120px; height:2px; background:linear-gradient(90deg,var(--accent-blue),var(--accent-cyan)); margin:24px auto 0; }}
.header h1 {{ font-size:26px; font-weight:900; background:linear-gradient(135deg,#e2e8f0,#94a3b8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.header .subtitle {{ font-size:13px; color:var(--text-muted); margin-top:8px; font-family:'JetBrains Mono',monospace; }}
.data-sources {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:20px; margin-bottom:32px; font-family:'JetBrains Mono',monospace; font-size:12px; }}
.data-sources .title {{ font-size:13px; font-weight:700; color:var(--accent-blue); margin-bottom:12px; }}
.data-sources .source-row {{ display:flex; gap:12px; align-items:center; padding:4px 0; color:var(--text-secondary); }}
.data-sources .badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-weight:700; font-size:11px; min-width:36px; text-align:center; }}
.badge-if {{ background:rgba(59,130,246,0.2); color:var(--accent-blue); }}
.badge-lof {{ background:rgba(6,182,212,0.2); color:var(--accent-cyan); }}
.badge-svm {{ background:rgba(139,92,246,0.2); color:var(--accent-violet); }}
.section {{ margin-bottom:48px; }}
.section-header {{ display:flex; align-items:center; gap:12px; margin-bottom:20px; padding-bottom:12px; border-bottom:1px solid var(--border); }}
.section-number {{ font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:700; color:var(--accent-blue); background:rgba(59,130,246,0.1); padding:4px 10px; border-radius:6px; }}
.section-title {{ font-size:17px; font-weight:700; }}
.section-desc {{ font-size:12px; color:var(--text-muted); margin-left:auto; }}
.chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
.chart-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:24px; }}
.chart-card.full {{ grid-column:1/-1; }}
.chart-card h3 {{ font-size:13px; font-weight:500; color:var(--text-secondary); margin-bottom:16px; }}
.chart-container.wide {{ position:relative; width:100%; height:400px; }}
.chart-container.tall {{ position:relative; width:100%; height:500px; }}
select.unit-select {{ background:var(--bg-primary); color:var(--text-primary); border:1px solid var(--border); border-radius:4px; padding:4px 8px; font-size:11px; font-family:'JetBrains Mono',monospace; margin-left:8px; }}
table.eval {{ width:100%; border-collapse:collapse; font-size:11px; font-family:'JetBrains Mono',monospace; }}
table.eval th {{ padding:8px 5px; font-weight:500; color:var(--text-muted); text-align:center; border-bottom:1px solid var(--border); font-size:10px; }}
table.eval th:first-child {{ text-align:left; min-width:85px; }}
table.eval td {{ padding:5px; text-align:center; border-bottom:1px solid rgba(30,41,59,0.5); }}
table.eval td:first-child {{ text-align:left; font-weight:500; color:var(--text-secondary); }}
.footer {{ text-align:center; padding:32px 0; border-top:1px solid var(--border); color:var(--text-muted); font-size:12px; font-family:'JetBrains Mono',monospace; }}
@media (max-width:1024px) {{ .chart-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>SHAP Feature Importance Dashboard</h1>
  <div class="subtitle">Isolation Forest · Local Outlier Factor · One-Class SVM — 10 Commodities × 2 Segments</div>
</div>

<div class="data-sources">
  <div class="title">Data Sources</div>
  <div class="source-row"><span class="badge badge-if">IF</span> {if_dir} — {if_meta.get('explainer','?')}, status: {if_meta.get('status','?')}, {if_meta.get('timestamp','?')}</div>
  <div class="source-row"><span class="badge badge-lof">LOF</span> {lof_dir} — {lof_meta.get('explainer','?')}, status: {lof_meta.get('status','?')}, {lof_meta.get('timestamp','?')}</div>
  <div class="source-row"><span class="badge badge-svm">SVM</span> {svm_dir} — {svm_meta.get('explainer','?')}, status: {svm_meta.get('status','?')}, {svm_meta.get('timestamp','?')}</div>
</div>

<div class="section">
  <div class="section-header">
    <span class="section-number">1</span>
    <span class="section-title">Global Feature Importance (Mean |SHAP|)</span>
    <span class="section-desc">Average across all 20 commodity × segment units</span>
  </div>
  <div class="chart-grid">
    <div class="chart-card"><h3>Absolute Values (raw scale — not comparable across models)</h3><div class="chart-container wide"><canvas id="global_bar"></canvas></div></div>
    <div class="chart-card"><h3>Normalized Proportion (sum=1 per model — cross-model comparable)</h3><div class="chart-container wide"><canvas id="global_bar_norm"></canvas></div></div>
  </div>
</div>

<div class="section">
  <div class="section-header">
    <span class="section-number">2</span>
    <span class="section-title">Top Feature by Commodity × Segment</span>
    <span class="section-desc">Most important feature per unit for each model</span>
  </div>
  <div class="chart-card full"><div id="unit_table"></div></div>
</div>

<div class="section">
  <div class="section-header">
    <span class="section-number">3</span>
    <span class="section-title">SHAP Heatmap (Time × Feature)</span>
    <span class="section-desc">Percentile-clipped (2nd~98th), Blue–White–Red diverging colormap</span>
  </div>
  <div class="chart-card full">
    <h3>
      Unit: <select id="hm_unit" class="unit-select"></select>
      Model: <select id="hm_model" class="unit-select">
        <option value="IF">Isolation Forest</option>
        <option value="LOF">Local Outlier Factor</option>
        <option value="SVM">One-Class SVM</option>
      </select>
      <button id="hm_toggle" style="margin-left:12px;background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);border-radius:4px;padding:4px 12px;font-size:11px;font-family:'JetBrains Mono',monospace;cursor:pointer;">Show: All Months</button>
    </h3>
    <div style="position:relative;">
      <div class="chart-container tall"><canvas id="heatmap_canvas"></canvas></div>
      <div id="hm_tooltip" style="display:none;position:absolute;background:rgba(17,24,39,0.95);border:1px solid #3b82f6;border-radius:6px;padding:8px 12px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#e2e8f0;pointer-events:none;z-index:10;white-space:nowrap;"></div>
    </div>
    <div id="heatmap_legend" style="margin-top:12px;text-align:center;font-size:11px;color:var(--text-muted);font-family:'JetBrains Mono',monospace;"></div>
  </div>
</div>

{beeswarm_html}

<div class="footer">SHAP Feature Importance Dashboard · Sunmoon University Capstone Design 11-1 · {timestamp_now}</div>
</div>

<script>
const FL={feature_labels_js};
const FC={json.dumps(FEATURE_COLUMNS)};
const C_={{if:'#3b82f6',lof:'#06b6d4',svm:'#8b5cf6'}};

// === Section 1: Absolute ===
new Chart(document.getElementById('global_bar'),{{
  type:'bar',
  data:{{labels:FL,datasets:[
    {{label:'Isolation Forest',data:{if_imp_js},backgroundColor:C_.if+'99',borderColor:C_.if,borderWidth:1,borderRadius:3}},
    {{label:'Local Outlier Factor',data:{lof_imp_js},backgroundColor:C_.lof+'99',borderColor:C_.lof,borderWidth:1,borderRadius:3}},
    {{label:'One-Class SVM',data:{svm_imp_js},backgroundColor:C_.svm+'99',borderColor:C_.svm,borderWidth:1,borderRadius:3}},
  ]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top',labels:{{boxWidth:12,color:'#94a3b8'}}}}}},scales:{{x:{{ticks:{{font:{{size:10}},color:'#94a3b8'}}}},y:{{title:{{display:true,text:'Mean |SHAP Value|',color:'#94a3b8'}},ticks:{{color:'#94a3b8'}}}}}}}}
}});

// === Section 1: Normalized (sum=1 per model) ===
function normArr(arr){{const s=arr.reduce((a,b)=>a+b,0);return s>0?arr.map(v=>+(v/s).toFixed(4)):arr;}}
const ifNorm=normArr({if_imp_js}),lofNorm=normArr({lof_imp_js}),svmNorm=normArr({svm_imp_js});
new Chart(document.getElementById('global_bar_norm'),{{
  type:'bar',
  data:{{labels:FL,datasets:[
    {{label:'Isolation Forest',data:ifNorm,backgroundColor:C_.if+'99',borderColor:C_.if,borderWidth:1,borderRadius:3}},
    {{label:'Local Outlier Factor',data:lofNorm,backgroundColor:C_.lof+'99',borderColor:C_.lof,borderWidth:1,borderRadius:3}},
    {{label:'One-Class SVM',data:svmNorm,backgroundColor:C_.svm+'99',borderColor:C_.svm,borderWidth:1,borderRadius:3}},
  ]}},
  options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top',labels:{{boxWidth:12,color:'#94a3b8'}}}},tooltip:{{callbacks:{{label:function(ctx){{return ctx.dataset.label+': '+(ctx.raw*100).toFixed(1)+'%';}}}}}}}},scales:{{x:{{ticks:{{font:{{size:10}},color:'#94a3b8'}}}},y:{{title:{{display:true,text:'Proportion (%)',color:'#94a3b8'}},ticks:{{color:'#94a3b8',callback:function(v){{return(v*100).toFixed(0)+'%';}}}},max:0.3}}}}}}
}});

// === Section 2 ===
const ifU={if_units_js},lofU={lof_units_js},svmU={svm_units_js};
let tH='<table class="eval"><thead><tr><th>Commodity</th><th>Isolation Forest</th><th>Imp.</th><th>Local Outlier Factor</th><th>Imp.</th><th>One-Class SVM</th><th>Imp.</th></tr></thead><tbody>';
for(let i=0;i<ifU.length;i++){{const a=ifU[i],b=lofU[i],c=svmU[i];tH+=`<tr><td>${{a.cid}} ${{a.seg}}</td><td>${{a.top}}</td><td>${{a.imp.toFixed(4)}}</td><td>${{b.top}}</td><td>${{b.imp.toFixed(4)}}</td><td>${{c.top}}</td><td>${{c.imp.toFixed(4)}}</td></tr>`;}}
tH+='</tbody></table>';document.getElementById('unit_table').innerHTML=tH;

// === Section 3: Heatmap (percentile-clipped, blue-white-red, tooltip, anomaly filter) ===
const hmData={{IF:{if_heatmap_js},LOF:{lof_heatmap_js},SVM:{svm_heatmap_js}}};
const units={units_js};
const hmUS=document.getElementById('hm_unit'),hmMS=document.getElementById('hm_model');
const hmToggle=document.getElementById('hm_toggle');
const hmTooltip=document.getElementById('hm_tooltip');
units.forEach(u=>{{const o=document.createElement('option');o.value=u;o.textContent=u.replace('_',' ');hmUS.appendChild(o);}});

let hmShowAll=true;
// Store current heatmap state for tooltip
let hmState={{mL:0,mT:0,cW:0,cH:0,nD:0,nF:0,dates:[],clipMax:0,features:{{}},filteredIndices:null}};

hmToggle.addEventListener('click',()=>{{
  hmShowAll=!hmShowAll;
  hmToggle.textContent=hmShowAll?'Show: All Months':'Show: Anomaly Months Only';
  hmToggle.style.background=hmShowAll?'rgba(59,130,246,0.15)':'rgba(16,185,129,0.15)';
  hmToggle.style.color=hmShowAll?'#3b82f6':'#10b981';
  hmToggle.style.borderColor=hmShowAll?'rgba(59,130,246,0.3)':'rgba(16,185,129,0.3)';
  drawHeatmap();
}});

function drawHeatmap(){{
  const unit=hmUS.value,model=hmMS.value;
  const d=hmData[model];if(!d||!d[unit])return;
  const ud=d[unit];
  let dates=ud.dates,features=ud.features,anomalyIdx=ud.anomaly||[];

  // Filter to anomaly months only if toggled
  let filteredIndices=null;
  if(!hmShowAll&&anomalyIdx.length>0){{
    filteredIndices=anomalyIdx;
    dates=anomalyIdx.map(i=>ud.dates[i]);
    features={{}};
    FC.forEach(f=>{{features[f]=anomalyIdx.map(i=>ud.features[f][i]);}});
  }}

  // Percentile clipping
  const allVals=[];
  FC.forEach(f=>features[f].forEach(v=>allVals.push(v)));
  allVals.sort((a,b)=>a-b);
  const p2=allVals[Math.floor(allVals.length*0.02)];
  const p98=allVals[Math.floor(allVals.length*0.98)];
  const clipMax=Math.max(Math.abs(p2),Math.abs(p98))||1;

  const canvas=document.getElementById('heatmap_canvas');
  const ctx=canvas.getContext('2d');
  const rect=canvas.parentElement.getBoundingClientRect();
  canvas.width=rect.width;canvas.height=rect.height;

  const mL=160,mR=20,mT=30,mB=80;
  const pW=canvas.width-mL-mR,pH=canvas.height-mT-mB;
  const nD=dates.length,nF=FC.length;
  const cW=pW/nD,cH=pH/nF;

  // Store state for tooltip
  hmState={{mL,mT,cW,cH,nD,nF,dates,clipMax,features,filteredIndices}};

  ctx.clearRect(0,0,canvas.width,canvas.height);

  function valColor(v){{
    const clamped=Math.max(-clipMax,Math.min(clipMax,v));
    const t=clipMax>0?clamped/clipMax:0;
    let r,g,b;
    if(t>=0){{r=255;g=Math.round(255*(1-t));b=Math.round(255*(1-t));}}
    else{{const at=-t;r=Math.round(255*(1-at));g=Math.round(255*(1-at));b=255;}}
    return`rgb(${{r}},${{g}},${{b}})`;
  }}

  // Draw cells
  FC.forEach((f,fi)=>{{
    features[f].forEach((v,di)=>{{
      ctx.fillStyle=valColor(v);
      ctx.fillRect(mL+di*cW,mT+fi*cH,Math.ceil(cW)+0.5,Math.ceil(cH)+0.5);
    }});
  }});

  // Y labels
  ctx.fillStyle='#e2e8f0';ctx.font='11px JetBrains Mono';ctx.textAlign='right';ctx.textBaseline='middle';
  FC.forEach((f,i)=>ctx.fillText(FL[i],mL-8,mT+i*cH+cH/2));

  // X labels
  ctx.fillStyle='#94a3b8';ctx.textAlign='center';ctx.textBaseline='top';
  const maxLabels=hmShowAll?15:Math.min(nD,30);
  const step=Math.max(1,Math.floor(nD/maxLabels));
  for(let i=0;i<nD;i+=step){{
    ctx.save();ctx.translate(mL+i*cW+cW/2,mT+pH+8);ctx.rotate(-Math.PI/4);
    ctx.fillText(dates[i],0,0);ctx.restore();
  }}

  // Title
  const modeLabel=hmShowAll?'All Months':'Anomaly Months ('+nD+')';
  ctx.fillStyle='#e2e8f0';ctx.font='13px Noto Sans KR';ctx.textAlign='center';ctx.textBaseline='top';
  ctx.fillText(unit.replace('_',' ')+' — '+model+' — '+modeLabel,canvas.width/2,4);

  // Legend gradient
  const gW=200,gH=12,gX=(canvas.width-gW)/2,gY=mT+pH+52;
  const grad=ctx.createLinearGradient(gX,0,gX+gW,0);
  grad.addColorStop(0,'rgb(0,0,255)');grad.addColorStop(0.5,'rgb(255,255,255)');grad.addColorStop(1,'rgb(255,0,0)');
  ctx.fillStyle=grad;ctx.fillRect(gX,gY,gW,gH);
  ctx.strokeStyle='#64748b';ctx.strokeRect(gX,gY,gW,gH);

  ctx.fillStyle='#94a3b8';ctx.font='10px JetBrains Mono';ctx.textAlign='center';ctx.textBaseline='top';
  ctx.fillText('-'+clipMax.toFixed(2),gX,gY+gH+4);
  ctx.fillText('0',gX+gW/2,gY+gH+4);
  ctx.fillText('+'+clipMax.toFixed(2),gX+gW,gY+gH+4);
  ctx.fillText('SHAP Value (clipped 2nd~98th percentile)',canvas.width/2,gY+gH+18);
}}

// Tooltip on mousemove
document.getElementById('heatmap_canvas').addEventListener('mousemove',(e)=>{{
  const canvas=e.target;
  const rect=canvas.getBoundingClientRect();
  const mx=e.clientX-rect.left;
  const my=e.clientY-rect.top;
  const s=hmState;

  const di=Math.floor((mx-s.mL)/s.cW);
  const fi=Math.floor((my-s.mT)/s.cH);

  if(di>=0&&di<s.nD&&fi>=0&&fi<s.nF){{
    const date=s.dates[di];
    const feat=FC[fi];
    const featLabel=FL[fi];
    const val=s.features[feat][di];

    hmTooltip.style.display='block';
    hmTooltip.innerHTML=`<div style="color:#3b82f6;font-weight:700;margin-bottom:2px">${{date}}</div><div>${{featLabel}}</div><div style="margin-top:4px;font-size:13px;font-weight:700;color:${{val>=0?'#ef4444':'#3b82f6'}}">${{val>=0?'+':''}}${{val.toFixed(4)}}</div>`;

    // Position tooltip
    let tx=e.clientX-rect.left+16;
    let ty=e.clientY-rect.top-10;
    if(tx+180>canvas.width)tx=tx-196;
    if(ty<0)ty=10;
    hmTooltip.style.left=tx+'px';
    hmTooltip.style.top=ty+'px';
  }}else{{
    hmTooltip.style.display='none';
  }}
}});

document.getElementById('heatmap_canvas').addEventListener('mouseleave',()=>{{
  hmTooltip.style.display='none';
}});

hmUS.addEventListener('change',drawHeatmap);hmMS.addEventListener('change',drawHeatmap);
setTimeout(drawHeatmap,100);
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="SHAP 대시보드 생성")
    parser.add_argument("--if-dir", type=str, required=True)
    parser.add_argument("--lof-dir", type=str, required=True)
    parser.add_argument("--svm-dir", type=str, required=True)
    args = parser.parse_args()

    results_base = Path(os.path.dirname(os.path.abspath(__file__))) / "results"
    features_dir = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "data" / "processed" / "phase7_ml" / "features"
    predictions_dir = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "data" / "processed" / "phase7_ml" / "predictions"

    print("[SHAP-Dashboard] 데이터 로딩...")
    if_summary, if_meta, if_detail = load_model_data(results_base, args.if_dir)
    lof_summary, lof_meta, lof_detail = load_model_data(results_base, args.lof_dir)
    svm_summary, svm_meta, svm_detail = load_model_data(results_base, args.svm_dir)
    print(f"  IF:  {len(if_summary)} units, {len(if_detail)} rows")
    print(f"  LOF: {len(lof_summary)} units, {len(lof_detail)} rows")
    print(f"  SVM: {len(svm_summary)} units, {len(svm_detail)} rows")

    # 출력 디렉토리
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = results_base / f"대시보드_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Beeswarm PNG 생성
    print("[SHAP-Dashboard] Beeswarm PNG 생성...")
    beeswarm_ok = True
    try:
        generate_beeswarm_png(if_detail, features_dir, "Isolation Forest", output_dir / "beeswarm_IF.png")
        generate_beeswarm_png(lof_detail, features_dir, "Local Outlier Factor", output_dir / "beeswarm_LOF.png")
        generate_beeswarm_png(svm_detail, features_dir, "One-Class SVM", output_dir / "beeswarm_SVM.png")
    except Exception as e:
        print(f"  [WARNING] Beeswarm 생성 실패: {e}")
        beeswarm_ok = False

    # HTML 생성
    print("[SHAP-Dashboard] HTML 생성...")
    html = generate_html(
        if_summary, lof_summary, svm_summary,
        if_meta, lof_meta, svm_meta,
        if_detail, lof_detail, svm_detail,
        args.if_dir, args.lof_dir, args.svm_dir,
        beeswarm_ok, predictions_dir=str(predictions_dir),
    )

    output_path = output_dir / "dashboard_shap.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[SHAP-Dashboard] 생성 완료: {output_path}")
    if beeswarm_ok:
        print(f"  Beeswarm PNGs: {output_dir}/beeswarm_*.png")


if __name__ == "__main__":
    main()