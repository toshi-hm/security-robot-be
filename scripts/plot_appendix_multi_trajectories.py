
import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import os
import math

INPUT_FILE = "multi_agent_trajectories_all.json"
OUTPUT_DIR = "report/result/thesis_experiment/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Grid settings
GRID_SIZE = 20

def plot_appendix_trajectories():
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
    
    robot_colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    
    for session_data in sessions:
        robots_count = session_data['robots_count']
        print(f"Plotting for {robots_count} robots...")
        
        # 5 rows x 10 cols = 50 episodes
        fig, axes = plt.subplots(5, 10, figsize=(20, 10))
        # Reduce spacing
        plt.subplots_adjust(wspace=0.1, hspace=0.2)
        
        episodes_order = sorted([int(k) for k in session_data['episodes'].keys()])
        
        for idx, ep in enumerate(episodes_order):
            if idx >= 50: break # limit 50
            
            row = idx // 10
            col = idx % 10
            ax = axes[row, col]
            
            ep_str = str(ep)
            ep_data = session_data['episodes'][ep_str]
            trajectories = ep_data['trajectories']
            obstacles = ep_data['obstacles']
            
            # Setup Grid
            ax.set_xlim(0, GRID_SIZE)
            ax.set_ylim(0, GRID_SIZE)
            ax.set_aspect('equal')
            ax.invert_yaxis()
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Subplot Title: "Episode N"
            ax.set_title(f"Episode {ep}", fontsize=8)
            
            # Draw Obstacles
            for obs in obstacles:
                rect = plt.Rectangle((obs[0], obs[1]), 1, 1, color='black')
                ax.add_patch(rect)
                
            # Collect all segments to sort by time
            all_segments = []
            markers = []
            
            max_steps = 0
            for r_key, path in trajectories.items():
                if len(path) > max_steps:
                    max_steps = len(path)
            if max_steps == 0: max_steps = 1

            for r_key, path in trajectories.items():
                r_id = int(r_key)
                if not path:
                    continue
                
                path = np.array(path)
                x = path[:, 0] + 0.5
                y = path[:, 1] + 0.5
                
                base_c = mcolors.to_rgb(robot_colors[r_id % len(robot_colors)])
                
                points = np.array([x, y]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                
                for i, seg in enumerate(segments):
                    # Filter jumps
                    p1 = seg[0]
                    p2 = seg[1]
                    dist = np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                    if dist > 1.8:
                        continue

                    prog = i / max(1, len(segments) - 1)
                    alpha = 0.05 + (0.95 * prog)
                    c_rgba = (*base_c, alpha)
                    all_segments.append((i, seg, c_rgba))
                
                markers.append({'x': x[0], 'y': y[0], 'type': 'start', 'color': base_c})
                markers.append({'x': x[-1], 'y': y[-1], 'type': 'end', 'color': base_c})

            # Sort and Plot
            all_segments.sort(key=lambda x: x[0])
            sorted_segs = [x[1] for x in all_segments]
            sorted_cols = [x[2] for x in all_segments]
            
            if sorted_segs:
                from matplotlib.collections import LineCollection
                lc = LineCollection(sorted_segs, colors=sorted_cols, linewidths=1.0) # slightly thinner line for dense plot? User said "match style", verify linewidth? v2 use 1.5. Keep 1.5 or reduce for small subplots?
                # User said "match style", but subplots are small.
                # Let's use 1.5 but might look thick. I'll stick to 1.5 requested style or maybe 1.2.
                # v2 was 1.5. I'll try 1.2 to be safe for small plots.
                lc.set_linewidth(1.2)
                ax.add_collection(lc)
            
            # Plot Markers
            for m in markers:
                if m['type'] == 'start':
                    ax.plot(m['x'], m['y'], marker='o', color=m['color'], markersize=4, markeredgewidth=0, zorder=10) # Smaller marker for small subplot
                else:
                    ax.plot(m['x'], m['y'], marker='s', color=m['color'], markersize=2, markeredgewidth=0, zorder=10)

            # Add border
            rect_border = plt.Rectangle((0, 0), GRID_SIZE, GRID_SIZE, fill=False, edgecolor='black', linewidth=0.5)
            ax.add_patch(rect_border)
        
        # Save Figure
        output_file = f"{OUTPUT_DIR}/appendix_trajectories_{robots_count}robots.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Saved {output_file}")
        plt.close(fig)

if __name__ == "__main__":
    plot_appendix_trajectories()
