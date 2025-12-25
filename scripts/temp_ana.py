import httpx
import asyncio

import sys

async def main():
    async with httpx.AsyncClient() as client:
        if len(sys.argv) > 1:
            ids_str = sys.argv[1]
            ids = [int(x) for x in ids_str.split(",")]
        else:
            ids = [59, 60, 61, 62]

        print(f"{'ID':<4} {'Rob':<4} {'Mode':<8} {'Rew':<10} {'Team':<10} {'Cov':<6}")
        print("-" * 50)
        
        for i in ids:
            try:
                # Status
                resp_st = await client.get(f"http://localhost:8000/api/v1/training/{i}/status")
                if resp_st.status_code != 200:
                    print(f"{i:<4} Error status {resp_st.status_code}")
                    continue
                st = resp_st.json()
                
                # Metrics
                resp_mt = await client.get(f"http://localhost:8000/api/v1/training/sessions/{i}/metrics?page_size=20")
                if resp_mt.status_code != 200:
                    print(f"{i:<4} Error metrics {resp_mt.status_code}")
                    continue
                mts = resp_mt.json().get("metrics", [])
                
                # Sort by timestep and take last 10
                mts.sort(key=lambda x: x['timestep'])
                last_mts = mts[-10:]
                
                if not last_mts:
                    print(f"{i:<4} No metrics")
                    continue
                
                rew = sum(m['reward'] for m in last_mts)/len(last_mts)
                cov = sum(m['coverage_ratio'] or 0 for m in last_mts)/len(last_mts)
                
                mode = st.get('reward_normalization_mode', 'mean')
                rob = st.get('num_robots', 3)
                
                # Fallback calculation
                add_metrics = last_mts[-1].get('additional_metrics') or {}
                team_rew = add_metrics.get('team_reward')
                
                if team_rew is None:
                    if mode == 'mean':
                        team_rew = rew * rob
                    else:
                        team_rew = rew
                
                print(f"{i:<4} {rob:<4} {mode:<6} {rew:<10.1f} {team_rew:<10.1f} {cov:<6.4f}")
            except Exception as e:
                print(f"{i:<4} Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
