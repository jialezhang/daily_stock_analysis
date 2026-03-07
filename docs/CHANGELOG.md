# Changelog

所有重要更改都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增（#minor）
- 🌍 **三地市场复盘模块（US/HK/A）**
  - 新增 `modules/daily_review/`：并发采集宏观/流动性/板块/持仓数据，输出三地仓位建议（进攻/平衡/防守）
  - 新增市场状态评分、板块资金偏好、异常告警（RED/YELLOW）与 Markdown 报告渲染
  - 新增可选 LLM 摘要与 Telegram 推送能力（MarkdownV2 转义、分段发送、失败重试）
  - 新增手动入口脚本 `scripts/run-daily-review.py`，报告落盘 `reports/review_YYYYMMDD.md`
- 🚀 **桌面端 CI 自动发布到 GitHub Releases**
  - 新增 `.github/workflows/desktop-release.yml`
  - 支持 Windows 安装包（exe）+ 免安装包（zip）与 macOS x64/arm64 DMG 并行构建
  - 支持 tag 触发自动发布，以及手动指定 `release_tag` 发布
- 📈 **盘中实时技术面**（Issue #234）
  - 技术面数据（MA5/MA10/MA20、多头排列）使用盘中实时价格计算，而非昨日收盘
  - 盘中分析时，将实时价作为虚拟 K 线追加到历史序列，重算均线与趋势判断
  - 报告「今日行情」与「均线系统」与当前价格一致，多头排列判断不再滞后
  - 配置项：`ENABLE_REALTIME_TECHNICAL_INDICATORS`（默认 `true`）；设为 `false` 可回退为昨日收盘逻辑
  - 非交易日或 `enable_realtime_quote` 关闭时保持原有行为
- 🧩 **Excel 形态组合交易信号**
  - 新增基于根目录 `止跌见顶形态.xlsx` 的形态共振规则加载（sheet: `止跌形态` / `见顶形态`）
  - 命中止跌组合时，趋势信号增加「分批买入」建议；命中见顶组合时，优先给出「卖出/减仓」建议
  - 分析上下文新增 `bottom_pattern_hits`、`top_pattern_hits`、`pattern_advice`，用于 Web/API/Agent 输出一致展示
- 📊 **技术面分析模块（每只股票）**
  - 新增结构化技术面模块：价格区间（箱体理论 + 斐波那契回撤 + 趋势线）与强/弱支撑阻力位
  - 新增近一年止跌/见顶信号回顾（基于 `止跌见顶形态.xlsx` 规则）
  - 新增技术参数评分：`RSI`、`ASR`、`CC(CCI14 代理)`、`SAR`、`MACD`、`KDJ`、`BIAS`、`KC`、`BBIBOLL`、`神奇九转` 与综合评分
  - 各技术指标新增解释说明（Web 端 `!` 悬浮提示）与“近期解读 + 买卖倾向”文本
  - 止跌/见顶信号展示增强：展示次数、时间范围与最近明细（不再仅显示简短片段）
  - Pipeline 将该模块注入分析上下文，Web 报告新增“技术面分析模块”展示区
- 💼 **仓位管理模块（Web/API）**
  - 仓位管理升级为 Web 一级导航页面（与首页/问股/设置并列），不再挂在单股票报告内
  - 新增全局接口：`GET /api/v1/position-management`、`PUT /api/v1/position-management`、`POST /api/v1/position-management/refresh`
  - 基础信息改为：`初始仓位 + 输出币种(RMB/HKD/USD) + 目标收益率`，支持修改保存
  - 汇率改为自动获取：USD/CNY、HKD/CNY 自动抓取并展示
  - 持仓录入改为轻量输入：仅录入“资产一级/二级分类 + 标的代码 + 持仓股数”，最新价格/币种/汇率自动获取并计算
  - 资产一级分类收敛为五大类：权益类、加密货币、贵金属、债券、货币基金；
    权益类二级分类限制为 A股、港股、美股、ETF
  - 新增每日仓位复盘：按二级分类输出“名称/总价值/占比”，并结合目标收益、市场复盘与资产分布生成 AI 建议
  - 每日仓位复盘自动推送到 Telegram（已配置 Telegram Bot Token/Chat ID 时）
  - 新增手动触发接口 `POST /api/v1/position-management/review-push`，Web 端仓位管理页顶部新增「复盘推送」按钮
  - 页面展示资产分布环图、涨跌热力图、收益额与目标进度看板
  - 新增 AI 风向建议区：根据持仓集中度、收益与波动输出再平衡/止盈止损提示
  - 持仓展示迭代为「仓位分布 + 资产明细」双模块：
    仓位分布仅展示二级类目名称/总价值/占比；右上角新增「资产明细」入口用于快速跳转
  - 「资产明细」改为二级页面（`/position-management/assets`）独立展示，不再在仓位管理主页面下方内联渲染
  - 资产明细新增/编辑交互改为弹窗录入，保存成功后提醒并自动关闭弹窗
  - 修复资产明细“名称显示代码”问题：名称缺失时不再回写代码到名称字段，并清洗历史脏数据展示
  - 新增一级资产分类「现金」，支持无代码现金持仓录入并自动按币种汇率折算，纳入资产分布与总值统计
  - 每日资产管理复盘升级为固定三段结构（宏观风向 / 目标追踪 / 行动建议），新增 `GET /api/v1/position-management/review/latest` 供前端展示最近复盘
  - 复盘内容持续以 Markdown 保存到本地 `reports/position_review_YYYYMMDD.md`
  - 仓位管理主页将「每日资产管理复盘」模块前置到顶部，优先展示当日复盘结论
  - 复盘解析新增历史格式兼容：旧版复盘（`二级分类资产分布/目标与进度/AI资产配置建议`）也可被 Web 端结构化展示
  - 新增复盘历史能力：`GET /api/v1/position-management/review/history`，并在前端新增二级页 `/position-management/reviews`
  - 新增复盘批注能力：`PUT /api/v1/position-management/review/{review_date}/note`，支持按日手动填写与保存批注
  - 资产明细名称增强：新增常见标的离线名称兜底映射，行情源不可用时不再整列为空
  - 资产明细展示迭代：新增“数量”列；占比改为“单资产占整体资产比例”；名称优先展示中文映射
  - 仓位管理首页复盘卡片新增“默认一句话提炼 + 展开/收起完整内容”交互
  - 复盘 section 文本改为完整展示，不再在后端生成/解析阶段做固定长度截断
- 🗑️ **历史记录删除能力（Web/API）**
  - 新增 `DELETE /api/v1/history/{record_id}`，支持按历史记录主键删除单条记录
  - Web 历史列表新增删除按钮与二次确认弹窗，删除后自动刷新列表
  - 删除当前已查看记录时，右侧报告自动清空，避免显示已删除数据
- 🔄 **单股历史报告数据刷新能力（Web/API）**
  - 新增 `POST /api/v1/history/{record_id}/refresh`，支持 `full` / `partial` 两种刷新模式
  - `full` 模式会刷新整条分析数据，但保留价格区间中的 `Rhino 价格区间`
  - `partial` 模式支持按模块刷新：`price_zones`、`pattern_signals`、`technical_indicators`、`sniper_points`、`summary`、`news`
  - Web 报告页新增“数据更新”控制区，支持手动触发全量刷新或子模块刷新
- 🧱 **Rhino 价格区间手动录入持久化（Web/API）**
  - 新增 `POST /api/v1/history/{record_id}/rhino-zones` 与 `DELETE /api/v1/history/{record_id}/rhino-zones/{zone_id}`
  - 手动新增/删除区间将写入历史记录 `technical_module.price_zones.rhino_zones`，页面刷新后仍保留
  - 前端手动区间来源改为后端持久化数据，不再仅前端临时态
- 🔄 **模块级异步更新任务与更新时间记录（Web/API）**
  - 新增 `POST /api/v1/history/{record_id}/modules/{module}/refresh` 与 `GET /api/v1/history/{record_id}/modules/refresh-jobs`
  - 报告页改为每个模块独立“更新”按钮，不再依赖顶部勾选区；更新任务异步执行，刷新页面后可继续查看任务进度
  - 新增 `raw_result.module_update_meta`，记录各模块 `last_updated_at/history/update_count`，用于前端显示模块更新时间
- 🧩 **Rhino 价格区间交互增强（Web/API）**
  - 新增 `PUT /api/v1/history/{record_id}/rhino-zones/{zone_id}`，支持手动区间在线修改并持久化
  - Rhino 模式新增右上角「增加区间」入口，点击后在页面内动态插入新增行（下限→上限→强度）
  - 价格区间展示改为结构化行数据：下限/上限/强度/区间定义（单行可展开）/操作栏（删除、修改）
  - 在区间列表中按当前价格位置插入高亮提示行并给出操作建议；支持“现有模式 / Rhino 价格区间”切换，存在 Rhino 数据时默认展示 Rhino
- 📢 **PushPlus 群组推送**：新增 `PUSHPLUS_TOPIC` 配置项，支持一对多群组推送，配置群组编码后消息推送给群组所有订阅用户
- 📢 **Discord 分段发送**：新增 `DISCORD_MAX_WORDS` 配置项，支持将长文字按段落或字数只能分割后，分段发送。
- 📅 **交易日判断**（Issue #373）
  - 默认非交易日不执行分析，按 A 股 / 港股 / 美股各自交易日历区分
  - 混合持仓时，每只股票只在其市场开市日分析，休市股票当日跳过
  - 全部相关市场休市时，整体跳过执行（不启动 pipeline、不发推送）
  - 依赖 `exchange-calendars`（A 股 XSHG、港股 XHKG、美股 XNYS）
  - 配置项：`TRADING_DAY_CHECK_ENABLED`（默认 `true`）
  - 覆盖方式：`--force-run` 或 `TRADING_DAY_CHECK_ENABLED=false`
- 🤖 **Agent 策略问股**（全链路，#367）
  - **API**：新增 `/api/v1/agent/strategies`（获取策略列表）与 `/api/v1/agent/chat/stream`（SSE 流式对话）
  - **核心**：`src/agent/`（AgentExecutor ReAct 循环、LLMToolAdapter 多厂商适配、ConversationManager 会话持久化、ToolRegistry 工具注册）
  - **内置策略**：11 种 YAML 策略（多头趋势、均线金叉、量价突破、缩量回踩、缠论、波浪理论、情绪周期、箱体震荡、龙头策略、一阳三阴、底部放量）
  - **Web**：`/chat` 页面支持策略选择、流式进度反馈、多轮追问、从历史报告跳转追问
  - **Bot**：`/ask <code> [strategy]` 命令触发策略分析，`/chat` 命令进入多轮对话
  - **流水线接入**：`AGENT_MODE=true` 时 pipeline 自动路由至 Agent 分析分支，向下兼容
  - **配置项**：`AGENT_MODE`、`AGENT_MAX_STEPS`、`AGENT_STRATEGY_DIR`
  - **兼容性**：`AGENT_MODE` 默认 false，不影响现有非 Agent 模式；回滚只需将 `AGENT_MODE` 设为 false
- 💬 **聊天历史持久化**（Issue #400）
  - `/chat` 页面支持会话历史记录，刷新或重新进入页面后可恢复之前的对话
  - 侧边栏展示历史会话列表，支持切换、新建和删除会话（含二次确认）
  - 后端新增 3 个 REST API：会话列表、会话消息查询、会话删除
  - 基于已有 `conversation_messages` 表聚合，无需数据库迁移
  - `session_id` 通过 localStorage 持久化，跨页面刷新保持会话连续性
- ⚙️ **Agent 工具链能力增强**
  - 扩展 `analysis_tools` 与 `data_tools`，优化策略问股的工具调用链路与分析覆盖
- 📡 **LiteLLM Proxy 接入**
  - 支持通过 LiteLLM Proxy 统一路由 Gemini、DeepSeek、Claude 等模型，自动处理 Reasoning 模型透传
  - 新增 `docs/LITELLM_PROXY_SETUP.md` 接入指南、`litellm_config.yaml.example` 示例配置
  - `.env` 方案五：`OPENAI_BASE_URL` + `OPENAI_API_KEY` + `OPENAI_MODEL` 指向 Proxy
  - OpenAI 兼容 API Key 长度校验放宽为 `>= 8`，支持 LiteLLM 本地开发常用短 Key

### 修复（#patch）
- 🧭 **首页入口与左侧导航调整**
  - 左侧 Dock 导航移除「问股」「回测」两个 tab
  - 首页顶部新增「问股」「回测」快捷入口按钮，保持两个模块可达
  - 首页报告区移除重复的「追问 AI」按钮，避免与顶部「问股」入口重复
  - 首页顶部「回测」按钮配色提亮，增强可点击状态识别
- 🧩 **仓位管理弹窗保存态与可读性优化**
  - 资产明细新增/编辑弹窗在保存进行中时，输入框与下拉框统一禁用，避免保存中继续编辑导致状态不一致
  - 仓位管理页面文字对比度提升：`text-muted` 与 `text-secondary` 在该页面局部提亮，提升可读性
  - 仓位管理页编辑类提醒统一改为右侧 Toast 展示，成功提醒在 3 秒后自动消失
- 🧭 **仓位管理涨跌幅热力图排序优化**
  - 全局仓位管理与历史仓位管理模块的 `derived.heatmap` 统一按 `change_pct` 降序输出
  - 前端仓位管理页与历史报告仓位模块增加渲染层排序兜底，旧数据也按涨跌幅降序展示
- 🐛 **修复 NVDA/MSFT 技术面模块“止跌/见顶信号为空”**
  - 根因：断点续传仅校验“今日是否有数据”，历史库可能只有近 30 天，导致技术模块只扫描到约 42 根K线
  - 修复：`fetch_and_save_stock_data` 新增技术面历史完整性检查（近一年窗口至少 180 bars），不足时自动回源补齐并写库
  - 结果：`pattern_signals_1y` 恢复近一年命中结果（NVDA/MSFT 可返回历史止跌/见顶时间点），`window.bars` 可达到 252
- 🐛 **技术面箱体升级为多区间输出**
  - 新增 `price_zones.multi_boxes`（含 `support_boxes`/`resistance_boxes`），由关键价位聚类生成多个支撑/阻力箱体
  - 解决此前仅看到单一箱体区间的问题，支持更贴近实盘的分层价格带展示
- 🐛 **止跌/见顶信号拆分为独立前端模块**
  - Web 报告新增独立“止跌/见顶信号模块”卡片，展示次数、窗口与近一年明细
  - 技术面模块聚焦价格区间与技术指标解读，模块职责更清晰
- 🐛 **价格区间与形态信号展示重构**
  - 价格区间改为单图展示：左侧筹码式堆积分布（强度越强越宽）+ 当前价格虚线标记
  - 右侧仅保留区间与关键价位来源说明（含关键价位明细），减少重复信息
  - 价格区间卡片中的 5 个核心价格（当前价/强弱支撑/强弱阻力）移动到模块底部
  - 止跌/见顶模块改为结构化表格：信号类型图标、日期、组合、强弱、未来 7 天/30 天涨跌幅
  - 后端 `pattern_signals_1y.signals` 新增 `signal_strength`、`signal_strength_score`、`future_7d_return_pct`、`future_30d_return_pct`
- 🐛 **模块更新交互与列表去重修复**
  - 报告页每个模块“更新”按钮接入异步任务状态机（排队/进行中/成功/失败）并增加页面内提醒，不再仅为静态文字
  - 子模块标题统一显示更新时间（无记录时显示“未更新”）
  - 历史股票列表按 `stock_code` 去重，默认仅展示每个代码的最新一条记录
  - 价格区间“现有模式”新增当前价提示；手动区间补充可编辑/删除操作入口
- 🐛 **仓位复盘推送 405 与 API 路由兜底修复**
  - 修复 SPA 回退路由对 `/api/*` 的误匹配：未知 API 路径不再返回 `200 null` 或误报 `405`，统一返回 `404`
  - 前端开发环境默认 API 地址由 `http://127.0.0.1:8000` 调整为 `http://127.0.0.1:8001`，避免请求落到旧端口导致“方法不允许”
  - 仓位页「复盘推送」接口单独放宽前端超时时间到 120s，避免 Telegram+AI 生成耗时导致前端过早报错
  - README 启动与健康检查示例端口同步为 `8001`
- 🐛 **填写操作补齐保存状态与交互反馈**
  - 仓位管理页：保存动作新增“保存中”状态提示，保存成功/失败 toast，保存进行时禁用填写控件，避免重复提交
  - 历史报告「仓位管理模块」：新增统一保存提示（进行中/成功/失败），并支持输入框 Enter 保存与文本框 Ctrl+Enter 保存
  - 历史报告「价格区间模块」：新增新增/修改/删除区间的进行中状态、结果提醒与交互禁用，草稿支持 Enter 直接保存
- ⚡ **仓位管理加载性能优化与加载态强化**
  - 后端 `GET /api/v1/position-management` 调整为优先返回本地缓存快照（不在首屏阻塞行情/汇率回源），显著减少页面首开等待
  - 行情刷新链路补充并行抓取（多标的并发拉取），降低手动刷新耗时
  - 仓位管理页在“数据未加载完成”阶段新增子模块 loading 占位，并禁用交互，避免空数据可编辑导致误操作
- 🐛 **仓位管理持仓列表展示与删除交互修复**
  - 持仓列表展示收敛为 4 个核心字段：一级分类、名称、最新报价、总价值
  - 股票类标的展示名称（有名称时不再以代码替代主显示字段）
  - 删除持仓改为弹窗二次确认，避免误删
  - 报价列显示为“整数 + 币种单位”，总价值在保存后自动回算
  - 编辑持仓支持回车自动保存，不再依赖对勾保存按钮
  - 持仓区新增刷新符号按钮，点击后重拉权益类报价并 toast 提示结果
  - 修复刷新覆盖问题：刷新前自动保存脏持仓，避免“报价未知→后续拉取成功”场景下数量被重置
  - 持仓列表按总价值降序展示，并新增一级资产分类占整体资产比例（两位小数）展示
- 🐛 **手动区间“区间定义”可自定义并持久化**
  - 手动新增/修改区间时支持填写 `区间定义`，后端持久化到 `logic_detail`
  - `Rhino 价格区间 / 人工判断区间` 与智能模式中的手动区间均展示自定义定义内容
- 🧭 **价格区间双模式（现有模式 / Rhino 模式）**
  - 新增 `Rhino 价格区间` 模式，支持与现有模式手动切换；当存在 Rhino 数据时默认展示 Rhino
  - 后端 `price_zones` 新增 `rhino_zones`（上限、下限、强弱程度、关键价位逻辑），并按上限价格从高到低排序
  - Rhino 模式支持前端手动新增多条区间（弱/中/强/超强）并即时按价格排序展示
- 🐛 **修复桌面端打包后 FastAPI 缺少 `python-multipart`**
  - 现象：桌面客户端启动时报错 `Form data requires "python-multipart" to be installed`
  - 根因：`python-multipart` 由 FastAPI 在运行时检查，且 Windows 打包脚本中 `pip` 与 `pyinstaller` 可能来自不同 Python 环境，导致 `multipart` 未被收录
  - 修复：为后端打包流程补充 `multipart` / `multipart.multipart` 隐式导入，并统一改为 `python -m PyInstaller`（Windows / macOS 打包脚本）
  - 兼容性：无破坏性变更，仅影响桌面端打包产物
- 🐛 **Agent 策略渲染遗漏 framework 分类**（Issue #403）
  - 根因：`get_skill_instructions()` 仅遍历 `trend/pattern/reversal` 三个分类，`category: framework` 的 4 个策略（箱体震荡、缠论、波浪理论、情绪周期）被静默丢弃
  - 修复：补充 `framework` 分类，并增加动态回退机制，确保未来自定义分类不会遗漏
  - 文档：`.env.example` 补充 `AGENT_SKILLS=all` 写法，`README.md` 配置表新增 `AGENT_SKILLS`
  - Docker：Dockerfile 补充 `COPY strategies/`，docker-compose.yml 挂载 `strategies/` 目录（此前容器内策略目录缺失，导致所有策略均无法加载）
- 🐛 **历史报告「相关资讯」刷新无返回**
  - 根因：前端“刷新”仅重复读取历史关联数据，未触发回源搜索，导致旧记录长期为空
  - 修复：`GET /api/v1/history/{record_id}/news` 新增 `refresh=true` 参数；前端刷新按钮改为携带该参数并触发回源抓取
  - 兼容性：默认行为不变（`refresh=false` 仅返回历史数据），无破坏性变更
- 🐛 **支持 DeepSeek 思考模式**（Issue #379）
  - 根因：Agent 模式（tool calls）下使用 DeepSeek 思考模式时，未在 assistant 消息中回传 `reasoning_content`，导致 API 返回 400
  - 修复：`llm_adapter._call_openai` 解析并透传 `reasoning_content`；`executor` 在 assistant_msg 中写入该字段
  - 按模型名自动识别：`deepseek-reasoner`、`deepseek-r1`、`qwq` 等自动返回 reasoning_content，不发送 extra_body；`deepseek-chat` 需显式启用，系统自动处理
  - 兼容性：非 DeepSeek 提供商不受影响；用户无需配置，无破坏性变更
- 🐛 **Agent Reasoning 400 修复**（Fixes #409）
  - 根因：Gemini 3、DeepSeek 等 Reasoning 模型在工具调用响应中返回 `thought_signature`，多轮对话未回传导致代理返回 400
  - 修复：`llm_adapter._call_openai` 解析并透传 `provider_specific_fields.thought_signature`；`executor` 在 assistant_msg 的 tool_calls 中写入该字段
  - 兼容性：非 Reasoning 模型不受影响；与 LiteLLM Proxy 及其他 OpenAI 兼容代理兼容
- 🐛 **Agent 模式下报告页「相关资讯」为空**（Issue #396）
  - 根因：Agent 工具结果仅用于 LLM 上下文，未写入 `news_intel`，前端 `GET /api/v1/history/{query_id}/news` 查询不到数据
  - 修复：在 `_analyze_with_agent` 中 Agent 运行结束后，调用 `search_stock_news` 并持久化（仅 1 次 API 调用，与 Agent 工具逻辑一致，无额外延迟）
  - 兼容性：无破坏性变更，Agent 模式下报告页「相关资讯」可正常展示
- 🐛 **修复 HTTP 非安全上下文下 /chat 页面黑屏**（Issue #377）
  - `crypto.randomUUID()` 仅在 HTTPS/localhost 安全上下文中可用，通过 `http://IP:port` 访问时页面崩溃黑屏
  - 新增 `apps/dsa-web/src/utils/uuid.ts`，提供带 fallback 的 `generateUUID()` 工具函数
  - `ChatPage.tsx` 中的 session ID 生成改为调用 `generateUUID()`，兼容 HTTP 访问场景
- 🐛 **Docker 网络/DNS 解析失败** (Issue #372)
  - `docker-compose.yml` 增加 host 模式下 `--port` 与端口映射关系的注释说明
  - FAQ 新增 Q14.1：Docker 中 DNS 解析失败时的排查步骤（显式 DNS 配置、host 网络模式兜底）
- 🐛 **Agent 对话 Bug 修复**（#367 review follow-up）
  - 修复 `bot/commands/ask.py` 中 `list_strategies()` 方法不存在导致策略名称回显失败，改为 `list_skills()` 正确属性访问
  - 修复 `session_id` 缺省值为 `"default_session"` 导致多用户/多标签页会话串用，改为每次生成 UUID
  - 修复 LLM 失败时对话消息不落库，下一轮上下文断层；现在成功/失败均写入历史
  - `asyncio.get_event_loop()` 改为 Python 3.10+ 推荐的 `get_running_loop()`
  - `storage.py` 中 `session.query()` 改为 SQLAlchemy 2.x 风格 `session.execute(select(...))`
  - `ChatPage.tsx` 消除所有 `@typescript-eslint/no-explicit-any` 报错，引入 `FollowUpContext`、`ChatStreamPayload` 接口
  - Agent 进度提示从「第 N 步：AI 正在思考...」改为具体动作描述（如「行情获取」已完成，继续深入分析...）
- 🐛 **Agent 对话会话存储与默认策略修复**
  - 修复 `DatabaseManager` 缺失 `session_scope` 导致 `/api/v1/agent/chat` 返回 500 的问题
  - 修复会话历史读取的数据结构不一致问题，避免多轮对话中断
  - 新增内置默认多头策略 `bull_trend`，并将默认策略收敛为更适合常规个股分析的组合
  - Web 端对话页文案调整为“策略对话”，并默认勾选多头相关策略，降低使用门槛
- 🐛 **Dashboard 嵌套映射与测试硬编码修复**
  - 修复 Dashboard 端策略结果映射中的嵌套结构解析问题，避免展示异常
  - 修复测试中的硬编码数据，减少因固定值导致的回归误报
- 🐛 **yfinance 并行下载股票代码问题修复**
  - 增加了代码逻辑，根据当前股票代码筛选并提取下载的数据，解决dataframe里出现多个股票的数据，造成后续数据处理出错。

### 测试（#patch）
- ✅ **Agent 相关测试更新**
  - 更新策略数量断言（`6 -> 11`），并同步 `test_agent_pipeline`、`test_agent_registry` 的断言逻辑

### 文档（#skip）
- 📝 **Agent 文档补充**
  - 更新 `README.md`、`docs/README_EN.md`、`docs/README_CHT.md` 与 changelog，补充策略问股使用说明与测试说明
- 📝 **LiteLLM Proxy 文档**
  - 更新 `docs/full-guide.md`、`README.md`、`.env.example`，补充 LiteLLM Proxy 配置说明与冲突警告

## [3.2.11] - 2026-02-23

### 修复（#patch）
- 🐛 **StockTrendAnalyzer 从未执行** (Issue #357)
  - 根因：`get_analysis_context` 仅返回 2 天数据且无 `raw_data`，pipeline 中 `raw_data in context` 始终为 False
  - 修复：Step 3 直接调用 `get_data_range` 获取 90 日历天（约 60 交易日）历史数据用于趋势分析
  - 改善：趋势分析失败时用 `logger.warning(..., exc_info=True)` 记录完整 traceback

## [3.2.10] - 2026-02-22

### 新增
- ⚙️ 支持 `RUN_IMMEDIATELY` 配置项，设为 `true` 时定时任务触发后立即执行一次分析，无需等待首个定时点

### 修复
- 🐛 修复 Web UI 页面居中问题
- 🐛 修复 Settings 返回 500 错误

## [3.2.9] - 2026-02-22

### 修复
- 🐛 **ETF 分析仅关注指数走势**（Issue #274）
  - 美股/港股 ETF（如 VOO、QQQ）与 A 股 ETF 不再纳入基金公司层面风险（诉讼、声誉等）
  - 搜索维度：ETF/指数专用 risk_check、earnings、industry 查询，避免命中基金管理人新闻
  - AI 提示：指数型标的分析约束，`risk_alerts` 不得出现基金管理人公司经营风险

## [3.2.8] - 2026-02-21

### 修复
- 🐛 **BOT 与 WEB UI 股票代码大小写统一**（Issue #355）
  - BOT `/analyze` 与 WEB UI 触发分析的股票代码统一为大写（如 `aapl` → `AAPL`）
  - 新增 `canonical_stock_code()`，在 BOT、API、Config、CLI、task_queue 入口处规范化
  - 历史记录与任务去重逻辑可正确识别同一股票（大小写不再影响）

## [3.2.7] - 2026-02-20

### 新增
- 🔐 **Web 页面密码验证**（Issue #320, #349）
  - 支持 `ADMIN_AUTH_ENABLED=true` 启用 Web 登录保护
  - 首次访问在网页设置初始密码；支持「系统设置 > 修改密码」和 CLI `python -m src.auth reset_password` 重置

## [3.2.6] - 2026-02-20
### ⚠️ 破坏性变更（Breaking Changes）

- **历史记录 API 变更 (Issue #322)**
  - 路由变更：`GET /api/v1/history/{query_id}` → `GET /api/v1/history/{record_id}`
  - 参数变更：`query_id` (字符串) → `record_id` (整数)
  - 新闻接口变更：`GET /api/v1/history/{query_id}/news` → `GET /api/v1/history/{record_id}/news`
  - 原因：`query_id` 在批量分析时可能重复，无法唯一标识单条历史记录。改用数据库主键 `id` 确保唯一性
  - 影响范围：使用旧版历史详情 API 的所有客户端需同步更新

### 修复
- 修复美股（如 ADBE）技术指标矛盾：akshare 美股复权数据异常，统一美股历史数据源为 YFinance（Issue #311）
- 🐛 **历史记录查询和显示问题 (Issue #322)**
  - 修复历史记录列表查询中日期不一致问题：使用明天作为 endDate，确保包含今天全天的数据
  - 修复服务器 UI 报告选择问题：原因是多条记录共享同一 `query_id`，导致总是显示第一条。现改用 `analysis_history.id` 作为唯一标识
  - 历史详情、新闻接口及前端组件已全面适配 `record_id`
  - 新增后台轮询（每 30s）与页面可见性变更时静默刷新历史列表，确保 CLI 发起的分析完成后前端能及时同步，使用 `silent` 模式避免触发 loading 状态
- 🐛 **美股指数实时行情与日线数据** (Issue #273)
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 ^GSPC）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源
  - 消除重复的美股识别逻辑，统一使用 `is_us_stock_code()` 函数

### 优化
- 🎨 **首页输入栏与 Market Sentiment 布局对齐优化**
  - 股票代码输入框左缘与历史记录 glass-card 框左对齐
  - 分析按钮右缘与 Market Sentiment 外框右对齐
  - Market Sentiment 卡片向下拉伸填满格子，消除与 STRATEGY POINTS 之间的空隙
  - 窄屏时输入栏填满宽度，响应式对齐保持一致

## [3.2.5] - 2026-02-19

### 新增
- 🌍 **大盘复盘可选区域**（Issue #299）
  - 支持 `MARKET_REVIEW_REGION` 环境变量：`cn`（A股）、`us`（美股）、`both`（两者）
  - us 模式使用 SPX/纳斯达克/道指/VIX 等指数；both 模式可同时复盘 A 股与美股
  - 默认 `cn`，保持向后兼容

## [3.2.4] - 2026-02-18

### 修复
- 🐛 **统一美股数据源为 YFinance**（Issue #311）
  - akshare 美股复权数据异常，统一美股历史数据源为 YFinance
  - 修复 ADBE 等美股股票技术指标矛盾问题

## [3.2.3] - 2026-02-18

### 修复
- 🐛 **标普500实时数据缺失**（Issue #273）
  - 修复 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指数无法获取实时行情的问题
  - 新增 `us_index_mapping` 模块，将用户输入（如 SPX）映射为 Yahoo Finance 符号（如 `^GSPC`）
  - 美股指数与美股股票日线数据直接路由至 YfinanceFetcher，避免遍历不支持的数据源

## [3.2.2] - 2026-02-16

### 新增
- 📊 **PE 指标支持**（Issue #296）
  - AI System Prompt 增加 PE 估值关注
- 📰 **新闻时效性筛查**（Issue #296）
  - `NEWS_MAX_AGE_DAYS`：新闻最大时效（天），默认 3，避免使用过时信息
- 📈 **强势趋势股乖离率放宽**（Issue #296）
  - `BIAS_THRESHOLD`：乖离率阈值（%），默认 5.0，可配置
  - 强势趋势股（多头排列且趋势强度 ≥70）自动放宽乖离率到 1.5 倍

## [3.2.1] - 2026-02-16

### 新增
- 🔧 **东财接口补丁可配置开关**
  - 支持 `EFINANCE_PATCH_ENABLED` 环境变量开关东财接口补丁（默认 `true`）
  - 补丁不可用时可降级关闭，避免影响主流程

## [3.2.0] - 2026-02-15

### 新增
- 🔒 **CI 门禁统一（P0）**
  - 新增 `scripts/ci_gate.sh` 作为后端门禁单一入口
  - 主 CI 改为 `backend-gate`、`docker-build`、`web-gate` 三段式
  - CI 触发改为所有 PR，避免 Required Checks 因路径过滤缺失而卡住合并
  - `web-gate` 支持前端路径变更按需触发
  - 新增 `network-smoke` 工作流承载非阻断网络场景回归
- 📦 **发布链路收敛（P0）**
  - `docker-publish` 调整为 tag 主触发，并增加发布前门禁校验
  - 手动发布增加 `release_tag` 输入与 semver/changelog 强校验
  - 发布前新增 Docker smoke（关键模块导入）
- 📝 **PR 模板升级（P0）**
  - 增加背景、范围、验证命令与结果、回滚方案、Issue 关联等必填项
- 🤖 **AI 审查覆盖增强（P0）**
  - `pr-review` 纳入 `.github/workflows/**` 范围
  - 新增 `AI_REVIEW_STRICT` 开关，可选将 AI 审查失败升级为阻断

## [3.1.13] - 2026-02-15

### 新增
- 📊 **仅分析结果摘要**（Issue #262）
  - 支持 `REPORT_SUMMARY_ONLY` 环境变量，设为 `true` 时只推送汇总，不含个股详情
  - 默认 `false`，多股时适合快速浏览

## [3.1.12] - 2026-02-15

### 新增
- 📧 **个股与大盘复盘合并推送**（Issue #190）
  - 支持 `MERGE_EMAIL_NOTIFICATION` 环境变量，设为 `true` 时将个股分析与大盘复盘合并为一次推送
  - 默认 `false`，减少邮件数量、降低被识别为垃圾邮件的风险

## [3.1.11] - 2026-02-15

### 新增
- 🤖 **Anthropic Claude API 支持**（Issue #257）
  - 支持 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`ANTHROPIC_TEMPERATURE`、`ANTHROPIC_MAX_TOKENS`
  - AI 分析优先级：Gemini > Anthropic > OpenAI
- 📷 **从图片识别股票代码**（Issue #257）
  - 上传自选股截图，通过 Vision LLM 自动提取股票代码
  - API: `POST /api/v1/stocks/extract-from-image`；支持 JPEG/PNG/WebP/GIF，最大 5MB
  - 支持 `OPENAI_VISION_MODEL` 单独配置图片识别模型
- ⚙️ **通达信数据源手动配置**（Issue #257）
  - 支持 `PYTDX_HOST`、`PYTDX_PORT` 或 `PYTDX_SERVERS` 配置自建通达信服务器

## [3.1.10] - 2026-02-15

### 新增
- ⚙️ **立即运行配置**（Issue #332）
  - 支持 `RUN_IMMEDIATELY` 环境变量，`true` 时定时任务启动后立即执行一次
- 🐛 修复 Docker 构建问题

## [3.1.9] - 2026-02-14

### 新增
- 🔌 **东财接口补丁机制**
  - 新增 `patch/eastmoney_patch.py` 修复 efinance 上游接口变更
  - 不影响其他数据源的正常运行

## [3.1.8] - 2026-02-14

### 新增
- 🔐 **Webhook 证书校验开关**（Issue #265）
  - 支持 `WEBHOOK_VERIFY_SSL` 环境变量，可关闭 HTTPS 证书校验以支持自签名证书
  - 默认保持校验，关闭存在 MITM 风险，仅建议在可信内网使用

## [3.1.7] - 2026-02-14

### 修复
- 🐛 修复包导入错误（package import error）

## [3.1.6] - 2026-02-13

### 修复
- 🐛 修复 `news_intel` 中 `query_id` 不一致问题

## [3.1.5] - 2026-02-13

### 新增
- 📷 **Markdown 转图片通知**（Issue #289）
  - 支持 `MARKDOWN_TO_IMAGE_CHANNELS` 配置，对 Telegram、企业微信、自定义 Webhook（Discord）、邮件发送图片格式报告
  - 邮件为内联附件，增强对不支持 HTML 客户端的兼容性
  - 需安装 `wkhtmltopdf` 和 `imgkit`

## [3.1.4] - 2026-02-12

### 新增
- 📧 **股票分组发往不同邮箱**（Issue #268）
  - 支持 `STOCK_GROUP_N` + `EMAIL_GROUP_N` 配置，不同股票组报告发送到对应邮箱
  - 大盘复盘发往所有配置的邮箱

## [3.1.3] - 2026-02-12

### 修复
- 🐛 修复 Docker 内运行时通过页面修改配置报错 `[Errno 16] Device or resource busy` 的问题

## [3.1.2] - 2026-02-11

### 修复
- 🐛 修复 Docker 一致性问题，解决关键批次处理与通知 Bug

## [3.1.1] - 2026-02-11

### 变更
- ♻️ `API_HOST` → `WEBUI_HOST`：Docker Compose 配置项统一

## [3.1.0] - 2026-02-11

### 新增
- 📊 **ETF 支持增强与代码规范化**
  - 统一各数据源 ETF 代码处理逻辑
  - 新增 `canonical_stock_code()` 统一代码格式，确保数据源路由正确

## [3.0.5] - 2026-02-08

### 修复
- 🐛 修复信号 emoji 与建议不一致的问题（复合建议如"卖出/观望"未正确映射）
- 🐛 修复 `*ST` 股票名在微信/Dashboard 中 markdown 转义问题
- 🐛 修复 `idx.amount` 为 None 时大盘复盘 TypeError
- 🐛 修复分析 API 返回 `report=None` 及 ReportStrategy 类型不一致问题
- 🐛 修复 Tushare 返回类型错误（dict → UnifiedRealtimeQuote）及 API 端点指向

### 新增
- 📊 大盘复盘报告注入结构化数据（涨跌统计、指数表格、板块排名）
- 🔍 搜索结果 TTL 缓存（500 条上限，FIFO 淘汰）
- 🔧 Tushare Token 存在时自动注入实时行情优先级
- 📰 新闻摘要截断长度 50→200 字

### 优化
- ⚡ 补充行情字段请求限制为最多 1 次，减少无效请求

## [3.0.4] - 2026-02-07

### 新增
- 📈 **回测引擎** (PR #269)
  - 新增基于历史分析记录的回测系统，支持收益率、胜率、最大回撤等指标评估
  - WebUI 集成回测结果展示

## [3.0.3] - 2026-02-07

### 修复
- 🐛 修复狙击点位数据解析错误问题 (PR #271)

## [3.0.2] - 2026-02-06

### 新增
- ✉️ 可配置邮件发送者名称 (PR #272)
- 🌐 外国股票支持英文关键词搜索

## [3.0.1] - 2026-02-06

### 修复
- 🐛 修复 ETF 实时行情获取、市场数据回退、企业微信消息分块问题
- 🔧 CI 流程简化

## [3.0.0] - 2026-02-06

### 移除
- 🗑️ **移除旧版 WebUI**
  - 删除基于 `http.server.ThreadingHTTPServer` 的旧版 WebUI（`web/` 包）
  - 旧版 WebUI 的功能已完全被 FastAPI（`api/`）+ React 前端替代
  - `--webui` / `--webui-only` 命令行参数标记为弃用，自动重定向到 `--serve` / `--serve-only`
  - `WEBUI_ENABLED` / `WEBUI_HOST` / `WEBUI_PORT` 环境变量保持兼容，自动转发到 FastAPI 服务
  - `webui.py` 保留为兼容入口，启动时直接调用 FastAPI 后端
  - Docker Compose 中移除 `webui` 服务定义，统一使用 `server` 服务

### 变更
- ♻️ **服务层重构**
  - 将 `web/services.py` 中的异步任务服务迁移至 `src/services/task_service.py`
  - Bot 分析命令（`bot/commands/analyze.py`）改为使用 `src.services.task_service`
  - Docker 环境变量 `WEBUI_HOST`/`WEBUI_PORT` 更名为 `API_HOST`/`API_PORT`（旧名仍兼容）

## [2.3.0] - 2026-02-01

### 新增
- 🇺🇸 **增强美股支持** (Issue #153)
  - 实现基于 Akshare 的美股历史数据获取 (`ak.stock_us_daily()`)
  - 实现基于 Yfinance 的美股实时行情获取（优先策略）
  - 增加对不支持数据源（Tushare/Baostock/Pytdx/Efinance）的美股代码过滤和快速降级

### 修复
- 🐛 修复 AMD 等美股代码被误识别为 A 股的问题 (Issue #153)

## [2.2.5] - 2026-02-01

### 新增
- 🤖 **AstrBot 消息推送** (PR #217)
  - 新增 AstrBot 通知渠道，支持推送到 QQ 和微信
  - 支持 HMAC SHA256 签名验证，确保通信安全
  - 通过 `ASTRBOT_URL` 和 `ASTRBOT_TOKEN` 配置

## [2.2.4] - 2026-02-01

### 新增
- ⚙️ **可配置数据源优先级** (PR #215)
  - 支持通过环境变量（如 `YFINANCE_PRIORITY=0`）动态调整数据源优先级
  - 无需修改代码即可优先使用特定数据源（如 Yahoo Finance）

## [2.2.3] - 2026-01-31

### 修复
- 📦 更新 requirements.txt，增加 `lxml_html_clean` 依赖以解决兼容性问题

## [2.2.2] - 2026-01-31

### 修复
- 🐛 修复代理配置区分大小写问题 (fixes #211)

## [2.2.1] - 2026-01-31

### 修复
- 🐛 **YFinance 兼容性修复** (PR #210, fixes #209)
  - 修复新版 yfinance 返回 MultiIndex 列名导致的数据解析错误

## [2.2.0] - 2026-01-31

### 新增
- 🔄 **多源回退策略增强**
  - 实现了更健壮的数据获取回退机制 (feat: multi-source fallback strategy)
  - 优化了数据源故障时的自动切换逻辑

### 修复
- 🐛 修复 analyzer 运行后无法通过改 .env 文件的 stock_list 内容调整跟踪的股票

## [2.1.14] - 2026-01-31

### 文档
- 📝 更新 README 和优化 auto-tag 规则

## [2.1.13] - 2026-01-31

### 修复
- 🐛 **Tushare 优先级与实时行情** (Fixed #185)
  - 修复 Tushare 数据源优先级设置问题
  - 修复 Tushare 实时行情获取功能

## [2.1.12] - 2026-01-30

### 修复
- 🌐 修复代理配置在某些情况下的区分大小写问题
- 🌐 修复本地环境禁用代理的逻辑

## [2.1.11] - 2026-01-30

### 优化
- 🚀 **飞书消息流优化** (PR #192)
  - 优化飞书 Stream 模式的消息类型处理
  - 修改 Stream 消息模式默认为关闭，防止配置错误运行时报错

## [2.1.10] - 2026-01-30

### 合并
- 📦 合并 PR #154 贡献

## [2.1.9] - 2026-01-30

### 新增
- 💬 **微信文本消息支持** (PR #137)
  - 新增微信推送的纯文本消息类型支持
  - 添加 `WECHAT_MSG_TYPE` 配置项

## [2.1.8] - 2026-01-30

### 修复
- 🐛 修正日志中 API 提供商显示错误 (PR #197)

## [2.1.7] - 2026-01-30

### 修复
- 🌐 禁用本地环境的代理设置，避免网络连接问题

## [2.1.6] - 2026-01-29

### 新增
- 📡 **Pytdx 数据源 (Priority 2)**
  - 新增通达信数据源，免费无需注册
  - 多服务器自动切换
  - 支持实时行情和历史数据
- 🏷️ **多源股票名称解析**
  - DataFetcherManager 新增 `get_stock_name()` 方法
  - 新增 `batch_get_stock_names()` 批量查询
  - 自动在多数据源间回退
  - Tushare 和 Baostock 新增股票名称/列表方法
- 🔍 **增强搜索回退**
  - 新增 `search_stock_price_fallback()` 用于数据源全部失败时
  - 新增搜索维度：市场分析、行业分析
  - 最大搜索次数从 3 增加到 5
  - 改进搜索结果格式（每维度 4 条结果）

### 改进
- 更新搜索查询模板以提高相关性
- 增强 `format_intel_report()` 输出结构

## [2.1.5] - 2026-01-29

### 新增
- 📡 新增 Pytdx 数据源和多源股票名称解析功能

## [2.1.4] - 2026-01-29

### 文档
- 📝 更新赞助商信息

## [2.1.3] - 2026-01-28

### 文档
- 📝 重构 README 布局
- 🌐 新增繁体中文翻译 (README_CHT.md)

### 修复
- 🐛 修复 WebUI 无法输入美股代码问题
  - 输入框逻辑改成所有字母都转换成大写
  - 支持 `.` 的输入（如 `BRK.B`）

## [2.1.2] - 2026-01-27

### 修复
- 🐛 修复个股分析推送失败和报告路径问题 (fixes #166)
- 🐛 修改 CR 错误，确保微信消息最大字节配置生效

## [2.1.1] - 2026-01-26

### 新增
- 🔧 添加 GitHub Actions auto-tag 工作流
- 📡 添加 yfinance 兜底数据源及数据缺失警告

### 修复
- 🐳 修复 docker-compose 路径和文档命令
- 🐳 Dockerfile 补充 copy src 文件夹 (fixes #145)

## [2.1.0] - 2026-01-25

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 📈 **MACD 和 RSI 技术指标**
  - MACD：趋势确认、金叉死叉信号（零轴上金叉⭐、金叉✅、死叉❌）
  - RSI：超买超卖判断（超卖⭐、强势✅、超买⚠️）
  - 指标信号纳入综合评分系统
- 🎮 **Discord 推送支持** (PR #124, #125, #144)
  - 支持 Discord Webhook 和 Bot API 两种方式
  - 通过 `DISCORD_WEBHOOK_URL` 或 `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` 配置
- 🤖 **机器人命令交互**
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
- 🌡️ **AI 温度参数可配置** (PR #142)
  - 支持自定义 AI 模型温度参数
- 🐳 **Zeabur 部署支持**
  - 添加 Zeabur 镜像部署工作流
  - 支持 commit hash 和 latest 双标签

### 重构
- 🏗️ **项目结构优化**
  - 核心代码移至 `src/` 目录，根目录更清爽
  - 文档移至 `docs/` 目录
  - Docker 配置移至 `docker/` 目录
  - 修复所有 import 路径，保持向后兼容
- 🔄 **数据源架构升级**
  - 新增数据源熔断机制，单数据源连续失败自动切换
  - 实时行情缓存优化，批量预取减少 API 调用
  - 网络代理智能分流，国内接口自动直连
- 🤖 Discord 机器人重构为平台适配器架构

### 修复
- 🌐 **网络稳定性增强**
  - 自动检测代理配置，对国内行情接口强制直连
  - 修复 EfinanceFetcher 偶发的 `ProtocolError`
  - 增加对底层网络错误的捕获和重试机制
- 📧 **邮件渲染优化**
  - 修复邮件中表格不渲染问题 (#134)
  - 优化邮件排版，更紧凑美观
- 📢 **企业微信推送修复**
  - 修复大盘复盘推送不完整问题
  - 增强消息分割逻辑，支持更多标题格式
  - 增加分批发送间隔，避免限流丢失
- 👷 **CI/CD 修复**
  - 修复 GitHub Actions 中路径引用的错误

## [2.0.0] - 2026-01-24

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代码直接输入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作为美股数据源
- 🤖 **机器人命令交互** (PR #113)
  - 钉钉机器人支持 `/分析 股票代码` 命令触发分析
  - 支持 Stream 长连接模式
  - 支持选择精简报告或完整报告
- 🎮 **Discord 推送支持** (PR #124)
  - 支持 Discord Webhook 推送
  - 添加 Discord 环境变量到工作流

### 修复
- 🐳 修复 WebUI 在 Docker 中绑定 0.0.0.0 (fixed #118)
- 🔔 修复飞书长连接通知问题
- 🐛 修复 `analysis_delay` 未定义错误
- 🔧 启动时 config.py 检测通知渠道，修复已配置自定义渠道情况下仍然提示未配置问题

### 改进
- 🔧 优化 Tushare 优先级判断逻辑，提升封装性
- 🔧 修复 Tushare 优先级提升后仍排在 Efinance 之后的问题
- ⚙️ 配置 TUSHARE_TOKEN 时自动提升 Tushare 数据源优先级
- ⚙️ 实现 4 个用户反馈 issue (#112, #128, #38, #119)

## [1.6.0] - 2026-01-19

### 新增
- 🖥️ WebUI 管理界面及 API 支持（PR #72）
  - 全新 Web 架构：分层设计（Server/Router/Handler/Service）
  - 核心 API：支持 `/analysis` (触发分析), `/tasks` (查询进度), `/health` (健康检查)
  - 交互界面：支持页面直接输入代码并触发分析，实时展示进度
  - 运行模式：新增 `--webui-only` 模式，仅启动 Web 服务
  - 解决了 [#70](https://github.com/ZhuLinsen/daily_stock_analysis/issues/70) 的核心需求（提供触发分析的接口）
- ⚙️ GitHub Actions 配置灵活性增强（[#79](https://github.com/ZhuLinsen/daily_stock_analysis/issues/79)）
  - 支持从 Repository Variables 读取非敏感配置（如 STOCK_LIST, GEMINI_MODEL）
  - 保持对 Secrets 的向下兼容

### 修复
- 🐛 修复企业微信/飞书报告截断问题（[#73](https://github.com/ZhuLinsen/daily_stock_analysis/issues/73)）
  - 移除 notification.py 中不必要的长度硬截断逻辑
  - 依赖底层自动分片机制处理长消息
- 🐛 修复 GitHub Workflow 环境变量缺失（[#80](https://github.com/ZhuLinsen/daily_stock_analysis/issues/80)）
  - 修复 `CUSTOM_WEBHOOK_BEARER_TOKEN` 未正确传递到 Runner 的问题

## [1.5.0] - 2026-01-17

### 新增
- 📲 单股推送模式（[#55](https://github.com/ZhuLinsen/daily_stock_analysis/issues/55)）
  - 每分析完一只股票立即推送，不用等全部分析完
  - 命令行参数：`--single-notify`
  - 环境变量：`SINGLE_STOCK_NOTIFY=true`
- 🔐 自定义 Webhook Bearer Token 认证（[#51](https://github.com/ZhuLinsen/daily_stock_analysis/issues/51)）
  - 支持需要 Token 认证的 Webhook 端点
  - 环境变量：`CUSTOM_WEBHOOK_BEARER_TOKEN`

## [1.4.0] - 2026-01-17

### 新增
- 📱 Pushover 推送支持（PR #26）
  - 支持 iOS/Android 跨平台推送
  - 通过 `PUSHOVER_USER_KEY` 和 `PUSHOVER_API_TOKEN` 配置
- 🔍 博查搜索 API 集成（PR #27）
  - 中文搜索优化，支持 AI 摘要
  - 通过 `BOCHA_API_KEYS` 配置
- 📊 Efinance 数据源支持（PR #59）
  - 新增 efinance 作为数据源选项
- 🇭🇰 港股支持（PR #17）
  - 支持 5 位代码或 HK 前缀（如 `hk00700`、`hk1810`）

### 修复
- 🔧 飞书 Markdown 渲染优化（PR #34）
  - 使用交互卡片和格式化器修复渲染问题
- ♻️ 股票列表热重载（PR #42 修复）
  - 分析前自动重载 `STOCK_LIST` 配置
- 🐛 钉钉 Webhook 20KB 限制处理
  - 长消息自动分块发送，避免被截断
- 🔄 AkShare API 重试机制增强
  - 添加失败缓存，避免重复请求失败接口

### 改进
- 📝 README 精简优化
  - 高级配置移至 `docs/full-guide.md`


## [1.3.0] - 2026-01-12

### 新增
- 🔗 自定义 Webhook 支持
  - 支持任意 POST JSON 的 Webhook 端点
  - 自动识别钉钉、Discord、Slack、Bark 等常见服务格式
  - 支持配置多个 Webhook（逗号分隔）
  - 通过 `CUSTOM_WEBHOOK_URLS` 环境变量配置

### 修复
- 📝 企业微信长消息分批发送
  - 解决自选股过多时内容超过 4096 字符限制导致推送失败的问题
  - 智能按股票分析块分割，每批添加分页标记（如 1/3, 2/3）
  - 批次间隔 1 秒，避免触发频率限制

## [1.2.0] - 2026-01-11

### 新增
- 📢 多渠道推送支持
  - 企业微信 Webhook
  - 飞书 Webhook（新增）
  - 邮件 SMTP（新增）
  - 自动识别渠道类型，配置更简单

### 改进
- 统一使用 `NOTIFICATION_URL` 配置，兼容旧的 `WECHAT_WEBHOOK_URL`
- 邮件支持 Markdown 转 HTML 渲染

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持
  - 支持 DeepSeek、通义千问、Moonshot、智谱 GLM 等
  - Gemini 和 OpenAI 格式二选一
  - 自动降级重试机制

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 决策仪表盘分析
  - 一句话核心结论
  - 精确买入/止损/目标点位
  - 检查清单（✅⚠️❌）
  - 分持仓建议（空仓者 vs 持仓者）
- 📊 大盘复盘功能
  - 主要指数行情
  - 涨跌统计
  - 板块涨跌榜
  - AI 生成复盘报告
- 🔍 多数据源支持
  - AkShare（主数据源，免费）
  - Tushare Pro
  - Baostock
  - YFinance
- 📰 新闻搜索服务
  - Tavily API
  - SerpAPI
- 💬 企业微信机器人推送
- ⏰ 定时任务调度
- 🐳 Docker 部署支持
- 🚀 GitHub Actions 零成本部署

### 技术特性
- Gemini AI 模型（gemini-3-flash-preview）
- 429 限流自动重试 + 模型切换
- 请求间延时防封禁
- 多 API Key 负载均衡
- SQLite 本地数据存储

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.3.0...HEAD
[2.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.5...v2.3.0
[2.2.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.4...v2.2.5
[2.2.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.14...v2.2.0
[2.1.14]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.13...v2.1.14
[2.1.13]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.12...v2.1.13
[2.1.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.11...v2.1.12
[2.1.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.10...v2.1.11
[2.1.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.9...v2.1.10
[2.1.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.8...v2.1.9
[2.1.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.7...v2.1.8
[2.1.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.6...v2.1.7
[2.1.6]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.5...v2.1.6
[2.1.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.4...v2.1.5
[2.1.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.3...v2.1.4
[2.1.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v1.0.0
