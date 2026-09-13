from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRID_SIZE = 7
SYMBOLS = ["CHEF", "BURGER", "FRIES", "COLA", "DONUT", "CUCUMBER"]

# 依據 $0.20 賭注轉換而來的賠率倍數表
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

def get_multiplier(symbol, count):
    if symbol not in PAYOUT_TABLE or count < 5:
        return 0
    # 找出符合數量的最高級距
    tiers = sorted(PAYOUT_TABLE[symbol].keys(), reverse=True)
    for t in tiers:
        if count >= t:
            return PAYOUT_TABLE[symbol][t]
    return 0

def generate_grid():
    return [[random.choice(SYMBOLS) for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

def find_clusters(grid):
    visited = set()
    clusters = []
    
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if (r, c) not in visited and grid[r][c] != "EMPTY":
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
                    clusters.append({
                        "symbol": target_symbol,
                        "positions": current_cluster,
                        "count": len(current_cluster)
                    })
    return clusters

def apply_avalanche(grid):
    for c in range(GRID_SIZE):
        column = [grid[r][c] for r in range(GRID_SIZE) if grid[r][c] != "EMPTY"]
        missing = GRID_SIZE - len(column)
        new_column = [random.choice(SYMBOLS) for _ in range(missing)] + column
        for r in range(GRID_SIZE):
            grid[r][c] = new_column[r]
    return grid

@app.post("/api/spin")
async def spin(request: SpinRequest):
    grid = generate_grid()
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
            multiplier = get_multiplier(cluster["symbol"], cluster["count"])
            step_win += request.bet_amount * multiplier
            removed.extend(cluster["positions"])
            
        total_win += step_win
        
        spin_history.append({
            "grid": [row[:] for row in grid],
            "step_win": step_win
        })
        
        for r, c in removed:
            grid[r][c] = "EMPTY"
            
        grid = apply_avalanche(grid)

    return {
        "bet": request.bet_amount,
        "total_win": round(total_win, 2),
        "history": spin_history
    }
    
