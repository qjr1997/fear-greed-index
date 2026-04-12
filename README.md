# A股恐惧贪婪指数 (Fear & Greed Index)

基于5大指标的中国股市情绪指标，帮助投资者判断市场处于恐惧还是贪婪状态。

![FGI](https://img.shields.io/badge/FGI-39.7-blue)
![Data](https://img.shields.io/badge/Data-2017~2026-green)

## 🌐 在线访问

**https://qjr1997.github.io/fear-greed-index/**

## 📊 指标构成

| 指标 | 权重 | 说明 |
|------|------|------|
| 市场波动率 | 20% | VIX中国波指 |
| 股价强度 | 20% | 沪深300成分股252日新高比例 |
| 股指期货升贴水 | 20% | IF期货年化基差率 |
| 避险需求 | 20% | 股债收益差 |
| 成交量 | 20% | A股成交额历史分位 |

## 📁 文件说明

- `data.json` - 近252天数据（图表展示用，约33KB）
- `data_full.json` - 完整历史数据（2017年至今，约328KB）
- `index.html` - 网页主体
- `manifest.json` - PWA配置
- `sw.js` - Service Worker

## 🔄 数据更新

数据每日自动或手动更新，最新日期：2026-04-10

## 📈 最新数据

```
日期: 2026-04-10
FGI: 39.7 (恐惧)
Derivative: -0.4
```

## 🛠️ 技术栈

- 前端：原生 HTML + CSS + JavaScript
- 图表：Chart.js
- 数据源：AKShare (Python)
- 部署：GitHub Pages

---

*数据来源：腾讯财经、新浪财经、东方财富*
