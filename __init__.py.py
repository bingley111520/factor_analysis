"""因子分析包（Polars 版）。

================================================================
架构说明
================================================================
目录结构:
    config    —— 全局常量：指数映射、字段列表、主题、CSS
    utils     —— 底层算法（Polars）：IC、换手率、中性化
    plotter   —— Plotly 可视化，接收 pandas
    analyzer  —— 核心计算：FactorAnalyzer（Polars）
    report    —— 报告组装：ReportBuilder

数据格式约定:
    * FactorAnalyzer 纯计算，数据表通过参数传入（不再依赖 dai）。
    * 计算结果（whole_perf / yearly_perf / ic_df / group_cumret）保持 Polars。
    * ReportBuilder 在交给 plotter 前统一 .to_pandas() 桥接。
================================================================
"""
from __future__ import annotations

__all__ = [
    "AlphaConfig",
    "FactorAnalyzer",
    "FactorPlotter",
    "ReportBuilder",
]

from .config import AlphaConfig
from .plotter import FactorPlotter
from .analyzer import FactorAnalyzer
from .report import ReportBuilder