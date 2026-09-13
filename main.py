from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 部署時請改為你的 Cloudflare Pages 網址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GRID_SIZE = 7
# 依據賠付表簡化的符號陣列 (不含特殊符號以簡化生成機率)
BASE_SYMBOLS = ["CHEF", "BURGER", "FRIES", "SODA", "DONUT", "PICKLE"]
SPECIAL_SYMBOLS = ["WILD", "SCATTER", "EXP_WILD"]

class SpinRequest(BaseModel):
    bet_amount: float

def generate_random_symbol():
    # 這裡未來需替換為基於 92.16% RTP 的加權隨機 (Weighted Random)
    return random.choice(BASE_SYMBOLS)

def create_initial_grid():
    return [[generate_random_symbol() for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]

def find_clusters(grid):
    """
    使用廣度優先搜尋 (BFS) 找出 5 個以上相連的群集
    """
    visited = set()
    clusters = []
    
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if (r, c) not in visited and grid[r][c] not in ["SCATTER", "EXP_WILD", "EMPTY"]:
                target_symbol = grid[r][c]
                if target_symbol == "WILD": 
                    continue # 讓百搭符號依附在一般符號的群集中
                
                current_cluster = []
                queue = [(r, c)]
                
                while queue:
                    curr_r, curr_c = queue.pop(0)
                    if (curr_r, curr_c) in visited: continue
                    
                    visited.add((curr_r, curr_c))
                    current_cluster.append((curr_r, curr_c))
                    
                    # 檢查上下左右
                    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                    for dr, dc in directions:
                        nr, nc = curr_r + dr, curr_c + dc
                        if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                            if (nr, nc) not in visited:
                                # 若相鄰符號相同，或是百搭符號，則加入佇列
                                if grid[nr][nc] == target_symbol or grid[nr][nc] == "WILD":
                                    queue.append((nr, nc))
                
                # 規則：5個或更多相同符號連接才算贏
                if len(current_cluster) >= 5:
                    clusters.append({
                        "symbol": target_symbol,
                        "positions": current_cluster,
                        "count": len(current_cluster)
                    })
    return clusters

def apply_avalanche(grid):
    """
    將空缺(EMPTY)上方的符號往下掉落，並在頂部生成新符號
    """
    for c in range(GRID_SIZE):
        # 抓出該直列所有非空缺的符號
        column_symbols = [grid[r][c] for r in range(GRID_SIZE) if grid[r][c] != "EMPTY"]
        missing_count = GRID_SIZE - len(column_symbols)
        
        # 頂部生成新的隨機符號補滿
        new_column = [generate_random_symbol() for _ in range(missing_count)] + column_symbols
        
        # 寫回原始網格
        for r in range(GRID_SIZE):
            grid[r][c] = new_column[r]
    return grid

@app.post("/api/spin")
async def spin(request: SpinRequest):
    grid = create_initial_grid()
    # 規則：底層網格初始倍率為 x2
    multipliers = [[2 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    
    spin_history = []
    total_win = 0
    cascading = True
    
    while cascading:
        # 1. 尋找贏分群集
        clusters = find_clusters(grid)
        
        if not clusters:
            cascading = False
            # 紀錄最終盤面
            spin_history.append({"grid": [row[:] for row in grid], "clusters": [], "step_win": 0})
            break
            
        step_win = 0
        removed_positions = []
        
        # 2. 計算贏分與標記消除
        for cluster in clusters:
            # 這裡需對應你圖片中的 paytable 計算贏分 (例如 25+個漢堡贏多少)
            # 簡化示範：基礎賠率 * 數量 * 該區塊倍率加總
            base_payout = cluster["count"] * 0.5 
            
            cluster_multiplier = sum([multipliers[r][c] for r, c in cluster["positions"]])
            win_amount = base_payout * cluster_multiplier * request.bet_amount
            step_win += win_amount
            
            removed_positions.extend(cluster["positions"])
            
        total_win += step_win
        
        # 紀錄消除前的狀態，供前端播放消除動畫
        spin_history.append({
            "grid": [row[:] for row in grid],
            "clusters": clusters,
            "step_win": step_win,
            "multipliers": [row[:] for row in multipliers]
        })
        
        # 3. 移除符號
        for r, c in removed_positions:
            grid[r][c] = "EMPTY"
            
        # 這裡需額外實作：判斷是否有爆炸萬能符號 (Exploding Wild)，並翻倍周圍的 multipliers 矩陣
            
        # 4. 執行雪崩掉落
        grid = apply_avalanche(grid)

    return {
        "bet": request.bet_amount,
        "total_win": total_win,
        "history": spin_history # 前端接收此陣列，依序用 setTimeout 播放消除與掉落動畫
    }
  
