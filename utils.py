"""算法工具（Polars 版）：按日 Spearman IC、换手率、截面中性化。

全部基于 polars + numpy 实现，输入输出均为 polars.DataFrame。
本模块无状态、无外部依赖（除 numpy/scipy/polars），便于单测。
"""
from __future__ import annotations

import numpy as np
import polars as pl
from scipy.linalg import lstsq as scipy_lstsq


class AlphaUtils:
    """因子分析底层算法集合（Polars）。"""

    # ==================================================================
    # IC 计算
    # ==================================================================
    @staticmethod
    def spearman_ic_by_date(df: pl.DataFrame,
                            x: str = 'factor',
                            y: str = 'daily_ret') -> pl.DataFrame:
        """按日计算 Spearman 秩相关 IC。

        原理：Spearman = 秩变换后的 Pearson。先按日对 x/y 做秩变换，
        再用 Pearson 展开式一次性聚合，避免逐日 Python 循环。

        Args:
            df: 含 date / x / y 三列。
            x:  因子列名。
            y:  收益列名。

        Returns:
            pl.DataFrame[date, g_ic]，按日期升序。
            输入为空时返回同 schema 空表，调用方可安全 concat。
        """
        df = df.select(['date', x, y]).drop_nulls()
        if df.height == 0:
            return pl.DataFrame(schema={'date': pl.Date, 'g_ic': pl.Float64})

        # 秩变换：over('date') 即按日截面 rank
        df = df.with_columns([
            pl.col(x).rank().over('date').alias('rx'),
            pl.col(y).rank().over('date').alias('ry'),
        ]).with_columns([
            (pl.col('rx') * pl.col('rx')).alias('rx_sq'),
            (pl.col('ry') * pl.col('ry')).alias('ry_sq'),
            (pl.col('rx') * pl.col('ry')).alias('rxy'),
        ])

        # 一次性聚合出 Pearson 所需统计量
        agg = df.group_by('date').agg([
            pl.len().alias('n'),
            pl.col('rx').sum().alias('sx'),
            pl.col('ry').sum().alias('sy'),
            pl.col('rx_sq').sum().alias('sxx'),
            pl.col('ry_sq').sum().alias('syy'),
            pl.col('rxy').sum().alias('sxy'),
        ])

        # Pearson 展开：cov=Σxy-ΣxΣy/n，denom=sqrt(var_x·var_y)
        agg = agg.with_columns([
            (pl.col('sxy') - pl.col('sx') * pl.col('sy') / pl.col('n')).alias('cov'),
            (
                (pl.col('sxx') - pl.col('sx') ** 2 / pl.col('n')) *
                (pl.col('syy') - pl.col('sy') ** 2 / pl.col('n'))
            ).sqrt().alias('denom'),
        ]).with_columns(
            # denom=0（当日全部同值）时置 null 表示该日 IC 无效
            pl.when(pl.col('denom') > 0)
              .then(pl.col('cov') / pl.col('denom'))
              .otherwise(None)
              .alias('g_ic')
        )

        return agg.select(['date', 'g_ic']).sort('date')

    # ==================================================================
    # 换手率
    # ==================================================================
    @staticmethod
    def calc_turnover(df: pl.DataFrame) -> float:
        """组合换手率 = 相邻交易日持仓变动的平均比例。

        算法：把日期映射为整数索引；对每只股票找它上次出现的索引，
        若恰为前一交易日则视为「持有未变」，否则换手。
        口径衡量持仓名单变动，不含权重变动。

        Args:
            df: 含 date / instrument 的持仓明细（当日持有即一行）。

        Returns:
            平均日换手率（0~1）。少于 2 个交易日时无相邻比较，返回 0。
        """
        d = df.select(['date', 'instrument']).unique()

        # 日期 -> 0..T-1 整数索引
        date_idx = d.select('date').unique().sort('date').with_row_index('d_idx')
        d = d.join(date_idx, on='date').sort(['instrument', 'd_idx'])

        # 同一股票前一行的日期索引；首行为 null
        d = d.with_columns(
            pl.col('d_idx').shift(1).over('instrument').alias('prev_idx')
        ).with_columns(
            # 差分==1 说明昨日也持有
            (pl.col('d_idx') - pl.col('prev_idx') == 1).alias('is_repeat')
        )

        agg = d.group_by('d_idx').agg([
            pl.len().alias('total'),
            pl.col('is_repeat').sum().alias('repeat'),
        ])
        if agg.height < 2:
            return 0.0
        return float((1 - agg['repeat'] / agg['total']).mean())

    # ==================================================================
    # 截面中性化
    # ==================================================================

    @staticmethod
    def batch_neutralize(df: pl.DataFrame,
                         col: str,
                         industry_col: str = 'industry_level1_code',
                         cap_col: str = 'log_cap') -> pl.DataFrame:
        """按日截面中性化：行业哑变量 + 对数市值回归取残差。"""
        df = df.drop_nulls().sort('date')
        if df.height == 0:
            return df

        # 使用 numpy 手动重新编码，彻底避开 Polars to_physical 的版本差异
        ind_series = df[industry_col]
        unique_inds = ind_series.unique().to_list()
        ind_map = {k: v for v, k in enumerate(unique_inds)}
        ind_codes_np = np.array([ind_map[x] for x in ind_series.to_list()])
        
        n_ind = len(unique_inds)
        dummies = np.eye(n_ind, dtype=np.float64)[ind_codes_np]
        
        log_cap = df[cap_col].to_numpy().reshape(-1, 1)
        X_all = np.hstack([dummies, log_cap])
        y_all = df[col].to_numpy().astype(np.float64)

        # 按日期切成连续块，逐块求解
        dates = df['date'].to_numpy()
        order = np.argsort(dates, kind='mergesort')
        _, starts = np.unique(dates[order], return_index=True)
        ends = np.append(starts[1:], len(order))

        residuals = np.empty_like(y_all)
        for s, e in zip(starts, ends):
            idx = order[s:e]
            # gelsy：QR 分解驱动，可处理秩亏（某行业当日仅 1 只股）
            coef, *_ = scipy_lstsq(X_all[idx], y_all[idx], lapack_driver='gelsy')
            residuals[idx] = y_all[idx] - X_all[idx] @ coef

        return df.with_columns(pl.Series(col, residuals))