
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os

INPUT_FILE = "multi_agent_trajectories_v2.json"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = f"{OUTPUT_DIR}/multi_agent_trajectories.png"

# Grid settings
GRID_SIZE = 20

def plot_trajectories():
    if not os.path.exists(INPUT_FILE):
        print(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r') as f:
        all_data = json.load(f)

    # Sort sessions by robot count
    sessions = []
    for sid, data in all_data.items():
        data['session_id'] = sid
        sessions.append(data)
    sessions.sort(key=lambda x: x['robots_count'])
    
    # We want 3 rows (2, 3, 4 robots) x 5 cols (Ep 1, 2, 25, 49, 50)
    fig, axes = plt.subplots(3, 5, figsize=(15, 10))
    # fig.tight_layout(pad=3.0) 
    # Actually tight layout might crowd titles, but we have no titles?
    # User said "No Title" (presumably Main title?). Subplot titles? "Ep X"?
    # The user example shows "Robots: 2", "Ep: 1" etc?
    # User said "Title is not needed". I'll skip main title. 
    # I should probably label rows and columns? 
    # "Robot台数別の軌跡変化" caption suggests rows/cols are self-explanatory or labeled.
    # Usually: Row label = Robot Count, Col Label = Episode.
    # I will add row/col labels to margins.
    
    episodes_order = [1, 2, 25, 49, 50]
    
    # Colors for different robots? No, "color intensity corresponds to time".
    # Usually different robots have different hues? Or just one color for all robots?
    # "線の色の濃さは時間経過に対応している" -> "Line color intensity corresponds to time"
    # If multiple robots, distinguishing them might be good, OR just showing coverage density.
    # If all same color, it shows overall coverage.
    # User didn't specify distinct robot colors.
    # Let's use different hues for Robot 1, 2, 3, 4 to distinguish them, 
    # AND vary intensity (alpha) or value (light->dark) with time?
    # Or just use ONE color (e.g. blue) for all robots, but alpha indicates time?
    # The previous single agent used time-gradient.
    # For multi-agent, if they cross paths, single color helps see "system" coverage.
    # But seeing individual paths helps see "cooperation".
    # I'll use distinct base colors for each robot ID (0..3) and fade them over time.
    # Robot Colors: Blue, Orange, Green, Red (Tab10)
    
    robot_colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    
    for row_idx, session_data in enumerate(sessions):
        robots_count = session_data['robots_count']
        
        for col_idx, ep in enumerate(episodes_order):
            ax = axes[row_idx, col_idx]
            ep_str = str(ep)
            
            if ep_str not in session_data['episodes']:
                ax.axis('off')
                continue
            
            ep_data = session_data['episodes'][ep_str]
            trajectories = ep_data['trajectories'] # dict r_id -> list of [x,y]
            obstacles = ep_data['obstacles']
            
            # Setup Grid
            ax.set_xlim(0, GRID_SIZE)
            ax.set_ylim(0, GRID_SIZE)
            ax.set_aspect('equal')
            ax.invert_yaxis() # 0,0 top left usually for grids
            # Axis ticks? Often removed for cleanliness in grid plots
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Draw Grid Lines
            # ax.grid(True, linestyle=':', color='lightgray') # Optional
            
            # Draw Obstacles
            for obs in obstacles:
                # Obstacle is full cell. rectangle at x, y
                rect = plt.Rectangle((obs[0], obs[1]), 1, 1, color='black')
                ax.add_patch(rect)
            
            # Draw Trajectories
            # Time gradient: older points lighter? or newer points darker?
            # User: "Color intensity corresponds to time" -> usually Dark = Late, Light = Early? Or Fade out?
            # Standard: Start = Light, End = Dark.
            
            # Collect all segments to sort by time
            all_segments = []
            all_colors = []
            
            # Start/End markers to plot later
            markers = []
            
            max_steps = 0
            for r_key, path in trajectories.items():
                if len(path) > max_steps:
                    max_steps = len(path)

            if max_steps == 0:
                max_steps = 1 # avoid div by zero

            for r_key, path in trajectories.items():
                r_id = int(r_key)
                if not path:
                    continue
                
                path = np.array(path)
                x = path[:, 0] + 0.5
                y = path[:, 1] + 0.5
                
                # Base color
                base_c = mcolors.to_rgb(robot_colors[r_id % len(robot_colors)])
                
                # Create segments
                points = np.array([x, y]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                
                # Add to list with time index
                for i, seg in enumerate(segments):
                    # Check distance to avoid drawing large jumps (e.g. reset to start)
                    p1 = seg[0]
                    p2 = seg[1]
                    dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                    if dist > 1.8:
                        continue

                    # Time progress: 0.0 to 1.0
                    prog = i / max(1, len(segments) - 1)
                    # Alpha: 0.05 to 1.0 (more pronounced)
                    alpha = 0.05 + (0.95 * prog)
                    
                    c_rgba = (*base_c, alpha)
                    
                    # Store as (step, segment, color)
                    # We use 'i' as step.
                    all_segments.append((i, seg, c_rgba))
                
                # Markers
                markers.append({'x': x[0], 'y': y[0], 'type': 'start', 'color': base_c})
                markers.append({'x': x[-1], 'y': y[-1], 'type': 'end', 'color': base_c})

            # Sort all segments by time step
            all_segments.sort(key=lambda x: x[0])
            
            # Unzip
            sorted_segs = [x[1] for x in all_segments]
            sorted_cols = [x[2] for x in all_segments]
            
            if sorted_segs:
                from matplotlib.collections import LineCollection
                lc = LineCollection(sorted_segs, colors=sorted_cols, linewidths=1.5)
                ax.add_collection(lc)
            
            # Plot Markers (Start/End) ON TOP
            for m in markers:
                if m['type'] == 'start':
                    # Start: lighter? No, usually start is solid color just to see IT IS start.
                    # But maybe use alpha=0.5 if it's super early?
                    # Let's keep markers opaque for visibility.
                    # User requested larger start markers.
                    ax.plot(m['x'], m['y'], marker='o', color=m['color'], markersize=8, markeredgewidth=0, zorder=10)
                else:
                    ax.plot(m['x'], m['y'], marker='s', color=m['color'], markersize=4, markeredgewidth=0, zorder=10)

            # Add border
            # Rectangle 0,0 to 20,20
            rect_border = plt.Rectangle((0, 0), GRID_SIZE, GRID_SIZE, fill=False, edgecolor='black', linewidth=1)
            ax.add_patch(rect_border)

            # Row Labels (Left of 1st col)
            if col_idx == 0:
                ax.set_ylabel(f"{robots_count} Robots", fontsize=12, rotation=90, labelpad=5)
            
            # Col Labels (Top of 1st row)
            if row_idx == 0:
                ax.set_title(f"Episode {ep}", fontsize=12)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=300, bbox_inches='tight')
    print(f"Saved plot to {OUTPUT_FILE}")

if __name__ == "__main__":
    plot_trajectories()
