"""
数据获取模块测试
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from brain.data import DataFetcher


class TestDataFetcher:
    """测试 DataFetcher 类"""

    def test_init_default_cache_dir(self):
        """测试默认缓存目录初始化"""
        fetcher = DataFetcher()
        assert fetcher.cache_dir is not None
        assert "cache" in str(fetcher.cache_dir)

    def test_init_custom_cache_dir(self):
        """测试自定义缓存目录初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DataFetcher(cache_dir=tmpdir)
            assert str(fetcher.cache_dir) == tmpdir
            assert fetcher.cache_dir.exists()

    def test_fetch_stock_daily_structure(self):
        """测试 fetch_stock_daily 返回正确的数据结构"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DataFetcher(cache_dir=tmpdir)

            # 使用缓存测试，避免网络请求
            # 创建模拟数据
            mock_data = pl.DataFrame({
                "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "open": [100.0, 101.0, 102.0],
                "high": [105.0, 106.0, 107.0],
                "low": [98.0, 99.0, 100.0],
                "close": [103.0, 104.0, 105.0],
                "volume": [10000, 15000, 20000],
            })

            # 保存到缓存
            cache_path = fetcher._get_cache_path(
                "000001", "stock", "20240101", "20240103"
            )
            mock_data.write_parquet(cache_path)

            # 从缓存获取
            df = fetcher.fetch_stock_daily(
                "000001", "20240101", "20240103", use_cache=True
            )

            # 验证返回类型
            assert isinstance(df, pl.DataFrame)

            # 验证必要的列存在
            required_cols = ["date", "open", "high", "low", "close", "volume"]
            for col in required_cols:
                assert col in df.columns, f"Missing column: {col}"

            # 验证行数
            assert len(df) == 3

    def test_fetch_index_daily_structure(self):
        """测试 fetch_index_daily 返回正确的数据结构"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DataFetcher(cache_dir=tmpdir)

            # 使用缓存测试
            mock_data = pl.DataFrame({
                "date": ["2024-01-01", "2024-01-02"],
                "open": [3000.0, 3010.0],
                "high": [3050.0, 3060.0],
                "low": [2980.0, 2990.0],
                "close": [3040.0, 3050.0],
                "volume": [1000000, 1200000],
            })

            cache_path = fetcher._get_cache_path(
                "000001", "index", "20240101", "20240102"
            )
            mock_data.write_parquet(cache_path)

            df = fetcher.fetch_index_daily("000001", "20240101", "20240102")

            assert isinstance(df, pl.DataFrame)

            required_cols = ["date", "open", "high", "low", "close", "volume"]
            for col in required_cols:
                assert col in df.columns

    def test_cache_mechanism(self):
        """测试缓存机制"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DataFetcher(cache_dir=tmpdir)

            # 创建测试数据
            mock_data = pl.DataFrame({
                "date": ["2024-01-01"],
                "open": [100.0],
                "high": [105.0],
                "low": [98.0],
                "close": [103.0],
                "volume": [10000],
            })

            cache_path = fetcher._get_cache_path(
                "TEST", "stock", "20240101", "20240101"
            )
            fetcher._save_to_cache(mock_data, cache_path)

            # 验证缓存文件存在
            assert cache_path.exists()

            # 从缓存加载
            loaded_df = fetcher._load_from_cache(cache_path)
            assert loaded_df is not None
            assert len(loaded_df) == 1
            assert loaded_df["close"][0] == 103.0

    def test_standardize_columns(self):
        """测试列名标准化"""
        fetcher = DataFetcher()

        # 测试中文列名
        df_cn = pl.DataFrame({
            "日期": ["2024-01-01"],
            "开盘": [100.0],
            "最高": [105.0],
            "最低": [98.0],
            "收盘": [103.0],
            "成交量": [10000],
        })

        df_std = fetcher._standardize_columns(df_cn)
        assert "date" in df_std.columns
        assert "open" in df_std.columns
        assert "close" in df_std.columns
        assert "volume" in df_std.columns

        # 测试英文列名
        df_en = pl.DataFrame({
            "Date": ["2024-01-01"],
            "Open": [100.0],
            "High": [105.0],
            "Low": [98.0],
            "Close": [103.0],
            "Volume": [10000],
        })

        df_std = fetcher._standardize_columns(df_en)
        assert "date" in df_std.columns
        assert "close" in df_std.columns

    def test_standardize_columns_missing_required(self):
        """测试缺少必要列时抛出异常"""
        fetcher = DataFetcher()

        df_invalid = pl.DataFrame({
            "date": ["2024-01-01"],
            "open": [100.0],
            # 缺少 high, low, close, volume
        })

        with pytest.raises(ValueError, match="Missing required column"):
            fetcher._standardize_columns(df_invalid)

    def test_date_format_handling(self):
        """测试日期格式处理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fetcher = DataFetcher(cache_dir=tmpdir)

            mock_data = pl.DataFrame({
                "date": ["2024-01-01", "2024-01-02"],
                "open": [100.0, 101.0],
                "high": [105.0, 106.0],
                "low": [98.0, 99.0],
                "close": [103.0, 104.0],
                "volume": [10000, 15000],
            })

            # 使用带横线的日期格式
            cache_path = fetcher._get_cache_path(
                "000001", "stock", "20240101", "20240102"
            )
            mock_data.write_parquet(cache_path)

            # 测试自动转换日期格式
            df = fetcher.fetch_stock_daily(
                "000001", "2024-01-01", "2024-01-02", use_cache=True
            )
            assert len(df) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
