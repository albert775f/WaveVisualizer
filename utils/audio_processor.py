import os
import numpy as np
import librosa
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)

def process_audio_visualization(audio_path, image_path, output_path, color='#00FFFF', fps=30):
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
            
            # Create a new figure for the spectrogram with the same size as background
            fig, ax = plt.subplots(figsize=(img_width/100, img_height/100), dpi=100)
            
            # Plot the background image
            ax.imshow(img)
            
            # Calculate frequency bins to show (focus on audible range)
            # Get reduced number of frequency bins (more visually appealing)
            n_bins = min(128, D_db.shape[0])
            D_db_subset = D_db[:n_bins, :]
            
            # Calculate average amplitude across time for each frequency bin
            avg_amplitudes = np.mean(D_db_subset, axis=1)
            
            # Normalize to 0-1 range for visualization
            normalized_amps = (avg_amplitudes - np.min(avg_amplitudes)) / (np.max(avg_amplitudes) - np.min(avg_amplitudes))
            
            # Calculate bar positions and heights
            n_bars = 64  # Number of bars to display
            bar_width = (img_width * 0.8) / n_bars
            bar_spacing = (img_width * 0.8) / (n_bars - 1) - bar_width
            
            # Resample to desired number of bars
            bars_heights = np.interp(
                np.linspace(0, len(normalized_amps) - 1, n_bars),
                np.arange(len(normalized_amps)),
                normalized_amps
            )
            
            # Draw bars
            margin_x = img_width * 0.1  # 10% margin on each side
            margin_y = img_height * 0.1  # 10% margin on top and bottom
            max_bar_height = img_height * 0.8
            
            for j, height in enumerate(bars_heights):
                bar_height = height * max_bar_height
                x_pos = margin_x + j * (bar_width + bar_spacing)
                
                # Draw bar as rectangle
                rect = plt.Rectangle(
                    (x_pos, (img_height - margin_y) - bar_height),
                    bar_width,
                    bar_height,
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
            # Run FFmpeg with detailed output for debugging
            process = subprocess.run(
                ffmpeg_cmd, 
                check=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"FFmpeg output: {process.stdout}")
            
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
        logger.error(f"Error in process_audio_visualization: {str(e)}")
        # Clean up any temporary files
        if 'frames_dir' in locals() and os.path.exists(frames_dir):
            for file in os.listdir(frames_dir):
                try:
                    os.remove(os.path.join(frames_dir, file))
                except:
                    pass
            try:
                os.rmdir(frames_dir)
            except:
                pass
        raise
