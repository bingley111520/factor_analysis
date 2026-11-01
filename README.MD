# Factor Analysis (Polars 版)

基于 **Polars** 的高性能单因子分析框架。支持因子数据清洗、分组回测、IC 分析、行业市值中性化，并一键生成可交互的 HTML 分析报告。

## ✨ 特性

- ⚡ **极致性能**：底层计算全部基于 `Polars` 实现，相比 Pandas 有 5-10 倍的提速，尤其适合大体量面板数据。
- 📊 **交互式图表**：内置基于 `Plotly` 的报告生成器，直接产出带有可编辑标题、可复制表格、可缩放图表的 HTML 文件。
- 🛡️ **健壮的预处理**：内置去极值、标准化、以及基于行业与市值截面的 OLS 中性化（`batch_neutralize`）。
- 🔌 **零依赖数据源**：纯计算与渲染分离，兼容任意本地数据或数据库取数逻辑。

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
├── analyzer.py      # 核心计算 (FactorAnalyzer，Polars 实现)
├── report.py        # 报告组装 (ReportBuilder，输出 HTML)
└── example.py       # 使用示例
```

## 🚀 快速上手

### 1. 准备因子数据
准备一个包含 `instrument` (股票代码)、`date` (日期)、`factor` (因子值) 的 DataFrame（支持 `pandas` 或 `polars` 格式）。

### 2. 运行因子分析
```python
import polars as pl
from factor_analysis.analyzer import FactorAnalyzer
from factor_analysis.report import ReportBuilder

# 1. 载入你的因子数据 (这里以 polars 为例)
# factor_data = dai.query("...").df()

# 2. 配置参数
params = {
    'group_num': 5,                 # 分组数量
    'factor_field': 'factor',       # 因子列名
    'instruments': '全市场',        # 股票池: '沪深300' / '中证500' / '中证1000' / '全市场'
    'factor_direction': 1,          # 1代表因子越大越好，-1代表越小越好
    'benchmark': '中证500',         # 基准，传 None 或 '全市场' 则无基准
    'data_process': False           # 是否进行去极值、标准化、中性化
}

# 3. 实例化并计算
fa = FactorAnalyzer(params, factor_data)

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
| `instruments` | `str` | `'全市场'` | 股票池过滤选项 |
| `factor_direction` | `int` | `1` | 因子方向（1 正向，-1 反向） |
| `benchmark` | `str` | `None` | 基准指数。传 `None` 不报错，超额收益退化为绝对收益 |
| `data_process` | `bool` | `False` | 是否开启预处理（3σ去极值 + Z-score标准化 + 行业市值中性化） |

## ⚠️ 注意事项

1. **数据表依赖**：`FactorAnalyzer` 内部默认通过 `dai.query` 获取股票池、行业、市值和行情数据。如果在非 `dai` 环境下运行，你需要修改 `analyzer.py` 中的取数逻辑，或者直接使用 `SimpleNamespace` Mock 数据传给 `ReportBuilder`。
2. **PyArrow 依赖**：`Polars` 和 `Pandas` 之间的互相转换（例如给 Plotly 准备数据时）强依赖 `pyarrow`，请确保安装。
3. **中性化说明**：开启 `data_process=True` 时，代码会自动获取申万一级行业和总市值进行截面回归，剥离行业和风格暴露。如果当日某行业只有一只股票，代码已通过 `lstsq(gelsy)` 驱动处理秩亏，不会报错。

## 📝 待办事项 (TODO)

- [ ] **多因子批量回测报告生成**：支持输入因子列表，批量计算 IC、IR、多空收益等核心指标，并生成横向对比的总览报告（HTML），大幅提升因子筛选与评估效率。
- [ ] **数据源接口解耦**：将 `analyzer.py` 中强依赖的 `dai.query` 抽象为数据源接口，方便接入本地 CSV、MySQL 或其他数据平台。
- [ ] **单元测试补全**：针对 `utils.py` 中的 Polars 算法（IC、中性化等）增加与 Pandas/Scipy 的对比测试用例。
