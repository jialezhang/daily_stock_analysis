"""Anomaly detection for daily market review."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from modules.daily_review.data.liquidity import LiquidityData
from modules.daily_review.data.macro import MacroData
from modules.daily_review.data.sector import SectorData
from modules.daily_review.data.stock import StockEntry


@dataclass
class AnomalyAlert:
    """Detected anomaly alert."""

    level: str
    name: str
    message: str
    action: str
    affected_markets: List[str] = field(default_factory=list)
    possible_cause: str = ""
    potential_impact: str = ""


def _norm_return(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if abs(value) > 1:
        return value / 100.0
    return value


def _norm_pct_to_decimal(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return value / 100.0


def _norm_treasury_change(macro: MacroData, days: int = 1) -> Optional[float]:
    point = macro.get("us_10y")
    if point is None:
        return None
    raw = point.daily_change_abs if days == 1 else point.change_5d_abs
    if raw is None:
        return None
    if point.value is not None and abs(point.value) > 20:
        return raw / 10.0
    return raw


def _sector_daily_for_stock(stock: StockEntry, sectors: SectorData) -> Optional[float]:
    if stock.market == "US":
        row = next((x for x in sectors.us if x.ticker == stock.sector), None)
        return row.daily_change_pct if row is not None else None
    if stock.market == "HK":
        row = next((x for x in sectors.hk if x.name == stock.sector or x.ticker == stock.sector), None)
        return row.daily_change_pct if row is not None else None
    if stock.market == "A":
        row = next((x for x in sectors.a if x.name == stock.sector), None)
        return row.daily_change_pct if row is not None else None
    return None


def _stock_vs_sector(stock: StockEntry, sectors: SectorData) -> Optional[float]:
    if stock.vs_sector is not None:
        return stock.vs_sector
    if stock.daily_change_pct is None:
        return None
    sector_daily = stock.sector_daily_change_pct
    if sector_daily is None:
        sector_daily = _sector_daily_for_stock(stock, sectors)
    if sector_daily is None:
        return None
    return stock.daily_change_pct - sector_daily


def detect_anomalies(
    macro: MacroData,
    liquidity: LiquidityData,
    stocks: List[StockEntry],
    sectors: SectorData,
) -> List[AnomalyAlert]:
    """Detect RED/YELLOW alerts with explicit rule checks."""

    alerts: List[AnomalyAlert] = []

    treasury_10y_daily_change = _norm_treasury_change(macro, days=1)
    treasury_10y_5d_change = _norm_treasury_change(macro, days=5)
    vix = macro.get("vix").value if macro.get("vix") is not None else None
    vix_daily_change_pct = _norm_pct_to_decimal(macro.get("vix").daily_change_pct) if macro.get("vix") is not None else None
    usd_index = macro.get("usd_index").value if macro.get("usd_index") is not None else None
    usd_cnh_daily_change_pct = (
        _norm_pct_to_decimal(macro.get("usd_cnh").daily_change_pct) if macro.get("usd_cnh") is not None else None
    )

    if treasury_10y_daily_change is not None and abs(treasury_10y_daily_change) > 0.15:
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="美债收益率剧震",
                message=f"10Y 美债单日变动 {treasury_10y_daily_change:.3f}，超过 0.15 阈值，利率冲击显著。",
                action="检查持仓中成长股和港股仓位，考虑减仓或对冲",
                affected_markets=["US", "HK"],
                possible_cause="美联储路径预期突变、通胀数据超预期或风险偏好骤降引发利率重定价。",
                potential_impact="美股成长板块估值承压，港股科技与高估值资产回撤风险上升。",
            )
        )

    if (vix is not None and vix > 30) or (vix_daily_change_pct is not None and vix_daily_change_pct > 0.30):
        change_text = f"{vix_daily_change_pct:.2%}" if vix_daily_change_pct is not None else "NA"
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="VIX 恐慌飙升",
                message=f"VIX={vix}, 日变动={change_text}，市场进入恐慌区间。",
                action="立即审视所有仓位，减仓至防守水平；若 VIX > 40 可分批观察建仓",
                affected_markets=["US", "HK", "A"],
                possible_cause="地缘事件、系统性风险或宏观数据冲击导致避险情绪集中释放。",
                potential_impact="美股波动急升并向全球传导，港股与A股高弹性板块风险偏好下降。",
            )
        )

    if usd_index is not None and (usd_index > 107 or usd_index < 99):
        action = "减仓港股和 A 股外资重仓股" if usd_index > 107 else "加仓新兴市场相关标的"
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="美元指数突破关键位",
                message=f"美元指数当前 {usd_index:.2f}，突破关键区间 99-107。",
                action=action,
                affected_markets=["HK", "A", "US"],
                possible_cause="美债利率与美元资产吸引力提升，或全球避险交易集中回流美元。",
                potential_impact="美元偏强压制港股与A股外资流入，并抬升新兴市场资产估值折现压力。",
            )
        )

    if liquidity.northbound_net_billion is not None and liquidity.northbound_net_billion < -100:
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="北向资金恐慌性流出",
                message=f"北向单日净流出 {liquidity.northbound_net_billion:.1f} 亿，低于 -100 亿。",
                action="减仓外资重仓股，等待资金流企稳",
                affected_markets=["A", "HK"],
                possible_cause="风险偏好下降、汇率压力上升或政策预期转弱导致外资集中撤出。",
                potential_impact="A股核心权重承压，港股中资权重同步受拖累，短线波动加大。",
            )
        )

    if liquidity.a_turnover_billion is not None and liquidity.a_turnover_billion < 5000:
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="A 股成交额断崖",
                message=f"A 股成交额 {liquidity.a_turnover_billion:.0f} 亿，低于 5000 亿。",
                action="停止交易，等待放量信号；轻仓时可关注左侧机会",
                affected_markets=["A"],
                possible_cause="增量资金缺席、情绪退潮，市场进入极端存量博弈。",
                potential_impact="个股流动性折价扩大，追涨策略失效概率上升，防守优先。",
            )
        )

    if usd_cnh_daily_change_pct is not None and usd_cnh_daily_change_pct > 0.005:
        alerts.append(
            AnomalyAlert(
                level="RED",
                name="离岸人民币急贬",
                message=f"USDCNH 日涨幅 {usd_cnh_daily_change_pct:.2%}，超过 0.5%。",
                action="减仓港股，关注央行是否出手维稳",
                affected_markets=["HK", "A"],
                possible_cause="美元走强叠加资本流动扰动，人民币资产风险溢价抬升。",
                potential_impact="港股与A股外资敏感板块承压，资金更偏好防守与高股息方向。",
            )
        )

    if vix is not None and 25 < vix <= 30:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="VIX 进入警戒区间",
                message=f"VIX 当前 {vix:.2f}，处于 25-30 警戒带。",
                action="控制仓位在 50% 以下，暂停加仓",
                affected_markets=["US", "HK", "A"],
                possible_cause="风险对冲需求上升，但尚未进入全面恐慌阶段。",
                potential_impact="全球风险资产波动率提升，高弹性板块回撤概率上升。",
            )
        )

    if treasury_10y_5d_change is not None and treasury_10y_5d_change > 0.20:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="美债收益率持续攀升",
                message=f"10Y 美债 5 日累计上行 {treasury_10y_5d_change:.3f}，超过 0.20。",
                action="逐步减仓长久期资产（成长股、港股科技）",
                affected_markets=["US", "HK"],
                possible_cause="通胀黏性与利率预期上修，长端利率中枢上移。",
                potential_impact="成长风格估值扩张受限，港股科技波动加大。",
            )
        )

    if liquidity.northbound_3d_cumulative is not None and liquidity.northbound_3d_cumulative < -150:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="北向资金连续流出",
                message=f"北向 3 日累计净流出 {liquidity.northbound_3d_cumulative:.1f} 亿，低于 -150 亿。",
                action="减仓外资重仓股，转向内资偏好板块",
                affected_markets=["A", "HK"],
                possible_cause="外资持续降低中国敞口，风险偏好未恢复。",
                potential_impact="A股大盘风格偏弱，港股资金承接不足时回撤风险上升。",
            )
        )

    margin_5d_change = _norm_return(liquidity.margin_balance_5d_change_pct)
    if margin_5d_change is not None and margin_5d_change < -0.02:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="融资盘去杠杆",
                message=f"融资余额 5 日变动 {margin_5d_change:.2%}，低于 -2%。",
                action="警惕融资盘踩踏，避开高融资占比个股",
                affected_markets=["A"],
                possible_cause="风险偏好下降触发融资资金主动降杠杆。",
                potential_impact="高弹性题材回撤加速，盘面波动率抬升。",
            )
        )

    if liquidity.a_turnover_3d_all_below_7000 is True:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="A 股持续缩量",
                message="A 股成交额连续 3 日低于 7000 亿。",
                action="降低交易频率，等待放量方向选择",
                affected_markets=["A"],
                possible_cause="场外增量观望，市场缺乏持续主线。",
                potential_impact="趋势延续性差，追涨回撤比恶化。",
            )
        )

    hyg_5d_return = _norm_return(liquidity.hyg_5d_return)
    if hyg_5d_return is not None and hyg_5d_return < -0.02:
        alerts.append(
            AnomalyAlert(
                level="YELLOW",
                name="美股信用利差走阔",
                message=f"HYG 5 日收益 {hyg_5d_return:.2%}，低于 -2%。",
                action="美股仓位转向防守型板块，减少高 beta 敞口",
                affected_markets=["US"],
                possible_cause="信用风险偏好下降，融资环境边际收紧。",
                potential_impact="高杠杆与高估值资产承压，防守板块相对占优。",
            )
        )

    for stock in stocks:
        if stock.daily_change_pct is None:
            continue

        stock_vs_sector = _stock_vs_sector(stock, sectors)
        if stock_vs_sector is not None and stock_vs_sector < -3.0:
            alerts.append(
                AnomalyAlert(
                    level="YELLOW",
                    name="持仓个股异动",
                    message=f"{stock.name} 当日涨跌 {stock.daily_change_pct:.2f}% ，相对板块超额 {stock_vs_sector:.2f}%。",
                    action="检查个股是否有利空消息，必要时执行止损",
                    affected_markets=[stock.market],
                    possible_cause="个股基本面或事件扰动强于板块层面变化。",
                    potential_impact="单一持仓拖累组合收益，需要重新评估仓位与止损阈值。",
                )
            )

        if stock.volume_ratio is not None and stock.volume_ratio > 3.0 and stock.daily_change_pct < -2.0:
            alerts.append(
                AnomalyAlert(
                    level="YELLOW",
                    name="持仓个股异常放量",
                    message=f"{stock.name} 放量比 {stock.volume_ratio:.2f} 且下跌 {stock.daily_change_pct:.2f}%。",
                    action="高度警惕，优先控制仓位风险",
                    affected_markets=[stock.market],
                    possible_cause="筹码松动或突发利空导致资金集中撤离。",
                    potential_impact="后续波动延续概率高，短期需降低单票风险暴露。",
                )
            )

    return sorted(alerts, key=lambda x: 0 if x.level == "RED" else 1)
