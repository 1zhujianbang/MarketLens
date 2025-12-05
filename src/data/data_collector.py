# src/data/data_collector.py
import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import time
from typing import Dict, List, Optional, Any
from ..config.config_manager import UserConfig, DataConfig
import os

class MarketClient:
    """通用市场数据客户端"""
    
    def __init__(self, user_config: UserConfig, data_config: DataConfig):
        """
        初始化客户端
        
        Args:
            user_config: 用户配置
            data_config: 数据配置
        """
        self.user_config = user_config
        self.data_config = data_config
        # 市场符号列表（股票、指数、商品等）
        self.symbols = []
        # 数据源配置
        self.data_source = data_config.data_source
        
    def get_symbols(self) -> List[str]:
        """从配置中获取市场符号列表"""
        return self.user_config.symbols if hasattr(self.user_config, 'symbols') else self.symbols
    
    def get_timeframe(self) -> str:
        """从配置中获取时间框架"""
        return self.data_config.timeframe if hasattr(self.data_config, 'timeframe') else '1H'  # 默认为1小时
    
    def get_historical_days(self) -> int:
        """从配置中获取历史天数"""
        return self.data_config.historical_days if hasattr(self.data_config, 'historical_days') else 30
    
    def set_symbols(self, symbols: List[str]):
        """设置市场符号列表"""
        self.symbols = symbols
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """获取单个市场符号的行情数据"""
        # 根据不同数据源实现不同的行情获取逻辑
        # 这里提供一个通用接口，具体实现需要根据数据源扩展
        print(f"获取 {symbol} 行情数据...")
        # TODO: 实现通用行情获取逻辑
        return None
    
    def get_all_tickers(self) -> Dict[str, Dict]:
        """获取所有市场符号的行情数据"""
        tickers = {}
        symbols = self.get_symbols()
        print(f"正在获取 {len(symbols)} 个市场符号的实时行情...")
        
        for symbol in symbols:
            ticker_data = self.get_ticker(symbol)
            if ticker_data:
                tickers[symbol] = ticker_data
                print(f"✅ 成功获取 {symbol} 实时数据")
            else:
                print(f"❌ 无法获取 {symbol} 实时数据")
            time.sleep(2)  # 限速
        return tickers
    
    def get_kline(self, 
                  symbol: str, 
                  timeframe: str = None, 
                  limit: int = 100,
                  start_time: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        获取K线/蜡烛图数据
        
        Args:
            symbol: 市场符号
            timeframe: 时间周期，如果为None则使用配置中的timeframe
            limit: 数据条数
            start_time: 起始时间
        """
        if timeframe is None:
            timeframe = self.get_timeframe()
            
        # 根据不同数据源实现不同的K线获取逻辑
        # 这里提供一个通用接口，具体实现需要根据数据源扩展
        print(f"获取 {symbol} 的 {timeframe} K线数据...")
        # TODO: 实现通用K线获取逻辑
        return None
    
    def _parse_candles_data(self, candles_data: List) -> pd.DataFrame:
        """解析K线/蜡烛图数据"""
        if not candles_data:
            return pd.DataFrame()
        
        # 通用的蜡烛图数据解析，支持不同数据源的格式
        # 这里假设数据格式为 [timestamp, open, high, low, close, volume, ...]
        df = pd.DataFrame(candles_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume'
        ])
        
        # 数据类型转换
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 处理时间戳
        if 'timestamp' in df.columns:
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
            except:
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        return df
    
    def get_historical_klines(self, 
                            symbol: str, 
                            timeframe: str = None,
                            days: int = None,
                            limit: int = 100) -> pd.DataFrame:
        """
        获取历史K线/蜡烛图数据（自动分页）
        
        Args:
            symbol: 市场符号
            timeframe: 时间周期，如果为None则使用配置中的timeframe
            days: 数据天数，如果为None则使用配置中的historical_days
            limit: 每次请求的条数
        """
        if timeframe is None:
            timeframe = self.get_timeframe()
        if days is None:
            days = self.get_historical_days()
            
        print(f"获取 {symbol} 的 {days} 天数据，时间框架: {timeframe}")
        
        all_data = pd.DataFrame()
        limit = 240  # 每次最多获取的条数
        
        # 计算需要的总条数（基于时间框架和天数）
        total_bars = self._calculate_total_bars(timeframe, days)
        
        if total_bars <= 0:
            print(f"❌ 时间框架 {timeframe} 和天数 {days} 计算出的条数为0")
            return all_data
        
        print(f"需要获取大约 {total_bars} 条K线数据")
        
        # 分批获取数据 - 从最新数据开始向前获取
        current_count = 0
        
        # TODO: 根据不同数据源实现具体的历史数据获取逻辑
        # 这里提供一个通用框架，需要根据数据源扩展
        print(f"  🚧 历史数据获取功能正在开发中...")
        
        return all_data

    def export_historical_klines_to_csv(self,
                                       instId: str,
                                       output_path: str,
                                       bar: str = None,
                                       years: int = 5,
                                       include_technical_indicators: bool = True) -> str:
        """
        导出历史K线数据到指定CSV文件
        
        Args:
            instId: 交易对
            output_path: 输出CSV文件路径
            bar: K线周期
            years: 数据年数
            include_technical_indicators: 是否包含技术指标
            
        Returns:
            导出的文件路径
        """
        import os
        from datetime import datetime
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        print(f"📤 开始导出 {instId} 的 {years} 年历史数据...")
        print(f"💾 输出路径: {output_path}")
        
        # 获取历史数据
        days = years * 365
        df = self.get_historical_klines(instId=instId, bar=bar, days=days)
        
        if df.empty:
            print(f"❌ 未能获取到 {instId} 的历史数据")
            return ""
        
        # 计算技术指标（如果需要）
        if include_technical_indicators:
            try:
                from ..analysis.technical_calculator import TechnicalCalculator
                calculator = TechnicalCalculator()
                df = calculator.calculate_all_indicators(df)
                print(f"✅ 技术指标计算完成")
            except Exception as e:
                print(f"⚠️  技术指标计算失败: {e}")
        
        # 添加元数据列
        df['symbol'] = instId
        df['timeframe'] = bar if bar else self.get_timeframe()
        
        # 导出到CSV
        try:
            # 使用utf-8-sig编码支持中文，避免乱码
            df.to_csv(output_path, encoding='utf-8-sig', index=True)
            
            # 验证文件是否成功创建
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path) / 1024 / 1024  # MB
                print(f"✅ 数据成功导出到: {output_path}")
                print(f"📊 导出统计:")
                print(f"   数据条数: {len(df)}")
                print(f"   列数: {len(df.columns)}")
                print(f"   时间范围: {df.index[0]} 到 {df.index[-1]}")
                print(f"   文件大小: {file_size:.2f} MB")
                print(f"   包含列: {', '.join(df.columns.tolist()[:5])}...")  # 显示前5列
                
                return output_path
            else:
                print(f"❌ 文件创建失败: {output_path}")
                return ""
                
        except Exception as e:
            print(f"❌ 导出CSV失败: {str(e)}")
            return ""
    
    def batch_export_historical_data(self,
                                   instIds: list,
                                   output_dir: str,
                                   bar: str = None,
                                   years: int = 5,
                                   include_technical_indicators: bool = True) -> dict:
        """
        批量导出多个交易对的历史数据
        
        Args:
            instIds: 交易对列表
            output_dir: 输出目录
            bar: K线周期
            years: 数据年数
            include_technical_indicators: 是否包含技术指标
            
        Returns:
            导出结果字典 {交易对: 文件路径}
        """
        import os
        from datetime import datetime
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        results = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"🚀 开始批量导出 {len(instIds)} 个交易对的数据...")
        print(f"📁 输出目录: {output_dir}")
        
        for i, instId in enumerate(instIds, 1):
            print(f"\n{'='*60}")
            print(f"处理第 {i}/{len(instIds)} 个交易对: {instId}")
            print(f"{'='*60}")
            
            try:
                # 生成文件名
                safe_instId = instId.replace('-', '_').replace('/', '_')
                filename = f"{safe_instId}_{bar if bar else self.get_timeframe()}_{years}years_{timestamp}.csv"
                output_path = os.path.join(output_dir, filename)
                
                # 导出数据
                filepath = self.export_historical_klines_to_csv(
                    instId=instId,
                    output_path=output_path,
                    bar=bar,
                    years=years,
                    include_technical_indicators=include_technical_indicators
                )
                
                results[instId] = filepath
                
                # 交易对之间的延迟，避免请求过快
                if i < len(instIds):  # 最后一个不需要延迟
                    print("⏳ 等待3秒后处理下一个交易对...")
                    time.sleep(3)
                    
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"❌ 处理 {instId} 时出错: {error_msg}")
                results[instId] = error_msg
        
        # 打印汇总结果
        self._print_export_summary(results)
        
        return results
    
    def _print_export_summary(self, results: dict):
        """打印导出汇总信息"""
        print(f"\n{'🎯 批量导出完成 ':=^50}")
        
        success_count = sum(1 for path in results.values() if path and not str(path).startswith('Error'))
        failed_count = len(results) - success_count
        
        print(f"✅ 成功: {success_count} 个")
        print(f"❌ 失败: {failed_count} 个")
        
        if failed_count > 0:
            print(f"\n📋 失败详情:")
            for instId, result in results.items():
                if str(result).startswith('Error'):
                    print(f"   {instId}: {result}")
        
        # 显示成功文件列表
        if success_count > 0:
            print(f"\n📁 成功导出的文件:")
            for instId, filepath in results.items():
                if filepath and not str(filepath).startswith('Error'):
                    file_size = os.path.getsize(filepath) / 1024 / 1024
                    print(f"   📄 {instId}: {filepath} ({file_size:.2f} MB)")



        
    def _calculate_total_bars(self, bar: str, days: int) -> int:
        """根据时间框架和天数计算需要的K线条数"""
        try:
            if bar.endswith('m'):
                minutes = int(bar[:-1])
                return (days * 24 * 60) // minutes
            elif bar.endswith('H'):
                hours = int(bar[:-1])
                return (days * 24) // hours
            elif bar.endswith('D'):
                return days
            elif bar.endswith('W'):
                return days // 7
            elif bar.endswith('M'):
                return days // 30
            elif bar.endswith('Y'):
                return days // 365
            else:
                # 默认按小时计算
                return days * 24
        except:
            # 如果计算失败，返回默认值
            return days * 24
    
    def get_all_historical_klines(self) -> Dict[str, pd.DataFrame]:
        """获取配置中所有交易对的历史K线数据"""
        market_data = {}
        symbols = self.get_symbols()
        print(f"开始获取 {len(symbols)} 个交易对的历史数据...")
        
        success_count = 0
        for instId in symbols:
            print(f"获取 {instId} 的历史数据...")
            kline_data = self.get_historical_klines(instId)
            if kline_data is not None and not kline_data.empty:
                market_data[instId] = kline_data
                success_count += 1
                print(f"✅ 成功获取 {instId} 的历史数据，共 {len(kline_data)} 条")
            else:
                print(f"❌ 获取 {instId} 的历史数据失败")
            time.sleep(1)  # 限速
        
        print(f"历史数据获取完成: 成功 {success_count}/{len(symbols)} 个交易对")
        return market_data
    
    def get_instruments(self, instType: str = "SPOT") -> List[Dict]:
        """获取可交易产品信息"""
        try:
            result = self.api.public.get_instruments(instType=instType)
            if result['code'] == '0':
                instruments = result['data']
                print(f"✅ 获取到 {len(instruments)} 个{instType}产品")
                return instruments
            else:
                print(f"❌ 获取产品信息失败: {result.get('msg', 'Unknown error')}")
                return []
        except Exception as e:
            print(f"❌ 获取产品信息异常: {str(e)}")
            return []
    
    def get_funding_rate(self, instId: str) -> Optional[Dict]:
        """获取资金费率（仅永续合约有效）"""
        try:
            result = self.api.market.get_funding_rate(instId=instId)
            if result['code'] == '0' and result['data']:
                return result['data'][0]
            else:
                print(f"⚠️ 获取 {instId} 资金费率失败: {result.get('msg', 'Not a swap instrument')}")
                return None
        except Exception as e:
            print(f"❌ 获取资金费率异常: {str(e)}")
            return None

    def get_realtime_data(self) -> Dict[str, Dict]:
        """获取所有交易对的实时数据"""
        return self.get_all_tickers()
    
    def validate_instruments(self):
        """验证配置的交易对是否可用"""
        print("验证交易对配置...")
        available_instruments = self.get_instruments("SPOT")
        available_pairs = [inst['instId'] for inst in available_instruments]
        
        configured_pairs = self.get_symbols()
        
        valid_pairs = []
        invalid_pairs = []
        
        for pair in configured_pairs:
            if pair in available_pairs:
                valid_pairs.append(pair)
            else:
                invalid_pairs.append(pair)
        
        print(f"✅ 有效交易对: {valid_pairs}")
        if invalid_pairs:
            print(f"❌ 无效交易对: {invalid_pairs}")
            print(f"💡 建议使用以下格式: BTC-USDT, ETH-USDT, SOL-USDT")
        
        return valid_pairs, invalid_pairs
    
    def calculate_price_changes(self, ticker_data: Dict) -> Dict:
        """
        计算价格涨跌幅
        
        Args:
            ticker_data: 单个交易对的行情数据
            
        Returns:
            包含涨跌幅的数据
        """
        if not ticker_data:
            return {}
            
        result = ticker_data.copy()
        
        try:
            # 当前价格
            current_price = float(ticker_data.get('last', 0))
            # 24小时开盘价
            open_price_24h = float(ticker_data.get('open24h', 0))
            
            if open_price_24h > 0:
                # 计算涨跌幅
                price_change = current_price - open_price_24h
                price_change_percent = (price_change / open_price_24h) * 100
                
                result['price_change'] = price_change
                result['price_change_percent'] = price_change_percent
                result['open24h'] = open_price_24h
            else:
                result['price_change'] = 0
                result['price_change_percent'] = 0
                
        except (ValueError, TypeError) as e:
            print(f"计算涨跌幅时出错: {e}")
            result['price_change'] = 0
            result['price_change_percent'] = 0
            
        return result
    
    def get_ticker_with_changes(self, instId: str) -> Optional[Dict]:
        """获取带涨跌幅的行情数据"""
        ticker_data = self.get_ticker(instId)
        if ticker_data:
            return self.calculate_price_changes(ticker_data)
        return None
    
    def get_all_tickers_with_changes(self) -> Dict[str, Dict]:
        """获取所有交易带涨跌幅的行情数据"""
        tickers = self.get_all_tickers()
        tickers_with_changes = {}
        
        for instId, ticker_data in tickers.items():
            tickers_with_changes[instId] = self.calculate_price_changes(ticker_data)
            
        return tickers_with_changes
    
    def format_price_display(self, ticker_data: Dict) -> str:
        """
        格式化价格显示
        
        Args:
            ticker_data: 包含涨跌幅的行情数据
            
        Returns:
            格式化的价格字符串
        """
        if not ticker_data:
            return "N/A"
            
        symbol = ticker_data.get('instId', 'Unknown')
        current_price = float(ticker_data.get('last', 0))
        change_percent = ticker_data.get('price_change_percent', 0)
        
        # 确定颜色和符号
        if change_percent > 0:
            color_indicator = "🟢"  # 绿色上涨
            change_sign = "+"
        elif change_percent < 0:
            color_indicator = "🔴"  # 红色下跌
            change_sign = ""
        else:
            color_indicator = "⚪"  # 白色持平
            change_sign = ""
            
        return f"{color_indicator} {symbol}: {current_price:.2f} ({change_sign}{change_percent:.2f}%)"