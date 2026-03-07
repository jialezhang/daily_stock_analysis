# Scripts Usage Guide

本目录汇总了项目常用脚本。以下命令默认都在仓库根目录执行：

```bash
cd /Users/gkjiale/stock/daily_stock_analysis
```

## Quick Index

| Script | Platform | Purpose |
| --- | --- | --- |
| `scripts/service-8001.sh` | macOS/Linux | 启动/停止/重启/检查 8001 端口服务 |
| `scripts/refresh-watchlist-web.sh` | macOS/Linux | 手动刷新 Web 关注列表对应数据 |
| `scripts/run-daily-review.py` | macOS/Linux/Windows | 手动生成三地市场复盘报告（可选 Telegram / LLM） |
| `scripts/ci_gate.sh` | macOS/Linux | 本地执行后端 CI 关键检查 |
| `scripts/build-backend-macos.sh` | macOS | 构建后端可执行产物 |
| `scripts/build-desktop-macos.sh` | macOS | 构建桌面端安装包（依赖后端产物） |
| `scripts/build-all-macos.sh` | macOS | 一键构建后端 + 桌面端 |
| `scripts/build-backend.ps1` | Windows PowerShell | 构建后端可执行产物 |
| `scripts/build-desktop.ps1` | Windows PowerShell | 构建桌面端安装包（依赖后端产物） |
| `scripts/build-all.ps1` | Windows PowerShell | 一键构建后端 + 桌面端 |
| `scripts/run-desktop.ps1` | Windows PowerShell | 本地开发模式启动桌面端 |

## 1) 服务管理

### `scripts/service-8001.sh`

用途：管理 `127.0.0.1:8001` 的后端服务，带健康检查。  
日志文件：`/tmp/dsa-serve-8001.log`  
PID 文件：`/tmp/dsa-serve-8001.pid`

示例：

```bash
./scripts/service-8001.sh start
./scripts/service-8001.sh status
./scripts/service-8001.sh restart
./scripts/service-8001.sh stop
```

## 2) 手动刷新关注列表

### `scripts/refresh-watchlist-web.sh`

用途：手动触发一次“Web 可见”的关注列表数据刷新。  
执行时会自动设置稳定环境参数（关闭代理、关闭实时增强等），减少因数据源差异导致的前端不一致。

常用示例：

```bash
# 先预览实际会跑哪些标的（不执行）
./scripts/refresh-watchlist-web.sh --print-only

# 直接刷新（默认串行逐只 + 自动重试，优先读 .env 的 STOCK_LIST）
./scripts/refresh-watchlist-web.sh

# 串行模式下调整重试次数和重试间隔
./scripts/refresh-watchlist-web.sh --retries 3 --retry-delay 2

# 批量模式（旧行为：一次性提交全部标的）
./scripts/refresh-watchlist-web.sh --batch

# 指定标的刷新
./scripts/refresh-watchlist-web.sh --stocks "hk00700,hk09988,600519,AAPL"
```

参数：

- `--stocks "<comma-separated-codes>"`：覆盖默认股票列表。
- `--serial`：串行逐只刷新（默认）。
- `--batch`：批量一次性刷新全部标的（兼容旧行为）。
- `--retries <N>`：串行模式每只股票最大重试次数，默认 `3`。
- `--retry-delay <seconds>`：串行模式重试间隔秒数，默认 `2`。
- `--print-only`：仅打印最终命令，不实际执行。
- `-h, --help`：查看帮助。

股票列表解析规则：

- 优先使用 `.env` 中的 `STOCK_LIST`。
- 若 `STOCK_LIST` 为空，则回退到本地 `analysis_history` 最近 30 天去重后的代码。
- 5 位纯数字（如 `00700`）会自动标准化为 `hk00700`。
- 最终会自动去重，避免重复分析同一标的。

## 3) 本地 CI 检查

### `scripts/ci_gate.sh`

用途：执行本地后端质量门禁，包括语法检查、关键 flake8 检查、离线测试。

示例：

```bash
./scripts/ci_gate.sh
```

该脚本会依次执行：

- `python -m py_compile ...`
- `flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics`
- `./test.sh code`
- `./test.sh yfinance`
- `python -m pytest -m "not network"`

## 4) 手动生成三地复盘

### `scripts/run-daily-review.py`

用途：手动执行 `modules.daily_review.runner` 流程，生成并保存当日复盘 Markdown（默认不推送 Telegram，不调用 LLM）。

示例：

```bash
# 仅生成并保存报告
python3 scripts/run-daily-review.py

# 生成并发送 Telegram
python3 scripts/run-daily-review.py --send-telegram

# 生成并调用 LLM 摘要
python3 scripts/run-daily-review.py --use-llm
```

参数：

- `--send-telegram`：启用 Telegram 推送（需配置 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`）。
- `--use-llm`：启用 LLM 摘要（需配置 `OPENAI_API_KEY`）。

## 5) macOS 构建脚本

### `scripts/build-backend-macos.sh`

用途：构建后端可执行目录产物（PyInstaller），并先构建前端静态资源。  
默认输出：`dist/backend/stock_analysis`

示例：

```bash
./scripts/build-backend-macos.sh
```

可选环境变量：

- `PYTHON_BIN`：指定 Python 可执行文件路径，例如：

```bash
PYTHON_BIN=/usr/local/bin/python3 ./scripts/build-backend-macos.sh
```

### `scripts/build-desktop-macos.sh`

用途：构建 macOS 桌面安装包（Electron Builder）。  
前置：必须先有 `dist/backend/stock_analysis`。

示例：

```bash
./scripts/build-desktop-macos.sh
```

可选环境变量：

- `DSA_MAC_ARCH`：`x64` 或 `arm64`。不设置时使用默认架构。

```bash
DSA_MAC_ARCH=arm64 ./scripts/build-desktop-macos.sh
```

### `scripts/build-all-macos.sh`

用途：一键执行后端 + 桌面端构建。

示例：

```bash
./scripts/build-all-macos.sh
```

## 6) Windows 构建/运行脚本

### `scripts/build-backend.ps1`

用途：Windows 下构建后端可执行目录产物（PyInstaller），并先构建前端静态资源。  
默认输出：`dist\backend\stock_analysis`

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-backend.ps1
```

可选环境变量：

- `PYTHON_BIN`：指定 Python 命令，如 `python` 或 `py -3.11` 对应可执行入口。

### `scripts/build-desktop.ps1`

用途：Windows 下构建桌面安装包（NSIS）。  
前置：必须先执行 `build-backend.ps1`。

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-desktop.ps1
```

可选环境变量：

- `DSA_SKIP_DEVMODE_CHECK=true`：跳过开发者模式检查。
- `CI=true`：CI 环境下自动跳过开发者模式检查。

### `scripts/build-all.ps1`

用途：一键执行 Windows 后端 + 桌面端构建。

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-all.ps1
```

### `scripts/run-desktop.ps1`

用途：本地开发模式运行桌面端（先构建前端静态资源，再启动 Electron dev）。

示例：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-desktop.ps1
```

## 7) 常见问题

### 权限不足（macOS/Linux）

```bash
chmod +x scripts/*.sh
```

### 依赖未安装

- Python 依赖：`pip install -r requirements.txt`
- Web 依赖：脚本会在缺少 `node_modules` 时自动执行 `npm install`

### 刷新后 Web 没变化

- 先执行 `./scripts/service-8001.sh status` 确认服务健康。
- 再执行 `./scripts/refresh-watchlist-web.sh --print-only` 确认本次实际刷新标的列表。
