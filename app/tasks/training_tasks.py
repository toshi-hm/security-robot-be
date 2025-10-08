"""Celery tasks for reinforcement learning training."""

import logging
from typing import Dict, Any

from app.tasks.celery_app import celery_app
from app.utils.datetime import utcnow

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='training.run_ppo_training')
def run_ppo_training_task(self, session_id: int, config: Dict[str, Any]) -> Dict[str, Any]:
  """
  Run PPO training as a Celery background task.
  
  Args:
    self: Celery task instance (bound)
    session_id: Training session ID
    config: Training configuration dictionary
  
  Returns:
    Training result dictionary
  """
  try:
    logger.info(f"Starting PPO training task for session {session_id}")
    
    # Update task state
    self.update_state(
      state='STARTED',
      meta={'session_id': session_id, 'status': 'initializing'}
    )
    
    # Import here to avoid circular dependencies
    from app.core.training.ppo_service import ppo_service
    from app.core.websocket.manager import websocket_manager
    from rl.callbacks.websocket_callback import WebSocketTrainingCallback
    from app.db.session import SessionLocal
    
    # Create database session
    db = SessionLocal()
    
    try:
      # Update training job status in database
      from app.models.training import TrainingJob, TrainingJobStatus
      job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
      if job:
        job.status = TrainingJobStatus.running
        job.started_at = utcnow()
        db.commit()
      
      # Create WebSocket callback for progress updates
      ws_callback = WebSocketTrainingCallback(
        session_id=session_id,
        websocket_manager=websocket_manager,
        update_interval=config.get('progress_update_interval', 100),
        verbose=1
      )
      
      # Run training (this is a blocking call)
      import asyncio
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      
      result = loop.run_until_complete(
        ppo_service.start_training(
          config=config,
          callbacks=[ws_callback]
        )
      )
      
      loop.close()
      
      # Update job status in database
      if job:
        if result.get('status') == 'completed':
          job.status = TrainingJobStatus.completed
          job.completed_at = utcnow()
          job.current_timestep = result.get('total_timesteps', 0)
          job.model_path = result.get('model_path')
        else:
          job.status = TrainingJobStatus.failed
          job.completed_at = utcnow()
        db.commit()
      
      logger.info(f"PPO training task completed for session {session_id}")
      return result
      
    finally:
      db.close()
      
  except Exception as e:
    logger.error(f"PPO training task failed: {e}", exc_info=True)
    
    # Update job status to failed
    try:
      from app.db.session import SessionLocal
      from app.models.training import TrainingJob, TrainingJobStatus
      
      db = SessionLocal()
      job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
      if job:
        job.status = TrainingJobStatus.failed
        job.completed_at = utcnow()
        db.commit()
      db.close()
    except Exception as db_error:
      logger.error(f"Failed to update job status: {db_error}")
    
    # Send error notification via WebSocket
    try:
      from app.core.websocket.manager import websocket_manager
      import asyncio
      
      error_message = {
        "type": "training_error",
        "session_id": session_id,
        "error_message": str(e),
        "error_type": type(e).__name__
      }
      
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      loop.run_until_complete(
        websocket_manager.broadcast_to_session(session_id, error_message)
      )
      loop.close()
    except Exception as ws_error:
      logger.error(f"Failed to send error via WebSocket: {ws_error}")
    
    return {
      'status': 'failed',
      'session_id': session_id,
      'error': str(e)
    }


@celery_app.task(bind=True, name='training.run_a3c_training')
def run_a3c_training_task(self, session_id: int, config: Dict[str, Any]) -> Dict[str, Any]:
  """
  Run A3C training as a Celery background task.
  
  Args:
    self: Celery task instance (bound)
    session_id: Training session ID
    config: Training configuration dictionary
  
  Returns:
    Training result dictionary
  """
  try:
    logger.info(f"Starting A3C training task for session {session_id}")
    
    self.update_state(
      state='STARTED',
      meta={'session_id': session_id, 'status': 'initializing'}
    )
    
    # A3C implementation would go here
    # For now, return a placeholder
    logger.warning("A3C training not yet fully implemented")
    
    return {
      'status': 'failed',
      'session_id': session_id,
      'error': 'A3C training not yet implemented'
    }
    
  except Exception as e:
    logger.error(f"A3C training task failed: {e}", exc_info=True)
    return {
      'status': 'failed',
      'session_id': session_id,
      'error': str(e)
    }


@celery_app.task(name='training.stop_training')
def stop_training_task(session_id: int) -> Dict[str, Any]:
  """
  Stop a running training task.
  
  Args:
    session_id: Training session ID
  
  Returns:
    Stop result dictionary
  """
  try:
    logger.info(f"Stopping training task for session {session_id}")
    
    # Update database status
    from app.db.session import SessionLocal
    from app.models.training import TrainingJob, TrainingJobStatus
    
    db = SessionLocal()
    try:
      job = db.query(TrainingJob).filter(TrainingJob.id == session_id).first()
      if job:
        job.status = TrainingJobStatus.paused
        db.commit()
        
        # Note: Actual training interruption needs to be implemented
        # via a custom callback that checks a stop flag
        logger.warning("Training stop requested - full implementation needed")
        
        return {
          'status': 'stopped',
          'session_id': session_id,
          'message': 'Training stop requested'
        }
      else:
        return {
          'status': 'error',
          'session_id': session_id,
          'error': 'Training session not found'
        }
    finally:
      db.close()
      
  except Exception as e:
    logger.error(f"Failed to stop training: {e}", exc_info=True)
    return {
      'status': 'error',
      'session_id': session_id,
      'error': str(e)
    }


# Legacy function for backward compatibility
@celery_app.task
def run_training_job(config: dict) -> dict:
  """Legacy training job - use run_ppo_training_task or run_a3c_training_task instead."""
  logger.warning("run_training_job is deprecated")
  return {'status': 'queued', 'config': config}
