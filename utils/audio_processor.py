import os
import numpy as np
import librosa
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.patches as patches
import subprocess
import tempfile
import logging
import gc  # For garbage collection
from types import SimpleNamespace
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

# Import our custom utility modules
from utils.image_processor import ensure_even_dimensions
from utils.video_processor import create_video_from_frames

logger = logging.getLogger(__name__)

def process_frame(args):
    """Process a single frame with the given parameters"""
    i, segment, image_path, width, height, color, bar_count, bar_width_ratio, bar_height_scale, \
    glow_effect, glow_intensity, responsiveness, smoothing, vertical_position, horizontal_margin, \
    prev_heights, frames_dir = args
    
    try:
        # Calculate spectrum using Short-time Fourier transform (STFT)
        n_fft = min(2048, len(segment))
        hop_length = n_fft // 4
        D = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))
        D_db = librosa.amplitude_to_db(D, ref=np.max)
        
        # Create figure
        fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
        
        # Plot background
        bg_img = plt.imread(image_path)
        ax.imshow(bg_img, origin='upper')
        
        # Process frequency data
        n_bins = min(128, D_db.shape[0])
        D_db_subset = D_db[:n_bins, :]
        avg_amplitudes = np.mean(D_db_subset, axis=1) * responsiveness
        normalized_amps = (avg_amplitudes - np.min(avg_amplitudes)) / (np.max(avg_amplitudes) - np.min(avg_amplitudes))
        
        # Apply smoothing
        if prev_heights is not None:
            normalized_amps = prev_heights * smoothing + normalized_amps * (1 - smoothing)
        
        # Draw visualization
        total_width = width * (1 - 2 * horizontal_margin)
        bar_width = (total_width / bar_count) * bar_width_ratio
        max_height = height * 0.8 * bar_height_scale
        
        for j in range(bar_count):
            idx = int(j * (len(normalized_amps) / bar_count))
            if idx >= len(normalized_amps):
                idx = len(normalized_amps) - 1
            amplitude = normalized_amps[idx]
            
            rect_height = amplitude * max_height
            x_pos = horizontal_margin * width + j * (total_width / bar_count)
            rect_y = height * vertical_position - (rect_height / 2)
            
            if glow_effect:
                glow_rect = patches.Rectangle(
                    (x_pos - 5, rect_y - 5),
                    bar_width + 10,
                    rect_height + 10,
                    color=color,
                    alpha=0.3 * glow_intensity,
                    edgecolor='none'
                )
                ax.add_patch(glow_rect)
            
            rect = patches.Rectangle(
                (x_pos, rect_y),
                bar_width,
                rect_height,
                color=color,
                alpha=0.7
            )
            ax.add_patch(rect)
        
        ax.axis('off')
        ax.set_xlim(0, width)
        ax.set_ylim(0, height)
        
        # Save frame
        frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
        plt.savefig(frame_path, bbox_inches='tight', pad_inches=0, format='png')
        plt.close('all')
        
        return i, normalized_amps
        
    except Exception as e:
        logger.error(f"Error processing frame {i}: {str(e)}")
        raise

def process_audio_visualization(
    audio_path, 
    image_path, 
    output_path, 
    color='#00FFFF', 
    fps=30,
    bar_count=64,
    bar_width_ratio=0.8,
    bar_height_scale=1.0,
    glow_effect=False,
    glow_intensity=0.5,
    responsiveness=1.0,
    smoothing=0.2,
    vertical_position=0.5,
    horizontal_margin=0.1,
    progress_callback=None
):
    """
    Process audio file to generate visualization frames, overlay on image, and create video
    
    Parameters:
    - audio_path: Path to WAV audio file
    - image_path: Path to background image
    - output_path: Path where output MP4 will be saved
    - color: Color for the visualization (hex code)
    - fps: Frames per second for the output video
    """
    try:
        logger.info("Loading audio file...")
        # Load the audio file
        y, sr = librosa.load(audio_path, sr=None)
        
        # Get audio duration and calculate number of frames needed
        duration = librosa.get_duration(y=y, sr=sr)
        n_frames = int(duration * fps)
        
        # Process image to ensure even dimensions (required for H.264 encoding)
        logger.info("Processing background image...")
        image_path, width, height = ensure_even_dimensions(image_path)
        if width == 0 or height == 0:
            raise ValueError("Failed to process background image dimensions")
        
        # Create a temporary directory for frames
        frames_dir = tempfile.mkdtemp()
        
        # Frame generation settings
        frame_length = len(y) // n_frames
        
        logger.info(f"Generating {n_frames} visualization frames...")
        
        # Prepare frame processing arguments
        frame_args = []
        prev_heights = None
        
        for i in range(n_frames):
            start_idx = i * frame_length
            end_idx = min((i + 1) * frame_length, len(y))
            
            if start_idx >= len(y):
                break
                
            segment = y[start_idx:end_idx]
            frame_args.append((
                i, segment, image_path, width, height, color, bar_count, bar_width_ratio,
                bar_height_scale, glow_effect, glow_intensity, responsiveness, smoothing,
                vertical_position, horizontal_margin, prev_heights, frames_dir
            ))
        
        # Process frames in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_frame, args) for args in frame_args]
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    frame_idx, new_heights = future.result()
                    prev_heights = new_heights
                    
                    if progress_callback and i % max(1, n_frames // 20) == 0:
                        progress_percent = min(int(i / n_frames * 70) + 5, 75)
                        progress_callback(progress_percent)
                        
                except Exception as e:
                    logger.error(f"Error processing frame {i}: {str(e)}")
                    raise
        
        logger.info("All frames generated. Creating video...")
        
        # Create video from frames using our specialized video processor
        # This handles ensuring dimensions are even for H.264 compatibility
        logger.info("Using video processor to create final video...")
        
        if progress_callback:
            progress_callback(80)  # Video generation starting
            
        try:
            # Use our dedicated video processor to handle FFmpeg compatibility
            create_video_from_frames(
                frames_dir=frames_dir,
                audio_path=audio_path,
                output_path=output_path,
                fps=fps,
                progress_callback=progress_callback
            )
            
            logger.info(f"Video successfully created at {output_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            raise Exception(f"FFmpeg error: {e.stderr}")
        except Exception as e:
            logger.error(f"Error verifying output file: {str(e)}")
            raise
        
        # Clean up temporary frames
        for file in os.listdir(frames_dir):
            os.remove(os.path.join(frames_dir, file))
        os.rmdir(frames_dir)
        
        return True
        
    except Exception as e:
        logger.error(f"Error in process_audio_visualization: {str(e)}", exc_info=True)
        # Clean up any temporary files
        frames_dir_var = locals().get('frames_dir')
        if frames_dir_var and os.path.exists(frames_dir_var):
            for file in os.listdir(frames_dir_var):
                try:
                    os.remove(os.path.join(frames_dir_var, file))
                except Exception as cleanup_error:
                    logger.error(f"Error removing frame file: {cleanup_error}")
            try:
                os.rmdir(frames_dir_var)
            except Exception as cleanup_error:
                logger.error(f"Error removing frames directory: {cleanup_error}")
        raise