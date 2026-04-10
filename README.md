# Brain - 量化交易框架

Brain 是一个智能量化交易框架，提供从数据获取、策略开发、回测验证到实盘交易的全流程支持。

## 特性

- **数据管理**: 支持多种数据源，包括 A 股实时和历史数据
- **策略开发**: 基于 Backtrader 的强大回测引擎
- **信号系统**: 灵活的信号生成和策略组合
- **风险控制**: 内置仓位管理和风险监控
- **实时监控**: Telegram 机器人实时推送交易信号
- **高性能**: 使用 Polars 进行快速数据处理

## 项目结构

```
brain/
├── data/
│   ├── raw/           # 原始数据
│   ├── processed/     # 处理后数据
│   └── features/      # 特征工程数据
├── strategies/        # 交易策略
├── backtest/          # 回测引擎
├── bots/              # 交易机器人
├── config/            # 配置文件
├── tests/             # 单元测试
└── examples/          # 使用示例
```

## 安装

### 使用 Poetry (推荐)

```bash
# 安装 Poetry
curl -sSL https://install.python-poetry.org | python3 -

# 克隆项目
git clone https://github.com/yourusername/brain.git
cd brain

# 安装依赖
poetry install

# 进入虚拟环境
poetry shell
```

### 使用 pip

```bash
pip install -r requirements.txt
```

## 快速开始

```python
from brain.strategies.macd import MACDStrategy
from brain.backtest.engine import BacktestEngine

# 创建策略
strategy = MACDStrategy(
    fast_period=12,
    slow_period=26,
    signal_period=9
)

# 运行回测
engine = BacktestEngine(
    strategy=strategy,
    start_date="2023-01-01",
    end_date="2023-12-31"
)
results = engine.run()
```

## 配置

配置文件位于 `config/` 目录：

- `data.yaml` - 数据源配置
- `strategy.yaml` - 策略参数配置
- `telegram.yaml` - Telegram 机器人配置

## 开发

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black brain/
```

### 类型检查

```bash
mypy brain/
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。使用本框架进行交易，风险自负。
