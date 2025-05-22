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
    horizontal_margin=0.1
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
            
            # Calculate spectrum using Short-time Fourier transform (STFT)
            D = np.abs(librosa.stft(segment, n_fft=2048, hop_length=512))
            
            # Convert to decibels
            D_db = librosa.amplitude_to_db(D, ref=np.max)
            
            # Plot the spectrum
            plt.figure(figsize=(10, 4))
            plt.imshow(plt.imread(image_path))
            
            # Get image dimensions to size the spectrum visualization
            img = plt.imread(image_path)
            img_height, img_width = img.shape[0], img.shape[1]
            
            # Make sure width and height are even (required for H.264 encoding)
            # We need to resize the actual image, not just the figure
            from PIL import Image
            
            # Load image with PIL to resize if needed
            pil_img = Image.open(image_path)
            adjusted_width = img_width if img_width % 2 == 0 else img_width - 1
            adjusted_height = img_height if img_height % 2 == 0 else img_height - 1
            
            # Resize only if dimensions are odd
            if img_width % 2 != 0 or img_height % 2 != 0:
                pil_img = pil_img.resize((adjusted_width, adjusted_height))
                
                # Save the resized image to a temporary file
                temp_image_path = os.path.join(tempfile.gettempdir(), "resized_image.png")
                pil_img.save(temp_image_path)
                
                # Use the resized image instead
                img = plt.imread(temp_image_path)
                logger.info(f"Resized image from {img_width}x{img_height} to {adjusted_width}x{adjusted_height}")
            
            # Create a new figure for the spectrogram with adjusted size
            fig, ax = plt.subplots(figsize=(adjusted_width/100, adjusted_height/100), dpi=100)
            
            # Plot the background image with correct orientation (not upside down)
            ax.imshow(img, origin='upper')
            
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
            
            # Store current heights for next frame as an attribute of the function
            # This is a bit of a hack but lets us avoid global variables
            process_audio_visualization._prev_heights = normalized_amps.copy()
            
            # Calculate bar positions and heights using custom parameters
            n_bars = bar_count  # Number of bars to display
            
            # Adjust width based on ratio parameter
            effective_width = img_width * (1 - 2 * horizontal_margin)
            bar_width = (effective_width * bar_width_ratio) / n_bars
            bar_spacing = (effective_width * (1 - bar_width_ratio)) / (n_bars - 1)
            
            # Resample to desired number of bars
            bars_heights = np.interp(
                np.linspace(0, len(normalized_amps) - 1, n_bars),
                np.arange(len(normalized_amps)),
                normalized_amps
            )
            
            # Apply height scaling
            bars_heights = bars_heights * bar_height_scale
            
            # Determine vertical position
            # vertical_position: 0.0 = top, 1.0 = bottom, 0.5 = center
            margin_x = img_width * horizontal_margin  # Horizontal margin
            
            # Calculate vertical positioning
            bar_section_height = img_height * 0.8  # Height of the section where bars appear
            base_y = img_height * (0.1 + 0.8 * vertical_position)
            max_bar_height = bar_section_height * 0.8
            
            # Draw bars
            for j, height in enumerate(bars_heights):
                bar_height = height * max_bar_height
                x_pos = margin_x + j * (bar_width + bar_spacing)
                
                # Calculate y position based on vertical_position
                if vertical_position <= 0.5:
                    # Top half - bars go down from position
                    y_pos = base_y
                    rect_y = y_pos
                    rect_height = bar_height
                else:
                    # Bottom half - bars go up from position
                    y_pos = base_y - bar_height
                    rect_y = y_pos
                    rect_height = bar_height
                
                # Add glow effect if enabled
                if glow_effect:
                    # Create a larger, more transparent rectangle for glow
                    glow_extra = bar_width * 0.5 * glow_intensity
                    glow_rect = patches.Rectangle(
                        (x_pos - glow_extra, rect_y - glow_extra),
                        bar_width + 2 * glow_extra,
                        rect_height + 2 * glow_extra,
                        color=color,
                        alpha=0.3 * glow_intensity,
                        edgecolor='none'
                    )
                    ax.add_patch(glow_rect)
                
                # Draw bar as rectangle with customized alpha
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
            
            # Save frame
            frame_path = os.path.join(frames_dir, f"frame_{i:04d}.png")
            plt.savefig(frame_path, bbox_inches='tight', pad_inches=0)
            plt.close('all')
            
            if i % 10 == 0:
                logger.info(f"Generated frame {i}/{n_frames}")
        
        logger.info("All frames generated. Creating video...")
        
        # Create video from frames using FFmpeg
        frames_pattern = os.path.join(frames_dir, "frame_%04d.png")
        
        # Build FFmpeg command
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-framerate', str(fps),
            '-i', frames_pattern,
            '-i', audio_path,
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-strict', 'experimental',
            '-shortest',
            output_path
        ]
        
        # Execute FFmpeg command
        logger.info("Running FFmpeg to create video...")
        try:
            # Before running FFmpeg, let's verify the dimensions of the frames
            # Check the first frame
            first_frame_path = os.path.join(frames_dir, "frame_0000.png")
            if os.path.exists(first_frame_path):
                from PIL import Image
                with Image.open(first_frame_path) as img:
                    width, height = img.size
                    logger.info(f"Frame dimensions: {width}x{height}")
                    
                    # If width or height is odd, resize all frames
                    if width % 2 != 0 or height % 2 != 0:
                        logger.info("Fixing odd dimensions in frames...")
                        new_width = width if width % 2 == 0 else width - 1
                        new_height = height if height % 2 == 0 else height - 1
                        
                        # Resize all frames to ensure even dimensions
                        for file in os.listdir(frames_dir):
                            if file.startswith("frame_") and file.endswith(".png"):
                                frame_path = os.path.join(frames_dir, file)
                                with Image.open(frame_path) as frame:
                                    resized = frame.resize((new_width, new_height))
                                    resized.save(frame_path)
            
            # Run FFmpeg with detailed output for debugging
            process = subprocess.run(
                ffmpeg_cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if not os.path.exists(output_path):
                logger.error("FFmpeg completed but output file was not created")
                raise Exception("Failed to create output video file")
                
            # Check if file is readable
            with open(output_path, 'rb') as f:
                # Just read a small chunk to verify file is accessible
                f.read(1024)
                
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
