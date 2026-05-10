"""全局配置"""
import os

# 报表输出目录（CSV 文件存这里）
REPORT_DIR = os.path.join(os.path.dirname(__file__), "data", "reports")

# ============ 赔率配置 ============
# 约定：所有赔率均为「净赚倍数」，profit = amount × multiplier
#       退本金（不吃不赔）= 0；输 = -amount

# 单点下注赔率（无保无仔）
ODDS_SINGLE = {
    1: 4.0,   # 点1净赚4倍
    2: 5.0,
    3: 5.0,
    4: 5.0,
    5: 5.0,
    6: 5.0,
}

# 保规则赔率 (/) —— 最多保两个子；保子统一退本金
# 主号 = 1
ODDS_BAO_1_SUB1 = 3.2     # 1 保 1 个子，主中
ODDS_BAO_1_SUB2 = 2.4     # 1 保 2 个子，主中
# 主号 ≠ 1
ODDS_BAO_X_SUB1_HAS1 = 3.8    # 主非1，保 1 个子且=1，主中
ODDS_BAO_X_SUB1_NO1  = 4.0    # 主非1，保 1 个子且≠1，主中
ODDS_BAO_X_SUB2_HAS1 = 2.8    # 主非1，保 2 个子且含 1，主中
ODDS_BAO_X_SUB2_NO1  = 3.0    # 主非1，保 2 个子且均≠1，主中

# 仔规则赔率 (//) —— 最多仔一个子；仔子统一净赚 1 倍
ODDS_ZAI_1           = 2.4    # 主=1，主中
ODDS_ZAI_X_SUB_1     = 2.6    # 主非1，仔的子=1，主中
ODDS_ZAI_X_SUB_NO1   = 3.0    # 主非1，仔的子≠1，主中
ODDS_ZAI_SUB         = 1.0    # 仔子中（净赚 1 倍）

# 三码下注赔率
ODDS_SANMA_NO1            = 1.0    # 不含 1，中
ODDS_SANMA_HAS1_HIT_1     = 0.7    # 含 1，开 1
ODDS_SANMA_HAS1_HIT_OTHER = 1.0    # 含 1，开非 1 的子

# ============ 开奖范围 ============
DICE_MIN = 1
DICE_MAX = 6

