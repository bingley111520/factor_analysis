# Factor Analysis (Polars 版)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Polars](https://img.shields.io/badge/Polars-0.20%2B-CD792C)

**基于 Polars 构建的高性能、去中心化单因子分析框架。**

## 📖 项目背景与参考来源

本项目参考了 **BigQuant 的因子分析框架**。原版框架功能完备，但深度绑定其底层数据接口（`dai`），导致在本地或其他量化平台复用时门槛较高。

为此，本项目进行了彻底的**去中心化重构**：将底层计算全面迁移至 `Polars` 以获得极致的运算性能，并将数据获取与核心计算逻辑完全解耦，成为了一个轻量级的纯计算库。

## 🎯 目的

为量化研究员提供一个**通用、高效、轻量**的因子评估工具。让研究员无论使用何种数据源（本地 CSV、MySQL、ClickHouse 或云端平台），都能以极低的接入成本，快速完成对 Alpha 因子的有效性检验与可视化评估，加速策略研发。

## ✨ 核心功能

- ⚡ **极致性能**：底层计算全部基于 `Polars` 实现，相比传统 Pandas 有 5-10 倍的提速，完美应对大体量面板数据。
- 🔌 **零数据源依赖**：解除了对特定数据库的强制依赖。用户只需传入标准的 DataFrame 即可运行，做到真正的随插随用。
- 🛡️ **健壮的预处理**：内置 3σ 去极值、Z-score 标准化，以及基于行业与市值截面的 OLS 中性化（`batch_neutralize`），并利用 `lstsq(gelsy)` 完美处理单行业个股的秩亏问题。
- 📊 **交互式图表**：内置基于 `Plotly` 的报告生成器，一键产出带有可编辑标题、可复制表格、可缩放图表的 HTML 报告，告别静态截图。

## 📦 环境依赖

请确保使用 Python 3.9+ 环境（推荐使用 Conda 管理）。

```bash
pip install polars pandas numpy scipy plotly empyrical-reloaded pyarrow
```
*(注：原版 `empyrical` 已停止维护，在 Python 3.12+ 下会编译失败，请安装维护分支 `empyrical-reloaded`，导入名依然是 `empyrical`)*

## 📂 目录结构

```text
factor_analysis/
├── __init__.py      # 包导出入口 (包含架构说明)
├── config.py        # 全局配置 (指数映射、绩效字段、CSS 样式)
├── utils.py         # 底层算法 (Spearman IC、换手率、OLS 中性化)
├── plotter.py       # Plotly 可视化 (接收 pandas，输出交互图表)
├── analyzer.py      # 核心计算 (FactorAnalyzer，纯计算无依赖)
├── report.py        # 报告组装 (ReportBuilder，输出 HTML)
└── example.py       # 使用示例
```

## 🚀 快速上手

### 1. 在外部准备数据
由于框架已彻底解耦，你需要自己查询数据（比如通过 SQL），并准备好以下 DataFrame：
- `factor_data`: 必须包含 `date`, `instrument`, `factor`。
- `price_data`: 必须包含 `date`, `instrument`, `daily_ret`（个股下一期收益率）。
- `bm_data`: 包含 `date`, `benchmark_ret`（基准收益，不传则无基准）。
- `base_data`: 包含 `date`, `instrument`, `st_status`, `trading_days`, `amount`, `industry_level1_code`, `total_market_cap`（用于过滤和中性化，不传则跳过相关步骤）。

### 2. 运行因子分析
```python
from factor_analysis.analyzer import FactorAnalyzer
from factor_analysis.report import ReportBuilder

# 1. 假设你已经从任意数据库查好了上述的 DataFrame
# factor_df, price_df, bm_df, base_df = your_query_function()

# 2. 配置参数
params = {
    'group_num': 5,                 # 分组数量
    'factor_field': 'factor',       # 因子列名
    'factor_direction': 1,          # 1代表因子越大越好，-1代表越小越好
    'benchmark': '中证500',         # 基准，传 None 或 '全市场' 则无基准
    'data_process': True            # 是否进行去极值、标准化、行业市值中性化
}

# 3. 实例化并计算
fa = FactorAnalyzer(
    params=params, 
    factor_data=factor_df,
    price_data=price_df,
    bm_data=bm_df,
    base_data=base_df
)

# 4. 打印快速摘要 (用于批量筛选因子)
print(fa.summary())

# 5. 生成并保存 HTML 报告
rb = ReportBuilder(fa)
rb.render(output_html='factor_report.html', show=False)
```

### 3. 查看报告
运行完毕后，当前目录下会生成 `factor_report.html`。
- **在浏览器中**：直接双击打开，即可查看交互式图表。
- **在 VS Code 中**：建议安装 `Live Preview` 插件，右键 HTML 文件选择 `Show Preview` 进行渲染。

## ⚙️ 参数说明

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `group_num` | `int` | `10` | 截面分组数量（建议 5 或 10） |
| `factor_field` | `str` | 必填 | 因子所在的列名 |
| `factor_direction` | `int` | `1` | 因子方向（1 正向，-1 反向） |
| `benchmark` | `str` | `None` | 基准指数。传 `None` 不报错，超额收益退化为绝对收益 |
| `data_process` | `bool` | `False` | 是否开启预处理（3σ去极值 + Z-score标准化 + 行业市值中性化） |

## 📝 待办事项 (TODO)

- [ ] **多因子批量回测报告生成**：支持输入因子列表，批量计算 IC、IR、多空收益等核心指标，并生成横向对比的总览报告（HTML），大幅提升因子筛选与评估效率。
- [ ] **单元测试补全**：针对 `utils.py` 中的 Polars 算法（IC、中性化等）增加与 Pandas/Scipy 的对比测试用例。

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 协议开源。
这意味着你可以自由地使用、修改、分发代码，甚至用于**商业项目**，唯一的要求是保留原作者的版权声明和许可声明。