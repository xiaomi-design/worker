#!/usr/bin/env python3
"""微信下注机器人 —— Web 页面版"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file
from engine import GameEngine, EngineError
from report import export_game_csv

app = Flask(__name__)
engine = GameEngine()


@app.route("/")
def index():
    groups = engine.list_groups()
    return render_template("index.html", groups=groups)


# ========== 群管理 ==========

@app.route("/api/group/add", methods=["POST"])
def add_group():
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify(ok=False, msg="群名不能为空")
    engine.add_group(name)
    return jsonify(ok=True, msg=f"已添加群: {name}")


@app.route("/api/groups")
def list_groups():
    return jsonify(groups=engine.list_groups())


@app.route("/api/group/remove", methods=["POST"])
def remove_group():
    name = request.json.get("name", "").strip()
    try:
        engine.remove_group(name)
        return jsonify(ok=True, msg=f"群 [{name}] 已解散")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 局管理 ==========

@app.route("/api/game/new", methods=["POST"])
def new_game():
    group = request.json.get("group")
    try:
        game = engine.new_game(group)
        return jsonify(ok=True, msg=f"第 {game.id} 局已开始")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/game/seal", methods=["POST"])
def seal():
    group = request.json.get("group")
    try:
        engine.seal(group)
        return jsonify(ok=True, msg="已封盘")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/game/open", methods=["POST"])
def open_dice():
    group = request.json.get("group")
    number = request.json.get("number")  # None = 随机
    try:
        game, round_results = engine.open_dice(group, number)
        summary = engine.get_summary(group)
        return jsonify(ok=True, round_results=round_results, summary=summary,
                       msg=f"第 {game.round_count} 轮开奖: {game.dice_results[-1]}")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/game/end", methods=["POST"])
def end_game():
    group = request.json.get("group")
    try:
        engine.end_game(group)
        summary = engine.get_summary(group)
        return jsonify(ok=True, summary=summary, msg="本局已结束")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 下注 ==========

@app.route("/api/bet", methods=["POST"])
def place_bet():
    group = request.json.get("group")
    user = request.json.get("user", "").strip()
    bet_text = request.json.get("bet_text", "").strip()
    try:
        bet = engine.place_bet(group, user, bet_text)
        return jsonify(ok=True, msg=f"{user} 下注: {bet_text} 金额: {bet.amount}")
    except (EngineError, Exception) as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/bet/parse", methods=["POST"])
def parse_bets():
    """解析粘贴的微信消息，返回识别出的下注列表（不提交）"""
    from wechat import parse_wechat_messages
    text = request.json.get("text", "")
    msgs = parse_wechat_messages(text)
    parsed = []
    for user, bet_text in msgs:
        parsed.append({"user": user, "bet_text": bet_text})
    if not parsed:
        return jsonify(ok=False, msg="未识别到下注信息，格式示例：\n张三:\n3/1000")
    return jsonify(ok=True, parsed=parsed, msg=f"识别到 {len(parsed)} 条下注")


@app.route("/api/bet/batch", methods=["POST"])
def batch_bet():
    """批量确认下注"""
    group = request.json.get("group")
    bets = request.json.get("bets", [])
    success = 0
    errors = []
    for b in bets:
        try:
            engine.place_bet(group, b["user"], b["bet_text"])
            success += 1
        except Exception as e:
            errors.append(f"{b['user']}: {e}")
    msg = f"成功下注 {success} 条"
    if errors:
        msg += f"，失败 {len(errors)} 条: " + "; ".join(errors)
    return jsonify(ok=len(errors) == 0, msg=msg)


# ========== 修改/删除下注 ==========

@app.route("/api/bet/remove", methods=["POST"])
def remove_bet():
    group = request.json.get("group")
    index = request.json.get("index")
    try:
        engine.remove_bet(group, index)
        return jsonify(ok=True, msg="已删除下注")
    except (EngineError, Exception) as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/bet/update", methods=["POST"])
def update_bet():
    group = request.json.get("group")
    index = request.json.get("index")
    new_text = request.json.get("bet_text", "").strip()
    try:
        engine.update_bet(group, index, new_text)
        return jsonify(ok=True, msg="已修改下注")
    except (EngineError, Exception) as e:
        return jsonify(ok=False, msg=str(e))


# ========== 系统剪贴板 ==========

@app.route("/api/clipboard")
def read_clipboard():
    """读取系统剪贴板（macOS 用 pbpaste，Linux 用 xclip，Windows 用 powershell）"""
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            text = subprocess.check_output(["pbpaste"]).decode("utf-8")
        elif sys.platform.startswith("linux"):
            text = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"]).decode("utf-8")
        elif sys.platform == "win32":
            text = subprocess.check_output(
                ["powershell", "-Command", "Get-Clipboard"]).decode("utf-8")
        else:
            return jsonify(ok=False, msg="不支持的系统")
        return jsonify(ok=True, text=text)
    except Exception as e:
        return jsonify(ok=False, msg=f"读取剪贴板失败: {e}")


# ========== 本筒操作 ==========

@app.route("/api/round/clear", methods=["POST"])
def clear_round():
    group = request.json.get("group")
    try:
        engine.clear_pending_bets(group)
        return jsonify(ok=True, msg="已清除本筒")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/round/revert", methods=["POST"])
def revert_round():
    group = request.json.get("group")
    try:
        engine.revert_last_round(group)
        return jsonify(ok=True, msg="已返回上筒")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/round/last")
def last_round():
    group = request.args.get("group")
    try:
        data = engine.get_last_round(group)
        return jsonify(ok=True, data=data)
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 模拟开奖 ==========

@app.route("/api/simulate")
def simulate():
    group = request.args.get("group")
    try:
        results = engine.simulate_all_dice(group)
        return jsonify(ok=True, results=results)
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 查询 ==========

@app.route("/api/status")
def get_status():
    group = request.args.get("group")
    try:
        game = engine.get_current_game(group)
        summary = engine.get_summary(group)
        pending = [{"user": b.user, "raw_text": b.raw_text, "amount": b.amount}
                   for b in engine.get_pending_bets(group)]
        all_results = engine.get_all_results(group)
        members = engine.get_members(group)
        rankings = engine.get_rankings(group)
        return jsonify(ok=True, game_status=game.status.value if game else None,
                       summary=summary, pending_bets=pending, all_results=all_results,
                       members=members, rankings=rankings)
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 成员管理 ==========

@app.route("/api/member/add", methods=["POST"])
def add_member():
    group = request.json.get("group")
    name = request.json.get("name", "").strip()
    if not name:
        return jsonify(ok=False, msg="成员名不能为空")
    try:
        engine.add_member(group, name)
        return jsonify(ok=True, msg=f"已添加成员: {name}")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/member/remove", methods=["POST"])
def remove_member():
    group = request.json.get("group")
    name = request.json.get("name", "").strip()
    try:
        engine.remove_member(group, name)
        return jsonify(ok=True, msg=f"已移除成员: {name}")
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


# ========== 报表 ==========

@app.route("/api/report/export", methods=["POST"])
def export_report():
    group = request.json.get("group")
    try:
        game = engine.get_current_game(group)
        if not game or game.status.value != "ended":
            return jsonify(ok=False, msg="请先结束本局再导出")
        summary = engine.get_summary(group)
        results = engine.get_all_results(group)
        filepath = export_game_csv(group, game.id, summary, results)
        return jsonify(ok=True, msg="报表已生成", filepath=filepath)
    except EngineError as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/api/report/download")
def download_report():
    filepath = request.args.get("filepath")
    if filepath and os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify(ok=False, msg="文件不存在")


if __name__ == "__main__":
    print("🎲 微信下注机器人 Web 版已启动！")
    print("👉 请用浏览器打开: http://127.0.0.1:5000")
    print()
    app.run(host="0.0.0.0", port=5000, debug=True)

