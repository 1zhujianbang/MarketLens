import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

class MarketAnalysisEnvironment:
    def __init__(self, df, 
                 lookback_window=50):
        
        # 数据预处理 - 填充NaN值
        self.df = df.reset_index(drop=True).fillna(method='bfill').fillna(method='ffill')
        self.lookback_window = int(lookback_window)
        
        # 特征维度
        self.feature_dim = self._get_feature_dim()
        
        self.reset()
    
    def _get_feature_dim(self):
        base_features = 4      # OHLC log returns
        technical_features = 17
        market_features = 3    # volume, volatility, trend
        history_features = self.lookback_window * 2
        
        return base_features + technical_features + market_features + history_features
    
    def _get_features(self, step):
        if step < self.lookback_window:
            step = self.lookback_window
        row = self.df.iloc[step]
        
        # 当前价格
        current_price = row['close']
        
        # 基础价格特征 - 对数收益率相对于收盘价
        price_features = [
            np.log(row['open'] / current_price + 1e-8),
            np.log(row['high'] / current_price + 1e-8),
            np.log(row['low'] / current_price + 1e-8),
            0.0  # close / close = 1 → log(1)=0
        ]
        
        # 技术指标特征 - 归一化
        def safe_div(a, b):
            return a / (b + 1e-8)
        
        technical_features = [
            safe_div(row['ma_5'] - current_price, current_price),
            safe_div(row['ma_10'] - current_price, current_price),
            safe_div(row['ma_20'] - current_price, current_price),
            safe_div(row['ma_50'] - current_price, current_price),
            safe_div(row['ma_200'] - current_price, current_price),
            safe_div(row['ema_12'] - current_price, current_price),
            safe_div(row['ema_26'] - current_price, current_price),
            (row['rsi'] - 50) / 50 if not pd.isna(row['rsi']) else 0.0,
            safe_div(row['macd'], current_price),
            safe_div(row['macd_signal'], current_price),
            safe_div(row['bollinger_upper'] - current_price, current_price),
            safe_div(row['bollinger_middle'] - current_price, current_price),
            safe_div(row['bollinger_lower'] - current_price, current_price),
            safe_div(row['atr'], current_price),
            np.log(row['volume'] + 1),
            np.log(row['volume_ma_5'] + 1),
            (row['volume_ratio'] - 1) if not pd.isna(row['volume_ratio']) else 0.0
        ]
        
        # 市场特征
        market_features = [
            np.log(row['volume'] + 1),
            safe_div(row['atr'], current_price),
            (row['rsi'] - 50) / 50 if not pd.isna(row['rsi']) else 0.0
        ]
        
        # 历史特征：对数收益率 + volume ratio
        history_features = []
        for i in range(step - self.lookback_window, step):
            if i >= 0:
                hist_row = self.df.iloc[i]
                hist_price = hist_row['close']
                price_return = np.log(hist_price / (current_price + 1e-8))
                volume_ratio = np.log((hist_row['volume'] + 1) / (row['volume'] + 1))
                history_features.extend([price_return, volume_ratio])
            else:
                history_features.extend([0.0, 0.0])
        
        # 组合 & 清理
        features = np.array(
            price_features + technical_features + market_features + history_features,
            dtype=np.float32
        )
        features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
        features = np.clip(features, -5.0, 5.0)  # 严格限制范围
        
        return features

    def reset(self):
        self.current_step = int(self.lookback_window)
        self.done = False
        
        return self._get_features(self.current_step)
    
    def step(self):
        if self.done:
            return self._get_features(self.current_step), 0, True, {}
        
        # 获取当前特征
        features = self._get_features(self.current_step)
        
        # 获取下一个时间步的价格
        if self.current_step + 1 < len(self.df):
            next_price = float(self.df.iloc[self.current_step + 1]['close'])
        else:
            next_price = float(self.df.iloc[self.current_step]['close'])
        
        # 计算市场变化
        current_price = float(self.df.iloc[self.current_step]['close'])
        price_change = (next_price - current_price) / current_price
        
        # 更新当前步骤
        self.current_step += 1
        
        # 检查是否完成
        if self.current_step >= len(self.df) - 1:
            self.done = True
        
        # 返回当前特征、价格变化、是否完成、信息
        return features, price_change, self.done, {"current_price": current_price, "next_price": next_price}
    
    def get_market_analysis(self, step):
        """获取市场分析数据"""
        features = self._get_features(step)
        row = self.df.iloc[step]
        
        # 计算市场分析指标
        analysis = {
            'price': row['close'],
            'volume': row['volume'],
            'rsi': row['rsi'] if not pd.isna(row['rsi']) else 50,
            'macd': row['macd'] if not pd.isna(row['macd']) else 0,
            'atr': row['atr'] if not pd.isna(row['atr']) else 0,
            'bollinger_upper': row['bollinger_upper'] if not pd.isna(row['bollinger_upper']) else row['close'],
            'bollinger_lower': row['bollinger_lower'] if not pd.isna(row['bollinger_lower']) else row['close'],
            'trend': 'bullish' if row['rsi'] > 50 else 'bearish' if row['rsi'] < 50 else 'neutral'
        }
        
        return features, analysis

class MarketAnalysisNetwork(nn.Module):
    def __init__(self, feature_dim, hidden_dim=256, activation=F.relu):
        super(MarketAnalysisNetwork, self).__init__()
        
        self.activation = activation
        
        # 特征提取器
        self.feature_extractor = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU()
        )
        
        # 市场分析输出层
        self.market_analysis = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 3)  # 3个输出：价格趋势、波动率、市场强度
        )
        
        # 初始化权重
        self._init_weights()
    
    def _init_weights(self):
        # 对线性层使用xavier初始化
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        
        # 最后一层使用较小的初始化
        nn.init.normal_(self.market_analysis[-1].weight, mean=0., std=0.01)
    
    def forward(self, x):
        features = self.feature_extractor(x)
        analysis = self.market_analysis(features)
        
        # 返回可解释的市场分析结果
        return analysis

class ExplainableMarketModel(nn.Module):
    def __init__(self, feature_dim, hidden_dim=256):
        super(ExplainableMarketModel, self).__init__()
        
        self.analysis_network = MarketAnalysisNetwork(feature_dim, hidden_dim)
    
    def forward(self, x):
        return self.analysis_network(x)
    
    def analyze_market(self, features):
        """分析市场并返回可解释的结果"""
        with torch.no_grad():
            analysis = self.analysis_network(features)
            
            # 解释分析结果
            trend = analysis[0].item()  # 价格趋势：正值上涨，负值下跌
            volatility = analysis[1].item()  # 波动率：正值越大越波动
            strength = analysis[2].item()  # 市场强度：正值市场强劲，负值市场疲软
            
            return {
                'trend': trend,
                'volatility': volatility,
                'market_strength': strength,
                'trend_interpretation': 'bullish' if trend > 0 else 'bearish' if trend < 0 else 'neutral',
                'volatility_interpretation': 'high' if volatility > 0.5 else 'medium' if volatility > 0 else 'low',
                'strength_interpretation': 'strong' if strength > 0.5 else 'moderate' if strength > 0 else 'weak'
            }


class MarketAnalyzer:
    def __init__(self, feature_dim, hidden_dim=256, lr=3e-4):
        self.device = device
        
        # 初始化可解释市场分析模型
        self.model = ExplainableMarketModel(feature_dim, hidden_dim).to(self.device)
        
        # 初始化优化器
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, eps=1e-5)
        
        # 损失函数 - 使用多任务学习损失
        self.trend_loss_fn = nn.MSELoss()
        self.volatility_loss_fn = nn.MSELoss()
        self.strength_loss_fn = nn.MSELoss()
        
        # 用于跟踪训练统计
        self.train_stats = {
            "trend_loss": [],
            "volatility_loss": [],
            "strength_loss": [],
            "total_loss": []
        }
    
    def analyze(self, features):
        """使用模型分析市场"""
        features = torch.FloatTensor(features).unsqueeze(0).to(self.device)
        return self.model.analyze_market(features)
    
    def train_step(self, features, targets):
        """执行一次训练步骤"""
        # 将数据转换为张量
        features = torch.FloatTensor(features).to(self.device)
        target_trend = torch.FloatTensor(targets['trend']).unsqueeze(1).to(self.device)
        target_volatility = torch.FloatTensor(targets['volatility']).unsqueeze(1).to(self.device)
        target_strength = torch.FloatTensor(targets['strength']).unsqueeze(1).to(self.device)
        
        # 前向传播
        outputs = self.model(features)
        pred_trend = outputs[:, 0:1]
        pred_volatility = outputs[:, 1:2]
        pred_strength = outputs[:, 2:3]
        
        # 计算损失
        trend_loss = self.trend_loss_fn(pred_trend, target_trend)
        volatility_loss = self.volatility_loss_fn(pred_volatility, target_volatility)
        strength_loss = self.strength_loss_fn(pred_strength, target_strength)
        
        # 总损失
        total_loss = trend_loss + volatility_loss + strength_loss
        
        # 反向传播
        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()
        
        # 记录训练统计
        self.train_stats["trend_loss"].append(trend_loss.item())
        self.train_stats["volatility_loss"].append(volatility_loss.item())
        self.train_stats["strength_loss"].append(strength_loss.item())
        self.train_stats["total_loss"].append(total_loss.item())
        
        return {
            "trend_loss": trend_loss.item(),
            "volatility_loss": volatility_loss.item(),
            "strength_loss": strength_loss.item(),
            "total_loss": total_loss.item()
        }
    
    def save(self, path):
        """保存模型"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict()
        }, path)
    
    def load(self, path):
        """加载模型"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    
    def explain_prediction(self, features):
        """生成预测解释"""
        analysis = self.analyze(features)
        
        # 生成自然语言解释
        explanation = []
        
        # 趋势解释
        if analysis['trend_interpretation'] == 'bullish':
            explanation.append(f"市场呈现看涨趋势（强度：{abs(analysis['trend']):.2f}），价格有望上涨。")
        elif analysis['trend_interpretation'] == 'bearish':
            explanation.append(f"市场呈现看跌趋势（强度：{abs(analysis['trend']):.2f}），价格可能下跌。")
        else:
            explanation.append(f"市场趋势中性（强度：{abs(analysis['trend']):.2f}），价格波动较小。")
        
        # 波动率解释
        if analysis['volatility_interpretation'] == 'high':
            explanation.append(f"市场波动率较高（程度：{analysis['volatility']:.2f}），价格波动较大，风险较高。")
        elif analysis['volatility_interpretation'] == 'medium':
            explanation.append(f"市场波动率中等（程度：{analysis['volatility']:.2f}），价格波动适中。")
        else:
            explanation.append(f"市场波动率较低（程度：{analysis['volatility']:.2f}），价格相对稳定，风险较低。")
        
        # 市场强度解释
        if analysis['strength_interpretation'] == 'strong':
            explanation.append(f"市场强度较强（指数：{analysis['market_strength']:.2f}），市场动能充足。")
        elif analysis['strength_interpretation'] == 'moderate':
            explanation.append(f"市场强度中等（指数：{analysis['market_strength']:.2f}），市场动能一般。")
        else:
            explanation.append(f"市场强度较弱（指数：{analysis['market_strength']:.2f}），市场动能不足。")
        
        # 综合建议
        if analysis['trend_interpretation'] == 'bullish' and analysis['strength_interpretation'] == 'strong':
            explanation.append("综合来看，市场处于强势上涨阶段，适合积极参与。")
        elif analysis['trend_interpretation'] == 'bearish' and analysis['strength_interpretation'] == 'strong':
            explanation.append("综合来看，市场处于强势下跌阶段，建议谨慎操作或观望。")
        elif analysis['volatility_interpretation'] == 'high':
            explanation.append("由于市场波动率较高，建议控制仓位，注意风险管理。")
        else:
            explanation.append("市场处于相对稳定阶段，可根据具体投资策略灵活操作。")
        
        return {
            "analysis": analysis,
            "explanation": " ".join(explanation),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def generate_report(self, market_data, features):
        """生成完整的市场分析报告"""
        # 运行市场分析
        analysis_result = self.analyze(features)
        explanation = self.explain_prediction(features)['explanation']
        
        # 构建报告
        report = {
            "symbol": market_data.get("symbol", "N/A"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_price": market_data.get("close", "N/A"),
            "price_change": market_data.get("price_change", "N/A"),
            "price_change_percent": market_data.get("price_change_percent", "N/A"),
            "volume": market_data.get("volume", "N/A"),
            "market_analysis": analysis_result,
            "explanation": explanation,
            "technical_indicators": {
                "rsi": market_data.get("rsi", "N/A"),
                "macd": market_data.get("macd", "N/A"),
                "macd_signal": market_data.get("macd_signal", "N/A"),
                "macd_hist": market_data.get("macd_hist", "N/A"),
                "ma_5": market_data.get("ma_5", "N/A"),
                "ma_20": market_data.get("ma_20", "N/A"),
                "ma_50": market_data.get("ma_50", "N/A")
            }
        }
        
        return report


class MarketAnalysisTrainer:
    def __init__(self, model, data_loader, learning_rate=3e-4):
        self.model = model
        self.data_loader = data_loader
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, eps=1e-5)
        
        # 损失函数 - 使用多任务学习损失
        self.trend_loss_fn = nn.MSELoss()
        self.volatility_loss_fn = nn.MSELoss()
        self.strength_loss_fn = nn.MSELoss()
        
        # 用于跟踪训练统计
        self.train_stats = {
            "trend_loss": [],
            "volatility_loss": [],
            "strength_loss": [],
            "total_loss": []
        }
    
    def train(self, epochs=100):
        """训练市场分析模型"""
        print("🚀 开始训练可解释市场分析模型...")
        
        for epoch in range(epochs):
            epoch_trend_loss = 0.0
            epoch_volatility_loss = 0.0
            epoch_strength_loss = 0.0
            epoch_total_loss = 0.0
            
            for batch_idx, (features, targets) in enumerate(self.data_loader):
                # 将数据转换为张量
                features = torch.FloatTensor(features).to(device)
                target_trend = torch.FloatTensor(targets['trend']).unsqueeze(1).to(device)
                target_volatility = torch.FloatTensor(targets['volatility']).unsqueeze(1).to(device)
                target_strength = torch.FloatTensor(targets['strength']).unsqueeze(1).to(device)
                
                # 前向传播
                outputs = self.model(features)
                pred_trend = outputs[:, 0:1]
                pred_volatility = outputs[:, 1:2]
                pred_strength = outputs[:, 2:3]
                
                # 计算损失
                trend_loss = self.trend_loss_fn(pred_trend, target_trend)
                volatility_loss = self.volatility_loss_fn(pred_volatility, target_volatility)
                strength_loss = self.strength_loss_fn(pred_strength, target_strength)
                
                # 总损失
                total_loss = trend_loss + volatility_loss + strength_loss
                
                # 反向传播
                self.optimizer.zero_grad()
                total_loss.backward()
                self.optimizer.step()
                
                # 累计损失
                epoch_trend_loss += trend_loss.item()
                epoch_volatility_loss += volatility_loss.item()
                epoch_strength_loss += strength_loss.item()
                epoch_total_loss += total_loss.item()
            
            # 计算平均损失
            avg_trend_loss = epoch_trend_loss / len(self.data_loader)
            avg_volatility_loss = epoch_volatility_loss / len(self.data_loader)
            avg_strength_loss = epoch_strength_loss / len(self.data_loader)
            avg_total_loss = epoch_total_loss / len(self.data_loader)
            
            # 记录训练统计
            self.train_stats["trend_loss"].append(avg_trend_loss)
            self.train_stats["volatility_loss"].append(avg_volatility_loss)
            self.train_stats["strength_loss"].append(avg_strength_loss)
            self.train_stats["total_loss"].append(avg_total_loss)
            
            print(f"Epoch {epoch+1}/{epochs} - 总损失: {avg_total_loss:.6f}, 趋势损失: {avg_trend_loss:.6f}, 波动率损失: {avg_volatility_loss:.6f}, 市场强度损失: {avg_strength_loss:.6f}")
        
        print("✅ 市场分析模型训练完成！")
        return self.train_stats
    
    def plot_training_progress(self):
        plt.figure(figsize=(12, 8))
        plt.subplot(2, 1, 1)
        plt.plot(self.train_stats['total_loss'], alpha=0.7, color='blue')
        plt.title('总损失变化')
        plt.xlabel('轮次 (Epoch)')
        plt.ylabel('损失值 (Loss)')
        plt.grid(True)
        
        plt.subplot(2, 1, 2)
        plt.plot(self.train_stats['trend_loss'], alpha=0.7, color='green', label='趋势损失')
        plt.plot(self.train_stats['volatility_loss'], alpha=0.7, color='orange', label='波动率损失')
        plt.plot(self.train_stats['strength_loss'], alpha=0.7, color='red', label='市场强度损失')
        plt.title('各子任务损失变化')
        plt.xlabel('轮次 (Epoch)')
        plt.ylabel('损失值 (Loss)')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()

def main():
    df = pd.read_csv('models/data/market_data.csv')
    print("📊 数据加载成功:", df.shape)
    print("📅 时间范围:", df['timestamp'].iloc[0] if 'timestamp' in df else 'N/A', 
            "→", df['timestamp'].iloc[-1] if 'timestamp' in df else 'N/A')
    
    
    # 创建市场分析环境
    env = MarketAnalysisEnvironment(
        df, 
        lookback_window=30
    )
    
    print("🔧 市场分析环境创建成功 | 特征维度:", env.feature_dim)
    
    # 初始化市场分析器
    analyzer = MarketAnalyzer(feature_dim=env.feature_dim)
    
    print("📈 市场分析器初始化完成")
    
    # 示例：使用环境获取数据并进行分析
    step = env.lookback_window
    features, price_change, done, info = env.step()
    
    print("🔍 市场分析示例:")
    print(f"当前价格: {info['current_price']:.2f}")
    print(f"价格变化: {price_change:.4f}")
    
    # 使用分析器进行市场分析
    analysis = analyzer.analyze(features)
    print("📊 市场分析结果:")
    print(f"趋势: {analysis['trend_interpretation']} (强度: {analysis['trend']:.2f})")
    print(f"波动率: {analysis['volatility_interpretation']} (程度: {analysis['volatility']:.2f})")
    print(f"市场强度: {analysis['strength_interpretation']} (指数: {analysis['market_strength']:.2f})")
    
    return analyzer


if __name__ == "__main__":
    agent, returns = main()