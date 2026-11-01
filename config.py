"""全局配置：指数映射、绩效字段列表、配色主题、报告 CSS。

纯常量模块，不依赖任何第三方库，可被任意模块安全导入。
"""
from __future__ import annotations


class AlphaConfig:
    """因子分析全局配置。只存放常量，不含逻辑。"""

    # -------------------------------------------------------------------
    # 指数名称 -> 交易代码
    #
    # '全市场' 无基准指数，值设为 None（而非字符串），下游用 `is None`
    # 判断即可。benchmark 为 None 时超额收益退化为绝对收益，不报错。
    # -------------------------------------------------------------------
    INDEX_CODE_MAP = {
        "沪深300": '000300.SH',
        "中证500": '000905.SH',
        "中证1000": '000852.SH',
        "全市场": None,
    }

    # 整体绩效表展示字段（顺序即列顺序），与 FactorAnalyzer.whole_perf 列名一致
    WHOLE_PERF_FIELDS = [
        'portfolio', 'ic', 'ir', 'turnover', 'return_ratio', 'annual_return_ratio',
        'ex_return_ratio', 'ex_annual_return_ratio', 'sharp_ratio',
        'return_volatility', 'information_ratio', 'max_drawdown',
        'win_percent', 'ic_252', 'ret_252',
    ]

    # 年度绩效表展示字段
    YEARLY_PERF_FIELDS = [
        'year', 'ic', 'return_ratio', 'annual_return_ratio', 'ex_return_ratio',
        'ex_annual_return_ratio', 'sharp_ratio', 'return_volatility',
        'max_drawdown', 'win_percent', 'trading_days',
    ]

    # -------------------------------------------------------------------
    # 配色主题
    #   paper/bg 画布与绘图区背景；grid/border 网格与外框；font 文字
    #   quantile_palette 分组曲线：索引0空头(深蓝) → 末尾多头(深红)
    #   ls_color/bm_color 多空与基准曲线；ic_pos/ic_neg IC 柱状正负色
    # -------------------------------------------------------------------
    THEME = dict(
        paper='#ffffff',
        bg='#ffffff',
        grid='#f0f0f0',
        border='#c8ccd0',
        font='#2c3e50',
        font_sub='#7f8c8d',
        quantile_palette=[
            '#313695', '#4575B4', '#74ADD1', '#ABD9E9',
            '#D1E5F0', '#FDD17D', '#FDAE61', '#F46D43',
            '#D73027', '#A50026',
        ],
        ls_color='#F26F21',
        bm_color='#34495e',
        ic_pos='#E64B35',
        ic_neg='#083C5F',
        palette=['#4575B4', '#74ADD1', '#ABD9E9', '#FDD17D', '#FDAE61', '#F46D43', '#D73027'],
    )

    # -------------------------------------------------------------------
    # 报告 HTML 样式。选择器均以 .factor-report 作用域限定，避免污染
    # Jupyter 全局样式。标题 contenteditable 可双击编辑；表格/图内文字可选中。
    # -------------------------------------------------------------------
    REPORT_CSS = """
    .factor-report {
        font-family: Arial, 'Microsoft YaHei', sans-serif;
        background: #fafbfc; color: #2c3e50;
        padding: 24px 32px;
        box-sizing: border-box;
    }
    .factor-report .report-title { text-align: center; color: #1f4e79; margin: 0 0 8px; font-size: 26px; }
    .factor-report .report-info  { text-align: center; color: #7f8c8d; font-size: 13px; margin: 0 0 16px; }
    .factor-report .report-nav   { text-align: center; padding: 10px 0; margin-bottom: 20px;
                                   border-bottom: 1px solid #e8eaed; }
    .factor-report .report-nav a { margin: 0 12px; color: #1f4e79; text-decoration: none; font-size: 14px; }
    .factor-report .report-nav a:hover { text-decoration: underline; }
    .factor-report .hint { text-align: center; color: #a0a8b0; font-size: 12px; margin: 4px 0 20px; }

    .factor-report .chart-block { margin-bottom: 44px; }

    .factor-report .chart-title {
        text-align: center; font-size: 17px; font-weight: 600;
        color: #2c3e50; margin: 0 0 14px; padding: 6px 10px;
        border-radius: 4px; outline: none;
        display: block; width: 100%; box-sizing: border-box;
        transition: background .15s;
    }
    .factor-report .chart-title:hover { background: #f0f4f8; cursor: text; }
    .factor-report .chart-title:focus { background: #e8f0fa; box-shadow: 0 0 0 2px #1f4e79 inset; }

    .factor-report .perf-table {
        width: 100%; border-collapse: collapse;
        font-size: 13px; font-family: Arial, 'Microsoft YaHei', sans-serif;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .factor-report .perf-table thead th {
        background: #1f4e79; color: white; padding: 9px 12px;
        text-align: center; font-weight: 600;
        white-space: nowrap; border: 1px solid #1f4e79;
    }
    .factor-report .perf-table tbody td {
        padding: 6px 12px; border: 1px solid #eef1f5; color: #2c3e50;
        text-align: center;
    }
    .factor-report .perf-table tbody tr.odd  td { background: #f7f9fc; }
    .factor-report .perf-table tbody tr.even td { background: #ffffff; }

    .factor-report .js-plotly-plot text,
    .factor-report .js-plotly-plot .gtitle,
    .factor-report .js-plotly-plot .gtitle tspan,
    .factor-report .js-plotly-plot .legend text {
        user-select: text !important;
        -webkit-user-select: text !important;
        cursor: text;
    }
    """