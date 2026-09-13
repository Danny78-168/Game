from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

GRID_SIZE = 7
# 加入 POTATO 作為會出現的符號
SYMBOLS = ["CHEF", "BURGER", "FRIES", "COLA", "DONUT", "CUCUMBER", "POTATO"]
PAYOUT_TABLE = {
    "CHEF": {25: 100.0, 20: 40.0, 15: 20.0, 12: 10.0, 10: 5.0, 9: 3.0, 8: 2.5, 7: 2.0, 6: 1.5, 5: 1.0},
    "BURGER": {25: 62.5, 20: 25.0, 15: 10.0, 12: 6.0, 10: 3.0, 9: 2.5, 8: 2.0, 7: 1.3, 6: 0.8, 5: 0.5},
    "FRIES": {25: 37.5, 20: 15.0, 15: 7.5, 12: 4.0, 10: 2.0, 9: 1.3, 8: 1.0, 7: 0.8, 6: 0.5, 5: 0.4},
    "COLA": {25: 25.0, 20: 10.0, 15: 5.0, 12: 3.0, 10: 1.0, 9: 0.8, 8: 0.6, 7: 0.5, 6: 0.4, 5: 0.3},
    "DONUT": {25: 20.0, 20: 7.5, 15: 4.0, 12: 2.0, 10: 0.9, 9: 0.7, 8: 0.5, 7: 0.4, 6: 0.3, 5: 0.2},
    "CUCUMBER": {25: 10.0, 20: 4.0, 15: 3.0, 12: 1.0, 10: 0.8, 9: 0.6, 8: 0.4, 7: 0.3, 6: 0.2, 5: 0.1}
}

class SpinRequest(BaseModel):
    bet_amount: float
    is_feature_buy: bool = False

def get_multiplier(symbol, count):
    if symbol not in PAYOUT_TABLE or count < 5: return 0
    for t in sorted(PAYOUT_TABLE[symbol].keys(), reverse=True):
        if count >= t: return PAYOUT_TABLE[symbol][t]
    return 0

def random_symbol():
    # 稍微降低特殊符號出現率
    return random.choices(SYMBOLS, weights=[15, 15, 15, 15, 15, 20, 5])[0]

def generate_grid(force_hot=False):
    grid = [[random_symbol() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    if force_hot:
        positions = random.sample([(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)], 3)
        for r, c in positions: grid[r][c] = "HOT"
    else:
        for _ in range(3):
            if random.random() < 0.05: grid[random.randint(0, 6)][random.randint(0, 6)] = "HOT"
    return grid

def find_clusters(grid):
    visited, clusters = set(), []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if (r, c) not in visited and grid[r][c] not in ["EMPTY", "HOT", "POTATO"]:
                target = grid[r][c]
                curr_cluster, queue = [], [(r, c)]
                while queue:
                    curr_r, curr_c = queue.pop(0)
                    if (curr_r, curr_c) in visited: continue
                    visited.add((curr_r, curr_c))
                    curr_cluster.append((curr_r, curr_c))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = curr_r + dr, curr_c + dc
                        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                            # 簡化：不將POTATO視為連線Wild，僅作爆炸用途
                            if (nr, nc) not in visited and grid[nr][nc] == target:
                                queue.append((nr, nc))
                if len(curr_cluster) >= 5:
                    clusters.append({"symbol": target, "positions": curr_cluster, "count": len(curr_cluster)})
    return clusters

def explode_potatoes(grid, multipliers):
    exploded = False
    removed = []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == "POTATO":
                exploded = True
                grid[r][c] = "EMPTY"
                # 3x3 範圍爆炸與倍率提升
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                            if grid[nr][nc] != "HOT": removed.append((nr, nc))
                            # 倍率翻倍邏輯 (最大 x128)
                            if multipliers[nr][nc] == 1: multipliers[nr][nc] = 2
                            else: multipliers[nr][nc] = min(128, multipliers[nr][nc] * 2)
    for rr, rc in removed: grid[rr][rc] = "EMPTY"
    return exploded

def apply_avalanche(grid):
    for c in range(GRID_SIZE):
        column = [grid[r][c] for r in range(GRID_SIZE) if grid[r][c] != "EMPTY"]
        missing = GRID_SIZE - len(column)
        new_column = [random_symbol() for _ in range(missing)] + column
        for r in range(GRID_SIZE): grid[r][c] = new_column[r]
    return grid

def run_single_spin(bet_amount, force_hot=False, current_multipliers=None):
    grid = generate_grid(force_hot)
    # 如果沒有傳入倍率矩陣（一般旋轉），則重置為 1；若有傳入（免遊），則繼續沿用
    multipliers = current_multipliers if current_multipliers else [[1]*GRID_SIZE for _ in range(GRID_SIZE)]
    spin_history = []
    total_win = 0
    cascading = True
    
    while cascading:
        clusters = find_clusters(grid)
        step_win = 0
        removed = []
        
        if clusters:
            for cluster in clusters:
                base_mult = get_multiplier(cluster["symbol"], cluster["count"])
                # 計算該群集涵蓋的倍率總和
                cluster_multiplier_sum = sum([multipliers[r][c] for r, c in cluster["positions"] if multipliers[r][c] > 1])
                final_mult = cluster_multiplier_sum if cluster_multiplier_sum > 0 else 1
                step_win += bet_amount * base_mult * final_mult
                removed.extend(cluster["positions"])
                
            for r, c in removed: grid[r][c] = "EMPTY"
            total_win += step_win
            spin_history.append({"grid": [row[:] for row in grid], "step_win": step_win, "multipliers": [row[:] for row in multipliers]})
            grid = apply_avalanche(grid)
            continue
            
        # 如果沒有群集消除，檢查是否有爆炸土豆
        if explode_potatoes(grid, multipliers):
            spin_history.append({"grid": [row[:] for row in grid], "step_win": 0, "multipliers": [row[:] for row in multipliers]})
            grid = apply_avalanche(grid)
            continue
            
        # 若無消除也無土豆，結束雪崩
        spin_history.append({"grid": [row[:] for row in grid], "step_win": 0, "multipliers": [row[:] for row in multipliers]})
        cascading = False
        
    hot_count = sum(row.count("HOT") for row in grid)
    return spin_history, total_win, hot_count, multipliers

@app.post("/api/spin")
async def spin(request: SpinRequest):
    total_cost = request.bet_amount * 10 if request.is_feature_buy else request.bet_amount
    history, total_win, hot_count, final_mults = run_single_spin(request.bet_amount, force_hot=request.is_feature_buy)
    
    # 觸發 10 次免費遊戲
    if hot_count >= 3:
        history.append({"is_free_spin_trigger": True, "grid": history[-1]["grid"], "step_win": 0, "multipliers": final_mults})
        # 免遊狀態下，將 final_mults 持續傳遞給下一次旋轉 (粘性倍率)
        current_fs_mults = final_mults
        for fs_index in range(1, 11):
            fs_history, fs_win, _, current_fs_mults = run_single_spin(request.bet_amount, force_hot=False, current_multipliers=current_fs_mults)
            
            # 在 history 中標記免遊狀態次數，供前端顯示
            for h in fs_history: h["free_spin_text"] = f"免費旋轉: {fs_index} / 10"
            history.extend(fs_history)
            total_win += fs_win
            
    return {"cost": total_cost, "total_win": round(total_win, 2), "history": history}
