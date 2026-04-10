#!/usr/bin/env python3
"""
A股数据获取模块

支持多种数据源:
1. akshare - 免费A股数据 (推荐)
2. baostock - 免费A股数据
3. 本地CSV文件
4. 模拟数据 (fallback)

数据字段:
- datetime: 日期时间
- open: 开盘价
- high: 最高价
- low: 最低价
- close: 收盘价
- volume: 成交量
- pre_close: 前收盘价 (用于计算涨跌停)
"""
import sys
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import time

import pandas as pd
import numpy as np

# 尝试导入akshare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


class AshareDataProvider:
    """A股数据提供者"""
    
    def __init__(self):
        self.data_source = self._detect_data_source()
        print(f"📊 数据提供者初始化: {self.data_source}")
    
    def _detect_data_source(self) -> str:
        """检测可用的数据源"""
        if AKSHARE_AVAILABLE:
            return "akshare"
        return "mock"
    
    def get_stock_data(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        period: str = "daily",
        adjust: str = "qfq"  # 前复权
    ) -> Optional[pd.DataFrame]:
        """
        获取股票数据
        
        Args:
            symbol: 股票代码 (如: 000001, 600000)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            period: 周期 (daily/weekly/monthly)
            adjust: 复权方式 (qfq-前复权, hfq-后复权, 空-不复权)
        
        Returns:
            DataFrame with columns: [open, high, low, close, volume, pre_close]
        """
        if self.data_source == "akshare":
            return self._get_akshare_data(symbol, start_date, end_date, period, adjust)
        else:
            return self._generate_mock_data(symbol, start_date, end_date)
    
    def _get_akshare_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str
    ) -> Optional[pd.DataFrame]:
        """使用akshare获取数据 (带重试机制)"""
        import time
        from urllib3.exceptions import MaxRetryError
        
        # 标准化代码
        symbol = symbol.zfill(6)
        
        # 判断市场 (6开头=上海, 0/3开头=深圳)
        if symbol.startswith('6'):
            symbol_full = f"{symbol}.SH"
        else:
            symbol_full = f"{symbol}.SZ"
        
        print(f"   正在获取 {symbol_full} 数据...")
        
        # 重试机制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 获取日线数据
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=start_date.replace('-', ''),
                    end_date=end_date.replace('-', ''),
                    adjust=adjust
                )
                
                if df is None or len(df) == 0:
                    print(f"   ⚠️  无数据返回")
                    return None
                
                # 标准化列名
                df = df.rename(columns={
                    '日期': 'datetime',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                })
                
                # 转换日期
                df['datetime'] = pd.to_datetime(df['datetime'])
                df.set_index('datetime', inplace=True)
                
                # 计算pre_close
                df['pre_close'] = df['close'].shift(1)
                df['pre_close'].iloc[0] = df['open'].iloc[0]
                
                # 选择需要的列
                df = df[['open', 'high', 'low', 'close', 'volume', 'pre_close']]
                
                # 数据清洗
                df = df.dropna()
                df = df[df['volume'] > 0]
                
                print(f"   ✅ 获取成功: {len(df)} 条数据 ({df.index[0].date()} ~ {df.index[-1].date()})")
                
                return df
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"   ⚠️  尝试 {attempt+1}/{max_retries} 失败, 重试中...")
                    time.sleep(2)
                else:
                    print(f"   ❌ 获取失败: {e}")
                    return None
    
    def _generate_mock_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """生成模拟数据 (fallback)"""
        print(f"   使用模拟数据 (数据源不可用)")
        
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=500)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        # 生成交易日历
        dates = pd.date_range(start=start, end=end, freq='B')
        
        # 生成随机漫步价格
        np.random.seed(hash(symbol) % 2**32)
        returns = np.random.normal(0.0003, 0.02, len(dates))
        prices = 100 * (1 + returns).cumprod()
        
        data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            daily_range = close * 0.015
            open_price = close + np.random.normal(0, daily_range * 0.3)
            high_price = max(open_price, close) + abs(np.random.normal(0, daily_range * 0.3))
            low_price = min(open_price, close) - abs(np.random.normal(0, daily_range * 0.3))
            
            data.append({
                'datetime': date,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close, 2),
                'volume': int(np.random.normal(10000000, 5000000)),
                'pre_close': round(prices[i-1], 2) if i > 0 else round(close * 0.99, 2)
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        
        return df
    
    def get_stock_list(self, market: str = "all") -> pd.DataFrame:
        """
        获取股票列表
        
        Args:
            market: all/sh/sz/bj
        
        Returns:
            DataFrame with [code, name, industry]
        """
        if not AKSHARE_AVAILABLE:
            print("⚠️  akshare不可用，返回示例列表")
            return self._get_sample_stock_list()
        
        try:
            df = ak.stock_zh_a_spot_em()
            
            # 选择需要的列
            df = df[['代码', '名称', '行业', '总市值']]
            df.columns = ['code', 'name', 'industry', 'market_cap']
            
            # 过滤市场
            if market == "sh":
                df = df[df['code'].str.startswith('6')]
            elif market == "sz":
                df = df[df['code'].str.startswith(('0', '3'))]
            
            return df
            
        except Exception as e:
            print(f"❌ 获取股票列表失败: {e}")
            return self._get_sample_stock_list()
    
    def _get_sample_stock_list(self) -> pd.DataFrame:
        """示例股票列表"""
        sample_data = [
            {'code': '000001', 'name': '平安银行', 'industry': '银行', 'market_cap': 3000},
            {'code': '000002', 'name': '万科A', 'industry': '房地产', 'market_cap': 2000},
            {'code': '000333', 'name': '美的集团', 'industry': '家电', 'market_cap': 4000},
            {'code': '000858', 'name': '五粮液', 'industry': '白酒', 'market_cap': 6000},
            {'code': '002415', 'name': '海康威视', 'industry': '电子', 'market_cap': 3500},
            {'code': '002594', 'name': '比亚迪', 'industry': '汽车', 'market_cap': 7000},
            {'code': '300750', 'name': '宁德时代', 'industry': '新能源', 'market_cap': 8000},
            {'code': '600000', 'name': '浦发银行', 'industry': '银行', 'market_cap': 2500},
            {'code': '600009', 'name': '上海机场', 'industry': '航空', 'market_cap': 1500},
            {'code': '600016', 'name': '民生银行', 'industry': '银行', 'market_cap': 2200},
            {'code': '600028', 'name': '中国石化', 'industry': '石油', 'market_cap': 5000},
            {'code': '600030', 'name': '中信证券', 'industry': '券商', 'market_cap': 3500},
            {'code': '600031', 'name': '三一重工', 'industry': '机械', 'market_cap': 2000},
            {'code': '600036', 'name': '招商银行', 'industry': '银行', 'market_cap': 9000},
            {'code': '600276', 'name': '恒瑞医药', 'industry': '医药', 'market_cap': 4500},
            {'code': '600519', 'name': '贵州茅台', 'industry': '白酒', 'market_cap': 20000},
            {'code': '600887', 'name': '伊利股份', 'industry': '食品', 'market_cap': 2500},
            {'code': '601012', 'name': '隆基绿能', 'industry': '新能源', 'market_cap': 3000},
            {'code': '601088', 'name': '中国神华', 'industry': '煤炭', 'market_cap': 4000},
            {'code': '601166', 'name': '兴业银行', 'industry': '银行', 'market_cap': 3800},
            {'code': '601318', 'name': '中国平安', 'industry': '保险', 'market_cap': 8000},
            {'code': '601398', 'name': '工商银行', 'industry': '银行', 'market_cap': 15000},
            {'code': '601888', 'name': '中国中免', 'industry': '免税', 'market_cap': 2800},
            {'code': '603288', 'name': '海天味业', 'industry': '食品', 'market_cap': 3200},
        ]
        return pd.DataFrame(sample_data)
    
    def get_index_data(
        self,
        index_code: str = "000001",  # 上证指数
        start_date: str = None,
        end_date: str = None
    ) -> Optional[pd.DataFrame]:
        """
        获取指数数据
        
        Args:
            index_code: 指数代码
                - 000001: 上证指数
                - 399001: 深证成指
                - 399006: 创业板指
                - 000300: 沪深300
                - 000905: 中证500
        """
        if not AKSHARE_AVAILABLE:
            return self._generate_mock_data(f"INDEX_{index_code}", start_date, end_date)
        
        try:
            # 指数代码映射
            index_name_map = {
                '000001': 'sh000001',
                '399001': 'sz399001',
                '399006': 'sz399006',
                '000300': 'sh000300',
                '000905': 'sh000905',
            }
            
            symbol = index_name_map.get(index_code, f"sh{index_code}")
            
            print(f"   正在获取指数 {index_code} 数据...")
            
            df = ak.index_zh_a_hist(
                symbol=index_code,
                period="daily",
                start_date=start_date.replace('-', '') if start_date else None,
                end_date=end_date.replace('-', '') if end_date else None
            )
            
            if df is None or len(df) == 0:
                return None
            
            # 标准化列名
            df = df.rename(columns={
                '日期': 'datetime',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
            })
            
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            
            # 计算pre_close
            df['pre_close'] = df['close'].shift(1)
            df['pre_close'].iloc[0] = df['open'].iloc[0]
            
            df = df[['open', 'high', 'low', 'close', 'volume', 'pre_close']]
            
            print(f"   ✅ 获取成功: {len(df)} 条数据")
            
            return df
            
        except Exception as e:
            print(f"   ❌ 获取失败: {e}")
            return None


# 便捷函数
def get_stock_data(symbol: str, **kwargs) -> Optional[pd.DataFrame]:
    """获取股票数据的便捷函数"""
    provider = AshareDataProvider()
    return provider.get_stock_data(symbol, **kwargs)


def get_stock_list(**kwargs) -> pd.DataFrame:
    """获取股票列表的便捷函数"""
    provider = AshareDataProvider()
    return provider.get_stock_list(**kwargs)


def get_index_data(index_code: str, **kwargs) -> Optional[pd.DataFrame]:
    """获取指数数据的便捷函数"""
    provider = AshareDataProvider()
    return provider.get_index_data(index_code, **kwargs)


def test_data_provider():
    """测试数据提供者"""
    print("=" * 80)
    print("🧪 测试A股数据提供者")
    print("=" * 80)
    
    provider = AshareDataProvider()
    
    # 测试获取股票列表
    print("\n📋 获取股票列表...")
    stocks = provider.get_stock_list()
    print(f"   获取到 {len(stocks)} 只股票")
    print(stocks.head(10).to_string(index=False))
    
    # 测试获取单只股票数据
    print("\n📈 获取单只股票数据...")
    symbol = "000001"  # 平安银行
    data = provider.get_stock_data(
        symbol=symbol,
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    
    if data is not None:
        print(f"\n   数据预览 ({symbol}):")
        print(data.head(10).to_string())
        print(f"\n   数据形状: {data.shape}")
        print(f"   列: {list(data.columns)}")
    
    # 测试获取指数数据
    print("\n📊 获取指数数据...")
    index_data = provider.get_index_data(
        index_code="000001",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    
    if index_data is not None:
        print(f"\n   上证指数数据预览:")
        print(index_data.head(5).to_string())
    
    print("\n" + "=" * 80)
    print("✅ 测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_data_provider()
