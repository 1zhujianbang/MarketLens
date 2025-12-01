import asyncio
from src.config.config_manager import TradingConfig
from src.agents.trading_agent import TradingAgent

async def main():
    try:
        # 方法1: 自动加载配置
        config = TradingConfig.from_yaml()
        
        # 方法2: 指定配置文件路径
        # config = TradingConfig.from_yaml('config/user_config.yaml')
        
        # 创建交易Agent
        agent = TradingAgent(config)
        await agent.initialize()
        
        print(agent.get_status())
        print("✅ 交易系统启动成功!")
        
        # 进入主循环
        # agent.run()

        return 0
        
    except Exception as e:
        print(f"💥 系统启动失败: {e}")
        return 1
    
    finally:
        # 显示关闭所有资源
        if agent:
            await agent.cleanup()
            print("🎯 所有资源已显示关闭")

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
        exit(0)