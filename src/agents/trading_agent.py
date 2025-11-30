from ..config.config_manager import TradingConfig
from ..models.model_loader import ModelLoader
from ..data.data_collector import OKXMarketClient
from ..data.news_collector import BlockbeatsNewsCollector, NewsType, Language
from datetime import datetime, timezone
import re

class TradingAgent:
    def __init__(self, config: TradingConfig):
        self.config = config
        self.model = None
        self.portfolio = {
            # 余额
            'cash': config.user_config.cash,
            # 持仓
            'positions': {},
        }
        self.is_ready = False
        self._cleanup_done = False

        # 初始化客户端
        self.okx_client = OKXMarketClient(config.user_config, config.data_config)
        self.news_collector = BlockbeatsNewsCollector(language=Language.CN)

        # 数据存储
        self.market_data = {}  # 历史K线数据
        self.realtime_data = {}  # 实时行情数据
        self.technical_data = {}  # 技术指标数据
        self.news_data = {}  # 新闻数据
        self.market_sentiment = {}  # 市场情绪分析

    async def initialize(self):
        """初始化Agent的核心流程"""
        print("Initializing AI Trading Agent...")

        try:
             # 1. 验证配置
            print("🔍 验证模型配置...")
            if not hasattr(self.config, 'modeL_config'):
                raise ValueError("配置中缺少 modeL_config 字段")
            
            if self.config.modeL_config is None:
                raise ValueError("modeL_config 为 None")
            
            print(f"✅ 模型配置存在: {self.config.modeL_config.model_name}")

            # 2. 加载模型
            print("🔍 初始化模型加载器...")
            model_loader = ModelLoader()
            print(f"🔍 模型目录: {model_loader.models_dir}")
            print(f"🔍 模型名称: {self.config.modeL_config.model_name}")
            
            print("🔍 开始加载模型...")
            self.model = model_loader.load_model(self.config.modeL_config)
            print(f"✅ Model {self.config.modeL_config.model_name} loaded successfully.")

            # 3. 交易数据初始化 
            self._initialize_trading_data()

            # 4. 新闻数据初始化
            await self._initialize_news_data()

            # 5. 初始化数据流 (伪代码)
            # self.data_stream = DataStream(self.config.user_config.trading_pairs)

            # 6. 标记为就绪状态
            self.is_ready = True
            print("AI Trading Agent is now READY.")

        except Exception as e:
            print(f"❌ Agent初始化失败: {type(e).__name__}: {str(e)}")
            import traceback
            print("🔍 详细堆栈跟踪:")
            traceback.print_exc()
            raise

    def get_status(self):
        return {
            "is_ready": self.is_ready,
            "cash": self.config.user_config.cash,
            "risk_appetite": self.config.user_config.risk_appetite,
            "model_used": self.config.modeL_config.model_name,
            "market_sentiment": self.market_sentiment.get('sentiment', 'unknown'),
            "news_count": len(self.news_data.get('important', [])),
            "breaking_news": self.market_sentiment.get('breaking_news_count', 0)
        }
    
    async def cleanup(self):
        """清理资源 - 显示关闭所有客户端会话"""
        if self._cleanup_done:
            return
            
        print("🧹 清理交易Agent资源...")
        
        try:
            # 1. 关闭新闻收集器的会话
            if hasattr(self.news_collector, 'close'):
                await self.news_collector.close()
                print("✅ 新闻收集器会话已关闭")
            elif hasattr(self.news_collector, 'session') and self.news_collector.session:
                await self.news_collector.session.close()
                print("✅ 新闻收集器会话已关闭")
            
            # 2. 拓展

        except Exception as e:
            print(f"⚠️ 资源清理过程中出现错误: {e}")
        finally:
            self._cleanup_done = True

    def _initialize_trading_data(self):
        """初始化交易数据"""
        print("初始化交易数据...")
        
        # 3.1 验证交易对配置
        trading_pairs = self.okx_client.get_trading_pairs()
        print(f"配置的交易对: {trading_pairs}")
        
        if not trading_pairs:
            raise ValueError("未配置交易对")
        
        # 3.2 获取实时数据
        print("获取实时行情数据...")
        self.realtime_data = self.okx_client.get_realtime_data()
        print(f"成功获取 {len(self.realtime_data)} 个交易对的实时数据")
        
        # 验证实时数据
        for pair in trading_pairs:
            if pair not in self.realtime_data:
                print(f"⚠️  警告: 无法获取 {pair} 的实时数据")
        
        # 3.3 获取历史K线数据
        print("获取历史K线数据...")
        self.market_data = self.okx_client.get_all_historical_klines()
        print(f"成功获取 {len(self.market_data)} 个交易对的历史数据")
        
        # 验证历史数据完整性
        self._validate_market_data()
        
        # 3.4 初始化技术指标数据
        print("计算技术指标...")
        self._initialize_technical_data()
        
        # 3.5 打印数据统计
        self._print_data_statistics()

    def _validate_market_data(self):
        """验证市场数据完整性"""
        for pair, data in self.market_data.items():
            if data.empty:
                print(f"⚠️  警告: {pair} 历史数据为空")
                continue
                
            # 检查数据量是否足够
            min_data_points = self.config.modeL_config.data_window
            if len(data) < min_data_points:
                print(f"⚠️  警告: {pair} 数据点不足 ({len(data)} < {min_data_points})")
            
            # 检查数据时间范围
            time_range = data.index[-1] - data.index[0]
            print(f"   {pair}: {len(data)} 根K线, 时间范围: {time_range.days}天")

    def _initialize_technical_data(self):
        """初始化技术指标数据"""
        from ..analysis.technical_calculator import TechnicalCalculator
        
        # 初始化技术指标计算器
        tech_calculator = TechnicalCalculator()
        
        for pair, data in self.market_data.items():
            if not data.empty:
                try:
                    # 计算技术指标
                    self.technical_data[pair] = tech_calculator.calculate_all_indicators(data)
                    
                    # 验证技术指标计算
                    required_features = self.config.modeL_config.features
                    missing_features = tech_calculator.validate_features(
                        self.technical_data[pair], required_features
                    )
                    
                    if missing_features:
                        print(f"⚠️  警告: {pair} 缺少特征 {missing_features}")
                    else:
                        print(f"✅ {pair} 技术指标计算完成，包含 {len(self.technical_data[pair].columns)} 个特征")
                        
                except Exception as e:
                    print(f"❌ {pair} 技术指标计算失败: {e}")
                    # 如果计算失败，至少保留原始数据
                    self.technical_data[pair] = data

    def _print_data_statistics(self):
        """打印数据统计信息"""
        print("\n📊 数据初始化完成:")
        print(f"   交易对数量: {len(self.market_data)}")
        print(f"   时间框架: {self.okx_client.get_timeframe()}")
        print(f"   历史天数: {self.okx_client.get_historical_days()}")
        
        total_bars = sum(len(data) for data in self.market_data.values())
        print(f"   总K线数量: {total_bars}")
        
        # 显示每个交易对的最新价格
        print("\n   最新价格:")
        for pair, ticker in self.realtime_data.items():
            if ticker:
                price = float(ticker.get('last', 0))
                change_24h = float(ticker.get('24hChange', 0))
                print(f"     {pair}: {price:.2f} ({change_24h:+.2f}%)")

    async def _initialize_news_data(self):
        """初始化新闻数据"""
        print("📰 初始化新闻数据...")
    
        try:
            # 使用核心更新逻辑
            await self._update_news_core()
            
            # 初始化特定的设置
            self.news_data['initialized'] = True
            self.news_data['first_init_time'] = datetime.now(timezone.utc)
            
            # 打印新闻摘要
            self._print_news_summary()
            
        except Exception as e:
            print(f"❌ 新闻数据初始化失败: {str(e)}")
            self.news_data = {
                'important': [], 
                'error': str(e),
                'initialized': False
            }
    
    def _analyze_market_sentiment(self, news_list: list) -> dict:
        """分析市场情绪"""
        if not news_list:
            return {
                'sentiment_score': 0,
                'sentiment': 'neutral',
                'breaking_news_count': 0,
                'keywords': [],
                'last_updated': datetime.now(timezone.utc)
            }
        
        # 情绪关键词分类
        positive_keywords = [
            '上涨', '暴涨', '突破', '利好', '合作', '上线', '通过', '批准', '创新高',
            'bullish', 'surge', 'breakthrough', 'partnership', 'launch', 'approve'
        ]
        
        negative_keywords = [
            '下跌', '暴跌', '崩盘', '利空', '监管', '黑客', '被盗', '调查', '诉讼',
            'bearish', 'plunge', 'crash', 'regulation', 'hack', 'lawsuit'
        ]
        
        high_impact_keywords = [
            '监管', '政策', '黑客', '被盗', '突破', '暴涨', '暴跌',
            'regulation', 'policy', 'hack', 'breakthrough', 'surge', 'crash'
        ]
        
        # 分析新闻内容
        sentiment_score = 0
        breaking_news_count = 0
        all_keywords = []
        
        for news in news_list:
            title = self._clean_news_text(news.get('title', ''))
            content = self._clean_news_text(news.get('content', news.get('description', '')))
            text = f"{title} {content}"
            
            # 计算情绪分数
            positive_count = sum(1 for keyword in positive_keywords if keyword in text)
            negative_count = sum(1 for keyword in negative_keywords if keyword in text)
            
            sentiment_score += (positive_count - negative_count)
            
            # 统计重大新闻
            if any(keyword in text for keyword in high_impact_keywords):
                breaking_news_count += 1
            
            # 收集关键词
            words = self._extract_meaningful_keywords(text)
            all_keywords.extend(words)
        
        # 确定情绪状态
        if sentiment_score > 2:
            sentiment = 'bullish'
        elif sentiment_score < -2:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'
        
        # 统计关键词频率
        from collections import Counter
        keyword_freq = Counter(all_keywords)
        meaningful_keywords = [
            word for word, count in keyword_freq.most_common(20)
            if self._is_meaningful_keyword(word)
        ]
        
        return {
            'sentiment_score': sentiment_score,
            'sentiment': sentiment,
            'breaking_news_count': breaking_news_count,
            'top_keywords': meaningful_keywords[:10],
            'total_news': len(news_list),
            'last_updated': datetime.now(timezone.utc)
        }
    
    def _clean_news_text(self, text: str) -> str:
        """清理新闻文本，移除HTML标签和无意义内容"""
        if not text:
            return ""
        
        import re
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # 移除URL
        text = re.sub(r'https?://\S+', ' ', text)
        
        # 移除常见的无意义属性
        meaningless_patterns = [
            r'alt="[^"]*"',
            r'data-href="[^"]*"',
            r'style="[^"]*"',
            r'class="[^"]*"',
            r'width="[^"]*"',
            r'height="[^"]*"',
            r'src="[^"]*"',
            r'text-align:\s*\w*',
            r'display:\s*\w*',
            r'float:\s*\w*',
            r'position:\s*\w*',
            r'margin:\s*[^;]*;?',
            r'padding:\s*[^;]*;?',
            r'font-size:\s*[^;]*;?',
            r'color:\s*[^;]*;?',
            r'background:\s*[^;]*;?',
        ]
        
        for pattern in meaningless_patterns:
            text = re.sub(pattern, ' ', text)
        
        # 移除多余的空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _extract_meaningful_keywords(self, text: str) -> list:
        """从文本中提取有意义的关键词"""
        if not text:
            return []
        
        # 清理文本
        clean_text = self._clean_news_text(text)
        
        # 分词（简单的空格分词，你可以根据需要替换为更复杂的分词器）
        words = clean_text.split()
        
        # 过滤条件
        meaningful_words = []
        for word in words:
            word_lower = word.lower().strip('.,!?;:"\'()[]{}')
            
            # 过滤条件
            if (len(word_lower) >= 2 and                    # 至少2个字符
                word_lower not in self._get_stop_words() and # 不在停用词列表中
                not word_lower.isdigit() and                 # 不是纯数字
                not re.match(r'^[0-9\.]+$', word_lower) and # 不是数字和点的组合
                not re.match(r'^[^a-zA-Z0-9\u4e00-\u9fff]+$', word_lower)):  # 不是纯符号
                meaningful_words.append(word_lower)
        
        return meaningful_words

    def _is_meaningful_keyword(self, keyword: str) -> bool:
        """判断关键词是否有意义"""
        if not keyword or len(keyword) < 2:
            return False
        
        # 无意义关键词列表
        meaningless_words = {
            'alt', 'data', 'href', 'style', 'text', 'align', 'center', 'img',
            'width', 'height', 'src', 'class', 'border', 'margin', 'padding',
            'font', 'size', 'color', 'background', 'display', 'float', 'position',
            'absolute', 'relative', 'block', 'inline', 'flex', 'grid', 'https',
            'http', 'www', 'com', 'org', 'io', 'net', 'pump', 'fun', 'br', 'div',
            'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'b', 'i',
            'pump.fun', 'upbit', 'hyperliquid', 'monad', 'naver',
            'binance', 'okx', 'kucoin', 'gate.io', 'mexc', 'bybit',
            'uniswap', 'pancakeswap', 'sushiswap', 'curve', 'balancer',
            'metamask', 'trustwallet', 'coinbase', 'kraken', 'bitfinex'
        }
        
        return (keyword not in meaningless_words and
            not keyword.startswith(('0x', '#', '@', '.', '-', '_')) and
            not keyword.endswith(('.com', '.org', '.io', '.net', '.fun')) and
            len(keyword) <= 20 and
            not self._is_crypto_exchange(keyword) and
            not self._is_defi_platform(keyword) and 
            not self._is_common_company(keyword)
        )
    
    def _is_crypto_exchange(self, keyword: str) -> bool:
        """判断是否为加密货币交易所名称"""
        crypto_exchanges = {
            'upbit', 'binance', 'okx', 'kucoin', 'gate', 'mexc', 'bybit',
            'coinbase', 'kraken', 'bitfinex', 'huobi', 'bitstamp', 'gemini',
            'bithumb', 'coinone', 'korbit', 'probit'
        }
        return keyword.lower() in crypto_exchanges

    def _is_defi_platform(self, keyword: str) -> bool:
        """判断是否为DeFi平台名称"""
        defi_platforms = {
            'pump.fun', 'hyperliquid', 'uniswap', 'pancakeswap', 'sushiswap',
            'curve', 'balancer', 'aave', 'compound', 'makerdao', 'yearn',
            'synthetix', 'dydx', 'perp', 'gmx'
        }
        return keyword.lower() in defi_platforms

    def _is_common_company(self, keyword: str) -> bool:
        """判断是否为常见公司名称"""
        common_companies = {
            'naver', 'kakao', 'samsung', 'lg', 'hyundai', 'google', 'apple',
            'microsoft', 'amazon', 'facebook', 'twitter', 'telegram', 'discord'
        }
        return keyword.lower() in common_companies

    def _get_stop_words(self) -> set:
        """获取停用词列表"""
        return {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'as', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
            'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会',
            '着', '没有', '看', '好', '自己', '知道', '可以', '如', '但', '那'
        }

    def _print_news_summary(self):
        """打印新闻摘要"""
        sentiment = self.market_sentiment
        important_news = self.news_data.get('important', [])
        
        print("\n📰 新闻数据摘要:")
        print(f"   总新闻数: {sentiment.get('total_news', 0)}")
        print(f"   市场情绪: {sentiment.get('sentiment', 'unknown')} (分数: {sentiment.get('sentiment_score', 0)})")
        print(f"   重大新闻: {sentiment.get('breaking_news_count', 0)} 条")
        print(f"   热门关键词: {', '.join(sentiment.get('top_keywords', [])[:5])}")
        
        # 显示最新3条重要新闻
        if important_news:
            print("\n   最新重要新闻:")
            for i, news in enumerate(important_news[:3], 1):
                title = news.get('title', '无标题')
                # 截断过长的标题
                if len(title) > 60:
                    title = title[:57] + '...'
                print(f"     {i}. {title}")

    async def _update_news_core(self):
        """新闻数据核心更新逻辑 - 供初始化和更新共用"""
        important_news = await self.news_collector.get_latest_important_news(limit=20)
        self.news_data['important'] = important_news

        # 分析市场情绪
        self.market_sentiment = self._analyze_market_sentiment(important_news)
        
        # 更新交易对相关新闻
        trading_pairs = self.okx_client.get_trading_pairs()
        for pair in trading_pairs:
            symbol_keyword = pair.split('-')[0]
            related_news = await self.news_collector.search_news_by_keyword(symbol_keyword, limit=10)
            self.news_data[pair] = related_news

    async def update_news_data(self):
        """更新新闻数据"""
        if not self.is_ready:
            return
        
        try:
            print("🔄 更新新闻数据...")
            
            # 使用共用的核心更新逻辑
            await self._update_news_core()
            
            # 更新特定的处理
            self.news_data['last_updated'] = datetime.now(timezone.utc)
            self.news_data['update_count'] = self.news_data.get('update_count', 0) + 1
        
            self._print_news_summary()
            
            print(f"✅ 新闻数据更新完成")
            
        except Exception as e:
            print(f"❌ 新闻数据更新失败: {str(e)}")
            self.news_data['last_update_error'] = str(e)