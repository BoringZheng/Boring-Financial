Hello! Welcome to Boring's Financial. This is a project aiming to give you a method to manage your money. 

This project could show you how much you spend on your own categories and how much you spend in total every month or any time you like(you can change the code to do that).

In fact, you have two options to deploy the project. Both methods need your wechat bills and Alipay bills.

## To get your Bills

### 1. To get Wechat bills

Wechat -> 我的 -> 服务 -> 钱包 -> 账单 -> 右上角 -> 下载账单 -> 用于个人对账

### 2. To get Alipay bills

Alipay -> 我的 -> 账单-> 右上角 -> 开具交易流水证明 -> 用于个人对账

Notice that, you should delete the redundant parts in the chart. Make sure the first line of the chart should be like this:

![image.png](https://boring-picture1.oss-cn-hangzhou.aliyuncs.com/20250821012109188.png)


## To deploy the project

### 1. Via Obsidian

To use this project, you need obsidian, file sync(or you can copy the file every time) on your computer.

First, you should download your wechat or alipay bills in folder input. And notice that, you should delete the head in the xlsx or csv, the table's first row should be 交易时间 etc.

Then, you could open category_map.csv in your vscode and change your own category. Notice that, don't open it with wps or microsoft office.

And then you could run merge_bills.py, and then sync folder output and your obsidian volt folder.

In your obsidian folder, you should download and enable the community plugins dataviewer, and allow jvavscript query.

Last, make a new md file like this:


```dataviewjs

/***** ===== 配置区 ===== *****/
const CSV_PATH = "merged.csv";   // ← 改成你的 CSV 路径
const CURRENCY = "¥";                 // 显示货币符号
const MONTHS_BACK = 12;               // 本月起往前 N 个月（含本月）
const TOP_MERCHANTS = 10;             // 每月 Top 商家数量（支出）
const BIG_TOP = 10;                   // 每月大额支出显示条数
const BIG_MIN = 0;                    // 大额支出最小金额门槛（例如 200)

/***** ===== 工具函数 ===== *****/
function splitCsvLine(l){
  // 按逗号切分，忽略被双引号包裹的逗号
  return l.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(s=>s.replace(/^"|"$/g,"").trim());
}
function fmt(n){ return CURRENCY + (Math.round(n*100)/100).toFixed(2); }
function ym(d){ return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`; }
function monthStart(d){ return new Date(d.getFullYear(), d.getMonth(), 1); }
function monthEnd(d){ return new Date(d.getFullYear(), d.getMonth()+1, 0, 23,59,59); }
function sum(arr, sel){ return arr.reduce((a,x)=>a + (sel ? sel(x) : x), 0); }
function groupSum(rows, keyFn, valFn){
  const m = new Map();
  for(const r of rows){
    const k = keyFn(r);
    m.set(k, (m.get(k)||0) + valFn(r));
  }
  return m;
}

/***** ===== 读取 CSV ===== *****/
const raw = await dv.io.load(CSV_PATH);
if (!raw){ dv.paragraph("未找到文件：" + CSV_PATH); return; }
const lines = raw.trim().split(/\r?\n/);
if (lines.length < 2){ dv.paragraph("CSV 为空"); return; }
const header = lines[0].split(",").map(s=>s.trim());
const idx = Object.fromEntries(header.map((h,i)=>[h,i]));

// 解析为标准对象
let rows = lines.slice(1).map(l=>{
  const c = splitCsvLine(l);
  const d = new Date(c[idx["date"]]);
  return {
    date: d,
    month: isNaN(d) ? "" : ym(d),
    type: (c[idx["type"]]||"").trim(),              // "支出"/"收入"
    category: (c[idx["category"]]||"").trim() || "未分类",
    subcategory: (c[idx["subcategory"]]||"").trim(),
    amount: parseFloat(c[idx["amount"]]||"0") || 0,
    platform: (c[idx["platform"]]||"").trim(),
    merchant: (c[idx["merchant"]]||"").trim() || "（无商家）",
    item: (c[idx["item"]]||"").trim(),
    method: (c[idx["method"]]||"").trim(),
    status: (c[idx["status"]]||"").trim(),
    note: (c[idx["note"]]||"").trim()
  };
}).filter(r=>!isNaN(r.date));

/***** ===== 生成月份列表：本月 → 往前 N-1 个月 ===== *****/
const now = new Date();
const months = [];
for (let i = 0; i < MONTHS_BACK; i++){
  const d = new Date(now.getFullYear(), now.getMonth()-i, 1);
  months.push(ym(d));
}

/***** ===== 按月渲染 ===== *****/
dv.header(1, "年度财务总览（逐月）");

for(const m of months){
  const start = new Date(Number(m.slice(0,4)), Number(m.slice(5,7))-1, 1);
  const end = monthEnd(start);

  const rowsM = rows.filter(r => r.date >= start && r.date <= end);
  const expM = rowsM.filter(r => r.type.includes("支出"));
  const incM = rowsM.filter(r => r.type.includes("收入"));

  const expTotal = sum(expM, r=>r.amount);
  const incTotal = sum(incM, r=>r.amount);
  const netTotal = incTotal - expTotal;

  // 分类汇总（支出）
  const catMap = groupSum(expM, r=>r.category, r=>r.amount);
  const cats = Array.from(catMap.entries()).sort((a,b)=>b[1]-a[1]);

  // Top 商家（支出）
  const merMap = groupSum(expM, r=>r.merchant, r=>r.amount);
  const merchants = Array.from(merMap.entries()).sort((a,b)=>b[1]-a[1]).slice(0, TOP_MERCHANTS);

  // 大额支出（支出 Top N 或超过门槛）
  let big = expM.slice()
    .filter(r => r.amount >= BIG_MIN)
    .sort((a,b)=>b.amount - a.amount)
    .slice(0, BIG_TOP)
    .map(r => [
      r.date.toISOString().slice(0,10),
      r.merchant,
      r.item || r.note || "",
      fmt(r.amount),
      r.category
    ]);

  // —— 标题 + KPI
  dv.header(2, `${m}`);
  dv.table(["指标","金额"], [
    ["支出", fmt(expTotal)],
    ["收入", fmt(incTotal)],
    ["净流", fmt(netTotal)]
  ]);
  

  // —— 支出分类汇总
  dv.header(3, "支出分类");
  if (cats.length){
    dv.table(["分类","金额"], cats.map(([k,v]) => [k, fmt(v)]));
  }else{
    dv.paragraph("_本月无支出数据_");
  }

  // —— Top 商家（支出）
  dv.header(3, `Top 商家（支出，前 ${TOP_MERCHANTS}）`);
  if (merchants.length){
    dv.table(["商家","金额"], merchants.map(([k,v]) => [k, fmt(v)]));
  }else{
    dv.paragraph("_本月无支出商家_");
  }

  // —— 大额支出
  dv.header(3, `大额支出（Top ${BIG_TOP}${BIG_MIN>0? "，门槛≥"+fmt(BIG_MIN):""}）`);
  if (big.length){
    dv.table(["日期","商家","摘要","金额","分类"], big);
  }else{
    dv.paragraph("_无大额支出_");
  }

  // 分隔线更清晰
  dv.el("hr", "");
}
```


### 2. Deploy it as a software

In this way, you should download the newest release, and put your own bills in folder input. Then you could just click the .exe file to get your financial report.