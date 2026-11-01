"""Plotly 可视化：绩效表格、IC 柱状、IC 累积、分组累积收益曲线。

绘图接口接收 pandas.DataFrame（analyzer 在调用前用 .to_pandas() 桥接）。
本模块只负责画图，不涉及任何数据计算。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .config import AlphaConfig


class FactorPlotter:
    """因子分析图表生成器。

    用法::

        fig = FactorPlotter.cumret_chart(df_pandas)
    """

    THEME = AlphaConfig.THEME

    # ==================================================================
    # 统一主题
    # ==================================================================
    @staticmethod
    def _apply_theme(fig: go.Figure,
                     title: str | None = None,
                     height: int | None = None) -> go.Figure:
        """施加统一背景、网格、外框、图例、字体样式。

        Args:
            fig:    Plotly Figure（原地修改并返回）。
            title:  可选标题；None 时不设置。
            height: 可选画布高度（像素）。
        """
        t = FactorPlotter.THEME
        fig.update_layout(
            template='plotly_white',
            paper_bgcolor=t['paper'],
            plot_bgcolor=t['bg'],
            font=dict(family='Arial, Microsoft YaHei, sans-serif',
                      size=12, color=t['font']),
            margin=dict(l=60, r=40, t=90, b=50),
            hoverlabel=dict(bgcolor='white', font_size=12, bordercolor=t['grid']),
            # 图例统一顶部居中、水平排列
            legend=dict(
                orientation='h',
                yanchor='bottom', y=1.02,
                xanchor='center', x=0.5,
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#e0e0e0', borderwidth=1,
                font=dict(size=11),
                itemsizing='constant',
            ),
        )
        if title:
            fig.update_layout(title=dict(
                text=title, x=0.5, xanchor='center',
                font=dict(size=16, color=t['font']),
            ))
        if height:
            fig.update_layout(height=height)

        # 坐标轴：显示网格，不显示零线，四边外框均显示
        for axis in (fig.update_xaxes, fig.update_yaxes):
            axis(
                showgrid=True, gridcolor=t['grid'], zeroline=False,
                linecolor=t['border'], linewidth=1,
                ticks='outside', tickcolor=t['border'],
                mirror=True, showline=True,
            )
        return fig

    # ==================================================================
    # HTML 表格
    # ==================================================================
    @staticmethod
    def html_table(df: pd.DataFrame) -> str:
        """把 DataFrame 渲染为带样式的 HTML 表格。

        - 浮点列保留 4 位小数，NaN 显示为空；
        - 交替行底色（odd/even class）；
        - 单元格文字可选中复制（CSS 中已声明 user-select）。

        Args:
            df: 要展示的 DataFrame。

        Returns:
            完整的 <table> HTML 字符串。
        """

        def fmt_cell(v, col):
            if pd.isna(v):
                return ''
            if pd.api.types.is_float_dtype(df[col]):
                return f'{v:,.4f}'
            return str(v)

        thead = '<tr>' + ''.join(f'<th>{c}</th>' for c in df.columns) + '</tr>'
        rows = []
        for i, (_, row) in enumerate(df.iterrows()):
            cls = 'odd' if i % 2 else 'even'
            cells = ''.join(f'<td>{fmt_cell(row[c], c)}</td>' for c in df.columns)
            rows.append(f'<tr class="{cls}">{cells}</tr>')

        return (f'<table class="perf-table"><thead>{thead}</thead>'
                f'<tbody>{"".join(rows)}</tbody></table>')

    # ==================================================================
    # IC 柱状图
    # ==================================================================
    @staticmethod
    def bar_chart(df: pd.DataFrame, title: str, x: str,
                  y: list[str]) -> go.Figure:
        """IC 柱状图：正红负蓝，可叠加若干滚动均值折线。

        Args:
            df: 数据。
            x:  横轴列名（通常是 'date'）。
            y:  [柱状列, 折线列1, 折线列2, ...]；第一个画柱，其余画线。

        Returns:
            Plotly Figure。
        """
        t = FactorPlotter.THEME
        fig = go.Figure()

        bar_col = y[0]
        # 正负值分别着色
        colors = np.where(df[bar_col].fillna(0) >= 0, t['ic_pos'], t['ic_neg'])
        # 数据点过多时降低柱状不透明度，避免糊成一片
        opacity = 0.85 if len(df) <= 500 else 0.35
        fig.add_trace(go.Bar(
            x=df[x], y=df[bar_col], name=bar_col,
            marker=dict(color=colors, line=dict(width=0)),
            opacity=opacity,
        ))

        # 叠加折线（第一条深灰，其余用调色板）
        for i, col in enumerate(y[1:]):
            fig.add_trace(go.Scatter(
                x=df[x], y=df[col], name=col, mode='lines',
                line=dict(width=2.2,
                          color='#2c3e50' if i == 0 else t['palette'][i]),
            ))

        fig.add_hline(y=0, line=dict(color='#95a5a6', width=1, dash='dot'))
        FactorPlotter._apply_theme(fig, title=title, height=460)
        fig.update_layout(barmode='overlay', hovermode='x unified')
        return fig

    # ==================================================================
    # IC 累积曲线
    # ==================================================================
    @staticmethod
    def ic_cum_chart(df: pd.DataFrame,
                     title: str = "IC 累积曲线") -> go.Figure:
        """IC 累积面积图。

        Args:
            df:    含 'date' 与 'ic_cumsum' 两列。
            title: 图表标题。

        Returns:
            Plotly Figure。
        """
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['date'], y=df['ic_cumsum'], name='IC累积',
            mode='lines', line=dict(width=2, color='#2c3e50'),
            fill='tozeroy', fillcolor='rgba(46, 117, 182, 0.15)',
            hovertemplate='%{x|%Y-%m-%d}<br>IC累积: %{y:.4f}<extra></extra>',
        ))
        fig.add_hline(y=0, line=dict(color='#bdc3c7', width=1, dash='dot'))
        FactorPlotter._apply_theme(fig, title=title, height=430)
        return fig

    # ==================================================================
    # 分组累积收益曲线
    # ==================================================================
    @staticmethod
    def cumret_chart(df: pd.DataFrame,
                     title: str = "分组累积收益率") -> go.Figure:
        """分组累积收益：分位数配色，多空/基准用特殊线型突出。

        df 的列应包含：
          - 数字字符串分组列（'0'..'N-1'），'0' 为空头、最大号为多头；
          - 可选 'ls'（多空组合）；
          - 可选 'bm'（基准）。

        Args:
            df:    累积收益 DataFrame，索引为日期。
            title: 图表标题。

        Returns:
            Plotly Figure。
        """
        t = FactorPlotter.THEME
        fig = go.Figure()

        # 提取数字分组列并按数值排序
        group_cols = sorted([c for c in df.columns if str(c).isdigit()], key=int)
        n = len(group_cols)
        max_group = group_cols[-1] if group_cols else None
        palette = t['quantile_palette']

        # ---- 分组曲线：从空头色渐变到多头色 ----
        for i, col in enumerate(group_cols):
            # n==1 时取中间色；否则在调色板两端之间均匀取色
            color = (palette[len(palette) // 2] if n == 1
                     else palette[int(i * (len(palette) - 1) / (n - 1))])
            is_short = (col == '0')
            is_long = (col == max_group)
            # 空头、多头曲线加粗突出
            width = 2.6 if (is_short or is_long) else 1.5

            q = int(col) + 1
            if is_short:
                name = f'Q{q} (空头)'
            elif is_long:
                name = f'Q{q} (多头)'
            else:
                name = f'Q{q}'

            fig.add_trace(go.Scatter(
                x=df.index, y=df[col], name=name, mode='lines',
                line=dict(width=width, color=color),
                hovertemplate='%{x|%Y-%m-%d}<br>' + name + ': %{y:.2%}<extra></extra>',
            ))

        # ---- 多空组合与基准（存在才画）----
        for col, name, color, width, dash in [
            ('ls', 'Long-Short', t['ls_color'], 2.8, 'solid'),
            ('bm', 'Benchmark', t['bm_color'], 2.0, '8px,6px'),
        ]:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col], name=name, mode='lines',
                    line=dict(width=width, color=color, dash=dash),
                    hovertemplate='%{x|%Y-%m-%d}<br>' + name + ': %{y:.2%}<extra></extra>',
                ))

        fig.add_hline(y=0, line=dict(color='#d0d0d0', width=1, dash='dot'))
        FactorPlotter._apply_theme(fig, title=title, height=640)
        # 额外调整：悬浮合并、坐标轴标题、百分比刻度
        fig.update_layout(
            hovermode='x unified',
            xaxis_title='日期',
            yaxis_title='累积收益率',
            legend=dict(
                orientation='h',
                yanchor='bottom', y=1.02,
                xanchor='center', x=0.5,
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor='#e0e0e0', borderwidth=1,
                font=dict(size=11),
                itemsizing='constant',
            ),
            margin=dict(l=60, r=40, t=110, b=50),
        )
        fig.update_yaxes(tickformat='.0%')
        return fig