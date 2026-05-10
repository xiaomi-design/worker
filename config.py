"""全局配置"""
import os

# 报表输出目录（CSV 文件存这里）
REPORT_DIR = os.path.join(os.path.dirname(__file__), "data", "reports")

# ============ 赔率配置 ============
# 单点下注赔率
ODDS_SINGLE = {
    1: 4.0,   # 点1赔率4倍
    2: 5.0,
    3: 5.0,
    4: 5.0,
    5: 5.0,
    6: 5.0,
}

# 保规则赔率 (/) —— 最多保两个子
ODDS_BAO_MAIN = 3.2      # 主选中赔率
# 保子：退本金（赔率 1.0）

# 载规则赔率 (//) —— 最多载一个子
ODDS_ZAI_MAIN = 2.4       # 主选中赔率
ODDS_ZAI_SUB = 2.0         # 载子中赔率

# 三码下注赔率
ODDS_SANMA_CONTAINS_1 = 1.7   # 包含1中奖
ODDS_SANMA_NO_1 = 2.0          # 不含1中奖

# 平波下注赔率（4个号码）
ODDS_PINGBO = 1.5              # 中奖赔率

# ============ 开奖范围 ============
DICE_MIN = 1
DICE_MAX = 6

