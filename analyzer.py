"""核心计算模块（Polars 版）：FactorAnalyzer。
"""
from __future__ import annotations

import time
import warnings

import numpy as np
import pandas as pd
import polars as pl
import empyrical

from .config import AlphaConfig
from .utils import AlphaUtils

warnings.filterwarnings('ignore')


class FactorAnalyzer:
    """因子分析主流程（Polars 实现）。

    用法::

        fa = FactorAnalyzer(
            params=params, 
            factor_data=factor_df,   # 必传：date, instrument, factor
            price_data=price_df,     # 必传：date, instrument, daily_ret
            bm_data=bm_df,           # 选传：date, benchmark_ret
            base_data=base_df        # 选传：date, instrument, st_status, trading_days, amount, industry_level1_code, total_market_cap
        )
    """

    TOP_N_INS = 5

    def __init__(self, params: dict, factor_data, 
                 price_data=None, bm_data=None, base_data=None):
        print('==================因子分析开始==================')
        self.t0 = time.time()
        self.params = self._validate_params(params)
        self._summary = None

        # 统一转为 Polars 格式
        def _to_pl(df):
            if df is None: return None
            return pl.from_pandas(df) if isinstance(df, pd.DataFrame) else df

        # 1. 初始化内部数据表
        self.factor_data = _to_pl(factor_data).rename(
            {self.params['factor_field']: 'factor'}
        ).with_columns(
            (pl.col('factor') * self.params['factor_direction']).alias('factor')
        )
        self.price_data = _to_pl(price_data)
        self.bm_ret = _to_pl(bm_data)
        self.base_data = _to_pl(base_data)

        self.check_data_format(self.factor_data)
        t1 = time.time()
        print(f"耗时:{np.round(t1 - self.t0)}秒 数据格式检查通过")

        # 2. 过滤股票池 (基于外部传入的 base_data)
        self.stock_pool_filter()
        t2 = time.time()
        print(f'耗时:{np.round(t2 - t1)}秒 股票池过滤完成')

        # 3. 预处理 (基于 base_data 中的行业和市值)
        if self.params['data_process']:
            self.factor_data = self.factor_data_process('factor')
        t3 = time.time()
        print(f"耗时:{np.round(t3 - t2)}秒 数据预处理完成")

        self.start_date = str(self.factor_data['date'].min())
        self.end_date = str(self.factor_data['date'].max())

        # 4. 合并收益并分组
        if self.price_data is None:
            raise ValueError("必须提供 price_data (包含 date, instrument, daily_ret)")
            
        self.merge_data = (
            self.factor_data.sort(['date', 'instrument'])
            .join(self.price_data.sort(['date', 'instrument']), 
                  on=['date', 'instrument'], how='left')
        )
        self.group_data = self.get_group_data()
        t4 = time.time()
        print(f'耗时:{np.round(t4 - t3)}秒 因子分组完成')

        # 5. 基准与分组累计收益
        if self.bm_ret is None:
            self.bm_ret = pl.DataFrame(schema={'date': pl.Date, 'benchmark_ret': pl.Float64})

        self.group_cumret = self.get_group_cumret()
        t5 = time.time()
        print(f'耗时:{np.round(t5 - t4)}秒 分组收益率计算完成')

        self.whole_perf = self.get_whole_perf()
        t6 = time.time()
        print(f'耗时:{np.round(t6 - t5)}秒 整体绩效计算完成')

        self.yearly_perf = self.get_yearly_perf()
        t7 = time.time()
        print(f'耗时:{np.round(t7 - t6)}秒 年度绩效计算完成')

        self.ic_df = self.get_IC_data('all')
        self.ic = self.ic_df
        self.t10 = time.time()
        print(f'耗时:{np.round(self.t10 - t7)}秒 IC计算完成')


    # ==================================================================
    # 参数与格式校验
    # ==================================================================
    @staticmethod
    def _validate_params(params: dict) -> dict:
        p = dict(params)
        p.setdefault('group_num', 10)
        p.setdefault('instruments', '全市场')
        p.setdefault('factor_direction', 1)
        p.setdefault('benchmark', None)
        p.setdefault('data_process', False)

        if p['group_num'] < 2:
            raise ValueError('group_num 至少为 2')
        if p['factor_direction'] not in (1, -1):
            raise ValueError('factor_direction 只能为 1 或 -1')
        return p

    def check_data_format(self, df: pl.DataFrame) -> None:
        inst = df['instrument'].cast(pl.Utf8)
        ok = (
            (inst.str.ends_with('.SH') | inst.str.ends_with('.SZ') |
             inst.str.ends_with('.BJ')).all()
        )
        if not ok:
            raise ValueError("instrument 应以 .SH / .SZ / .BJ 结尾")
        if not df['factor'].dtype.is_float():
            raise ValueError("factor 列应为浮点型")
        if df['factor'].null_count() > 0:
            raise ValueError("factor 列存在 NaN，请先处理")

    # ==================================================================
    # 股票池过滤
    # ==================================================================
    def stock_pool_filter(self) -> None:
        """利用传入的 base_data 过滤 ST / 新股 / 北交所 / 停牌。"""
        if self.base_data is None:
            print("  [提示] 未传入 base_data，跳过 ST/新股/停牌 过滤。")
            return

        # 提取 6 位裸代码用于关联
        merge_df = self.factor_data.with_columns(
            pl.col('instrument').str.split('.').list.first().alias('bare_code')
        )

        # 关联基础信息
        base_info_pl = self.base_data.rename({'instrument': 'bare_code'})
        df = merge_df.join(base_info_pl, on=['date', 'bare_code'], how='left')

        # 执行过滤规则
        df = df.filter(
            (pl.col('st_status') == 0) &
            (pl.col('trading_days') > 252) &
            (pl.col('bare_code').str.len_chars() == 6) &
            (pl.col('amount') > 0)
        )
        
        df = df.with_columns(
            pl.when(pl.col('factor').is_infinite())
              .then(None).otherwise(pl.col('factor')).alias('factor')
        ).drop_nulls(subset=['factor'])

        self.factor_data = df.select(['instrument', 'date', 'factor'])

    # ==================================================================
    # 因子预处理
    # ==================================================================
    def factor_data_process(self, col: str) -> pl.DataFrame:
        """去极值 + 标准化 + 行业市值中性化（依赖 base_data）。"""
        df = self.factor_data.unique(['date', 'instrument'])

        # 3σ 截断 + 标准化
        g = pl.col(col)
        mean = g.mean().over('date')
        std = g.std().over('date')
        df = df.with_columns(
            pl.min_horizontal(pl.max_horizontal(g, mean - 3 * std), mean + 3 * std).alias(col)
        ).with_columns(
            pl.when(std > 0).then((g - mean) / std).otherwise(0.0).alias(col)
        )

        # 中性化需要行业和市值
        if self.base_data is not None and 'industry_level1_code' in self.base_data.columns:
            df = df.join(
                self.base_data.select(['date', 'instrument', 'industry_level1_code', 'total_market_cap']),
                on=['date', 'instrument'], how='inner'
            ).with_columns(pl.col('total_market_cap').log().alias('log_cap'))
            
            df = AlphaUtils.batch_neutralize(df, col=col)
        else:
            print("  [提示] base_data 中缺少行业或市值数据，跳过中性化。")
            
        return df.sort('date')

    # ==================================================================
    # 分组
    # ==================================================================
    def get_group_data(self) -> pl.DataFrame:
        df = self.merge_data.drop_nulls(subset=['factor', 'daily_ret'])
        group_num = self.params['group_num']
        df = df.with_columns(
            (pl.col('factor').rank(method='ordinal').over('date') /
             pl.len().over('date')).alias('pct')
        ).with_columns(
            pl.min_horizontal((pl.col('pct') * group_num).cast(pl.Int32), pl.lit(group_num - 1)).cast(pl.Utf8).alias('group')
        ).drop('pct')
        return df

    # ==================================================================
    # 分组累积收益
    # ==================================================================
    def get_group_cumret(self) -> pl.DataFrame:
        groupret = (
            self.group_data
            .group_by(['date', 'group'])
            .agg(pl.col('daily_ret').mean().alias('g_ret'))
        )
        pivot = groupret.pivot(values='g_ret', index='date', on='group')
        for i in range(self.params['group_num']):
            if str(i) not in pivot.columns:
                pivot = pivot.with_columns(pl.lit(None).alias(str(i)))
                
        top_col = str(self.params['group_num'] - 1)
        pivot = pivot.with_columns((pl.col(top_col) - pl.col('0')).alias('ls'))

        # 基准对齐
        if self.bm_ret.height > 0:
            bm_series = self.bm_ret.select(['date', 'benchmark_ret'])
            pivot = pivot.join(bm_series, on='date', how='left').with_columns(
                pl.col('benchmark_ret').fill_null(0.0).alias('bm')
            ).drop('benchmark_ret')
        else:
            pivot = pivot.with_columns(pl.lit(0.0).alias('bm'))

        pivot = (
            pivot.sort('date')
            .with_columns(pl.all().exclude('date').shift(1))
            .drop_nulls(subset=[top_col])
        )
        self.groupret_pivotdata = pivot

        # 累积求和
        value_cols = [c for c in pivot.columns if c != 'date']
        pivot = pivot.with_columns([pl.col(c).cum_sum().alias(c) for c in value_cols])

        ordered = (['date'] + [str(i) for i in range(self.params['group_num'])] + ['ls', 'bm'])
        return pivot.select([c for c in ordered if c in pivot.columns])

    # ==================================================================
    # 绩效指标
    # ==================================================================
    def _pivot_to_pd(self) -> pd.DataFrame:
        if not hasattr(self, '_pivot_pd_cache'):
            self._pivot_pd_cache = self.groupret_pivotdata.to_pandas().set_index('date').sort_index()
        return self._pivot_pd_cache

    def get_Performance(self, data_type: str) -> dict:
        col_map = {'long': str(self.params['group_num'] - 1), 'short': '0', 'long_short': 'ls'}
        col = col_map[data_type]
        df = self._pivot_to_pd().dropna(subset=[col])
        series = df[col]
        bm = df['bm'].reindex(series.index).fillna(0)
        ex = series - bm
        return {
            'return_ratio': series.sum(),
            'annual_return_ratio': series.sum() * 242 / len(series),
            'ex_return_ratio': ex.sum(),
            'ex_annual_return_ratio': ex.sum() * 242 / len(ex),
            'sharp_ratio': empyrical.sharpe_ratio(series, 0.035 / 242),
            'return_volatility': empyrical.annual_volatility(series),
            'information_ratio': series.mean() / series.std(),
            'max_drawdown': empyrical.max_drawdown(series),
            'win_percent': (series > 0).sum() / len(series),
            'trading_days': len(series),
            **{f'ret_{n}': series.rolling(n).sum().iloc[-1] for n in [3, 10, 21, 63, 126, 252]},
        }

    # ==================================================================
    # IC 与换手率
    # ==================================================================
    def get_IC_data(self, data_type: str = 'all'):
        if data_type == 'all':
            ic_df = AlphaUtils.spearman_ic_by_date(self.group_data)
            ic_df = ic_df.sort('date').with_columns([
                pl.col('g_ic').cum_sum().alias('ic_cumsum'),
                pl.col('g_ic').rolling_mean(22).alias('ic_roll_ma'),
            ])
            self.ic_df = ic_df.filter(pl.col('g_ic').is_not_null())
            return self.ic_df

        g = str(self.params['group_num'] - 1)
        if data_type == 'long': data = self.group_data.filter(pl.col('group') == g)
        elif data_type == 'short': data = self.group_data.filter(pl.col('group') == '0')
        else: data = self.group_data.filter(pl.col('group').is_in(['0', g]))
        
        ic_df = AlphaUtils.spearman_ic_by_date(data).drop_nulls()
        ic_mean = ic_df['g_ic'].mean()
        ir = ic_mean / ic_df['g_ic'].std()
        result = {'ic': ic_mean, 'ir': ir}
        for n in [3, 10, 21, 63, 126, 252]:
            result[f'ic_{n}'] = ic_df['g_ic'].tail(n).mean()
        return result

    def get_Turnover_data(self, data_type: str) -> dict:
        g = str(self.params['group_num'] - 1)
        if data_type == 'long':
            return {'turnover': AlphaUtils.calc_turnover(self.group_data.filter(pl.col('group') == g))}
        if data_type == 'short':
            return {'turnover': AlphaUtils.calc_turnover(self.group_data.filter(pl.col('group') == '0'))}
        
        long_df = self.group_data.filter(pl.col('group') == g)
        short_df = self.group_data.filter(pl.col('group') == '0')
        return {'turnover': (AlphaUtils.calc_turnover(long_df) + AlphaUtils.calc_turnover(short_df))}

    # ==================================================================
    # 汇总绩效
    # ==================================================================
    def get_whole_perf(self) -> pl.DataFrame:
        rows = []
        for _type in ['long', 'short', 'long_short']:
            d = {}
            d.update(self.get_IC_data(_type))
            d.update(self.get_Performance(_type))
            d.update(self.get_Turnover_data(_type))
            d['portfolio'] = _type
            rows.append(d)
        return pl.DataFrame(rows)

    def get_yearly_perf(self) -> pl.DataFrame:
        pivot = self.groupret_pivotdata.with_columns(pl.col('date').dt.year().alias('year'))
        top_col = str(self.params['group_num'] - 1)

        yearly_rows = []
        for year, grp in pivot.group_by('year', maintain_order=True):
            year = year[0]
            df_pd = grp.to_pandas().set_index('date').sort_index()
            series = df_pd[top_col].dropna()
            if len(series) == 0: continue
            bm = df_pd['bm'].reindex(series.index).fillna(0)
            ex = series - bm
            yearly_rows.append({
                'year': str(year),
                'return_ratio': series.sum(),
                'annual_return_ratio': series.sum() * 242 / len(series),
                'ex_return_ratio': ex.sum(),
                'ex_annual_return_ratio': ex.sum() * 242 / len(ex),
                'sharp_ratio': empyrical.sharpe_ratio(series, 0.035 / 242),
                'return_volatility': empyrical.annual_volatility(series),
                'max_drawdown': empyrical.max_drawdown(series),
                'win_percent': (series > 0).sum() / len(series),
                'trading_days': int(len(series)),
            })
        perf = pl.DataFrame(yearly_rows)

        long_data = self.group_data.filter(pl.col('group') == top_col)
        ic_df = AlphaUtils.spearman_ic_by_date(long_data).drop_nulls()
        ic_df = ic_df.with_columns(pl.col('date').dt.year().alias('year'))
        year_ic = (
            ic_df.group_by('year').agg(pl.col('g_ic').mean().alias('ic')).with_columns(pl.col('year').cast(pl.Utf8))
        )
        perf_cols = [c for c in perf.columns if c != 'year']
        return perf.join(year_ic, on='year', how='left').select(['year', 'ic'] + perf_cols)

    def summary(self) -> dict:
        if self._summary is None:
            long_row = self.whole_perf.filter(pl.col('portfolio') == 'long').row(0, named=True)
            ls_row = self.whole_perf.filter(pl.col('portfolio') == 'long_short').row(0, named=True)
            self._summary = {
                'ic': round(long_row['ic'], 4), 'ir': round(long_row['ir'], 4),
                'turnover': round(long_row['turnover'], 4), 'long_annual': round(long_row['annual_return_ratio'], 4),
                'ls_annual': round(ls_row['annual_return_ratio'], 4), 'ls_sharpe': round(ls_row['sharp_ratio'], 4),
                'ls_mdd': round(ls_row['max_drawdown'], 4),
            }
        return self._summary