"""
SHAP 대시보드 생성 (generate_shap_dashboard.py)
================================================
역할:
  3종 모델(IF/LOF/SVM)의 SHAP 결과를 읽어
  Bar Plot + Heatmap 시각화 대시보드 HTML을 생성한다.

입력:
  - tests/shap/results/{timestamp}_IF/   (shap_summary.csv + 개별 CSV + run_meta.json)
  - tests/shap/results/{timestamp}_LOF/
  - tests/shap/results/{timestamp}_SVM/

출력:
  - tests/shap/results/대시보드_{YYYYMMDD_HHMM}/dashboard_shap.html

위치: tests/shap/generate_shap_dashboard.py

실행:
  python tests/shap/generate_shap_dashboard.py --if-dir 20260519_1910_IF --lof-dir 20260519_2033_LOF --svm-dir 20260519_2041_SVM
"""

import sys
import os
import json
import argparse
import pandas as pd
import numpy as np
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


def load_model_data(results_base, dir_name):
    """한 모델의 SHAP 결과를 로드한다."""
    d = Path(results_base) / dir_name
    if not d.exists():
        raise FileNotFoundError(f"디렉토리 없음: {d}")

    summary = pd.read_csv(d / "shap_summary.csv", encoding="utf-8-sig")
    meta_path = d / "run_meta.json"
    meta = {}
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    # 개별 SHAP CSV 로드 (heatmap용)
    shap_all = []
    for csv_file in sorted(d.glob("*_shap.csv")):
        if csv_file.name == "shap_summary.csv":
            continue
        df = pd.read_csv(csv_file, encoding="utf-8-sig")
        shap_all.append(df)

    shap_detail = pd.concat(shap_all, ignore_index=True) if shap_all else pd.DataFrame()

    return summary, meta, shap_detail


def build_heatmap_data_js(shap_detail, model_name):
    """heatmap용 JS 데이터 생성 — 품목×세그먼트별 드롭다운 선택."""
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
        heatmap_data[key] = {"dates": dates, "features": features_data}

    return json.dumps(heatmap_data)


def generate_html(if_summary, lof_summary, svm_summary,
                  if_meta, lof_meta, svm_meta,
                  if_detail, lof_detail, svm_detail,
                  if_dir, lof_dir, svm_dir):

    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Bar Plot 데이터 (3종 모델의 글로벌 피처 중요도)
    def get_global_importance(summary):
        result = []
        for col in FEATURE_COLUMNS:
            key = f"mean_abs_{col}"
            result.append(round(summary[key].mean(), 6))
        return result

    if_imp = get_global_importance(if_summary)
    lof_imp = get_global_importance(lof_summary)
    svm_imp = get_global_importance(svm_summary)

    feature_labels_js = json.dumps([FEATURE_LABELS[c] for c in FEATURE_COLUMNS])
    if_imp_js = json.dumps(if_imp)
    lof_imp_js = json.dumps(lof_imp)
    svm_imp_js = json.dumps(svm_imp)

    # Per-unit top feature 테이블 데이터
    def unit_table_js(summary):
        rows = []
        for _, row in summary.iterrows():
            rows.append({
                "cid": row["commodity_id"],
                "seg": row["segment"],
                "top": row["top_feature"],
                "imp": round(row["top_importance"], 4),
            })
        return json.dumps(rows)

    if_units_js = unit_table_js(if_summary)
    lof_units_js = unit_table_js(lof_summary)
    svm_units_js = unit_table_js(svm_summary)

    # Heatmap 데이터
    if_heatmap_js = build_heatmap_data_js(if_detail, "IF")
    lof_heatmap_js = build_heatmap_data_js(lof_detail, "LOF")
    svm_heatmap_js = build_heatmap_data_js(svm_detail, "SVM")

    # 유닛 목록
    units_list = if_summary[["commodity_id", "segment"]].apply(lambda r: f"{r.commodity_id}_{r.segment}", axis=1).tolist()
    units_js = json.dumps(units_list)

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
.chart-container {{ position:relative; width:100%; }}
.chart-container.wide {{ height:400px; }}
.chart-container.tall {{ height:500px; }}
select.unit-select {{ background:var(--bg-primary); color:var(--text-primary); border:1px solid var(--border); border-radius:4px; padding:4px 8px; font-size:11px; font-family:'JetBrains Mono',monospace; margin-left:8px; }}
table.eval {{ width:100%; border-collapse:collapse; font-size:11px; font-family:'JetBrains Mono',monospace; }}
table.eval th {{ padding:8px 5px; font-weight:500; color:var(--text-muted); text-align:center; border-bottom:1px solid var(--border); font-size:10px; }}
table.eval th:first-child {{ text-align:left; min-width:85px; }}
table.eval td {{ padding:5px; text-align:center; border-bottom:1px solid rgba(30,41,59,0.5); }}
table.eval td:first-child {{ text-align:left; font-weight:500; color:var(--text-secondary); }}
.hl {{ display:inline-block; padding:1px 5px; border-radius:3px; font-weight:600; min-width:44px; font-size:11px; }}
.hl-best {{ background:rgba(16,185,129,0.22); color:#6ee7b7; }}
canvas.heatmap {{ image-rendering:pixelated; }}
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

<!-- Section 1: Global Bar Plot -->
<div class="section">
  <div class="section-header">
    <span class="section-number">1</span>
    <span class="section-title">Global Feature Importance (Mean |SHAP|)</span>
    <span class="section-desc">Average across all 20 commodity × segment units</span>
  </div>
  <div class="chart-grid">
    <div class="chart-card full"><div class="chart-container wide"><canvas id="global_bar"></canvas></div></div>
  </div>
</div>

<!-- Section 2: Per-Unit Top Feature Table -->
<div class="section">
  <div class="section-header">
    <span class="section-number">2</span>
    <span class="section-title">Top Feature by Commodity × Segment</span>
    <span class="section-desc">Most important feature per unit for each model</span>
  </div>
  <div class="chart-card full"><div id="unit_table"></div></div>
</div>

<!-- Section 3: Heatmap -->
<div class="section">
  <div class="section-header">
    <span class="section-number">3</span>
    <span class="section-title">SHAP Heatmap (Time × Feature)</span>
    <span class="section-desc">Select unit and model to view temporal SHAP contribution</span>
  </div>
  <div class="chart-card full">
    <h3>
      Unit: <select id="hm_unit" class="unit-select"></select>
      Model: <select id="hm_model" class="unit-select">
        <option value="IF">Isolation Forest</option>
        <option value="LOF">Local Outlier Factor</option>
        <option value="SVM">One-Class SVM</option>
      </select>
    </h3>
    <div class="chart-container tall"><canvas id="heatmap_canvas"></canvas></div>
    <div id="heatmap_legend" style="margin-top:12px;text-align:center;font-size:11px;color:var(--text-muted);font-family:'JetBrains Mono',monospace;"></div>
  </div>
</div>

<div class="footer">SHAP Feature Importance Dashboard · Sunmoon University Capstone Design 11-1 · {timestamp_now}</div>
</div>

<script>
const FL={feature_labels_js};
const FC={json.dumps(FEATURE_COLUMNS)};
const C={{if:'#3b82f6',lof:'#06b6d4',svm:'#8b5cf6'}};

// === Section 1: Global Bar Plot ===
const ifImp={if_imp_js}, lofImp={lof_imp_js}, svmImp={svm_imp_js};
new Chart(document.getElementById('global_bar'),{{
  type:'bar',
  data:{{
    labels:FL,
    datasets:[
      {{label:'Isolation Forest',data:ifImp,backgroundColor:C.if+'99',borderColor:C.if,borderWidth:1,borderRadius:3}},
      {{label:'Local Outlier Factor',data:lofImp,backgroundColor:C.lof+'99',borderColor:C.lof,borderWidth:1,borderRadius:3}},
      {{label:'One-Class SVM',data:svmImp,backgroundColor:C.svm+'99',borderColor:C.svm,borderWidth:1,borderRadius:3}},
    ]
  }},
  options:{{
    responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{position:'top',labels:{{boxWidth:12,color:'#94a3b8'}}}}}},
    scales:{{
      x:{{ticks:{{font:{{size:10}},color:'#94a3b8'}}}},
      y:{{title:{{display:true,text:'Mean |SHAP Value|',color:'#94a3b8'}},ticks:{{color:'#94a3b8'}}}},
    }}
  }}
}});

// === Section 2: Per-Unit Top Feature Table ===
const ifU={if_units_js}, lofU={lof_units_js}, svmU={svm_units_js};
let tH='<table class="eval"><thead><tr><th>Commodity</th><th>Isolation Forest</th><th>Imp.</th><th>Local Outlier Factor</th><th>Imp.</th><th>One-Class SVM</th><th>Imp.</th></tr></thead><tbody>';
for(let i=0;i<ifU.length;i++){{
  const a=ifU[i],b=lofU[i],c=svmU[i];
  tH+=`<tr><td>${{a.cid}} ${{a.seg}}</td><td>${{a.top}}</td><td>${{a.imp.toFixed(4)}}</td><td>${{b.top}}</td><td>${{b.imp.toFixed(4)}}</td><td>${{c.top}}</td><td>${{c.imp.toFixed(4)}}</td></tr>`;
}}
tH+='</tbody></table>';
document.getElementById('unit_table').innerHTML=tH;

// === Section 3: Heatmap ===
const hmData={{IF:{if_heatmap_js},LOF:{lof_heatmap_js},SVM:{svm_heatmap_js}}};
const units={units_js};
const hmUnitSel=document.getElementById('hm_unit');
const hmModelSel=document.getElementById('hm_model');
units.forEach(u=>{{const o=document.createElement('option');o.value=u;o.textContent=u.replace('_',' ');hmUnitSel.appendChild(o);}});

let hmChart=null;
function drawHeatmap(){{
  const unit=hmUnitSel.value;
  const model=hmModelSel.value;
  const d=hmData[model];
  if(!d||!d[unit])return;
  const ud=d[unit];
  const dates=ud.dates;
  const features=ud.features;

  // Build datasets: one per feature, x=date index, y=feature index, color=shap value
  const dataPoints=[];
  let maxAbs=0;
  FC.forEach((f,fi)=>{{
    features[f].forEach((v,di)=>{{
      dataPoints.push({{x:di,y:fi,v:v}});
      if(Math.abs(v)>maxAbs)maxAbs=Math.abs(v);
    }});
  }});

  // Draw on canvas manually
  const canvas=document.getElementById('heatmap_canvas');
  const ctx=canvas.getContext('2d');
  const rect=canvas.parentElement.getBoundingClientRect();
  canvas.width=rect.width;
  canvas.height=rect.height;

  const marginLeft=140,marginRight=20,marginTop=30,marginBottom=60;
  const plotW=canvas.width-marginLeft-marginRight;
  const plotH=canvas.height-marginTop-marginBottom;
  const nDates=dates.length;
  const nFeatures=FC.length;
  const cellW=plotW/nDates;
  const cellH=plotH/nFeatures;

  ctx.clearRect(0,0,canvas.width,canvas.height);

  // Color function: blue(negative) — black(zero) — red(positive)
  function valColor(v){{
    const t=maxAbs>0?v/maxAbs:0;
    if(t>=0){{
      const r=Math.round(55+200*t);
      const g=Math.round(20+20*t);
      const b=Math.round(20+20*t);
      return`rgb(${{r}},${{g}},${{b}})`;
    }}else{{
      const at=-t;
      const r=Math.round(20+20*at);
      const g=Math.round(40+60*at);
      const b=Math.round(80+175*at);
      return`rgb(${{r}},${{g}},${{b}})`;
    }}
  }}

  // Draw cells
  dataPoints.forEach(p=>{{
    const x=marginLeft+p.x*cellW;
    const y=marginTop+p.y*cellH;
    ctx.fillStyle=valColor(p.v);
    ctx.fillRect(x,y,Math.ceil(cellW),Math.ceil(cellH));
  }});

  // Y-axis labels (features)
  ctx.fillStyle='#94a3b8';
  ctx.font='11px JetBrains Mono';
  ctx.textAlign='right';
  ctx.textBaseline='middle';
  FC.forEach((f,i)=>{{
    ctx.fillText(FL[i],marginLeft-8,marginTop+i*cellH+cellH/2);
  }});

  // X-axis labels (dates — sample every N)
  ctx.textAlign='center';
  ctx.textBaseline='top';
  const step=Math.max(1,Math.floor(nDates/15));
  for(let i=0;i<nDates;i+=step){{
    ctx.save();
    ctx.translate(marginLeft+i*cellW+cellW/2, marginTop+plotH+8);
    ctx.rotate(-Math.PI/4);
    ctx.fillText(dates[i],0,0);
    ctx.restore();
  }}

  // Title
  ctx.fillStyle='#e2e8f0';
  ctx.font='13px Noto Sans KR';
  ctx.textAlign='center';
  ctx.textBaseline='top';
  ctx.fillText(unit.replace('_',' ')+' — '+model,canvas.width/2,4);

  // Legend
  document.getElementById('heatmap_legend').innerHTML=
    `<span style="color:#3b7dff">■ Negative SHAP</span> &nbsp; `+
    `<span style="color:#333">■ Zero</span> &nbsp; `+
    `<span style="color:#e03030">■ Positive SHAP</span> &nbsp; `+
    `| Max |SHAP| = ${{maxAbs.toFixed(4)}}`;
}}

hmUnitSel.addEventListener('change',drawHeatmap);
hmModelSel.addEventListener('change',drawHeatmap);
// Initial draw after page load
setTimeout(drawHeatmap,100);
</script>
</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="SHAP 대시보드 생성")
    parser.add_argument("--if-dir", type=str, required=True, help="IF 결과 폴더명 (예: 20260519_1910_IF)")
    parser.add_argument("--lof-dir", type=str, required=True, help="LOF 결과 폴더명 (예: 20260519_2033_LOF)")
    parser.add_argument("--svm-dir", type=str, required=True, help="SVM 결과 폴더명 (예: 20260519_2041_SVM)")
    args = parser.parse_args()

    results_base = Path(os.path.dirname(os.path.abspath(__file__))) / "results"

    print("[SHAP-Dashboard] 데이터 로딩...")
    if_summary, if_meta, if_detail = load_model_data(results_base, args.if_dir)
    lof_summary, lof_meta, lof_detail = load_model_data(results_base, args.lof_dir)
    svm_summary, svm_meta, svm_detail = load_model_data(results_base, args.svm_dir)
    print(f"  IF:  {len(if_summary)} units, {len(if_detail)} rows")
    print(f"  LOF: {len(lof_summary)} units, {len(lof_detail)} rows")
    print(f"  SVM: {len(svm_summary)} units, {len(svm_detail)} rows")

    html = generate_html(
        if_summary, lof_summary, svm_summary,
        if_meta, lof_meta, svm_meta,
        if_detail, lof_detail, svm_detail,
        args.if_dir, args.lof_dir, args.svm_dir,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = results_base / f"대시보드_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "dashboard_shap.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[SHAP-Dashboard] 생성 완료: {output_path}")


if __name__ == "__main__":
    main()
