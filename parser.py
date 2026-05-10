"""下注消息解析器

新格式（金额嵌入下注文本，用 / 分隔）:
  单点: "3/1000"                →  SINGLE(3), amount=1000
  保:   "2/3/1000"              →  BAO(main=2, subs=[3]), amount=1000
        "1/23/1000"             →  BAO(main=1, subs=[2,3]), amount=1000（短写法）
        "2/3/4/1000"            →  BAO(main=2, subs=[3,4]), amount=1000（长写法，最多保两个子）
  仔:   "2//3/1000"             →  ZAI(main=2, subs=[3]), amount=1000
  三码: "234/1000"              →  SANMA(main=2, subs=[3,4]), amount=1000
  多下注: "3/1000///2/3/500"    →  用 /// 隔开多个下注
"""
import re
from typing import List, Optional
from models import ParsedBet, BetType
from config import DICE_MIN, DICE_MAX


class ParseError(Exception):
    """解析异常"""
    pass


def _valid_num(n: int) -> bool:
    return DICE_MIN <= n <= DICE_MAX


def parse_message(text: str) -> Optional[List[ParsedBet]]:
    """解析一条下注消息, 返回 ParsedBet 列表; 非下注消息返回 None"""
    text = text.strip()
    if not text:
        return None

    # ---------- 多下注 (///) ----------
    if "///" in text:
        parts = text.split("///")
        results: List[ParsedBet] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            sub = _parse_single_bet(p)
            if sub is None:
                raise ParseError(f"多下注中无法识别: {p}")
            results.append(sub)
        if not results:
            return None
        return results

    # ---------- 单个下注 ----------
    bet = _parse_single_bet(text)
    if bet is None:
        return None
    return [bet]


def _parse_single_bet(text: str) -> Optional[ParsedBet]:
    """解析单个下注（不含 /// 分隔符）

    格式分析:
      载: 含 // → "2//3/1000" → split("//") → ["2", "3/1000"]
      其他: 用 / 分隔 → 最后一段是金额，前面是号码部分
    """
    text = text.strip()
    if not text:
        return None

    # ---------- 载规则: 含 // ----------
    if "//" in text:
        halves = text.split("//")
        if len(halves) != 2:
            raise ParseError("载规则格式错误，正确格式如: 2//3/1000")
        main_s = halves[0].strip()
        right = halves[1].strip()
        # right 应该是 "3/1000"
        right_parts = right.split("/")
        if len(right_parts) != 2:
            raise ParseError("载规则格式错误，正确格式如: 2//3/1000")
        sub_s, amount_s = right_parts[0].strip(), right_parts[1].strip()
        if not main_s.isdigit() or not sub_s.isdigit():
            raise ParseError("载规则号码必须是数字")
        main_n, sub_n = int(main_s), int(sub_s)
        if not _valid_num(main_n) or not _valid_num(sub_n):
            raise ParseError(f"号码必须在 {DICE_MIN}-{DICE_MAX} 之间")
        if main_n == sub_n:
            raise ParseError("载规则主号和子号不能相同")
        try:
            amount = float(amount_s)
        except ValueError:
            raise ParseError(f"金额格式错误: {amount_s}")
        return ParsedBet(BetType.ZAI, main_n, [sub_n], amount, text)

    # ---------- 用 / 分隔的格式 ----------
    if "/" not in text:
        return None

    parts = [p.strip() for p in text.split("/")]
    if len(parts) < 2:
        return None

    # 最后一段是金额
    amount_s = parts[-1]
    try:
        amount = float(amount_s)
    except ValueError:
        raise ParseError(f"金额格式错误: {amount_s}")

    num_parts = parts[:-1]  # 金额前面的部分

    if len(num_parts) == 1:
        token = num_parts[0]
        if len(token) == 1 and token.isdigit():
            # 单点: "3/1000"
            n = int(token)
            if not _valid_num(n):
                raise ParseError(f"号码必须在 {DICE_MIN}-{DICE_MAX} 之间")
            return ParsedBet(BetType.SINGLE, n, [], amount, text)

        if len(token) == 3 and token.isdigit():
            # 三码: "234/1000"
            nums = [int(c) for c in token]
            for n in nums:
                if not _valid_num(n):
                    raise ParseError(f"三码号码必须在 {DICE_MIN}-{DICE_MAX} 之间")
            if len(set(nums)) != 3:
                raise ParseError("三码号码不能重复")
            return ParsedBet(BetType.SANMA, nums[0], nums[1:], amount, text)

        raise ParseError(f"无法识别的下注格式: {text}")

    # 保规则: "2/3/1000" / "1/23/1000"（短写法）/ "2/3/4/1000"（长写法）
    if len(num_parts) == 2 or len(num_parts) == 3:
        main_s = num_parts[0]
        if not main_s.isdigit() or len(main_s) != 1:
            raise ParseError(f"保规则主号必须是单个数字: {main_s}")
        main_n = int(main_s)

        sub_nums: List[int] = []
        if len(num_parts) == 2:
            # 主号 + 子段：子段可为单数字（保 1 个）或两位连写（保 2 个）
            sub_token = num_parts[1]
            if not sub_token.isdigit():
                raise ParseError(f"保规则子号必须是数字: {sub_token}")
            if len(sub_token) == 1:
                sub_nums = [int(sub_token)]
            elif len(sub_token) == 2:
                sub_nums = [int(c) for c in sub_token]
            else:
                raise ParseError("保规则最多保两个子（子段最多 2 位）")
        else:
            # 长写法：主号 + 两个独立子号
            for p in num_parts[1:]:
                if not p.isdigit() or len(p) != 1:
                    raise ParseError(f"保规则号码必须是单个数字: {p}")
                sub_nums.append(int(p))

        all_nums = [main_n] + sub_nums
        for n in all_nums:
            if not _valid_num(n):
                raise ParseError(f"号码必须在 {DICE_MIN}-{DICE_MAX} 之间")
        if len(set(all_nums)) != len(all_nums):
            raise ParseError("保规则号码不能重复")
        return ParsedBet(BetType.BAO, main_n, sub_nums, amount, text)

    raise ParseError(f"无法识别的下注格式: {text}")

