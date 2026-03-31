from execution.brokers.alpaca import AlpacaBroker
from execution.risk import RiskEngine
from data.config import get_settings

s = get_settings()
broker = AlpacaBroker()
risk = RiskEngine(eval_profit_target=s.eval_profit_target)

acct = broker.get_account()
risk.seed(acct.equity)
print(risk.get_status())