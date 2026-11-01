"""HTML 报告组装：把 FactorAnalyzer 的计算结果渲染成报告。

职责：
  - 把各计算结果拼成 [(title, html, fig), ...] 内容块
  - 生成头部信息 + 导航
  - 保存为独立 HTML 文件（可选）/ 在 Jupyter 中逐块显示（可选）
  - 不包含任何因子计算逻辑

关于 Plotly.js 加载：
  - 保存文件时，只在第一个图里内联完整 plotly.js（include_plotlyjs=True），
    其余图 include_plotlyjs=False，避免重复加载导致文件膨胀。
  - Jupyter 内联显示时，图用 IPython 原生 display(fig) 渲染，
    不经过 pio.to_html，因此无需关心 include_plotlyjs。
"""
from __future__ import annotations

import pandas as pd
import polars as pl
import plotly.io as pio

from .config import AlphaConfig
from .plotter import FactorPlotter


class ReportBuilder:
    """因子分析报告生成器。

    用法::

        rb = ReportBuilder(analyzer)
        rb.render(output_html='report.html', show=True)   # 保存 + 显示
        rb.render(output_html=None, show=True)            # 仅显示
        rb.render(output_html='report.html', show=False)  # 仅写文件
    """

    def __init__(self, analyzer):
        """
        Args:
            analyzer: FactorAnalyzer 实例（已完成计算）。
        """
        self.analyzer = analyzer
        self.plotter = FactorPlotter()

    # ==================================================================
    # Polars -> pandas 桥接
    # ==================================================================
    @staticmethod
    def _to_pd(df) -> pd.DataFrame:
        """统一转 pandas；已为 pandas 则原样返回。"""
        if isinstance(df, pl.DataFrame):
            return df.to_pandas()
        return df

    # ==================================================================
    # 内容块：表格类
    # ==================================================================
    def _ic_summary_table(self) -> pd.DataFrame:
        """IC 汇总指标表（IC 均值 / |IC|>0.02 占比 / IR）。"""
        ic_df = self.analyzer.ic_df
        ic_mean = ic_df['g_ic'].mean()
        ir = ic_mean / ic_df['g_ic'].std()
        abs_ic = ic_df['g_ic'].abs()
        n = abs_ic.len()
        return pd.DataFrame({
            'IC': [round(ic_mean, 4)],
            '|IC|>0.02': [round((abs_ic >= 0.02).sum() / n, 4)],
            'IR': [round(ir, 4)],
        })

    def _top_bottom_tables(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """最后一天因子值最大 / 最小的 Top N 标的表。"""
        fa = self.analyzer
        # 取因子数据最后一天
        last_date = fa.factor_data['date'].max()
        last_day = (
            fa.factor_data
            .filter(pl.col('date') == last_date)
            .sort('factor')
            .to_pandas()
        )
        last_day['date'] = pd.to_datetime(last_day['date']).dt.strftime('%Y-%m-%d')
        cols = ['date', 'instrument', 'factor']
        df_max = last_day.nlargest(fa.TOP_N_INS, 'factor')[cols]
        df_min = last_day.nsmallest(fa.TOP_N_INS, 'factor')[cols]
        return df_max, df_min

    # ==================================================================
    # 内容块：图表类
    # ==================================================================
    def _cumret_block(self) -> tuple[str, object]:
        """分组累积收益率曲线块。返回 (html, fig)。"""
        cumret_pd = self._to_pd(self.analyzer.group_cumret).set_index('date')
        fig = self.plotter.cumret_chart(cumret_pd)
        fig.update_layout(title=None, margin=dict(t=20))
        return pio.to_html(fig, include_plotlyjs=False, full_html=False), fig

    def _ic_bar_block(self) -> tuple[str, object]:
        """IC 柱状 + 滚动均值曲线块。"""
        ic_pd = self._to_pd(self.analyzer.ic_df)
        fig = self.plotter.bar_chart(ic_pd, "", x='date', y=['g_ic', 'ic_roll_ma'])
        fig.update_layout(title=None, margin=dict(t=20))
        return pio.to_html(fig, include_plotlyjs=False, full_html=False), fig

    def _ic_cum_block(self) -> tuple[str, object]:
        """IC 累积曲线块。"""
        ic_pd = self._to_pd(self.analyzer.ic_df)
        fig = self.plotter.ic_cum_chart(ic_pd, "")
        fig.update_layout(title=None, margin=dict(t=20))
        return pio.to_html(fig, include_plotlyjs=False, full_html=False), fig

    # ==================================================================
    # 内容块汇总
    # ==================================================================
    def build_blocks(self) -> list[tuple[str, str, object]]:
        """构建所有内容块。

        Returns:
            [(title, html_str, plotly_fig_or_None), ...]
            fig 为 None 表示纯 HTML 表格；否则为 Plotly Figure
            （Jupyter 内联渲染用，保存文件时用其中的 html_str）。
        """
        fa = self.analyzer
        p = self.plotter
        blocks = []

        # 1. 整体绩效表
        whole_pd = self._to_pd(fa.whole_perf)
        whole_fields = [f for f in AlphaConfig.WHOLE_PERF_FIELDS
                        if f in whole_pd.columns]
        blocks.append(("整体绩效指标",
                       p.html_table(whole_pd[whole_fields]),
                       None))

        # 2. 年度绩效表
        year_pd = self._to_pd(fa.yearly_perf)
        year_fields = [f for f in AlphaConfig.YEARLY_PERF_FIELDS
                       if f in year_pd.columns]
        blocks.append(("年度绩效指标(多头组合)",
                       p.html_table(year_pd[year_fields]),
                       None))

        # 3. 分组累积收益率曲线
        html, fig = self._cumret_block()
        blocks.append(("分组累积收益率", html, fig))

        # 4. IC 汇总表
        blocks.append(("IC分析指标",
                       p.html_table(self._ic_summary_table()),
                       None))

        # 5. IC 曲线
        html, fig = self._ic_bar_block()
        blocks.append(("IC曲线", html, fig))

        # 6. IC 累积曲线
        html, fig = self._ic_cum_block()
        blocks.append(("IC累积曲线", html, fig))

        # 7. Top / Bottom 因子表
        df_max, df_min = self._top_bottom_tables()
        n = fa.TOP_N_INS
        blocks.append((f"因子值最大的{n}只标的", p.html_table(df_max), None))
        blocks.append((f"因子值最小的{n}只标的", p.html_table(df_min), None))

        return blocks

    # ==================================================================
    # 头部 / 导航
    # ==================================================================
    def _build_info_nav(self, blocks) -> tuple[str, str]:
        """构造报告头部信息行 + 锚点导航。"""
        fa = self.analyzer
        p = fa.params
        bm_text = p['benchmark'] if p['benchmark'] else '无'
        info = (f"因子: {p['factor_field']} | 股票池: {p['instruments']} | "
                f"分组: {p['group_num']} | 方向: {p['factor_direction']} | "
                f"基准: {bm_text} | 区间: {fa.start_date} ~ {fa.end_date}")
        titles = [t for t, _, _ in blocks]
        nav = "".join(f"<a href='#c{i}'>{name}</a>"
                      for i, name in enumerate(titles))
        return info, nav

    # ==================================================================
    # HTML 拼装
    # ==================================================================
    @staticmethod
    def _wrap_block(i: int, title: str, content: str) -> str:
        """单个内容块：可编辑标题 + 内容。"""
        return (
            f"<div class='chart-block' id='c{i}'>"
            f"<h2 class='chart-title' contenteditable='true' "
            f"spellcheck='false'>{title}</h2>"
            f"{content}"
            "</div>"
        )

    def _blocks_to_html(self, blocks, info: str, nav: str,
                        first_fig_js: bool = True) -> str:
        """拼出完整 HTML。

        Args:
            first_fig_js: 是否把完整 plotly.js 内联到第一个图里。
                          保存独立文件时必须为 True（否则离线打开无 js）。
        """
        body = (
            "<div class='factor-report'>"
            "<h1 class='report-title'>因子分析报告</h1>"
            f"<p class='report-info'>{info}</p>"
            f"<nav class='report-nav'>{nav}</nav>"
            "<p class='hint'>标题双击可编辑 · 表格单元格可选中复制 · 图例可点击切换</p>"
        )
        first_fig_done = False
        for i, (title, content, fig) in enumerate(blocks):
            # 第一个图注入完整 plotly.js，其余复用
            if fig is not None and first_fig_js and not first_fig_done:
                content = pio.to_html(fig, include_plotlyjs=True, full_html=False)
                first_fig_done = True
            body += self._wrap_block(i, title, content)
        body += "</div>"
        return body

    # ==================================================================
    # 对外入口
    # ==================================================================
    def render(self, output_html: str | None = 'factor_report.html',
               show: bool = True) -> list:
        """生成报告。

        Args:
            output_html: 保存路径。
                         - 字符串：保存到该路径；
                         - None：**不保存文件**，仅显示 / 返回 blocks。
            show:        是否在 Jupyter 中逐块显示。
                         - True：若在 IPython 环境，逐块 display；
                         否则仅打印保存路径。
                         - False：不显示，只保存 / 返回 blocks。

        Returns:
            blocks 列表 [(title, html_str, fig), ...]
        """
        blocks = self.build_blocks()
        info, nav = self._build_info_nav(blocks)

        # ---- 保存完整 HTML 文件（可选）----
        if output_html is not None:
            body = self._blocks_to_html(blocks, info, nav, first_fig_js=True)
            full_html = (
                "<!DOCTYPE html><html lang='zh-CN'><head>"
                "<meta charset='utf-8'><title>因子分析报告</title>"
                f"<style>{AlphaConfig.REPORT_CSS}</style>"
                "</head><body>"
                f"{body}"
                "</body></html>"
            )
            with open(output_html, 'w', encoding='utf-8') as f:
                f.write(full_html)

        # ---- Jupyter 显示 ----
        if show:
            try:
                from IPython.display import display, HTML

                # 头部（标题、信息、导航）
                display(HTML(
                    f"<style>{AlphaConfig.REPORT_CSS}</style>"
                    "<div class='factor-report'>"
                    "<h1 class='report-title'>因子分析报告</h1>"
                    f"<p class='report-info'>{info}</p>"
                    f"<nav class='report-nav'>{nav}</nav>"
                    "</div>"
                ))

                # 逐块显示：标题用 HTML，表格用 HTML，图用 display(fig)
                for i, (title, html_str, fig) in enumerate(blocks):
                    head = (
                        f"<style>{AlphaConfig.REPORT_CSS}</style>"
                        "<div class='factor-report' style='margin-bottom:0;'>"
                        f"<div class='chart-block' id='c{i}' style='margin-bottom:16px;'>"
                        f"<h2 class='chart-title' contenteditable='true' "
                        f"spellcheck='false'>{title}</h2>"
                        "</div></div>"
                    )
                    display(HTML(head))
                    if fig is None:
                        # 纯 HTML 表格
                        display(HTML(
                            f"<style>{AlphaConfig.REPORT_CSS}</style>"
                            "<div class='factor-report' style='margin-bottom:44px;'>"
                            f"{html_str}</div>"
                        ))
                    else:
                        # Plotly 图用 IPython 原生渲染
                        display(fig)
            except ImportError:
                if output_html is not None:
                    print(f"报告已保存至: {output_html}")
                else:
                    print("非 IPython 环境，且未指定 output_html，报告未输出。")

        return blocks