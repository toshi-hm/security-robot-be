
import json
import sys
import os

def check_collisions(filepath):
    print(f"Checking {filepath}...")
    
    with open(filepath, 'r') as f:
        # Read first line to get obstacles grid
        first_line = f.readline()
        if not first_line:
            print("Empty file")
            return
            
        data = json.loads(first_line)
        obstacles_grid = data["obstacles"]
        width = len(obstacles_grid[0])
        height = len(obstacles_grid)
        
        static_collision_count = 0
        robot_collision_count = 0
        total_steps = 0
        
        # Reset file pointer
        f.seek(0)
        
        for line in f:
            try:
                data = json.loads(line)
                total_steps += 1
                
                # Update obstacles grid for each step (random maps change per episode)
                obstacles_grid = data["obstacles"]
                
                positions = data["robot_positions"] # List of [x, y]
                
                # Check Static Collisions
                for i, pos in enumerate(positions):
                    x, y = int(pos[0]), int(pos[1])
                    if obstacles_grid[y][x]: # True means obstacle
                        # print(f"Static Collision: Ep {data['episode']} Step {data['step']} Robot {i} at ({x},{y})")
                        static_collision_count += 1
                
                # Check Robot-Robot Collisions
                seen_pos = {}
                for i, pos in enumerate(positions):
                    t_pos = tuple(pos)
                    if t_pos in seen_pos:
                        # print(f"Robot Collision: Ep {data['episode']} Step {data['step']} Robot {i} and {seen_pos[t_pos]} at {t_pos}")
                        robot_collision_count += 1
                    seen_pos[t_pos] = i
                    
            except json.JSONDecodeError:
                continue
                
        print(f"Total Steps: {total_steps}")
        print(f"Static (Wall) Collisions: {static_collision_count}")
        print(f"Dynamic (Robot) Collisions: {robot_collision_count}")
        print("-" * 30)

if __name__ == "__main__":
    check_collisions("trajectory_multi_zigzag.jsonl")
    check_collisions("trajectory_multi_spiral.jsonl")
