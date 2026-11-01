"""最小可运行自测：随机数据，验证 Polars 核心算法链路。

不依赖 dai / IPython，纯本地运行。
"""
import numpy as np
import pandas as pd
import polars as pl

from factor_analysis.utils import AlphaUtils


# ======================================================================
# 1. 造随机数据：50 只股票 × 100 天
# ======================================================================
rng = np.random.default_rng(42)
n_inst, n_day = 50, 100
instruments = [f"{i:06d}.SZ" for i in range(n_inst)]
dates = pd.bdate_range("2024-01-01", periods=n_day)

rows = []
for d in dates:
    for ins in instruments:
        rows.append({
            "date": d.date(),
            "instrument": ins,
            "factor": rng.normal(),
            "daily_ret": rng.normal(0, 0.02),
        })
df = pl.from_pandas(pd.DataFrame(rows))

print(f"数据: {df.height} 行, {df['date'].n_unique()} 天, {df['instrument'].n_unique()} 只股票")
print(df.head(3))

# ======================================================================
# 2. Spearman IC（按日）
# ======================================================================
ic = AlphaUtils.spearman_ic_by_date(df)
print("\n[IC]")
print(ic.head(3))
print(f"IC 均值: {ic['g_ic'].mean():.4f}  (随机数据应接近 0)")

# 与 scipy 对拍前 3 天
from scipy.stats import spearmanr
df_pd = df.to_pandas()
for d in ic['date'].head(3).to_list():
    sub = df_pd[df_pd['date'] == d]
    r, _ = spearmanr(sub['factor'], sub['daily_ret'])
    mine = ic.filter(pl.col('date') == d)['g_ic'][0]
    print(f"  {d}: polars={mine:.6f}  scipy={r:.6f}  diff={abs(mine-r):.2e}")

# ======================================================================
# 3. 换手率
# ======================================================================
turnover = AlphaUtils.calc_turnover(df)
print(f"\n[换手率] {turnover:.4f}  (随机全池持仓，应接近 0)")

# ======================================================================
# 4. 截面中性化（构造行业 + 市值）
# ======================================================================
df2 = df.with_columns([
    pl.Series("industry_level1_code",
              rng.choice(["A", "B", "C", "D"], size=df.height)),
    pl.Series("log_cap", rng.normal(10, 1, size=df.height)),
])
neutralized = AlphaUtils.batch_neutralize(df2, col="factor")
print("\n[中性化] 前后均值/标准差")
print(f"  前: mean={df2['factor'].mean():.6f}  std={df2['factor'].std():.6f}")
print(f"  后: mean={neutralized['factor'].mean():.6f}  std={neutralized['factor'].std():.6f}")
# 残差均值应≈0，与行业/市值相关性应≈0
corr_cap = np.corrcoef(
    neutralized["factor"].to_numpy(),
    neutralized["log_cap"].to_numpy(),
)[0, 1]
print(f"  残差 vs log_cap 相关系数: {corr_cap:.4f}  (应≈0)")

# ======================================================================
# 5. 分组累积收益（模拟 get_group_cumret 核心逻辑）
# ======================================================================
group_num = 5
gdf = df.with_columns(
    (pl.col("factor").rank(method="ordinal").over("date") /
     pl.len().over("date")).alias("pct")
).with_columns(
    pl.min_horizontal(
        (pl.col("pct") * group_num).cast(pl.Int32),
        pl.lit(group_num - 1)
    ).cast(pl.Utf8).alias("group")
).drop("pct")

groupret = gdf.group_by(["date", "group"]).agg(
    pl.col("daily_ret").mean().alias("g_ret"))
pivot = groupret.pivot(values="g_ret", index="date", on="group")
pivot = pivot.sort("date").with_columns(pl.all().exclude("date").shift(1))
value_cols = [c for c in pivot.columns if c != "date"]
pivot = pivot.with_columns([pl.col(c).cum_sum().alias(c) for c in value_cols])

print("\n[分组累积收益] 最后一行")
print(pivot.tail(1))
print("\n✅ 核心算法链路跑通")