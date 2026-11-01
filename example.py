"""使用示例：展示如何通过外部取数，然后调用框架生成报告。

运行::
    python -m factor_analysis.example
"""
import pandas as pd
import dai

from .analyzer import FactorAnalyzer
from .report import ReportBuilder


def get_data_from_dai(start_date="2022-01-01", end_date="2025-01-01"):
    """演示：在框架外部获取所有需要的 DataFrame。"""
    
    print("正在从 dai 获取因子数据...")
    factor_df = dai.query(f"""
        SELECT date, instrument, m_stddev(change_ratio, 5)/m_stddev(amount, 5) AS factor
        FROM cn_stock_bar1d 
        WHERE date >= '{start_date}' AND date <= '{end_date}'
    """).df()

    print("正在获取个股收益数据...")
    price_df = dai.query(f"""
        SELECT instrument, date, (m_lead(open, 2)/m_lead(open, 1) - 1) AS daily_ret
        FROM cn_stock_bar1d 
        WHERE date >= '{start_date}' AND date <= '{end_date}'
    """).df()

    print("正在获取基准收益数据...")
    bm_df = dai.query(f"""
        SELECT date, (close - m_Lag(close,1))/m_LAG(close, 1) AS benchmark_ret
        FROM cn_stock_index_bar1d 
        WHERE instrument = '000905.SH' AND date >= '{start_date}' AND date <= '{end_date}'
    """).df()

    print("正在获取基础信息（行业/市值/ST）...")
    # 这里需要根据你的实际数据库结构关联行业和市值表，这里简单合并示例
    base_df = dai.query(f"""
        SELECT b.date, b.instrument, b.st_status, b.trading_days, b.amount,
               v.total_market_cap, i.industry_level1_code
        FROM cn_stock_factors_base b
        LEFT JOIN cn_stock_valuation v ON b.date = v.date AND b.instrument = v.instrument
        LEFT JOIN cn_stock_industry_component i ON b.date = i.date AND b.instrument = i.instrument AND i.industry = 'sw2021'
        WHERE b.date >= '{start_date}' AND b.date <= '{end_date}'
    """).df()

    return factor_df, price_df, bm_df, base_df


if __name__ == "__main__":
    # 1. 准备数据
    factor_data, price_data, bm_data, base_data = get_data_from_dai()

    # 2. 配置参数
    params = {
        'group_num': 5,
        'factor_field': 'factor',       
        'instruments': '全市场',         
        'factor_direction': 1,           
        'benchmark': '中证500',          # 传 None 则不报错
        'data_process': True             # 开启预处理（需要 base_data 包含行业和市值）
    }

    # 3. 实例化并计算
    print("开始计算...")
    fa = FactorAnalyzer(
        params=params, 
        factor_data=factor_data,
        price_data=price_data,
        bm_data=bm_data,
        base_data=base_data
    )
    
    print(f"\n因子快速摘要: {fa.summary()}")

    # 4. 生成报告
    print("正在生成报告...")
    ReportBuilder(fa).render(output_html='factor_report.html', show=True)