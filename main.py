from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

GRID_SIZE = 7
SYMBOLS = ["CHEF", "BURGER", "FRIES", "COLA", "DONUT", "CUCUMBER"]
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

def generate_grid(force_hot=False):
    grid = [[random.choice(SYMBOLS) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    # 若購買特色，強制放置 3 個 HOT 符號
    if force_hot:
        positions = random.sample([(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE)], 3)
        for r, c in positions: grid[r][c] = "HOT"
    else:
        # 基礎機率：每局隨機給予 HOT 符號的機會
        for _ in range(3):
            if random.random() < 0.08: grid[random.randint(0, 6)][random.randint(0, 6)] = "HOT"
    return grid

def find_clusters(grid):
    visited = set()
    clusters = []
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            # HOT 符號不參與相連消除
            if (r, c) not in visited and grid[r][c] not in ["EMPTY", "HOT"]:
                target_symbol = grid[r][c]
                current_cluster = []
                queue = [(r, c)]
                while queue:
                    curr_r, curr_c = queue.pop(0)
                    if (curr_r, curr_c) in visited: continue
                    visited.add((curr_r, curr_c))
                    current_cluster.append((curr_r, curr_c))
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = curr_r + dr, curr_c + dc
                        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                            if (nr, nc) not in visited and grid[nr][nc] == target_symbol:
                                queue.append((nr, nc))
                if len(current_cluster) >= 5:
                    clusters.append({"symbol": target_symbol, "positions": current_cluster, "count": len(current_cluster)})
    return clusters

def apply_avalanche(grid):
    for c in range(GRID_SIZE):
        column = [grid[r][c] for r in range(GRID_SIZE) if grid[r][c] != "EMPTY"]
        missing = GRID_SIZE - len(column)
        new_column = [random.choice(SYMBOLS) for _ in range(missing)] + column
        for r in range(GRID_SIZE): grid[r][c] = new_column[r]
    return grid

def run_single_spin(bet_amount, force_hot=False):
    grid = generate_grid(force_hot)
    spin_history = []
    total_win = 0
    cascading = True
    while cascading:
        clusters = find_clusters(grid)
        if not clusters:
            spin_history.append({"grid": [row[:] for row in grid], "step_win": 0})
            break
        step_win = 0
        removed = []
        for cluster in clusters:
            step_win += bet_amount * get_multiplier(cluster["symbol"], cluster["count"])
            removed.extend(cluster["positions"])
        total_win += step_win
        spin_history.append({"grid": [row[:] for row in grid], "step_win": step_win})
        for r, c in removed: grid[r][c] = "EMPTY"
        grid = apply_avalanche(grid)
        
    hot_count = sum(row.count("HOT") for row in grid)
    return spin_history, total_win, hot_count

@app.post("/api/spin")
async def spin(request: SpinRequest):
    # 購買免費遊戲需支付 10 倍賭注
    total_cost = request.bet_amount * 10 if request.is_feature_buy else request.bet_amount
    
    # 1. 執行初始盤面
    history, total_win, hot_count = run_single_spin(request.bet_amount, force_hot=request.is_feature_buy)
    
    # 2. 如果盤面有 3 個(含)以上 HOT，自動追加 10 次免費遊戲
    if hot_count >= 3:
        history.append({"is_free_spin_trigger": True, "grid": history[-1]["grid"], "step_win": 0})
        for _ in range(10):
            fs_history, fs_win, _ = run_single_spin(request.bet_amount, force_hot=False)
            history.extend(fs_history)
            total_win += fs_win
            
    return {
        "cost": total_cost,
        "total_win": round(total_win, 2),
        "history": history
    }
