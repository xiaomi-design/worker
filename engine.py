"""游戏引擎 —— 管理局、下注、结算（纯内存版，支持多群）"""
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from models import Game, GameStatus, Bet, ParsedBet, BetType
from parser import parse_message, ParseError
from config import (
    DICE_MIN, DICE_MAX,
    ODDS_SINGLE,
    ODDS_BAO_MAIN,
    ODDS_ZAI_MAIN, ODDS_ZAI_SUB,
    ODDS_SANMA_CONTAINS_1, ODDS_SANMA_NO_1,
    ODDS_PINGBO,
)


class EngineError(Exception):
    pass


class MemberStats:
    """成员累计统计（跨局）"""

    def __init__(self, name: str):
        self.name = name
        self.total_bet_amount: float = 0.0    # 累计投入
        self.total_win: float = 0.0           # 累计赢（正数部分）
        self.total_lose: float = 0.0          # 累计输（负数部分的绝对值）
        self.total_profit: float = 0.0        # 累计输赢净值

    @property
    def profit_rate(self) -> float:
        """盈亏率 = 累计输赢 / 累计投入"""
        if self.total_bet_amount == 0:
            return 0.0
        return self.total_profit / self.total_bet_amount

    def update(self, bet_amount: float, profit: float):
        """更新一次结算"""
        self.total_bet_amount += bet_amount
        self.total_profit += profit
        if profit > 0:
            self.total_win += profit
        elif profit < 0:
            self.total_lose += abs(profit)


class GroupState:
    """单个群的游戏状态"""

    def __init__(self, group_name: str):
        self.group_name = group_name
        self.game_counter = 0
        self.current_game: Optional[Game] = None
        self.pending_bets: List[Bet] = []        # 当前轮待结算的下注
        self.all_results: List[dict] = []         # 本局所有轮次的结算结果（累加）
        self.all_bets: List[Bet] = []             # 本局所有轮次的下注（累加）
        self.members: Dict[str, MemberStats] = {}  # 成员累计统计（跨局）

    def get_or_create_member(self, name: str) -> MemberStats:
        if name not in self.members:
            self.members[name] = MemberStats(name)
        return self.members[name]


class GameEngine:
    """游戏引擎（纯内存，支持多群独立管理）"""

    def __init__(self):
        self._groups: Dict[str, GroupState] = {}

    # ---- 群管理 ----

    def add_group(self, group_name: str) -> GroupState:
        """添加一个群"""
        if group_name not in self._groups:
            self._groups[group_name] = GroupState(group_name)
            print(f"✅ 已添加群: {group_name}")
        return self._groups[group_name]

    def get_group(self, group_name: str) -> GroupState:
        if group_name not in self._groups:
            raise EngineError(f"群 [{group_name}] 不存在，请先添加")
        return self._groups[group_name]

    def list_groups(self) -> List[str]:
        return list(self._groups.keys())

    def remove_group(self, group_name: str):
        """解散群（本局必须已结束或没有进行中的局）"""
        gs = self.get_group(group_name)
        if gs.current_game and gs.current_game.status != GameStatus.ENDED:
            raise EngineError(f"[{group_name}] 当前局未结束，请先结束本局再解散")
        del self._groups[group_name]
        print(f"🗑️ 群 [{group_name}] 已解散")

    # ---- 局管理 ----

    def new_game(self, group_name: str) -> Game:
        """开始新一局"""
        gs = self.get_group(group_name)
        if gs.current_game and gs.current_game.status != GameStatus.ENDED:
            raise EngineError(f"[{group_name}] 第 {gs.current_game.id} 局尚未结束，请先结束本局")
        gs.game_counter += 1
        gs.current_game = Game(id=gs.game_counter, status=GameStatus.BETTING)
        gs.pending_bets = []
        gs.all_results = []
        gs.all_bets = []
        print(f"✅ [{group_name}] 第 {gs.current_game.id} 局已开始，等待下注...")
        return gs.current_game

    def seal(self, group_name: str) -> Game:
        """封盘"""
        gs = self.get_group(group_name)
        game = self._require_game(gs, GameStatus.BETTING)
        if not gs.pending_bets:
            raise EngineError(f"[{group_name}] 当前没有下注，无法封盘")
        game.status = GameStatus.SEALED
        round_num = game.round_count + 1
        print(f"🔒 [{group_name}] 第 {game.id} 局 第 {round_num} 轮已封盘")
        return game

    def open_dice(self, group_name: str, number: int = None) -> Tuple[Game, List[dict]]:
        """开奖 + 结算本轮，然后回到下注状态（一局可多次开奖）"""
        gs = self.get_group(group_name)
        if not gs.current_game:
            raise EngineError(f"[{group_name}] 当前没有进行中的局，请先开局")
        # 如果还在下注中，自动封盘
        if gs.current_game.status == GameStatus.BETTING:
            if not gs.pending_bets:
                raise EngineError(f"[{group_name}] 当前没有下注，无法开奖")
            gs.current_game.status = GameStatus.SEALED
            print(f"🔒 [{group_name}] 自动封盘")
        game = self._require_game(gs, GameStatus.SEALED)
        if number is None:
            number = random.randint(DICE_MIN, DICE_MAX)
        if not (DICE_MIN <= number <= DICE_MAX):
            raise EngineError(f"开奖号码必须在 {DICE_MIN}-{DICE_MAX} 之间")

        game.round_count += 1
        game.dice_results.append(number)

        # 结算本轮
        round_results = self._settle_round(gs, number)

        # 累加到本局总结果
        gs.all_results.extend(round_results)
        gs.all_bets.extend(gs.pending_bets)

        # 清空本轮下注，回到下注状态
        gs.pending_bets = []
        game.status = GameStatus.BETTING

        print(f"🎲 [{group_name}] 第 {game.id} 局 第 {game.round_count} 轮开奖: {number}")
        return game, round_results

    def end_game(self, group_name: str) -> Game:
        """结束本局"""
        gs = self.get_group(group_name)
        game = gs.current_game
        if not game or game.status == GameStatus.ENDED:
            raise EngineError(f"[{group_name}] 当前没有进行中的局")
        if game.status == GameStatus.SEALED:
            raise EngineError(f"[{group_name}] 当前已封盘未开奖，请先开奖再结束")
        if game.round_count == 0:
            raise EngineError(f"[{group_name}] 还没有开过奖，无法结束")
        game.status = GameStatus.ENDED
        game.ended_at = datetime.now().isoformat()
        print(f"🏁 [{group_name}] 第 {game.id} 局已结束（共 {game.round_count} 轮）")
        return game

    # ---- 下注 ----

    def place_bet(self, group_name: str, user: str, raw_text: str, amount: float = 0) -> Bet:
        """玩家下注（新格式中金额嵌入下注文本，amount 参数仅做兼容保留）"""
        gs = self.get_group(group_name)
        game = self._require_game(gs, GameStatus.BETTING)
        parsed = parse_message(raw_text)
        if parsed is None:
            raise EngineError("无法识别的下注内容")
        # 总金额 = 所有子注金额之和
        total_amount = sum(pb.amount for pb in parsed)
        bet = Bet(game_id=game.id, user=user, amount=total_amount,
                  parsed_bets=parsed, raw_text=raw_text)
        gs.pending_bets.append(bet)
        gs.get_or_create_member(user)  # 确保成员存在
        print(f"📝 [{group_name}] {user} 下注: {raw_text}  金额: {total_amount}")
        return bet

    # ---- 查询 ----

    def get_current_game(self, group_name: str) -> Optional[Game]:
        gs = self.get_group(group_name)
        return gs.current_game

    def get_pending_bets(self, group_name: str) -> List[Bet]:
        """当前轮待结算的下注"""
        gs = self.get_group(group_name)
        return list(gs.pending_bets)

    def get_all_results(self, group_name: str) -> List[dict]:
        """本局所有轮次的累加结算结果"""
        gs = self.get_group(group_name)
        return list(gs.all_results)

    def get_summary(self, group_name: str) -> dict:
        """获取本局累加汇总（一局未结束时实时累加）"""
        gs = self.get_group(group_name)
        game = gs.current_game

        # 累加下注金额 = 已结算轮次 + 当前待结算
        settled_bet_amount = sum(b.amount for b in gs.all_bets)
        pending_bet_amount = sum(b.amount for b in gs.pending_bets)
        total_bet_amount = settled_bet_amount + pending_bet_amount

        # 从累加结果统计输赢
        total_win = sum(r["profit"] for r in gs.all_results if r["profit"] > 0)
        total_lose = sum(r["profit"] for r in gs.all_results if r["profit"] < 0)
        total_profit = sum(r["profit"] for r in gs.all_results)

        return {
            "group_name": group_name,
            "game_id": game.id if game else None,
            "status": game.status.value if game else None,
            "round_count": game.round_count if game else 0,
            "dice_results": list(game.dice_results) if game else [],
            "total_bet_amount": total_bet_amount,
            "pending_bet_amount": pending_bet_amount,
            "total_win": total_win,
            "total_lose": total_lose,
            "total_profit": total_profit,
        }

    # ---- 结算 ----

    def _settle_round(self, gs: GroupState, dice: int) -> List[dict]:
        """结算当前轮的下注"""
        round_num = gs.current_game.round_count
        results = []
        for bet in gs.pending_bets:
            total_profit = 0.0
            for pb in bet.parsed_bets:
                profit = self._calc_single(pb, dice)
                total_profit += profit
            bet.result = total_profit
            # 更新成员累计统计
            member = gs.get_or_create_member(bet.user)
            member.update(bet.amount, total_profit)
            results.append({
                "round": round_num,
                "user": bet.user, "raw_text": bet.raw_text,
                "amount": bet.amount, "profit": total_profit,
                "dice_result": dice,
            })
        return results

    @staticmethod
    def _calc_single(pb: ParsedBet, dice: int) -> float:
        """计算单条解析下注的盈亏（金额从 ParsedBet.amount 取）"""
        main = pb.main_number
        subs = pb.sub_numbers
        amount = pb.amount

        if pb.bet_type == BetType.SINGLE:
            if dice == main:
                return amount * ODDS_SINGLE[main] - amount
            return -amount

        if pb.bet_type == BetType.BAO:
            if dice == main:
                return amount * ODDS_BAO_MAIN - amount
            if dice in subs:
                return 0.0
            return -amount

        if pb.bet_type == BetType.ZAI:
            if dice == main:
                return amount * ODDS_ZAI_MAIN - amount
            if dice in subs:
                return amount * ODDS_ZAI_SUB - amount
            return -amount

        if pb.bet_type == BetType.SANMA:
            all_nums = [main] + subs
            if dice in all_nums:
                if 1 in all_nums:
                    return amount * ODDS_SANMA_CONTAINS_1 - amount
                return amount * ODDS_SANMA_NO_1 - amount
            return -amount

        if pb.bet_type == BetType.PINGBO:
            all_nums = [main] + subs
            if dice in all_nums:
                return amount * ODDS_PINGBO - amount
            return -amount

        return -amount

    # ---- 模拟开奖 ----

    def simulate_all_dice(self, group_name: str) -> List[dict]:
        """模拟开1-6每个点数的盈亏情况"""
        gs = self.get_group(group_name)
        if not gs.pending_bets:
            return []
        results = []
        for dice in range(DICE_MIN, DICE_MAX + 1):
            # 按玩家汇总
            player_profits = {}
            total_profit = 0.0
            for bet in gs.pending_bets:
                bet_profit = 0.0
                for pb in bet.parsed_bets:
                    bet_profit += self._calc_single(pb, dice)
                player_profits.setdefault(bet.user, 0.0)
                player_profits[bet.user] += bet_profit
                total_profit += bet_profit
            players = [{"user": u, "profit": p} for u, p in player_profits.items()]
            results.append({
                "dice": dice,
                "total_player_profit": total_profit,
                "banker_profit": -total_profit,
                "players": players,
            })
        return results

    # ---- 本筒操作 ----

    def clear_pending_bets(self, group_name: str):
        """清除本筒（清空当前轮所有未结算的下注）"""
        gs = self.get_group(group_name)
        n = len(gs.pending_bets)
        gs.pending_bets = []
        print(f"🧹 [{group_name}] 已清除本筒 {n} 条下注")

    def revert_last_round(self, group_name: str):
        """返回上筒（撤销最后一轮开奖，恢复下注，回退成员统计）"""
        gs = self.get_group(group_name)
        game = gs.current_game
        if not game or game.round_count == 0:
            raise EngineError("没有可返回的上一轮")
        last_dice = game.dice_results[-1]
        last_round_num = game.round_count
        # 找出最后一轮的所有结算
        last_results = [r for r in gs.all_results if r["round"] == last_round_num]
        if not last_results:
            raise EngineError("找不到上一轮结算数据")
        # 回退成员统计
        for r in last_results:
            m = gs.members.get(r["user"])
            if m:
                m.total_bet_amount -= r["amount"]
                m.total_profit -= r["profit"]
                if r["profit"] > 0:
                    m.total_win -= r["profit"]
                elif r["profit"] < 0:
                    m.total_lose -= abs(r["profit"])
        # 把最后一轮的下注从 all_bets 移回 pending_bets
        last_bets = [b for b in gs.all_bets if b.game_id == game.id][-len(last_results):]
        for b in last_bets:
            gs.all_bets.remove(b)
            b.result = None
            gs.pending_bets.append(b)
        # 移除最后一轮的结算记录和开奖记录
        gs.all_results = [r for r in gs.all_results if r["round"] != last_round_num]
        game.dice_results.pop()
        game.round_count -= 1
        game.status = GameStatus.BETTING
        print(f"⏪ [{group_name}] 已返回上一轮（上次开 {last_dice}）")

    def get_last_round(self, group_name: str) -> dict:
        """查看上筒（最后一轮的开奖结果与下注明细）"""
        gs = self.get_group(group_name)
        game = gs.current_game
        if not game or game.round_count == 0:
            raise EngineError("还没有开过奖")
        last_round_num = game.round_count
        last_dice = game.dice_results[-1]
        last_results = [r for r in gs.all_results if r["round"] == last_round_num]
        return {
            "round": last_round_num,
            "dice": last_dice,
            "results": last_results,
            "total_profit": sum(r["profit"] for r in last_results),
        }

    # ---- 修改/删除下注 ----

    def remove_bet(self, group_name: str, bet_index: int):
        """删除当前轮的某条下注（按索引）"""
        gs = self.get_group(group_name)
        if bet_index < 0 or bet_index >= len(gs.pending_bets):
            raise EngineError("下注索引无效")
        removed = gs.pending_bets.pop(bet_index)
        print(f"🗑️ [{group_name}] 已删除 {removed.user} 的下注: {removed.raw_text}")

    def update_bet(self, group_name: str, bet_index: int, new_raw_text: str):
        """修改当前轮的某条下注"""
        gs = self.get_group(group_name)
        if bet_index < 0 or bet_index >= len(gs.pending_bets):
            raise EngineError("下注索引无效")
        old_bet = gs.pending_bets[bet_index]
        parsed = parse_message(new_raw_text)
        if parsed is None:
            raise EngineError("无法识别的下注内容")
        total_amount = sum(pb.amount for pb in parsed)
        old_bet.parsed_bets = parsed
        old_bet.amount = total_amount
        old_bet.raw_text = new_raw_text
        print(f"✏️ [{group_name}] 已修改 {old_bet.user} 的下注: {new_raw_text}")

    # ---- 成员统计 ----

    def get_members(self, group_name: str) -> List[dict]:
        """获取群成员列表及累计统计"""
        gs = self.get_group(group_name)
        members = []
        for i, m in enumerate(gs.members.values(), 1):
            members.append({
                "index": i,
                "name": m.name,
                "total_bet_amount": m.total_bet_amount,
                "total_win": m.total_win,
                "total_lose": m.total_lose,
                "total_profit": m.total_profit,
                "profit_rate": m.profit_rate,
            })
        return members

    def get_rankings(self, group_name: str) -> dict:
        """获取赢输排行榜"""
        gs = self.get_group(group_name)
        members = list(gs.members.values())
        winners = sorted([m for m in members if m.total_profit > 0],
                         key=lambda m: m.total_profit, reverse=True)
        losers = sorted([m for m in members if m.total_profit < 0],
                        key=lambda m: m.total_profit)
        total_win = sum(m.total_profit for m in members if m.total_profit > 0)
        total_lose = sum(m.total_profit for m in members if m.total_profit < 0)
        total = sum(m.total_profit for m in members)
        return {
            "winners": [{"name": m.name, "profit": m.total_profit} for m in winners],
            "losers": [{"name": m.name, "profit": m.total_profit} for m in losers],
            "total_win": total_win,
            "total_lose": total_lose,
            "total": total,
        }

    def add_member(self, group_name: str, member_name: str):
        """手动添加成员"""
        gs = self.get_group(group_name)
        gs.get_or_create_member(member_name)

    def remove_member(self, group_name: str, member_name: str):
        """移除成员"""
        gs = self.get_group(group_name)
        if member_name in gs.members:
            del gs.members[member_name]
        else:
            raise EngineError(f"成员 [{member_name}] 不存在")

    # ---- 辅助 ----

    @staticmethod
    def _require_game(gs: GroupState, expected_status: GameStatus) -> Game:
        if not gs.current_game:
            raise EngineError(f"[{gs.group_name}] 当前没有进行中的局，请先开局")
        if gs.current_game.status != expected_status:
            raise EngineError(
                f"[{gs.group_name}] 当前局状态为 {gs.current_game.status.value}，"
                f"期望 {expected_status.value}")
        return gs.current_game

