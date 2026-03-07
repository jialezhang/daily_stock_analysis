# -*- coding: utf-8 -*-
"""Global position management service."""

import json
import logging
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PRIMARY_ASSET_CLASSES = ["权益类", "加密货币", "贵金属", "债券", "货币基金", "现金"]
SECONDARY_ASSET_CLASSES: Dict[str, List[str]] = {
    "权益类": ["A股", "港股", "美股", "ETF"],
    "加密货币": ["主流币", "平台币", "稳定币", "DeFi"],
    "贵金属": ["黄金", "白银", "铂金", "钯金"],
    "债券": ["国债", "政金债", "信用债", "可转债", "美债"],
    "货币基金": ["场内货基", "场外货基", "现金管理"],
    "现金": ["人民币现金", "美元现金", "港币现金", "其他现金"],
}

SYMBOL_NAME_FALLBACK_MAP: Dict[str, str] = {
    # US / ADR
    "NVDA": "英伟达",
    "MSFT": "微软",
    "AAPL": "苹果",
    "TSLA": "特斯拉",
    "AMZN": "亚马逊",
    "META": "Meta",
    "GOOGL": "谷歌A",
    "GOOG": "谷歌C",
    "AMD": "AMD",
    "BABA": "阿里巴巴",
    "PDD": "拼多多",
    "JD": "京东",
    "BIDU": "百度",
    "NIO": "蔚来",
    "LI": "理想汽车",
    "XPEV": "小鹏汽车",
    # HK
    "00700": "腾讯控股",
    "0700": "腾讯控股",
    "00700.HK": "腾讯控股",
    "03690": "美团",
    "3690": "美团",
    "03690.HK": "美团",
    "09988": "阿里巴巴",
    "9988": "阿里巴巴",
    "09988.HK": "阿里巴巴",
    "01810": "小米集团",
    "1810": "小米集团",
    "01810.HK": "小米集团",
    # A-share
    "600519": "贵州茅台",
    "600519.SS": "贵州茅台",
    "000001": "平安银行",
    "000001.SZ": "平安银行",
    "300750": "宁德时代",
    "300750.SZ": "宁德时代",
}


class PositionManagementService:
    """Manage global position management data persisted in local JSON file."""

    def __init__(self, file_path: Optional[Path] = None):
        root = Path(__file__).resolve().parents[2]
        self._file_path = Path(file_path) if file_path else (root / "data" / "position_management.json")
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get_module(self) -> Dict[str, Any]:
        """Read current global module."""
        payload = self._read_payload()
        # Fast path for page load: use persisted quotes/fx and avoid blocking network calls.
        module = self._build_module(module=payload, refresh_quotes=False, refresh_fx=False)
        # Keep structure normalized and derived fields up-to-date for frontend rendering.
        self._write_payload(module)
        return {"updated": True, "module": module, "message": "读取成功"}

    def upsert_module(
        self,
        target: Optional[Dict[str, Any]],
        holdings: Optional[List[Dict[str, Any]]],
        macro_events: Optional[List[str]],
        notes: Optional[str],
        refresh_benchmarks: bool = True,
    ) -> Dict[str, Any]:
        """Upsert global module and persist."""
        current = self._read_payload()
        updated = {
            **current,
            "target": deepcopy(target) if isinstance(target, dict) else current.get("target"),
            "holdings": deepcopy(holdings) if isinstance(holdings, list) else current.get("holdings"),
            "macro_events": deepcopy(macro_events) if isinstance(macro_events, list) else current.get("macro_events"),
            "notes": str(notes or "").strip() if notes is not None else str(current.get("notes") or "").strip(),
        }
        module = self._build_module(
            module=updated,
            refresh_quotes=True,
            refresh_fx=bool(refresh_benchmarks),
        )
        self._write_payload(module)
        return {"updated": True, "module": module, "message": "保存成功"}

    def refresh_module(self) -> Dict[str, Any]:
        """Recompute derived data and refresh quotes/fx rates."""
        current = self._read_payload()
        module = self._build_module(module=current, refresh_quotes=True, refresh_fx=True)
        self._write_payload(module)
        return {"updated": True, "module": module, "message": "更新成功"}

    def _build_module(self, module: Dict[str, Any], refresh_quotes: bool, refresh_fx: bool) -> Dict[str, Any]:
        target = self._normalize_target(module.get("target"))
        prev_fx = module.get("fx") if isinstance(module.get("fx"), dict) else {}
        fx = self._get_fx_rates(previous=prev_fx, refresh=refresh_fx)
        holdings = self._normalize_holdings(module.get("holdings"), target=target, fx=fx, refresh_quotes=refresh_quotes)
        derived = self._build_derived(target=target, holdings=holdings, fx=fx)

        return {
            "scope": "global",
            "version": 2,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "target": target,
            "fx": fx,
            "holdings": holdings,
            "macro_events": self._normalize_text_list(module.get("macro_events")),
            "notes": str(module.get("notes") or "").strip(),
            "derived": derived,
        }

    def _normalize_target(self, target: Any) -> Dict[str, Any]:
        data = target if isinstance(target, dict) else {}
        output_currency = self._normalize_currency(data.get("output_currency") or data.get("base_currency"))
        initial_position = self._to_float(data.get("initial_position"))
        if initial_position <= 0:
            initial_position = self._to_float(data.get("initial_capital"))
        target_return_pct = self._to_float(data.get("target_return_pct"))
        if target_return_pct == 0 and data.get("target_return_pct") in (None, ""):
            target_return_pct = self._to_float(data.get("annual_return_target_pct")) or 30.0
        return {
            "initial_position": round(max(0.0, initial_position), 4),
            "output_currency": output_currency,
            "target_return_pct": round(target_return_pct, 4),
        }

    def _normalize_holdings(
        self,
        holdings: Any,
        target: Dict[str, Any],
        fx: Dict[str, Any],
        refresh_quotes: bool,
    ) -> List[Dict[str, Any]]:
        rows = holdings if isinstance(holdings, list) else []
        output_currency = self._normalize_currency(target.get("output_currency"))
        quote_cache: Dict[str, Dict[str, Any]] = {}
        if refresh_quotes:
            quote_symbols = set()
            for row in rows:
                item = row if isinstance(row, dict) else {}
                symbol = str(item.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                primary = self._normalize_primary_asset(
                    item.get("asset_primary") or item.get("asset_class_primary") or item.get("asset_class")
                )
                if primary == "现金":
                    continue
                secondary = self._normalize_secondary_asset(
                    primary=primary,
                    secondary=item.get("asset_secondary") or item.get("asset_class_secondary") or item.get("market_type"),
                )
                quote_symbols.add(self._resolve_quote_symbol(symbol=symbol, primary=primary, secondary=secondary))
            quote_symbols = {symbol for symbol in quote_symbols if symbol}
            if quote_symbols:
                max_workers = min(8, len(quote_symbols))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_map = {executor.submit(self._fetch_quote, symbol): symbol for symbol in quote_symbols}
                    for future in as_completed(future_map):
                        symbol = future_map[future]
                        try:
                            quote_cache[symbol] = future.result() or {}
                        except Exception:
                            quote_cache[symbol] = {}
        result: List[Dict[str, Any]] = []
        for index, row in enumerate(rows):
            item = row if isinstance(row, dict) else {}
            primary = self._normalize_primary_asset(
                item.get("asset_primary") or item.get("asset_class_primary") or item.get("asset_class")
            )
            secondary = self._normalize_secondary_asset(
                primary=primary,
                secondary=item.get("asset_secondary") or item.get("asset_class_secondary") or item.get("market_type"),
            )
            symbol = str(item.get("symbol") or "").strip().upper()
            quantity = max(0.0, self._to_float(item.get("quantity")))
            if primary == "现金":
                currency = self._normalize_currency(item.get("currency") or self._infer_cash_currency(secondary))
                latest_price = self._to_float(item.get("latest_price") or item.get("current_price"))
                if latest_price <= 0:
                    latest_price = 1.0
                prev_close = self._to_float(item.get("previous_close"))
                if prev_close <= 0:
                    prev_close = latest_price
                fx_rate = self._convert_fx_rate(from_currency=currency, to_currency=output_currency, fx=fx)
                market_value_output = quantity * latest_price * fx_rate
                daily_pnl_output = quantity * (latest_price - prev_close) * fx_rate if prev_close > 0 else 0.0
                change_pct = ((latest_price - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0
                result.append(
                    {
                        "id": str(item.get("id") or f"holding-{index + 1}-{uuid.uuid4().hex[:6]}"),
                        "asset_primary": primary,
                        "asset_secondary": secondary,
                        "symbol": symbol,
                        "quote_symbol": str(item.get("quote_symbol") or f"CASH-{currency}"),
                        "name": str(item.get("name") or secondary),
                        "quantity": round(quantity, 6),
                        "latest_price": round(max(0.0, latest_price), 8),
                        "previous_close": round(max(0.0, prev_close), 8) if prev_close > 0 else None,
                        "currency": currency,
                        "fx_to_output": round(fx_rate, 8),
                        "market_value_output": round(market_value_output, 4),
                        "daily_pnl_output": round(daily_pnl_output, 4),
                        "change_pct": round(change_pct, 4),
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                continue

            if not symbol:
                continue

            quote_symbol = self._resolve_quote_symbol(symbol=symbol, primary=primary, secondary=secondary)
            quote = quote_cache.get(quote_symbol, {}) if refresh_quotes else {}
            latest_price = self._to_float(quote.get("latest_price")) or self._to_float(item.get("latest_price") or item.get("current_price"))
            prev_close = self._to_float(quote.get("previous_close")) or self._to_float(item.get("previous_close"))
            currency = self._normalize_currency(quote.get("currency") or item.get("currency"))
            quote_name = str(quote.get("name") or "").strip()
            existing_name = str(item.get("name") or "").strip()
            if quote_name:
                resolved_name = quote_name
            else:
                resolved_name = self._resolve_holding_name(
                    existing_name=existing_name,
                    symbol=symbol,
                    quote_symbol=quote_symbol,
                    secondary=secondary,
                )
            fx_rate = self._convert_fx_rate(from_currency=currency, to_currency=output_currency, fx=fx)
            market_value_output = quantity * latest_price * fx_rate
            daily_pnl_output = quantity * (latest_price - prev_close) * fx_rate if prev_close > 0 else 0.0
            change_pct = ((latest_price - prev_close) / prev_close * 100.0) if prev_close > 0 else 0.0

            result.append(
                {
                    "id": str(item.get("id") or f"holding-{index + 1}-{uuid.uuid4().hex[:6]}"),
                    "asset_primary": primary,
                    "asset_secondary": secondary,
                    "symbol": symbol,
                    "quote_symbol": quote_symbol,
                    "name": resolved_name,
                    "quantity": round(quantity, 6),
                    "latest_price": round(max(0.0, latest_price), 8),
                    "previous_close": round(max(0.0, prev_close), 8) if prev_close > 0 else None,
                    "currency": currency,
                    "fx_to_output": round(fx_rate, 8),
                    "market_value_output": round(market_value_output, 4),
                    "daily_pnl_output": round(daily_pnl_output, 4),
                    "change_pct": round(change_pct, 4),
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
        return result

    def _resolve_holding_name(self, existing_name: str, symbol: str, quote_symbol: str, secondary: str) -> str:
        cleaned_existing = str(existing_name or "").strip()
        symbol_upper = str(symbol or "").strip().upper()
        if cleaned_existing and cleaned_existing.upper() != symbol_upper:
            return cleaned_existing

        candidates = [str(quote_symbol or "").strip().upper(), symbol_upper]
        digits = "".join(ch for ch in symbol_upper if ch.isdigit())
        if digits:
            candidates.extend([digits, digits.zfill(4), digits.zfill(5)])
            if secondary == "港股":
                candidates.extend([f"{digits.zfill(4)}.HK", f"{digits.zfill(5)}.HK"])
            if secondary == "A股":
                if len(digits) == 6:
                    candidates.extend([f"{digits}.SS", f"{digits}.SZ"])

        for key in candidates:
            if key in SYMBOL_NAME_FALLBACK_MAP:
                return SYMBOL_NAME_FALLBACK_MAP[key]
        return ""

    def _build_derived(self, target: Dict[str, Any], holdings: List[Dict[str, Any]], fx: Dict[str, Any]) -> Dict[str, Any]:
        output_currency = self._normalize_currency(target.get("output_currency"))
        initial = max(0.0, self._to_float(target.get("initial_position")))
        target_return_pct = self._to_float(target.get("target_return_pct"))

        total_value = sum(self._to_float(item.get("market_value_output")) for item in holdings)
        daily_pnl = sum(self._to_float(item.get("daily_pnl_output")) for item in holdings)
        profit_amount = total_value - initial
        profit_pct = (profit_amount / initial * 100.0) if initial > 0 else 0.0
        target_value = initial * (1.0 + target_return_pct / 100.0)
        gap_amount = target_value - total_value
        target_progress_pct = (total_value / target_value * 100.0) if target_value > 0 else 0.0

        alloc_map: Dict[str, float] = {}
        secondary_alloc_map: Dict[str, float] = {}
        for item in holdings:
            key = str(item.get("asset_primary") or "其他")
            alloc_map[key] = alloc_map.get(key, 0.0) + self._to_float(item.get("market_value_output"))
            secondary_key = str(item.get("asset_secondary") or "其他")
            secondary_alloc_map[secondary_key] = secondary_alloc_map.get(secondary_key, 0.0) + self._to_float(
                item.get("market_value_output")
            )
        allocation = []
        for key, value in sorted(alloc_map.items(), key=lambda entry: entry[1], reverse=True):
            ratio = value / total_value * 100.0 if total_value > 0 else 0.0
            allocation.append({"asset_primary": key, "value_output": round(value, 4), "ratio_pct": round(ratio, 4)})
        secondary_allocation = []
        for key, value in sorted(secondary_alloc_map.items(), key=lambda entry: entry[1], reverse=True):
            ratio = value / total_value * 100.0 if total_value > 0 else 0.0
            secondary_allocation.append(
                {"asset_secondary": key, "value_output": round(value, 4), "ratio_pct": round(ratio, 4)}
            )

        heatmap = []
        for item in holdings:
            change_pct = self._to_float(item.get("change_pct"))
            intensity = min(1.0, abs(change_pct) / 8.0)
            heatmap.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "asset_primary": item.get("asset_primary"),
                    "change_pct": round(change_pct, 4),
                    "daily_pnl_output": round(self._to_float(item.get("daily_pnl_output")), 4),
                    "intensity": round(intensity, 4),
                }
            )
        heatmap.sort(key=lambda row: self._to_float(row.get("change_pct")), reverse=True)

        return {
            "output_currency": output_currency,
            "totals": {
                "total_value_output": round(total_value, 4),
                "daily_pnl_output": round(daily_pnl, 4),
                "profit_amount_output": round(profit_amount, 4),
                "profit_pct": round(profit_pct, 4),
            },
            "target_progress": {
                "initial_position": round(initial, 4),
                "target_return_pct": round(target_return_pct, 4),
                "target_value_output": round(target_value, 4),
                "gap_to_target_output": round(gap_amount, 4),
                "target_progress_pct": round(target_progress_pct, 4),
            },
            "allocation": allocation,
            "secondary_allocation": secondary_allocation,
            "heatmap": heatmap,
            "fx": fx,
        }

    def _get_fx_rates(self, previous: Optional[Dict[str, Any]], refresh: bool) -> Dict[str, Any]:
        prev = previous if isinstance(previous, dict) else {}
        usd_cny = self._to_float(prev.get("usd_cny")) or 7.2
        hkd_cny = self._to_float(prev.get("hkd_cny")) or 0.92
        source = "cache"

        if refresh:
            fetched_usd_cny = self._fetch_pair_close("USDCNY=X")
            fetched_hkd_cny = self._fetch_pair_close("HKDCNY=X")
            usd_hkd = self._fetch_pair_close("USDHKD=X") or 7.8

            if fetched_usd_cny and fetched_usd_cny > 0:
                usd_cny = fetched_usd_cny
                source = "yfinance"
            if fetched_hkd_cny and fetched_hkd_cny > 0:
                hkd_cny = fetched_hkd_cny
                source = "yfinance"
            elif usd_cny > 0 and usd_hkd > 0:
                hkd_cny = usd_cny / usd_hkd
                source = "derived"

        return {
            "usd_cny": round(usd_cny, 6),
            "hkd_cny": round(hkd_cny, 6),
            "as_of": datetime.now().isoformat(timespec="seconds"),
            "source": source,
        }

    def _fetch_pair_close(self, symbol: str) -> Optional[float]:
        try:
            import yfinance as yf

            data = yf.download(
                tickers=symbol,
                period="5d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if data is None or data.empty:
                return None
            close = data.get("Close")
            if close is None:
                return None
            if hasattr(close, "columns"):
                if close.shape[1] <= 0:
                    return None
                close = close.iloc[:, 0]
            values = close.dropna()
            if values.empty:
                return None
            return float(values.iloc[-1])
        except Exception as exc:
            logger.debug("Failed to fetch fx pair %s: %s", symbol, exc)
            return None

    def _fetch_quote(self, symbol: str) -> Dict[str, Any]:
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist is None or hist.empty:
                return {}
            latest_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist["Close"]) > 1 else latest_close
            currency = ""
            name = ""
            try:
                info = ticker.fast_info
                if info:
                    currency = str(getattr(info, "currency", "") or "")
            except Exception:
                pass
            if not name:
                try:
                    info_data = ticker.get_info()
                    if isinstance(info_data, dict):
                        name = str(
                            info_data.get("shortName")
                            or info_data.get("longName")
                            or info_data.get("displayName")
                            or ""
                        ).strip()
                except Exception:
                    pass
            return {
                "latest_price": latest_close,
                "previous_close": prev_close,
                "currency": self._normalize_currency(currency or self._infer_currency_from_symbol(symbol)),
                "name": name,
            }
        except Exception as exc:
            logger.debug("Failed to fetch quote for %s: %s", symbol, exc)
            return {}

    def _resolve_quote_symbol(self, symbol: str, primary: str, secondary: str) -> str:
        upper = str(symbol or "").strip().upper()
        if not upper:
            return upper
        if primary == "加密货币":
            return upper if "-" in upper else f"{upper}-USD"
        if upper.endswith((".SS", ".SZ", ".HK")):
            return upper
        digits = "".join(ch for ch in upper if ch.isdigit())
        if len(digits) == 6:
            if secondary in {"A股"}:
                return f"{digits}.SS" if digits.startswith(("600", "601", "603", "605", "688")) else f"{digits}.SZ"
            if secondary in {"港股"}:
                return f"{digits[-4:].zfill(4)}.HK"
        if secondary in {"港股"} and len(digits) > 0:
            return f"{digits[-4:].zfill(4)}.HK"
        return upper

    def _normalize_primary_asset(self, value: Any) -> str:
        raw = str(value or "").strip()
        if raw in PRIMARY_ASSET_CLASSES:
            return raw

        # Backward compatibility for previous labels
        if raw in {"股票", "权益", "权益类"}:
            return "权益类"
        if raw in {"币", "加密", "数字货币"}:
            return "加密货币"
        if raw in {"贵金属类"}:
            return "贵金属"
        if raw in {"固收", "固定收益"}:
            return "债券"
        if raw in {"货基", "现金管理"}:
            return "货币基金"
        if raw in {"现金", "现金类", "活期现金"}:
            return "现金"
        return "权益类"

    def _normalize_secondary_asset(self, primary: str, secondary: Any) -> str:
        options = SECONDARY_ASSET_CLASSES.get(primary, [])
        raw = str(secondary or "").strip()
        if raw in options:
            return raw

        # Backward compatibility for previous labels
        if primary == "权益类":
            if raw in {"A股", "沪深A股", "沪市", "深市"}:
                return "A股"
            if raw in {"港股"}:
                return "港股"
            if raw in {"美股"}:
                return "美股"
            if raw in {"ETF"}:
                return "ETF"
        if primary == "现金":
            if raw in {"人民币现金", "人民币", "RMB", "CNY"}:
                return "人民币现金"
            if raw in {"美元现金", "美元", "USD"}:
                return "美元现金"
            if raw in {"港币现金", "港币", "HKD"}:
                return "港币现金"
            if raw in {"其他现金", "其他"}:
                return "其他现金"
        return options[0] if options else "A股"

    def _convert_fx_rate(self, from_currency: str, to_currency: str, fx: Dict[str, Any]) -> float:
        src = self._normalize_currency(from_currency)
        dst = self._normalize_currency(to_currency)
        usd_cny = max(0.000001, self._to_float(fx.get("usd_cny")) or 7.2)
        hkd_cny = max(0.000001, self._to_float(fx.get("hkd_cny")) or 0.92)

        if src == dst:
            return 1.0
        if src == "USD" and dst == "CNY":
            return usd_cny
        if src == "CNY" and dst == "USD":
            return 1.0 / usd_cny
        if src == "HKD" and dst == "CNY":
            return hkd_cny
        if src == "CNY" and dst == "HKD":
            return 1.0 / hkd_cny
        if src == "USD" and dst == "HKD":
            return usd_cny / hkd_cny
        if src == "HKD" and dst == "USD":
            return hkd_cny / usd_cny
        return 1.0

    def _infer_currency_from_symbol(self, symbol: str) -> str:
        upper = str(symbol or "").upper()
        if upper.endswith((".SS", ".SZ")):
            return "CNY"
        if upper.endswith(".HK"):
            return "HKD"
        return "USD"

    @staticmethod
    def _infer_cash_currency(secondary: str) -> str:
        text = str(secondary or "").strip()
        if "人民币" in text:
            return "CNY"
        if "港币" in text:
            return "HKD"
        if "美元" in text:
            return "USD"
        return "USD"

    @staticmethod
    def _normalize_text_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:20]

    @staticmethod
    def _normalize_currency(value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"RMB", "CNY", "CNH"}:
            return "CNY"
        if text == "HKD":
            return "HKD"
        return "USD"

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    def _read_payload(self) -> Dict[str, Any]:
        with self._lock:
            if not self._file_path.exists():
                return {
                    "target": {"initial_position": 0.0, "output_currency": "USD", "target_return_pct": 30.0},
                    "fx": {"usd_cny": 7.2, "hkd_cny": 0.92, "as_of": None, "source": "default"},
                    "holdings": [],
                    "macro_events": [],
                    "notes": "",
                }
            try:
                content = self._file_path.read_text(encoding="utf-8")
                data = json.loads(content)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {
                    "target": {"initial_position": 0.0, "output_currency": "USD", "target_return_pct": 30.0},
                    "fx": {"usd_cny": 7.2, "hkd_cny": 0.92, "as_of": None, "source": "default"},
                    "holdings": [],
                    "macro_events": [],
                    "notes": "",
                }

    def _write_payload(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self._file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
