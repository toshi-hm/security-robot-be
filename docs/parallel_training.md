# Parallel Training & GPU Optimization

## Overview
This system supports parallel training using `SubprocVecEnv` and GPU acceleration. This allows for significantly faster training (higher FPS) by utilizing multiple CPU cores for environment simulation and CUDA for policy optimization.

## Configuration
To enable parallel training, set `num_envs > 1` in the training configuration.

### Auto-Tuning Hyperparameters
When `num_envs > 1` or `policy_type="CnnPolicy"`, the system automatically adjusts hyperparameters for efficiency unless explicitly overridden:

- **Batch Size**: Defaults to `2048` (vs `64` for single env)
- **N Steps**: Defaults to `4096` (vs `2048` for single env)

These values are logged during training startup for transparency.

## Limitations

### Playback Recording
> [!WARNING]
> **Playback recording is disabled for parallel training (`num_envs > 1`).**

#### Technical Background
When using `SubprocVecEnv`, each environment runs in a separate subprocess. Python's `multiprocessing` module uses `pickle` to serialize objects passed to subprocesses. The `db_session_factory` (a callable that creates SQLAlchemy database sessions) cannot be pickled because:

1. Database connections contain OS-level file descriptors
2. SQLAlchemy session factories may reference non-picklable objects (connection pools, engine instances)
3. Even if pickling succeeded, database connections are not valid across process boundaries

#### Current Implementation
```python
# ppo_service.py
if num_envs > 1 and playback_enabled:
    logger.warning("Disabling playback recording for parallel training")
    playback_enabled = False
    db_session_factory = None  # Ensure closure captures None (picklable)
```

#### Future Improvements
Potential solutions for enabling playback in parallel environments:

1. **Redis Queue**: Send playback data to a Redis queue from subprocesses, with a main-process consumer writing to the database
2. **File-based Recording**: Write playback data to temporary files from each subprocess, then consolidate in main process
3. **Shared Memory**: Use `multiprocessing.Manager` to share a picklable data structure
4. **Process-local DB Sessions**: Create database sessions inside each subprocess (requires connection string, not session factory)

### Docker Security
- The containers use `seccomp:unconfined` and `shm_size: 8gb` to support PyTorch shared memory usage without requiring full `privileged` mode.
- This is more secure than `privileged: true` while still allowing `SubprocVecEnv` to function correctly.

## Debugging History

### Deleted Debug Scripts
The following debug scripts were used during development and have been removed after issues were resolved:

| Script | Purpose | Outcome |
|--------|---------|---------|
| `scripts/check_pickle.py` | Diagnose pickling errors with `SubprocVecEnv` | Identified `db_session_factory` as the cause; resolved by setting to `None` for parallel runs |

These scripts can be recreated from git history if needed for future debugging.
