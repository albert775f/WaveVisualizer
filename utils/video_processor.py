import os
import numpy as np
import subprocess
import tempfile
import logging
from PIL import Image

logger = logging.getLogger(__name__)

def create_video_from_frames(frames_dir, audio_path, output_path, fps=30, progress_callback=None):
    """
    Create video from frames using FFmpeg, ensuring H.264 compatibility
    
    Args:
        frames_dir: Directory containing frame images
        audio_path: Path to audio file
        output_path: Where to save the output video
        fps: Frames per second
        progress_callback: Optional callback for progress updates
    
    Returns:
        True if successful, raises exception otherwise
    """
    try:
        # Make sure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get first frame to check dimensions
        first_frame = None
        for file in sorted(os.listdir(frames_dir)):
            if file.endswith('.png'):
                first_frame = os.path.join(frames_dir, file)
                break
        
        if not first_frame:
            raise ValueError("No frames found in directory")
        
        # Check if dimensions are even (required for H.264)
        with Image.open(first_frame) as img:
            width, height = img.size
            logger.info(f"Frame dimensions: {width}x{height}")
            
            # If either dimension is odd, we need to resize all frames
            if width % 2 != 0 or height % 2 != 0:
                logger.info("Dimensions not even, resizing frames for H.264 compatibility")
                new_width = width if width % 2 == 0 else width - 1
                new_height = height if height % 2 == 0 else height - 1
                
                # Create temp directory for resized frames
                resized_frames_dir = tempfile.mkdtemp()
                
                # Resize all frames
                for file in sorted(os.listdir(frames_dir)):
                    if file.endswith('.png'):
                        frame_path = os.path.join(frames_dir, file)
                        with Image.open(frame_path) as frame:
                            resized = frame.resize((new_width, new_height))
                            resized.save(os.path.join(resized_frames_dir, file))
                
                # Update frames directory to use resized frames
                frames_dir = resized_frames_dir
                logger.info(f"Resized frames to {new_width}x{new_height}")
        
        if progress_callback:
            progress_callback(85)  # FFmpeg about to start
        
        # Build FFmpeg command with very explicit H.264 compatible settings
        frames_pattern = os.path.join(frames_dir, "frame_%04d.png")
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-framerate', str(fps),
            '-i', frames_pattern,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-preset', 'medium',  # Balance between encoding speed and compression
            '-profile:v', 'main',  # Widely compatible profile
            '-pix_fmt', 'yuv420p',  # Standard pixel format for compatibility
            '-c:a', 'aac',
            '-b:a', '192k',  # Good quality audio
            '-shortest',  # End encoding when shortest input stream ends
            output_path
        ]
        
        logger.info("Running FFmpeg command: " + " ".join(ffmpeg_cmd))
        
        # Run FFmpeg and capture output
        process = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True  # Raise exception on error
        )
        
        # Verify the output file exists and is readable
        if not os.path.exists(output_path):
            raise Exception(f"Output file not created: {output_path}")
        
        # Output final progress
        if progress_callback:
            progress_callback(100)  # Video completed
        
        logger.info(f"Video successfully created at {output_path}")
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr}")
        raise Exception(f"FFmpeg error: {e.stderr}")
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        raise