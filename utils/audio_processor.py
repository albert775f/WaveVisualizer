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

# Import our custom utility modules
from utils.image_processor import ensure_even_dimensions
from utils.video_processor import create_video_from_frames

logger = logging.getLogger(__name__)

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
        
        # Generate frames with visualization
        for i in range(n_frames):
            start_idx = i * frame_length
            end_idx = min((i + 1) * frame_length, len(y))
            
            if start_idx >= len(y):
                break
                
            segment = y[start_idx:end_idx]
            
            # Report progress if callback provided
            if progress_callback and i % max(1, n_frames // 20) == 0:  # Update progress ~20 times
                progress_percent = min(int(i / n_frames * 70) + 5, 75)  # 5-75% is frame generation
                progress_callback(progress_percent)
            
            # Calculate spectrum using Short-time Fourier transform (STFT)
            # Dynamically adjust n_fft based on segment length
            n_fft = min(2048, len(segment))
            hop_length = n_fft // 4  # Adjust hop length proportionally
            D = np.abs(librosa.stft(segment, n_fft=n_fft, hop_length=hop_length))
            
            # Convert to decibels
            D_db = librosa.amplitude_to_db(D, ref=np.max)
            
            # Get image dimensions to size the spectrum visualization
            img_width, img_height = width, height
            
            # Create a new figure for the spectrogram with adjusted size
            fig, ax = plt.subplots(figsize=(img_width/100, img_height/100), dpi=100)
            
            try:
                # Plot the background image with correct orientation (not upside down)
                bg_img = plt.imread(image_path)
                ax.imshow(bg_img, origin='upper')
                
                # Calculate frequency bins to show (focus on audible range)
                # Use the bar_count parameter for the number of frequency bins
                n_bins = min(128, D_db.shape[0])
                D_db_subset = D_db[:n_bins, :]
                
                # Calculate average amplitude across time for each frequency bin
                # Apply responsiveness multiplier
                avg_amplitudes = np.mean(D_db_subset, axis=1) * responsiveness
                
                # Normalize to 0-1 range for visualization
                normalized_amps = (avg_amplitudes - np.min(avg_amplitudes)) / (np.max(avg_amplitudes) - np.min(avg_amplitudes))
                
                # Apply smoothing between frames if needed
                prev_heights_var = getattr(process_audio_visualization, '_prev_heights', None)
                if i > 0 and smoothing > 0 and prev_heights_var is not None:
                    try:
                        # Apply smoothing between frames
                        normalized_amps = prev_heights_var * smoothing + normalized_amps * (1 - smoothing)
                    except Exception as e:
                        logger.warning(f"Smoothing error: {e}")
                
                # Store current heights for next frame
                process_audio_visualization._prev_heights = normalized_amps.copy()
                
                # Calculate bar positions and heights
                n_bars = bar_count
                total_width = img_width * (1 - 2 * horizontal_margin)
                bar_width = (total_width / n_bars) * bar_width_ratio
                max_height = img_height * 0.8 * bar_height_scale
                
                # Color conversion from hex to RGB
                if color.startswith('#'):
                    color_rgb = tuple(int(color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4))
                else:
                    color_rgb = (0, 1, 1)  # Default to cyan
                
                # Draw bars
                for j in range(n_bars):
                    idx = int(j * (len(normalized_amps) / n_bars))
                    if idx >= len(normalized_amps):
                        idx = len(normalized_amps) - 1
                    amplitude = normalized_amps[idx]
                    
                    rect_height = amplitude * max_height
                    x_pos = horizontal_margin * img_width + j * (total_width / n_bars)
                    rect_y = img_height * vertical_position - (rect_height / 2)
                    
                    # Draw glow effect if enabled
                    if glow_effect:
                        glow_extra = 5
                        glow_rect = patches.Rectangle(
                            (x_pos - glow_extra, rect_y - glow_extra),
                            bar_width + 2 * glow_extra,
                            rect_height + 2 * glow_extra,
                            color=color,
                            alpha=0.3 * glow_intensity,
                            edgecolor='none'
                        )
                        ax.add_patch(glow_rect)
                    
                    # Draw bar
                    rect = patches.Rectangle(
                        (x_pos, rect_y),
                        bar_width,
                        rect_height,
                        color=color,
                        alpha=0.7
                    )
                    ax.add_patch(rect)
                
                # Remove axes and set limits
                ax.axis('off')
                ax.set_xlim(0, img_width)
                ax.set_ylim(0, img_height)
                
                # Save frame with error handling
                try:
                    plt.savefig(frame_path, bbox_inches='tight', pad_inches=0, format='png')
                except Exception as e:
                    logger.error(f"Error saving frame {i}: {str(e)}")
                    raise
                
            except Exception as e:
                logger.error(f"Error processing frame {i}: {str(e)}")
                raise
            finally:
                plt.close('all')
                gc.collect()  # Force garbage collection
            
            if i % 10 == 0:
                logger.info(f"Generated frame {i}/{n_frames}")
        
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