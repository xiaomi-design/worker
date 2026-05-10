#!/usr/bin/env python3
"""微信下注机器人 —— 主入口（菜单式交互，支持多群，非技术人员可直接使用）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import GameEngine, EngineError
from report import export_game_csv, print_summary
from wechat import ClipboardWatcher


def show_menu(current_group: str):
    print()
    print("╔════════════════════════════════════════╗")
    print("║        🎲  微信下注机器人  🎲          ║")
    print(f"║  当前群: {current_group:<28s}  ║")
    print("╠════════════════════════════════════════╣")
    print("║  1. 开始新一局                         ║")
    print("║  2. 从微信复制下注（自动识别）         ║")
    print("║  3. 封盘                               ║")
    print("║  4. 开奖（随机）→ 继续下一轮           ║")
    print("║  5. 开奖（指定点数）→ 继续下一轮       ║")
    print("║  6. 查看当前下注 + 累计汇总            ║")
    print("║  7. 结束本局                           ║")
    print("║  8. 导出报表（CSV）                    ║")
    print("║  9. 切换/添加群                        ║")
    print("║  0. 退出                               ║")
    print("╚════════════════════════════════════════╝")


def show_round_results(summary, round_results):
    """显示累计汇总 + 本轮结算结果"""
    print_summary(summary)
    print()
    print(f"  本轮结算（第{round_results[0]['round']}轮 开奖: {round_results[0]['dice_result']}）:" if round_results else "")
    print("  ┌────────┬────────────┬──────────┬──────────┬──────┐")
    print("  │ 玩家   │ 下注内容   │ 下注金额 │ 盈亏     │ 结果 │")
    print("  ├────────┼────────────┼──────────┼──────────┼──────┤")
    for r in round_results:
        flag = "🟢赢" if r["profit"] > 0 else ("🔴输" if r["profit"] < 0 else "⚪平")
        print(f"  │ {r['user']:<6s} │ {r['raw_text']:<10s} │ {r['amount']:>8.0f} │ {r['profit']:>+8.1f} │ {flag} │")
    print("  └────────┴────────────┴──────────┴──────────┴──────┘")


def show_current_bets(engine, group):
    """显示当前待结算下注 + 累计汇总"""
    bets = engine.get_pending_bets(group)
    summary = engine.get_summary(group)
    print_summary(summary)
    if not bets:
        print("  📋 当前轮暂无下注记录")
        return
    print(f"  📋 当前轮待结算下注（{len(bets)} 条）:")
    for i, bet in enumerate(bets, 1):
        print(f"    {i}. {bet.user} → {bet.raw_text}  金额: {bet.amount:.0f}")


def choose_group(engine) -> str:
    """选择或添加群"""
    groups = engine.list_groups()
    print("\n当前已有群:")
    if groups:
        for i, g in enumerate(groups, 1):
            print(f"  {i}. {g}")
    else:
        print("  （还没有群）")
    print()
    name = input("输入群名（已有的直接切换，新的自动添加）: ").strip()
    if not name:
        return ""
    engine.add_group(name)
    return name


def main():
    engine = GameEngine()
    current_group = ""

    print("\n🎲 微信下注机器人已启动！")
    print("💡 提示: 不同微信群的下注和报表是独立的\n")

    # 先选一个群
    current_group = choose_group(engine)
    if not current_group:
        print("未输入群名，退出")
        return

    while True:
        show_menu(current_group)
        try:
            choice = input("\n请输入选项编号: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！👋")
            break

        try:
            if choice == "1":
                engine.new_game(current_group)

            elif choice == "2":
                game = engine.get_current_game(current_group)
                if not game or game.status.value != "betting":
                    print("❌ 请先开局（选项1），或等开奖后再继续下注")
                    continue
                print("\n💡 操作方法:")
                print("   1) 在微信群里选中要录入的消息")
                print("   2) 右键 → 复制")
                print("   3) 系统会自动识别下注人和下注内容")
                print("   4) 按 Ctrl+C 停止监听，回到主菜单\n")
                g = current_group
                watcher = ClipboardWatcher(
                    on_message=lambda u, t: engine.place_bet(g, u, t)
                )
                watcher.start()

            elif choice == "3":
                engine.seal(current_group)

            elif choice == "4":
                game, round_results = engine.open_dice(current_group)
                summary = engine.get_summary(current_group)
                show_round_results(summary, round_results)
                print("\n💡 可以继续下注 → 封盘 → 开奖，数据会累加")

            elif choice == "5":
                n = input("请输入开奖点数 (1-6): ").strip()
                if not n.isdigit() or int(n) < 1 or int(n) > 6:
                    print("❌ 请输入 1-6 的数字")
                    continue
                game, round_results = engine.open_dice(current_group, int(n))
                summary = engine.get_summary(current_group)
                show_round_results(summary, round_results)
                print("\n💡 可以继续下注 → 封盘 → 开奖，数据会累加")

            elif choice == "6":
                show_current_bets(engine, current_group)

            elif choice == "7":
                engine.end_game(current_group)
                summary = engine.get_summary(current_group)
                print_summary(summary)

            elif choice == "8":
                game = engine.get_current_game(current_group)
                if not game or game.status.value != "ended":
                    print("❌ 请先结束本局（选项7），或还没有开过奖")
                    continue
                summary = engine.get_summary(current_group)
                results = engine.get_all_results(current_group)
                export_game_csv(current_group, game.id, summary, results)

            elif choice == "9":
                g = choose_group(engine)
                if g:
                    current_group = g
                    print(f"✅ 已切换到群: {current_group}")

            elif choice == "0":
                print("再见！👋")
                break

            else:
                print("❌ 无效选项，请输入 0-9 的数字")

        except EngineError as e:
            print(f"❌ {e}")
        except Exception as e:
            print(f"⚠️  错误: {e}")


if __name__ == "__main__":
    main()

