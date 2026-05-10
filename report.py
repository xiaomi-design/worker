"""报表生成模块 —— 按群导出 CSV，含累加汇总抬头"""
import csv
import os
from datetime import datetime
from typing import List

from config import REPORT_DIR


def _ensure_dir(subdir: str = ""):
    path = os.path.join(REPORT_DIR, subdir) if subdir else REPORT_DIR
    os.makedirs(path, exist_ok=True)
    return path


def export_game_csv(group_name: str, game_id: int, summary: dict,
                    results: List[dict]) -> str:
    """导出单局报表 CSV（含累加汇总抬头），按群名分目录

    Args:
        group_name: 群名
        game_id: 局号
        summary: engine.get_summary() 返回的累加汇总数据
        results: engine.get_all_results() 返回的所有轮次结算数据
    Returns:
        生成的文件路径
    """
    report_dir = _ensure_dir(group_name)
    filename = f"第{game_id}局_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(report_dir, filename)

    dice_list = summary.get("dice_results", [])
    dice_str = " → ".join(str(d) for d in dice_list) if dice_list else "未开奖"

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # ===== 汇总抬头（累加） =====
        writer.writerow(["群名", group_name])
        writer.writerow(["局号", f"第{game_id}局"])
        writer.writerow(["共开奖轮数", summary.get("round_count", 0)])
        writer.writerow(["开奖数字", dice_str])
        writer.writerow(["总下注金额", f"{summary['total_bet_amount']:.0f}"])
        writer.writerow(["总赢（玩家赢）", f"{summary['total_win']:+.1f}"])
        writer.writerow(["总输（玩家输）", f"{summary['total_lose']:+.1f}"])
        writer.writerow(["庄家盈利", f"{-summary['total_profit']:+.1f}"])
        writer.writerow([])  # 空行分隔

        # ===== 玩家明细（含轮次） =====
        writer.writerow(["轮次", "玩家", "下注内容", "下注金额", "开奖数字", "盈亏", "结果"])
        for r in results:
            profit = r.get("profit", 0)
            flag = "赢" if profit > 0 else ("输" if profit < 0 else "平")
            writer.writerow([
                f"第{r.get('round', '')}轮",
                r.get("user", ""),
                r.get("raw_text", ""),
                f"{r.get('amount', 0):.0f}",
                r.get("dice_result", ""),
                f"{profit:+.1f}",
                flag,
            ])

    print(f"📊 [{group_name}] 报表已保存: {filepath}")
    return filepath


def print_summary(summary: dict):
    """在终端打印累加汇总信息"""
    gn = summary["group_name"]
    gid = summary["game_id"]
    status_map = {"betting": "下注中", "sealed": "已封盘", "ended": "已结束"}
    status = status_map.get(summary["status"], summary["status"])
    dice_list = summary.get("dice_results", [])
    dice_str = " → ".join(str(d) for d in dice_list) if dice_list else "-"
    rc = summary.get("round_count", 0)

    print()
    print(f"┌─── [{gn}] 第{gid}局 ── {status} ── 已开{rc}轮 ───")
    print(f"│ 总下注金额:   {summary['total_bet_amount']:.0f}")
    if summary.get("pending_bet_amount", 0) > 0:
        print(f"│ 待结算金额:   {summary['pending_bet_amount']:.0f}")
    print(f"│ 开奖数字:     {dice_str}")
    if rc > 0:
        print(f"│ 总赢(玩家):   {summary['total_win']:+.1f}")
        print(f"│ 总输(玩家):   {summary['total_lose']:+.1f}")
        print(f"│ 庄家盈利:     {-summary['total_profit']:+.1f}")
    print(f"└{'─' * 40}")

