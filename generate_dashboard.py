# -*- coding: utf-8 -*-
"""
设备技术分公司 · 现场巡查结果展示页生成器
只读连接草料二维码数据库 table_d93（现场巡查记录），筛选"所属单位=设备技术分公司"，
聚合后生成自包含 HTML 展示页。不写入、不修改数据库。
用法:
    python3 generate_dashboard.py        # 默认生成到本目录 设备技术分公司巡查结果.html
"""
import json, os, sys, datetime
from collections import Counter
try:
    import pymysql
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pymysql"], check=True)
    import pymysql

DB = dict(
    host="rm-bp1m4fy8d66u3c6xmbo.mysql.rds.aliyuncs.com",
    port=3306, user="cli_9677100", password="dfeb45e53d940a3b7fad2b934273a18a",
    database="cli_9677100", charset="utf8mb4", connect_timeout=15, read_timeout=60,
)
UNIT = "设备技术分公司"
FIELDS = [
    "记录时间", "项目分类_3712283", "巡查项目_3472176", "项目风险_3472174",
    "风险管理级别_3472224", "特殊作业_3472177", "项目现场负责人姓名_3472178",
    "项目现场监护人_3472179", "巡查人_3472187", "记录编号",
    "安全项目确认_人员安全（劳动防护用品、持证、身体情况等）_3472183_22707233",
    "安全项目确认_设备安全（安全装置、工索具等）_3472183_22707357",
    "安全项目确认_作业环境安全（警戒线、维修牌、人员站位、天气等_3472183_22707358",
    "安全项目确认_管理安全（规范开具作业票、防暑防寒防风措施到位_3472183_22707359",
]
COLNAME = ["time","cat","item","risk","risk_lvl","spec","leader","guard","inspector","rec_no",
           "s_person","s_equip","s_env","s_mgmt"]
RISK_ORDER = ["重大风险（人机混合、大型检维修）","较大风险（船舶靠离泊、清舱、皮带机）","一般风险","低风险"]
RISK_COLOR = {"重大风险（人机混合、大型检维修）":"#dc2626","较大风险（船舶靠离泊、清舱、皮带机）":"#f97316","一般风险":"#ca8a04","低风险":"#16a34a"}
# 用户重点关注的重点巡查人员（每人一个独立、互不相同的颜色）
PEOPLE = ["王建峰","石春华","匡俊华","吴道成","韩义成","韩超","王帅领","张志强","周波涛"]
PEOPLE_COLOR = {
    "王建峰":"#2563eb","石春华":"#16a34a","匡俊华":"#f59e0b","吴道成":"#db2777",
    "韩义成":"#0d9488","韩超":"#7c3aed","王帅领":"#0891b2","张志强":"#f43f5e","周波涛":"#84cc16",
}

def main():
    c = pymysql.connect(**DB); cur = c.cursor()
    cols = ", ".join("`%s`" % f for f in FIELDS)
    cur.execute("SELECT %s FROM table_d93 WHERE 所属单位_3730135=%%s ORDER BY 记录时间 DESC" % cols, (UNIT,))
    rows = cur.fetchall()
    recs = []
    for r in rows:
        d = dict(zip(COLNAME, r))
        for k in d:
            if isinstance(d[k], str):
                d[k] = d[k].strip()
        d["time"] = d["time"].strftime("%Y-%m-%d %H:%M") if d["time"] else ""
        d["date"] = (d["time"] or "")[:10]
        recs.append(d)
    cur.close(); c.close()

    total = len(recs)
    # 默认取"当前日期"为统计基准（每小时间自动刷新，显示最新到当前的数据）；可传日期参数手动指定
    if len(sys.argv) > 1:
        today = datetime.date.fromisoformat(sys.argv[1])
    else:
        today = datetime.date.today()
    def cnt_since(since):
        s = since.strftime("%Y-%m-%d")
        return sum(1 for r in recs if r["date"] >= s)
    last7 = cnt_since(today - datetime.timedelta(days=6))
    month = cnt_since(today.replace(day=1))
    year = cnt_since(datetime.date(today.year,1,1))

    def dist(key):
        c = Counter(r[key] for r in recs if r.get(key))
        return [{"name":k,"value":v} for k,v in c.items()]
    cats = dist("cat")
    risks = sorted(dist("risk"), key=lambda x: RISK_ORDER.index(x["name"]) if x["name"] in RISK_ORDER else 99)
    specs = sorted(dist("spec"), key=lambda x:-x["value"])
    lvls = sorted(dist("risk_lvl"), key=lambda x:-x["value"])
    items = sorted(dist("item"), key=lambda x:-x["value"])[:12]
    high = [r for r in recs if r["risk"] in ("重大风险（人机混合、大型检维修）","较大风险（船舶靠离泊、清舱、皮带机）")]

    # 安全确认不合格项（任一项=0，即未满足/存在隐患）
    fail = []
    for r in recs:
        bads = []
        if r["s_person"] == "0": bads.append("人员安全")
        if r["s_equip"] == "0": bads.append("设备安全")
        if r["s_env"] == "0": bads.append("作业环境安全")
        if r["s_mgmt"] == "0": bads.append("管理安全")
        if bads:
            r = dict(r); r["fail_items"] = bads
            fail.append(r)

    # 按月趋势
    mcounter = Counter(r["date"][:7] for r in recs if r["date"])
    mkeys = sorted(mcounter.keys())
    mdata = [{"month": k, "value": mcounter[k]} for k in mkeys]

    # 近30天每日
    day_start = today - datetime.timedelta(days=29)
    dc = Counter(r["date"] for r in recs if r["date"])
    ddates, dnums = [], []
    dd = day_start
    while dd <= today:
        s = dd.strftime("%Y-%m-%d"); ddates.append(s[5:]); dnums.append(dc.get(s,0)); dd += datetime.timedelta(days=1)

    recent = recs[:80]

    # 重点巡查人员：近30天每日巡查记录数 + 近30天累计
    person_series = {p: [0]*len(ddates) for p in PEOPLE}
    for r in recs:
        p = r.get("inspector")
        if p not in person_series:
            continue
        if r["date"]:
            try:
                idx = ddates.index(r["date"][5:])
            except ValueError:
                continue
            person_series[p][idx] += 1
    person_totals = [{"name": p, "value": sum(person_series[p])} for p in PEOPLE]
    person_totals.sort(key=lambda x: -x["value"])

    data = {
        "gen_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "unit": UNIT, "total": total, "last7": last7, "month": month, "year": year,
        "cat_count": len(cats), "high_count": len(high), "spec_total": sum(v["value"] for v in specs),
        "cats": cats, "risks": risks, "specs": specs, "lvls": lvls, "items": items,
        "monthly": mdata, "ddates": ddates, "dnums": dnums,
        "fail": fail, "recent": recent,
        "people": PEOPLE, "person_color": PEOPLE_COLOR,
        "person_daily": {p: person_series[p] for p in PEOPLE},
        "person_totals": person_totals,
    }
    html = TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "设备技术分公司巡查结果.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("OK 生成:", out)
    print("设备技术分公司 累计=%d 近7天=%d 本月=%d 今年=%d 分类=%d 重大+较大=%d 特殊作业合计=%d 安全不合格=%d" % (
        total, last7, month, year, len(cats), len(high), sum(v["value"] for v in specs), len(fail)))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>设备技术分公司 · 现场巡查结果展示</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230f766e'/%3E%3Cpath d='M18 33l10 10 18-20' stroke='white' stroke-width='6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<script>window.echarts || document.write('<script src="https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"><\/script>');</script>
<style>
:root{--bg:#f4f6fb;--panel:#ffffff;--panel2:#eef2f8;--line:#e4e9f1;--tx:#22304a;--tx2:#5d6f8a;--tx3:#8b98ad;--ac:#2563eb;--r-major:#dc2626;--r-big:#f97316}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;line-height:1.5;padding:18px;min-height:100vh}
.num{font-variant-numeric:tabular-nums}
.wrap{max-width:1240px;margin:0 auto}
.head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;padding:6px 2px 16px}
.head h1{font-size:22px;font-weight:800;color:var(--tx)}
.head .sub{color:var(--tx2);font-size:13px;margin-top:4px}
.head .meta{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.pill{background:var(--panel);border:1px solid var(--line);color:var(--tx2);border-radius:999px;padding:5px 13px;font-size:12.5px}
.pill b{color:var(--ac);font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
@media(max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}}
@media(max-width:480px){.kpis{grid-template-columns:1fr 1fr}}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 1px 2px rgba(34,48,74,.04)}
.kpi .k{font-size:12px;color:var(--tx2)}
.kpi .v{font-size:30px;font-weight:800;margin-top:6px;line-height:1}
.kpi .d{font-size:11.5px;color:var(--tx3);margin-top:6px}
.kpi.hot .v{color:var(--r-major)}
.kpi.ac .v{color:var(--ac)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 1px 2px rgba(34,48,74,.04)}
.panel h3{font-size:14px;font-weight:700;color:var(--tx);margin-bottom:10px;display:flex;align-items:center;gap:8px}
.panel h3 .dot{width:8px;height:8px;border-radius:2px;background:var(--ac);display:inline-block}
.chart{width:100%;height:280px}
.grid{display:grid;gap:12px;margin-top:12px}
.g-trend{grid-template-columns:1.6fr 1fr}
.g-dim{grid-template-columns:1fr 1fr 1fr}
.g-item{grid-template-columns:1fr 1fr}
.sec-title{margin-top:16px;margin-bottom:2px;font-size:15px;font-weight:800;color:var(--tx);display:flex;align-items:center;gap:8px}
.sec-title::before{content:"";width:10px;height:10px;background:var(--ac);border-radius:2px}
@media(max-width:900px){.g-trend,.g-dim,.g-item{grid-template-columns:1fr}}
.fail{border:1px solid rgba(220,38,38,.35);background:linear-gradient(180deg,rgba(220,38,38,.05),rgba(220,38,38,.015));margin-top:12px}
.fail h3 .dot{background:var(--r-major)}
.fail-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.fail-item{background:#fff7f7;border:1px solid rgba(249,115,22,.35);border-radius:10px;padding:10px 12px;font-size:12.5px}
.fail-item .t{color:var(--tx2);font-size:11.5px;display:flex;justify-content:space-between}
.fail-item .t b{color:var(--r-big);font-weight:800}
.fail-item .m{margin-top:6px;font-weight:700;font-size:13px}
.fail-item .u{color:var(--tx2);margin-top:4px;font-size:12px}
.fail-item .bad{margin-top:6px}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;background:rgba(220,38,38,.12);color:#b91c1c;margin-right:6px}
.empty{color:var(--tx3);font-size:13px;padding:6px 2px}
.tbl{overflow-x:auto;margin-top:12px}
table{width:100%;min-width:820px;border-collapse:collapse;table-layout:fixed;font-size:12.5px}
thead th{text-align:left;color:var(--tx2);font-weight:600;border-bottom:1px solid var(--line);padding:8px 8px;white-space:nowrap;background:var(--panel2)}
tbody td{border-bottom:1px solid var(--line);padding:8px;vertical-align:top}
tbody tr:hover{background:rgba(37,99,235,.04)}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600;white-space:nowrap}
.tag.major{background:rgba(220,38,38,.12);color:#b91c1c}
.tag.big{background:rgba(249,115,22,.14);color:#c2410c}
.tag.mid{background:rgba(202,138,4,.16);color:#92400e}
.tag.low{background:rgba(22,163,74,.13);color:#15803d}
.foot{color:var(--tx3);font-size:11.5px;text-align:center;margin-top:20px;line-height:1.8}
@media(max-width:520px){.head h1{font-size:18px}.kpi .v{font-size:24px}.panel h3{font-size:14px}table{font-size:13px}}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div>
      <h1>设备技术分公司 · 现场巡查结果展示</h1>
      <div class="sub">草料二维码「现场巡查记录」· 仅统计「设备技术分公司」</div>
    </div>
    <div class="meta">
      <div class="pill">生成时间：<b id="gen"></b></div>
    </div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="panel" style="margin-top:12px">
    <h3><span class="dot"></span>重点巡查人员每日巡查记录（近30天 · 按人配色）</h3>
    <div id="chPersonDay" class="chart" style="height:360px"></div>
  </div>

  <div class="grid" style="grid-template-columns:1fr 1fr">
    <div class="panel"><h3><span class="dot"></span>近30天各巡查人累计（对比）</h3><div id="chPersonTot" class="chart" style="height:320px"></div></div>
    <div class="panel"><h3><span class="dot"></span>近30天各巡查人出勤覆盖天数</h3><div id="chPersonDays" class="chart" style="height:320px"></div></div>
  </div>

  <div class="panel" style="margin-top:12px">
    <h3><span class="dot"></span>按日按人明细（近30天）</h3>
    <div id="personTableWrap" style="overflow:auto;max-height:420px"></div>
  </div>

  <div class="panel fail">
    <h3><span class="dot"></span>安全确认不合格项（重点关注）</h3>
    <div class="fail-list" id="fail"></div>
  </div>

  <div class="grid g-trend">
    <div class="panel"><h3><span class="dot"></span>近 30 天每日巡查记录数</h3><div id="chDay" class="chart"></div></div>
    <div class="panel"><h3><span class="dot"></span>按月巡查记录趋势</h3><div id="chMon" class="chart"></div></div>
  </div>

  <div class="grid g-dim">
    <div class="panel"><h3><span class="dot"></span>项目分类分布</h3><div id="chCat" class="chart"></div></div>
    <div class="panel"><h3><span class="dot"></span>项目风险分布</h3><div id="chRisk" class="chart"></div></div>
    <div class="panel"><h3><span class="dot"></span>风险管理级别分布</h3><div id="chLvl" class="chart"></div></div>
  </div>

  <div class="grid g-item">
    <div class="panel"><h3><span class="dot"></span>特殊作业类型分布</h3><div id="chSpec" class="chart" style="height:230px"></div></div>
    <div class="panel"><h3><span class="dot"></span>巡查项目 TOP</h3><div id="chItem" class="chart" style="height:260px"></div></div>
  </div>

  <div class="foot">
    数据来源：草料二维码「现场巡查记录」数据库（只读）· 本页仅统计「设备技术分公司」的巡查记录<br>
    展示口径：累计数据自 2025-09 起；「安全确认不合格项」指人员/设备/作业环境/管理四项安全确认中任一项未通过（=0）的记录
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const RISK_COLOR = {"重大风险（人机混合、大型检维修）":"#dc2626","较大风险（船舶靠离泊、清舱、皮带机）":"#f97316","一般风险":"#ca8a04","低风险":"#16a34a"};
const CAT_COLORS = ["#2563eb","#16a34a","#f59e0b","#7c3aed","#dc2626","#0d9488","#db2777","#64748b","#0891b2","#9333ea"];

function shortRisk(r){return (r||"").replace(/（.+）$/,"");}
function riskTagClass(r){if(r.indexOf("重大")===0)return "major";if(r.indexOf("较大")===0)return "big";if(r.indexOf("一般")===0)return "mid";return "low";}
document.getElementById("gen").textContent = DATA.gen_time;

const kpis = [
  {k:"累计巡查记录", v:DATA.total, d:"设备技术分公司累计", c:"ac"},
  {k:"近7天新增", v:DATA.last7, d:"近7天巡查记录", c:""},
  {k:"本月新增", v:DATA.month, d:"本月巡查记录", c:""},
  {k:"今年累计", v:DATA.year, d:"今年巡查记录", c:""},
  {k:"重大+较大风险", v:DATA.high_count, d:"累计高风险项", c:"hot"},
];
document.getElementById("kpis").innerHTML = kpis.map(k=>`<div class="kpi ${k.c}"><div class="k">${k.k}</div><div class="v num">${k.v}</div><div class="d">${k.d}</div></div>`).join("");

/* 重点巡查人员每日记录（近30天，堆叠柱状，按人配色） */
const PC = DATA.person_color;
(function(){
  const el=document.getElementById("chPersonDay"); if(!el) return;
  const ch=echarts.init(el);
  const series = DATA.people.map(p=>({name:p,type:"bar",stack:"total",barMaxWidth:16,itemStyle:{color:PC[p]||"#2563eb"},data:DATA.person_daily[p]}));
  ch.setOption({grid:{left:4,right:14,top:34,bottom:4,containLabel:true},tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},
    legend:{top:0,type:"scroll",textStyle:{color:"#5d6f8a",fontSize:10.5},itemWidth:12,itemHeight:8},
    xAxis:{type:"category",data:DATA.ddates,axisLabel:{color:"#5d6f8a",fontSize:10,interval:4},axisLine:{lineStyle:{color:"#d0d7e2"}}},
    yAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    series:series});
})();
/* 近30天各人累计对比 */
(function(){
  const el=document.getElementById("chPersonTot"); if(!el) return;
  const ch=echarts.init(el); const rows=DATA.person_totals.slice().reverse();
  ch.setOption({grid:{left:8,right:34,top:8,bottom:8,containLabel:true},tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},
    xAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    yAxis:{type:"category",data:rows.map(r=>r.name),axisLabel:{color:"#334155",fontSize:11.5},axisLine:{show:false},axisTick:{show:false}},
    series:[{type:"bar",data:rows.map(r=>({value:r.value,itemStyle:{color:PC[r.name]||"#2563eb",borderRadius:[0,3,3,0]}})),barMaxWidth:16,label:{show:true,position:"right",color:"#5d6f8a",fontSize:11}}]});
})();
/* 近30天出勤覆盖天数 */
(function(){
  const el=document.getElementById("chPersonDays"); if(!el) return;
  const ch=echarts.init(el);
  const data = DATA.people.map(p=>({name:p,value:DATA.person_daily[p].filter(v=>v>0).length}));
  const rows = data.slice().reverse();
  ch.setOption({grid:{left:8,right:34,top:8,bottom:8,containLabel:true},tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},
    xAxis:{type:"value",minInterval:1,max:30,splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    yAxis:{type:"category",data:rows.map(r=>r.name),axisLabel:{color:"#334155",fontSize:11.5},axisLine:{show:false},axisTick:{show:false}},
    series:[{type:"bar",data:rows.map(r=>({value:r.value,itemStyle:{color:PC[r.name]||"#2563eb",borderRadius:[0,3,3,0]}})),barMaxWidth:16,label:{show:true,position:"right",color:"#5d6f8a",fontSize:11,formatter:p=>p.value+"天"}}]});
})();

/* 不合格项 */
const fb = document.getElementById("fail");
if(DATA.fail.length===0){fb.innerHTML='<div class="empty">累计未发现安全确认不合格项</div>';}
else{
  fb.innerHTML = DATA.fail.map(r=>`<div class="fail-item">
    <div class="t"><span>${r.time} · ${r.inspector||"—"}</span><b>${shortRisk(r.risk||"低风险")}</b></div>
    <div class="m">${r.cat} · ${r.item||"—"}</div>
    <div class="u">现场负责人：${r.leader||"—"}</div>
    <div class="bad">${r.fail_items.map(x=>`<span class="badge">${x}未通过</span>`).join("")}</div>
  </div>`).join("");
}

/* 横向条形 */
function bar(id, data, colors){
  const el=document.getElementById(id); if(!el) return;
  const ch=echarts.init(el); const rows=data.slice().reverse();
  ch.setOption({grid:{left:8,right:30,top:8,bottom:8,containLabel:true},tooltip:{trigger:"axis",axisPointer:{type:"shadow"}},
    xAxis:{type:"value",splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    yAxis:{type:"category",data:rows.map(r=>r.name),axisLabel:{color:"#334155",fontSize:11.5,width:96,overflow:"truncate"},axisLine:{show:false},axisTick:{show:false}},
    series:[{type:"bar",data:rows.map(r=>r.value),barMaxWidth:16,itemStyle:{color:p=>colors?colors(p.name):CAT_COLORS[p.dataIndex%CAT_COLORS.length],borderRadius:[0,3,3,0]},label:{show:true,position:"right",color:"#5d6f8a",fontSize:11}}]});
  return ch;
}
bar("chCat", DATA.cats);
bar("chRisk", DATA.risks, n=>RISK_COLOR[n]||"#2563eb");
bar("chLvl", DATA.lvls);
bar("chSpec", DATA.specs);
bar("chItem", DATA.items);

/* 近30天 */
(function(){
  const el=document.getElementById("chDay"); if(!el) return; const ch=echarts.init(el);
  const last=DATA.dnums.length-1;
  ch.setOption({grid:{left:4,right:10,top:22,bottom:4,containLabel:true},tooltip:{trigger:"axis"},
    xAxis:{type:"category",data:DATA.ddates,axisLabel:{color:"#5d6f8a",fontSize:10,interval:4},axisLine:{lineStyle:{color:"#d0d7e2"}}},
    yAxis:{type:"value",splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    series:[{type:"bar",data:DATA.dnums,barMaxWidth:14,itemStyle:{color:p=>p.dataIndex===last?"#f97316":"#2563eb",borderRadius:[2,2,0,0]},label:{show:true,position:"top",color:"#5d6f8a",fontSize:9,formatter:p=>p.dataIndex===last?p.value:""}}]});
})();

/* 按月 */
(function(){
  const el=document.getElementById("chMon"); if(!el) return; const ch=echarts.init(el);
  ch.setOption({grid:{left:4,right:10,top:22,bottom:4,containLabel:true},tooltip:{trigger:"axis"},
    xAxis:{type:"category",data:DATA.monthly.map(r=>r.month),axisLabel:{color:"#5d6f8a",fontSize:10,interval:1},axisLine:{lineStyle:{color:"#d0d7e2"}}},
    yAxis:{type:"value",splitLine:{lineStyle:{color:"rgba(34,48,74,.08)"}},axisLabel:{color:"#5d6f8a",fontSize:11}},
    series:[{type:"line",data:DATA.monthly.map(r=>r.value),smooth:true,symbolSize:6,lineStyle:{width:3,color:"#0d9488"},itemStyle:{color:"#0d9488"},areaStyle:{color:"rgba(13,148,136,.10)"}}]});
})();

/* 按日按人明细表（近30天） */
(function(){
  const wrap=document.getElementById("personTableWrap"); if(!wrap) return;
  const dates=DATA.ddates, people=DATA.people, daily=DATA.person_daily;
  let h='<table style="min-width:700px"><thead><tr><th style="width:64px">日期</th>'+people.map(p=>`<th style="text-align:center;white-space:nowrap">${p}</th>`).join('')+'</tr></thead><tbody>';
  for(let i=dates.length-1;i>=0;i--){
    h+=`<tr><td style="white-space:nowrap">${dates[i]}</td>`;
    for(const p of people){ const v=daily[p][i];
      h+=`<td style="text-align:center">${v>0?`<b style="color:${PC[p]}">${v}</b>`:"·"}</td>`; }
    h+='</tr>';
  }
  h+='</tbody></table>';
  wrap.innerHTML=h;
})();

window.addEventListener("resize",()=>{["chDay","chMon","chCat","chRisk","chLvl","chSpec","chItem","chPersonDay","chPersonTot","chPersonDays"].forEach(id=>{const e=document.getElementById(id);if(e&&e.__ec)e.__ec.resize();});});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
