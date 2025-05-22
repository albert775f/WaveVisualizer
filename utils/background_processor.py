import os
import time
import logging
import threading
import uuid
from datetime import datetime

from models import db, BackgroundTask, OutputVideo
from utils.audio_processor import process_audio_visualization

logger = logging.getLogger(__name__)

# Dictionary to keep track of running tasks
running_tasks = {}


def process_video_task(task_id, audio_path, image_path, output_path, preset, app):
    """
    Process a video generation task in the background
    
    Parameters:
    - task_id: UUID of the task for tracking
    - audio_path: Path to audio file
    - image_path: Path to image file
    - output_path: Path for output video
    - preset: Visualization preset settings
    - app: Flask app context
    """
    with app.app_context():
        try:
            # Get task from database
            task = BackgroundTask.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return
            
            # Update task status
            task.status = "processing"
            task.progress = 5
            task.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Estimate processing time based on audio duration
            from librosa import get_duration
            import librosa
            y, sr = librosa.load(audio_path, sr=None)
            duration = get_duration(y=y, sr=sr)
            estimated_seconds = max(int(duration * 1.5), 10)  # Rough estimate: 1.5x audio length
            
            task.estimated_time = estimated_seconds
            db.session.commit()
            
            # Set up progress callback
            def update_progress(progress_percent):
                nonlocal task
                task.progress = progress_percent
                task.updated_at = datetime.utcnow()
                task.estimated_time = max(estimated_seconds - int((progress_percent / 100) * estimated_seconds), 0)
                db.session.commit()
            
            # Process the video with preset parameters
            process_audio_visualization(
                audio_path=audio_path,
                image_path=image_path,
                output_path=output_path,
                color=preset.color,
                fps=30,
                bar_count=preset.bar_count,
                bar_width_ratio=preset.bar_width_ratio,
                bar_height_scale=preset.bar_height_scale,
                glow_effect=preset.glow_effect,
                glow_intensity=preset.glow_intensity,
                responsiveness=preset.responsiveness,
                smoothing=preset.smoothing,
                vertical_position=preset.vertical_position,
                horizontal_margin=preset.horizontal_margin,
                progress_callback=update_progress
            )
            
            # Create the output video record
            output_filename = os.path.basename(output_path)
            display_name = f"{task.audio_file.display_name}_{task.image_file.display_name}.mp4"
            
            # Create output video entry with fresh database session
            output_video = OutputVideo()
            output_video.filename = output_filename
            output_video.display_name = display_name
            output_video.audio_file_id = task.audio_file_id
            output_video.image_file_id = task.image_file_id
            output_video.preset_id = task.preset_id
            db.session.add(output_video)
            
            # Update task as completed
            task.status = "completed"
            task.progress = 100
            task.estimated_time = 0
            task.output_filename = output_filename
            task.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Background task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error in background task {task_id}: {str(e)}")
            with app.app_context():
                task = BackgroundTask.query.filter_by(task_id=task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    task.updated_at = datetime.utcnow()
                    db.session.commit()
        
        finally:
            # Clean up task from running dictionary
            if task_id in running_tasks:
                del running_tasks[task_id]


def start_video_generation_task(audio_file, image_file, preset, app):
    """Start a new background task for video generation"""
    task_id = str(uuid.uuid4())
    
    # Create task record
    task = BackgroundTask()
    task.task_id = task_id
    task.status = "pending"
    task.progress = 0
    task.audio_file_id = audio_file.id
    task.image_file_id = image_file.id
    task.preset_id = preset.id
    db.session.add(task)
    db.session.commit()
    
    # Prepare file paths
    audio_path = os.path.join(os.getcwd(), 'uploads', 'audio', audio_file.filename)
    image_path = os.path.join(os.getcwd(), 'uploads', 'images', image_file.filename)
    output_filename = f"{uuid.uuid4()}.mp4"
    output_path = os.path.join(os.getcwd(), 'output', output_filename)
    
    # Start processing thread
    thread = threading.Thread(
        target=process_video_task,
        args=(task_id, audio_path, image_path, output_path, preset, app)
    )
    thread.daemon = True  # Allow the thread to be terminated when the main program exits
    thread.start()
    
    # Store thread in running tasks
    running_tasks[task_id] = thread
    
    return task


def get_task_status(task_id):
    """Get the current status of a task"""
    task = BackgroundTask.query.filter_by(task_id=task_id).first()
    if not task:
        return None
    return task.to_dict()


def get_all_tasks():
    """Get all tasks, sorted by newest first"""
    return BackgroundTask.query.order_by(BackgroundTask.created_at.desc()).all()


def cleanup_old_tasks():
    """Clean up completed/failed tasks older than 7 days"""
    from datetime import timedelta
    
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    old_tasks = BackgroundTask.query.filter(
        BackgroundTask.updated_at < cutoff_date,
        BackgroundTask.status.in_(['completed', 'failed'])
    ).all()
    
    for task in old_tasks:
        db.session.delete(task)
    
    db.session.commit()
    return len(old_tasks)