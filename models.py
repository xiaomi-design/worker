"""数据模型定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime


class BetType(Enum):
    """下注类型"""
    SINGLE = "single"           # 单点下注  e.g. 3/1000
    BAO = "bao"                 # 保规则    e.g. 2/3/1000  1/23/1000  2/3/4/1000（最多保两个子）
    ZAI = "zai"                 # 仔规则    e.g. 2//3/1000（最多仔一个子）
    SANMA = "sanma"             # 三码下注  e.g. 234/1000


class GameStatus(Enum):
    """游戏局状态"""
    BETTING = "betting"         # 下注中
    SEALED = "sealed"           # 已封盘
    ENDED = "ended"             # 本局已结束（可导出报表、开新局）


@dataclass
class ParsedBet:
    """解析后的单条下注"""
    bet_type: BetType
    main_number: int                       # 主下注号码
    sub_numbers: List[int] = field(default_factory=list)  # 保/载的子号码
    amount: float = 0.0                    # 本注金额（从下注文本中解析）
    raw_text: str = ""                      # 原始文本


@dataclass
class Bet:
    """一条完整的下注记录"""
    id: Optional[int] = None
    game_id: int = 0
    user: str = ""
    amount: float = 0.0
    parsed_bets: List[ParsedBet] = field(default_factory=list)
    raw_text: str = ""
    result: float = 0.0                     # 结算盈亏
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Game:
    """一局游戏（一局内可多次开奖）"""
    id: Optional[int] = None
    status: GameStatus = GameStatus.BETTING
    round_count: int = 0                     # 当前局内已开奖轮数
    dice_results: List[int] = field(default_factory=list)  # 每轮开奖结果
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None

