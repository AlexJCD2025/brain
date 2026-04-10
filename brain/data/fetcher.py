"""
数据获取模块 - 使用 AKShare 获取金融数据
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl


class DataFetcher:
    """
    数据获取器，用于从 AKShare 获取股票和指数数据

    支持自动缓存到 parquet 文件，提高重复查询效率
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化数据获取器

        Args:
            cache_dir: 缓存目录路径，默认为 brain/data/cache
        """
        if cache_dir is None:
            # 默认缓存目录在项目根目录下的 data/cache
            self.cache_dir = Path(__file__).parent.parent.parent / "data" / "cache"
        else:
            self.cache_dir = Path(cache_dir)

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, symbol: str, data_type: str, start_date: str, end_date: str) -> Path:
        """
        生成缓存文件路径

        Args:
            symbol: 股票代码
            data_type: 数据类型 (stock/index)
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            缓存文件路径
        """
        cache_key = f"{data_type}_{symbol}_{start_date}_{end_date}.parquet"
        return self.cache_dir / cache_key

    def _load_from_cache(self, cache_path: Path) -> Optional[pl.DataFrame]:
        """
        从缓存加载数据

        Args:
            cache_path: 缓存文件路径

        Returns:
            DataFrame 或 None（如果缓存不存在）
        """
        if cache_path.exists():
            try:
                return pl.read_parquet(cache_path)
            except Exception:
                # 缓存文件损坏，删除它
                cache_path.unlink(missing_ok=True)
        return None

    def _save_to_cache(self, df: pl.DataFrame, cache_path: Path) -> None:
        """
        保存数据到缓存

        Args:
            df: 要保存的 DataFrame
            cache_path: 缓存文件路径
        """
        try:
            df.write_parquet(cache_path)
        except Exception as e:
            # 缓存失败不影响主流程
            print(f"Warning: Failed to save cache to {cache_path}: {e}")

    def _standardize_columns(self, df: pl.DataFrame, is_stock: bool = True) -> pl.DataFrame:
        """
        标准化列名

        AKShare 返回的列名需要统一转换为标准格式:
        date, open, high, low, close, volume

        Args:
            df: 原始 DataFrame
            is_stock: 是否为股票数据

        Returns:
            标准化后的 DataFrame
        """
        # AKShare 列名映射
        column_mapping = {
            # 常见列名变体
            "日期": "date",
            "date": "date",
            "Date": "date",
            "开盘": "open",
            "open": "open",
            "Open": "open",
            "最高": "high",
            "high": "high",
            "High": "high",
            "最低": "low",
            "low": "low",
            "Low": "low",
            "收盘": "close",
            "close": "close",
            "Close": "close",
            "成交量": "volume",
            "volume": "volume",
            "Volume": "volume",
            "成交额": "amount",
            "amount": "amount",
            "Amount": "amount",
        }

        # 重命名列
        df = df.rename({k: v for k, v in column_mapping.items() if k in df.columns})

        # 确保必要列存在
        required_cols = ["date", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # 按日期排序
        df = df.sort("date")

        return df

    def fetch_stock_daily(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        use_cache: bool = True,
    ) -> pl.DataFrame:
        """
        获取股票日线数据

        Args:
            symbol: 股票代码 (如 "000001" 或 "sh600000")
            start_date: 开始日期 (格式: YYYYMMDD 或 YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYYMMDD 或 YYYY-MM-DD)
            use_cache: 是否使用缓存

        Returns:
            Polars DataFrame，包含标准化的列: date, open, high, low, close, volume
        """
        # 标准化日期格式
        start_date = start_date.replace("-", "")
        end_date = end_date.replace("-", "")

        # 检查缓存
        cache_path = self._get_cache_path(symbol, "stock", start_date, end_date)
        if use_cache:
            cached_df = self._load_from_cache(cache_path)
            if cached_df is not None:
                return cached_df

        # 导入 AKShare
        import akshare as ak

        # 获取数据
        try:
            # 处理股票代码格式
            if symbol.startswith("sh") or symbol.startswith("sz"):
                symbol_clean = symbol[2:]
            else:
                symbol_clean = symbol

            # 使用 AKShare 获取股票日线数据
            df_pd = ak.stock_zh_a_hist(
                symbol=symbol_clean,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",  # 前复权
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch stock data for {symbol}: {e}")

        if df_pd is None or df_pd.empty:
            raise ValueError(f"No data returned for {symbol}")

        # 转换为 Polars DataFrame
        df = pl.from_pandas(df_pd)

        # 标准化列名
        df = self._standardize_columns(df, is_stock=True)

        # 保存缓存
        if use_cache:
            self._save_to_cache(df, cache_path)

        return df

    def fetch_index_daily(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pl.DataFrame:
        """
        获取指数日线数据

        Args:
            symbol: 指数代码 (如 "000001" 表示上证指数)
            start_date: 开始日期 (格式: YYYYMMDD 或 YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYYMMDD 或 YYYY-MM-DD)

        Returns:
            Polars DataFrame，包含标准化的列: date, open, high, low, close, volume
        """
        # 标准化日期格式
        start_date = start_date.replace("-", "")
        end_date = end_date.replace("-", "")

        # 检查缓存
        cache_path = self._get_cache_path(symbol, "index", start_date, end_date)
        cached_df = self._load_from_cache(cache_path)
        if cached_df is not None:
            return cached_df

        # 导入 AKShare
        import akshare as ak

        # 获取数据
        try:
            # 处理指数代码格式
            if symbol.startswith("sh") or symbol.startswith("sz"):
                symbol_clean = symbol
            else:
                # 默认添加 sh 前缀
                symbol_clean = f"sh{symbol}"

            # 使用 AKShare 获取指数日线数据
            df_pd = ak.index_zh_a_hist(
                symbol=symbol_clean,
                period="daily",
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch index data for {symbol}: {e}")

        if df_pd is None or df_pd.empty:
            raise ValueError(f"No data returned for index {symbol}")

        # 转换为 Polars DataFrame
        df = pl.from_pandas(df_pd)

        # 标准化列名
        df = self._standardize_columns(df, is_stock=False)

        # 保存缓存
        self._save_to_cache(df, cache_path)

        return df
