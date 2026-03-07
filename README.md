<div align="center">

# 📈 股票智能分析系统

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![CI](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/)

> 🤖 基于 AI 大模型的 A股/港股/美股自选股智能分析系统，每日自动分析并推送「决策仪表盘」到企业微信/飞书/Telegram/邮箱

[**功能特性**](#-功能特性) · [**快速开始**](#-快速开始) · [**推送效果**](#-推送效果) · [**完整指南**](docs/full-guide.md) · [**常见问题**](docs/FAQ.md) · [**更新日志**](docs/CHANGELOG.md)

简体中文 | [English](docs/README_EN.md) | [繁體中文](docs/README_CHT.md)

</div>

## 💖 赞助商 (Sponsors)
<div align="center">
  <a href="https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis" target="_blank">
    <img src="./sources/serpapi_banner_zh.png" alt="轻松抓取搜索引擎上的实时金融新闻数据 - SerpApi" height="160">
  </a>
</div>
<br>


## ✨ 功能特性

| 模块 | 功能 | 说明 |
|------|------|------|
| AI | 决策仪表盘 | 一句话核心结论 + 精确买卖点位 + 操作检查清单 |
| 分析 | 多维度分析 | 技术面（盘中实时 MA/多头排列）+ 筹码分布 + 舆情情报 + 实时行情 |
| 技术面模块 | 结构化技术评估 | 价格区间（支持“智能模式 / Rhino 价格区间(美股) / 人工判断区间(非美股)”切换；二级模式仅展示手动区间，支持手动新增/修改/删除并持久化，且“区间定义”支持自定义填写与展示；当前价格提示条按“从上到下首个下限低于当前价”的区间插入在其上方；操作栏为符号按钮并提供默认/悬浮态）+ 独立止跌见顶信号表（类型/日期/组合/强弱/未来7天与30天涨跌）+ 多指标解读（RSI/ASR/CC/SAR/MACD/KDJ/BIAS/KC/BBIBOLL/神奇九转） |
| 仓位管理模块 | 全球资产仓位看板 | Web 端一级导航页面（与首页/问股/设置并列）；支持“初始仓位 + 输出币种(RMB/HKD/USD) + 目标收益率”配置；自动获取 USD/CNY、HKD/CNY 汇率；持仓仅需录入资产分类 + 标的代码 + 持仓股数，系统自动拉取最新价格/币种并完成折算与收益计算；列表展示精简为“一级分类/名称/最新报价/总价值”，删除持仓需二次弹窗确认 |
| 历史管理 | 删除 + 数据刷新 | Web 端历史列表支持单条删除（含二次确认）；每个模块卡片内提供独立“更新”按钮，异步刷新且页面刷新不阻断任务；支持全量刷新（保留 Rhino 价格区间）与子模块刷新（价格区间/止跌见顶信号/技术指标/狙击点位/概览/新闻），并记录模块更新时间 |
| 市场 | 全球市场 | 支持 A股、港股、美股及美股指数（SPX、DJI、IXIC 等） |
| 复盘 | 大盘复盘 | 每日市场概览、板块涨跌；支持 cn(A股)/us(美股)/both(两者) 切换 |
| 图片识别 | 从图片添加 | 上传自选股截图，Vision LLM 自动提取股票代码，一键加入监控 |
| 回测 | AI 回测验证 | 自动评估历史分析准确率，方向胜率、止盈止损命中率 |
| **Agent 问股** | **策略对话** | **多轮策略问答，支持均线金叉/缠论/波浪等 11 种内置策略，Web/Bot/API 全链路** |
| 推送 | 多渠道通知 | 企业微信、飞书、Telegram、钉钉、邮件、Pushover |
| 自动化 | 定时运行 | GitHub Actions 定时执行，无需服务器 |

### 技术栈与数据来源

| 类型 | 支持 |
|------|------|
| AI 模型 | [AIHubMix](https://aihubmix.com/?aff=CfMq)、Gemini（免费）、OpenAI 兼容、DeepSeek、通义千问、Claude、Ollama、LiteLLM Proxy |
| 行情数据 | AkShare、Tushare、Pytdx、Baostock、YFinance |
| 新闻搜索 | Tavily、SerpAPI、Bocha、Brave |

> 注：美股历史数据与实时行情统一使用 YFinance，确保复权一致性

### 内置交易纪律

| 规则 | 说明 |
|------|------|
| 严禁追高 | 乖离率超阈值（默认 5%，可配置）自动提示风险；强势趋势股自动放宽 |
| 趋势交易 | MA5 > MA10 > MA20 多头排列 |
| 形态组合 | 读取项目根目录 `止跌见顶形态.xlsx`：命中「止跌形态」组合给出分批买入建议，命中「见顶形态」组合给出卖出/减仓建议 |
| 精确点位 | 买入价、止损价、目标价 |
| 检查清单 | 每项条件以「满足 / 注意 / 不满足」标记 |
| 新闻时效 | 可配置新闻最大时效（默认 3 天），避免使用过时信息 |

## 🚀 快速开始

### 方式一：GitHub Actions（推荐）

> 5 分钟完成部署，零成本，无需服务器。


#### 1. Fork 本仓库

点击右上角 `Fork` 按钮（顺便点个 Star⭐ 支持一下）

#### 2. 配置 Secrets

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**AI 模型配置（至少配置一个）**

> 💡 **推荐 [AIHubMix](https://aihubmix.com/?aff=CfMq)**：一个 Key 即可使用 Gemini、GPT、Claude、DeepSeek 等全球主流模型，无需科学上网，含免费模型（glm-5、gpt-4o-free 等），付费模型高稳定性无限并发。本项目可享 **10% 充值优惠**。

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `AIHUBMIX_KEY` | [AIHubMix](https://aihubmix.com/?aff=CfMq) API Key，一 Key 切换使用全系模型，免费模型可用 | 可选 |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) 获取免费 Key（需科学上网） | 可选 |
| `ANTHROPIC_API_KEY` | [Anthropic Claude](https://console.anthropic.com/) API Key | 可选 |
| `ANTHROPIC_MODEL` | Claude 模型（如 `claude-3-5-sonnet-20241022`） | 可选 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（支持 DeepSeek、通义千问等） | 可选 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址（如 `https://api.deepseek.com/v1`） | 可选 |
| `OPENAI_MODEL` | 模型名称（如 `gemini-3.1-pro-preview`、`gemini-3-flash-preview`、`gpt-5.2`） | 可选 |
| `OPENAI_VISION_MODEL` | 图片识别专用模型（部分第三方模型不支持图像；不填则用 `OPENAI_MODEL`） | 可选 |

> 注：AI 优先级 Gemini > Anthropic > OpenAI（含 AIHubmix），至少配置一个。`AIHUBMIX_KEY` 无需配置 `OPENAI_BASE_URL`，系统自动适配。图片识别需 Vision 能力模型。DeepSeek 思考模式（deepseek-reasoner、deepseek-r1、qwq、deepseek-chat）按模型名自动识别，无需额外配置。

<details>
<summary><b>通知渠道配置</b>（点击展开，至少配置一个）</summary>


| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `WECHAT_WEBHOOK_URL` | 企业微信 Webhook URL | 可选 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | 可选 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（@BotFather 获取） | 可选 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可选 |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID (用于发送到子话题) | 可选 |
| `EMAIL_SENDER` | 发件人邮箱（如 `xxx@qq.com`） | 可选 |
| `EMAIL_PASSWORD` | 邮箱授权码（非登录密码） | 可选 |
| `EMAIL_RECEIVERS` | 收件人邮箱（多个用逗号分隔，留空则发给自己） | 可选 |
| `EMAIL_SENDER_NAME` | 邮件发件人显示名称（默认：daily_stock_analysis股票分析助手） | 可选 |
| `STOCK_GROUP_N` / `EMAIL_GROUP_N` | 股票分组发往不同邮箱（如 `STOCK_GROUP_1=600519,300750` `EMAIL_GROUP_1=user1@example.com`） | 可选 |
| `PUSHPLUS_TOKEN` | PushPlus Token（[获取地址](https://www.pushplus.plus)，国内推送服务） | 可选 |
| `PUSHPLUS_TOPIC` | PushPlus 群组编码（一对多推送，配置后消息推送给群组所有订阅用户） | 可选 |
| `SERVERCHAN3_SENDKEY` | Server酱³ Sendkey（[获取地址](https://sc3.ft07.com/)，手机APP推送服务） | 可选 |
| `CUSTOM_WEBHOOK_URLS` | 自定义 Webhook（支持钉钉等，多个用逗号分隔） | 可选 |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | 自定义 Webhook 的 Bearer Token（用于需要认证的 Webhook） | 可选 |
| `WEBHOOK_VERIFY_SSL` | Webhook HTTPS 证书校验（默认 true）。设为 false 可支持自签名证书。警告：关闭有严重安全风险，仅限可信内网 | 可选 |
| `SINGLE_STOCK_NOTIFY` | 单股推送模式：设为 `true` 则每分析完一只股票立即推送 | 可选 |
| `REPORT_TYPE` | 报告类型：`simple`(精简) 或 `full`(完整)，Docker环境推荐设为 `full` | 可选 |
| `REPORT_SUMMARY_ONLY` | 仅分析结果摘要：设为 `true` 时只推送汇总，不含个股详情 | 可选 |
| `ANALYSIS_DELAY` | 个股分析和大盘分析之间的延迟（秒），避免API限流，如 `10` | 可选 |
| `MERGE_EMAIL_NOTIFICATION` | 个股与大盘复盘合并推送（默认 false），减少邮件数量 | 可选 |

> 至少配置一个渠道，配置多个则同时推送。更多配置请参考 [完整指南](docs/full-guide.md)

</details>

**其他配置**

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `STOCK_LIST` | 自选股代码，如 `600519,hk00700,AAPL,TSLA` | ✅ |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/) 搜索 API（新闻搜索） | 推荐 |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/baidu-search-api?utm_source=github_daily_stock_analysis) 全渠道搜索 | 可选 |
| `BOCHA_API_KEYS` | [博查搜索](https://open.bocha.cn/) Web Search API（中文搜索优化，支持AI摘要，多个key用逗号分隔） | 可选 |
| `BRAVE_API_KEYS` | [Brave Search](https://brave.com/search/api/) API（隐私优先，美股优化，多个key用逗号分隔） | 可选 |
| `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro/weborder/#/login?reg=834638 ) Token | 可选 |
| `WECHAT_MSG_TYPE` | 企微消息类型，默认 markdown，支持配置 text 类型，发送纯 markdown 文本 | 可选 |
| `NEWS_MAX_AGE_DAYS` | 新闻最大时效（天），默认 3，避免使用过时信息 | 可选 |
| `BIAS_THRESHOLD` | 乖离率阈值（%），默认 5.0，超过提示不追高；强势趋势股自动放宽 | 可选 |
| `AGENT_MODE` | 开启 Agent 策略问股模式（`true`/`false`，默认 false） | 可选 |
| `AGENT_SKILLS` | 激活的策略（逗号分隔），`all` 启用全部 11 个；不配置时默认 4 个，详见 `.env.example` | 可选 |
| `AGENT_MAX_STEPS` | Agent 最大推理步数（默认 10） | 可选 |
| `AGENT_STRATEGY_DIR` | 自定义策略目录（默认内置 `strategies/`） | 可选 |
| `TRADING_DAY_CHECK_ENABLED` | 交易日检查（默认 `true`）：非交易日跳过执行；设为 `false` 或使用 `--force-run` 强制执行 | 可选 |

#### 3. 启用 Actions

`Actions` 标签 → `I understand my workflows, go ahead and enable them`

#### 4. 手动测试

`Actions` → `每日股票分析` → `Run workflow` → `Run workflow`

#### 完成

默认每个**工作日 18:00（北京时间）**自动执行，也可手动触发。默认非交易日（含 A/H/US 节假日）不执行；可使用 `TRADING_DAY_CHECK_ENABLED=false` 或 `--force-run` 强制执行。

### 方式二：本地运行 / Docker 部署

```bash
# 克隆项目
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git && cd daily_stock_analysis

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env && vim .env

# 运行分析
python main.py
```

> Docker 部署、定时任务配置请参考 [完整指南](docs/full-guide.md)
> 桌面客户端打包请参考 [桌面端打包说明](docs/desktop-package.md)

## 📱 推送效果

### 决策仪表盘
```
🎯 2026-02-08 决策仪表盘
共分析3只股票 | 🟢买入:0 🟡观望:2 🔴卖出:1

📊 分析结果摘要
⚪ 中钨高新(000657): 观望 | 评分 65 | 看多
⚪ 永鼎股份(600105): 观望 | 评分 48 | 震荡
🟡 新莱应材(300260): 卖出 | 评分 35 | 看空

⚪ 中钨高新 (000657)
📰 重要信息速览
💭 舆情情绪: 市场关注其AI属性与业绩高增长，情绪偏积极，但需消化短期获利盘和主力流出压力。
📊 业绩预期: 基于舆情信息，公司2025年前三季度业绩同比大幅增长，基本面强劲，为股价提供支撑。

🚨 风险警报:

风险点1：2月5日主力资金大幅净卖出3.63亿元，需警惕短期抛压。
风险点2：筹码集中度高达35.15%，表明筹码分散，拉升阻力可能较大。
风险点3：舆情中提及公司历史违规记录及重组相关风险提示，需保持关注。
✨ 利好催化:

利好1：公司被市场定位为AI服务器HDI核心供应商，受益于AI产业发展。
利好2：2025年前三季度扣非净利润同比暴涨407.52%，业绩表现强劲。
📢 最新动态: 【最新消息】舆情显示公司是AI PCB微钻领域龙头，深度绑定全球头部PCB/载板厂。2月5日主力资金净卖出3.63亿元，需关注后续资金流向。

---
生成时间: 18:00
```

### 大盘复盘
```
🎯 2026-01-10 大盘复盘

📊 主要指数
- 上证指数: 3250.12 (🟢+0.85%)
- 深证成指: 10521.36 (🟢+1.02%)
- 创业板指: 2156.78 (🟢+1.35%)

📈 市场概况
上涨: 3920 | 下跌: 1349 | 涨停: 155 | 跌停: 3

🔥 板块表现
领涨: 互联网服务、文化传媒、小金属
领跌: 保险、航空机场、光伏设备
```

### 三地市场复盘（US/HK/A）

新增模块：`modules/daily_review/`，支持一键产出三地联动复盘报告（宏观锚、流动性、板块主线、持仓异动、仓位建议）。

手动运行：

```bash
python3 scripts/run-daily-review.py
```

可选参数：

- `--send-telegram`：推送到 Telegram
- `--use-llm`：启用 LLM 摘要

输出文件：

- `reports/review_YYYYMMDD.md`

## ⚙️ 配置说明

> 📖 完整环境变量、定时任务配置请参考 [完整配置指南](docs/full-guide.md)


## 🖥️ Web 界面

![img.png](sources/fastapi_server.png)

包含完整的配置管理、任务监控和手动分析功能。

历史报告页支持两类刷新：
- 「相关资讯」支持手动刷新，触发一次回源搜索补齐旧记录中缺失的新闻条目。
- 「数据更新」支持当前股票全量刷新（保留 Rhino 价格区间）或按子模块局部刷新（如止跌见顶信号、技术指标、狙击点位、仓位管理等）。
- 左侧导航栏不再展示「问股」「回测」；两个模块入口已迁移到首页顶部快捷入口。
- 首页报告区不再重复展示「追问 AI」按钮，问股入口统一使用首页顶部快捷按钮。

组合管理模块已扩展 `src/portfolio/`，当前已包含：
- `analysis/`：组合健康诊断、跨市场环境评分、异常检测、再平衡计划
- `data/`：宏观、流动性、板块数据抓取已接入真实行情序列与现有数据源管理器，失败时自动回退为空值
- `report/`：Markdown 报告渲染与 LLM 摘要回退
- `runner.py`：支持从配置 JSON 构建组合，并可独立串起组合复盘流程
- `storage.py`：新增 `portfolio_snapshots` 每日快照落库
- `config.py` + `config_registry.py`：已接入 `PORTFOLIO_*` 配置项和 Web 配置元数据
- `main.py`：新增 `--portfolio-review` 独立入口
- `market_review.py`：大盘复盘完成后可按配置自动触发组合复盘
- Web 设置页已支持 `portfolio` 分类，`PORTFOLIO_HOLDINGS`/`PORTFOLIO_STOCK_TAGS` 可在结构化编辑器与原始 JSON 间切换
- 组合复盘数据源已与仓位管理打通：手动触发和大盘复盘自动触发时，默认优先使用当前仓位管理持仓，`PORTFOLIO_HOLDINGS` 仅作为兜底
- CLI `python main.py --portfolio-review` 也已与仓位管理数据源打通，不再只依赖 `PORTFOLIO_HOLDINGS`
- 仓位管理页已支持手动触发组合复盘，并查看最新组合复盘、历史快照及总资产/健康分趋势
- 组合复盘最新结果与历史快照读取已改为基于原始快照数据返回，避免 session 关闭后出现读取失败
- 手动重复生成当日组合复盘时，最新快照的 `generated_at` 会刷新为本次生成时间
- 组合市场口径已统一使用 `A`，历史或外部数据中的 `CN` 别名会自动归一化，不再导致健康评分或再平衡报错
- 仓位管理页面已移除与组合复盘重叠的“每日资产管理复盘”展示块与历史块，主阅读入口统一收敛到“组合复盘”
- 组合复盘正文已升级为章节卡片 + Markdown 富文本的阅读面板，不再只有纯文字；当前结果与历史快照统一使用相同样式展开
- 组合复盘已移除与仓位分布重复的市场暴露表、持仓明细表以及原始报告重复块，阅读重点只保留摘要与章节内容
- 组合复盘的 LLM 摘要已修复为兼容现有分析器调用链路，不再因方法不匹配而长期退回 `(AI 摘要不可用)`
- 组合复盘页面已进一步精简：不再单独重复展示总资产、现金占比、各市场暴露、健康分/等级概览，当前结果与历史记录默认直接展示 `AI 建议` 卡片，不再提供展开/收起
- 异常告警与交易建议已改为卡片式双列布局；健康评分、市场环境、板块风格会在宽屏同排展示，在窄屏自动折行
- 交易建议已补充预计数量，并统一使用中文市场名与中文资产名称；组合复盘正文中的代码/市场简称也会自动替换为中文名称
- 交易建议现会优先读取每只股票的一手股数（board lot / lot size），并按有效交易单位取整后再给出数量；A 股默认按 100 股、港股优先使用标的 lot size 并回退到 100 股、美股默认按 1 股
- 组合复盘的健康分已改为顶部标签式展示；市场环境已合并进三行市场板块卡片，按 `美股 / 港股 / A 股` 纵向展示各自的主线、强弱与解读
- 组合复盘卡片右上角已新增「每日复盘答疑」入口，会带着当天组合现状、市场板块摘要和完整组合复盘内容跳转到 `/chat`，并在同一会话里持续携带上下文
- 仓位管理主仪表盘已按 `prd/chicang.md` 重构为左右双栏：左侧是“目标达成”，右侧是“持仓概览”；主页面不再拆成“基础信息 / 仓位分布 / 资产分布总览 / 目标收益进度”四块
- “目标达成”面板现只保留初始仓位、收益额、收益率、距离目标差值四个结果卡；目标收益率和计算币种不再在只读态展示，仅在编辑态配置，且所有可见数值都支持点击隐藏
- “持仓概览”面板现使用二级类目饼图 + 图例表格展示持仓结构，右上角“修改持仓”会直接打开主页面持仓管理弹窗；鼠标悬停饼图时，右侧对应二级类目会放大高亮
- 持仓概览的饼图联动高亮已改为覆盖当前二级类目所在位置的悬浮浮层：底层行不再放大、不再改字重和字号，只在原位置上方做覆盖展示，不影响其他模块布局
- `src/portfolio/` 侧的 `Portfolio` 模型与报告渲染现已补齐 `output_currency` 语义，组合复盘目标追踪和持仓金额会按选定币种输出，不再写死 `CNY`
- 底部“宏观/地缘事件”“备注”输入区已从仓位管理页和历史报告编辑页移除
- `tests/`：覆盖健康评分、环境评分、异常检测、调仓约束，以及配置/落库/挂接集成测试

仓位管理模块（一级页面 `/position-management`）支持：
- 录入基础信息：初始仓位、输出币种（RMB/HKD/USD）、目标收益率，可修改并保存。
- 自动汇率：系统自动获取 USD/CNY、HKD/CNY 并用于折算。
- 持仓录入：按资产一级/二级分类，仅录入标的代码和持仓股数；最新价格、币种、汇率自动获取并展示。
  资产一级分类固定六大类：权益类、加密货币、贵金属、债券、货币基金、现金；
  权益类二级分类仅支持：A股、港股、美股、ETF。
- 持仓区域拆分为两个子模块：
  - 「仓位分布」仅展示二级类目名称、总价值与占比总资产比例；
  - 右上角「资产明细」入口跳转到二级页面 `/position-management/assets`，独立查看与编辑完整持仓。
- 资产明细录入交互改为弹窗：新增/编辑均在弹窗中完成，保存成功后 toast 提醒并自动关闭弹窗。
- 资产明细名称展示修复：后端不再把股票代码写入名称字段作为兜底，前端会清洗历史“名称=代码”的数据，避免名称列误显示代码。
- 现金类持仓支持无代码录入，按现金币种自动折算并参与总资产与分布计算。
- 持仓列表展示默认仅显示：一级分类、名称（股票优先展示名称）、最新报价、总价值；删除操作有弹窗确认。
- 报价展示为“整数 + 对应币种单位”；编辑持仓时回车可自动保存，并在保存后自动更新总价值。
- 持仓区提供“刷新”符号按钮，可一键重拉权益类资产报价；刷新前会自动保存未持久化的持仓改动，避免数量被覆盖；刷新成功后页面右上角 toast 提示结果。
- 持仓列表按总价值降序展示；并计算一级资产分类在整体资产中的占比（保留两位小数）用于展示。
- 所有可填写项统一补充了保存交互：保存中状态提示、成功/失败提醒、保存进行时控件禁用（历史报告中的价格区间与仓位管理填写项同样生效）。
- 仓位管理首屏加载已优化：默认优先读取本地已缓存的仓位快照，避免每次进入页面都同步回源拉取全部行情；如需最新行情可点击刷新按钮手动更新。
- 数据尚未加载完成时，子模块显示“加载中”占位态，并禁用交互控件，避免误操作。
- 每日仓位复盘新增：按二级分类输出“名称/总价值/占比”，并结合年度目标、当前市场复盘与资产分布生成 AI 建议；在 Telegram 配置可用时自动推送每日仓位复盘。
- 仓位管理页面顶部新增「复盘推送」按钮：可手动触发一次“仓位复盘 + AI 建议 + Telegram 推送”，并在页面内显示操作结果提示。
- 每日资产管理复盘改为固定三段结构并在页面内展示：
  - `🌪️ 宏观与跨市场风向`
  - `📊 组合偏离度与目标追踪（含沪深300/纳斯达克对比）`
  - `💡 行动与网格策略建议（风险预警 + 区间参考）`
- 仓位管理主页面中，「每日资产管理复盘」模块已调整为置顶展示（位于基础信息之前）。
- 复盘解析兼容历史旧格式（`二级分类资产分布/目标与进度/AI资产配置建议`），避免 Telegram 已推送但 Web 页面无内容展示。
- 每日复盘新增「查看过往复盘」入口，进入二级页 `/position-management/reviews` 查看历史每日复盘。
- 每日复盘支持手动填写批注并保存，支持主页面当日复盘与历史复盘逐日批注。
- 仓位管理首页复盘卡片默认仅展示一句话提炼，支持点击「展开/收起」查看完整复盘内容。
- 复盘内容截断策略已调整为展示完整文本（兼容旧格式解析与新格式生成），避免页面显示不全。
- 每次复盘均会在本地保存 Markdown 文件到 `reports/position_review_YYYYMMDD.md`，并支持前端读取最近一份复盘展示。
- 每日可修改并保存，自动更新收益额、收益率、资产分布与热力图。
- 涨跌幅热力图按涨跌幅从高到低排序展示（主仓位页与历史仓位模块一致）。
- 资产明细新增/编辑弹窗在保存中会禁用输入与选择控件，保存完成前不可继续修改。
- 仓位管理页文字对比度已提升，弱提示与次级文字在深色背景下更易读。
- 仓位管理编辑提醒统一改为右侧 Toast 提示，成功提示 3 秒后自动消失。
- 资产明细名称增加离线兜底映射（常见 A 股/港股/美股），在行情源不可用时仍尽量展示股票名称。
- 资产明细表格新增「数量」列。
- 资产明细中的占比口径调整为“该资产占整体资产比例”（单资产维度）。
- 资产明细名称展示优先中文（按常见代码映射），无中文映射时再回退原始名称。

**可选密码保护**：在 `.env` 中设置 `ADMIN_AUTH_ENABLED=true` 可启用 Web 登录，首次访问在网页设置初始密码，保护 Settings 中的 API 密钥等敏感配置。详见 [完整指南](docs/full-guide.md)。

### 从图片添加股票

在 **设置 → 基础设置** 中找到「从图片添加」区块，拖拽或选择自选股截图（如 APP 持仓页、行情列表截图），系统会通过 Vision AI 自动识别股票代码并合并到自选列表。

**配置与限制**：
- 需配置 `GEMINI_API_KEY`、`ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 中至少一个（Vision 能力模型）
- 支持 JPG、PNG、WebP、GIF，单张最大 5MB；请求超时 60 秒

**API 调用**：`POST /api/v1/stocks/extract-from-image`，表单字段 `file`，返回 `{ "codes": ["600519", "300750", ...] }`。详见 [完整指南](docs/full-guide.md)。

### 🤖 Agent 策略问股

在 `.env` 中设置 `AGENT_MODE=true` 后启动服务，访问 `/chat` 页面即可开始多轮策略问答。

- **选择策略**：均线金叉、缠论、波浪理论、多头趋势等 11 种内置策略
- **自然语言提问**：如「用缠论分析 600519」，Agent 自动调用实时行情、K线、技术指标、新闻等工具
- **流式进度反馈**：实时展示 AI 思考路径（行情获取 → 技术分析 → 新闻搜索 → 生成结论）
- **多轮对话**：支持追问上下文，会话历史持久化保存
- **Bot 支持**：`/ask <code> [strategy]` 命令触发策略分析
- **自定义策略**：在 `strategies/` 目录下新建 YAML 文件即可添加策略，无需写代码

> **注意**：Agent 模式依赖外部 LLM（Gemini/OpenAI 等），每次对话会产生 API 调用费用。不影响非 Agent 模式（`AGENT_MODE=false` 或未设置）的正常运行。

### 启动方式

1. **编译前端** (首次运行需要)
   ```bash
   cd ./apps/dsa-web
   npm install && npm run build
   cd ../..
   ```

2. **启动服务**
   ```bash
   ./scripts/service-8001.sh start  # 推荐：固定 8001 启动（含端口占用与健康检查）
   python main.py --webui       # 启动 Web 界面 + 执行定时分析
   python main.py --webui-only  # 仅启动 Web 界面
   python main.py --serve-only --host 127.0.0.1 --port 8001  # 推荐：仅启动 API/Web 服务
   ```

   常用管理命令：
   ```bash
   ./scripts/service-8001.sh status
   ./scripts/service-8001.sh restart
   ./scripts/service-8001.sh stop
   ```

访问 `http://127.0.0.1:8001` 即可使用。

> 也可以使用 `python main.py --serve` (等效命令)

3. **健康检查**（可选）
   ```bash
   curl http://127.0.0.1:8001/api/health
   ```

## 🗺️ Roadmap

查看已支持的功能和未来规划：[更新日志](docs/CHANGELOG.md)

> 有建议？欢迎 [提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)


---

## ☕ 支持项目

如果本项目对你有帮助，欢迎支持项目的持续维护与迭代，感谢支持 🙏  
赞赏可备注联系方式，祝股市长虹

| 支付宝 (Alipay) | 微信支付 (WeChat) | Ko-fi |
| :---: | :---: | :---: |
| <img src="./sources/alipay.jpg" width="200" alt="Alipay"> | <img src="./sources/wechatpay.jpg" width="200" alt="WeChat Pay"> | <a href="https://ko-fi.com/mumu157" target="_blank"><img src="./sources/ko-fi.png" width="200" alt="Ko-fi"></a> |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

详见 [贡献指南](docs/CONTRIBUTING.md)

### 本地门禁（建议先跑）

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
```

如修改前端（`apps/dsa-web`）：

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

## 📄 License
[MIT License](LICENSE) © 2026 ZhuLinsen

如果你在项目中使用或基于本项目进行二次开发，
非常欢迎在 README 或文档中注明来源并附上本仓库链接。
这将有助于项目的持续维护和社区发展。

## 📬 联系与合作
- GitHub Issues：[提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)

## ⭐ Star History
**如果觉得有用，请给个 ⭐ Star 支持一下！**

<a href="https://star-history.com/#ZhuLinsen/daily_stock_analysis&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ZhuLinsen/daily_stock_analysis&type=Date" />
 </picture>
</a>

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对使用本项目产生的任何损失负责。

---
