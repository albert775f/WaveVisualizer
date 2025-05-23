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
import time
import threading
from queue import Queue
import torch  # Für GPU-Erkennung

# Import our custom utility modules
from utils.image_processor import ensure_even_dimensions
from utils.video_processor import create_video_from_frames

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self, chunk_size=30):
        self.chunk_size = chunk_size
        self.gpu_available = self._check_gpu()
        logger.info(f"GPU available: {self.gpu_available}")
        
    def _check_gpu(self):
        try:
            return torch.cuda.is_available()
        except:
            return False
            
    def process_chunk(self, audio_chunk, start_time, image_path, width, height, 
                     color='#00FFFF', bar_count=64, bar_width_ratio=0.8,
                     bar_height_scale=1.0, glow_effect=False, glow_intensity=0.5,
                     responsiveness=1.0, smoothing=0.2, vertical_position=0.5,
                     horizontal_margin=0.1):
        """Process a single chunk of audio data"""
        try:
            # Calculate spectrum
            n_fft = min(2048, len(audio_chunk))
            hop_length = n_fft // 4
            
            if self.gpu_available:
                # GPU processing
                audio_tensor = torch.from_numpy(audio_chunk).cuda()
                stft = torch.stft(audio_tensor, n_fft=n_fft, hop_length=hop_length)
                D = torch.abs(stft).cpu().numpy()
            else:
                # CPU processing
                D = np.abs(librosa.stft(audio_chunk, n_fft=n_fft, hop_length=hop_length))
            
            D_db = librosa.amplitude_to_db(D, ref=np.max)
            
            # Create visualization
            frames = self._create_visualization(
                D_db, image_path, width, height, color, bar_count,
                bar_width_ratio, bar_height_scale, glow_effect,
                glow_intensity, responsiveness, smoothing,
                vertical_position, horizontal_margin
            )
            
            return {
                'start_time': start_time,
                'frames': frames,
                'duration': len(audio_chunk) / librosa.get_samplerate(audio_chunk),
                'processor': 'gpu' if self.gpu_available else 'cpu'
            }
            
        except Exception as e:
            logger.error(f"Error processing chunk at {start_time}: {str(e)}")
            raise
            
    def _create_visualization(self, D_db, image_path, width, height, color,
                            bar_count, bar_width_ratio, bar_height_scale,
                            glow_effect, glow_intensity, responsiveness,
                            smoothing, vertical_position, horizontal_margin):
        """Create visualization frames for a chunk"""
        frames = []
        plt.ioff()
        
        try:
            # Load and process background image
            bg_img = plt.imread(image_path)
            
            # Process frequency data
            n_bins = min(128, D_db.shape[0])
            D_db_subset = D_db[:n_bins, :]
            avg_amplitudes = np.mean(D_db_subset, axis=1) * responsiveness
            normalized_amps = (avg_amplitudes - np.min(avg_amplitudes)) / (np.max(avg_amplitudes) - np.min(avg_amplitudes))
            
            # Create figure
            fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
            ax.imshow(bg_img, origin='upper')
            
            # Pre-calculate bar positions
            total_width = width * (1 - 2 * horizontal_margin)
            bar_width = (total_width / bar_count) * bar_width_ratio
            max_height = height * 0.8 * bar_height_scale
            bar_positions = [(horizontal_margin * width + j * (total_width / bar_count)) for j in range(bar_count)]
            
            # Draw bars
            for j in range(bar_count):
                idx = int(j * (len(normalized_amps) / bar_count))
                if idx >= len(normalized_amps):
                    idx = len(normalized_amps) - 1
                amplitude = normalized_amps[idx]
                
                rect_height = amplitude * max_height
                x_pos = bar_positions[j]
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
            frame_path = os.path.join(tempfile.gettempdir(), f"frame_{int(time.time()*1000)}.png")
            plt.savefig(frame_path, bbox_inches='tight', pad_inches=0, format='png', optimize=True)
            frames.append(frame_path)
            
        finally:
            plt.close('all')
            gc.collect()
            
        return frames

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
    """Process audio file to generate visualization frames, overlay on image, and create video"""
    try:
        logger.info("Starting audio visualization process...")
        start_time = time.time()
        
        # Initialize processor
        processor = AudioProcessor(chunk_size=30)  # 30-second chunks
        
        # Load audio and get duration
        logger.info("Loading audio file...")
        y, sr = librosa.load(audio_path, sr=None)
        duration = librosa.get_duration(y=y, sr=sr)
        
        # Process image
        logger.info("Processing background image...")
        image_path, width, height = ensure_even_dimensions(image_path)
        if width == 0 or height == 0:
            raise ValueError("Failed to process background image dimensions")
        
        # Calculate chunks
        chunk_length = int(30 * sr)  # 30 seconds per chunk
        chunks = []
        for i in range(0, len(y), chunk_length):
            chunk = y[i:i + chunk_length]
            if len(chunk) > 0:
                chunks.append((chunk, i / sr))
        
        logger.info(f"Processing {len(chunks)} chunks...")
        
        # Process chunks in parallel
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for chunk, start_time in chunks:
                future = executor.submit(
                    processor.process_chunk,
                    chunk, start_time, image_path, width, height,
                    color, bar_count, bar_width_ratio, bar_height_scale,
                    glow_effect, glow_intensity, responsiveness,
                    smoothing, vertical_position, horizontal_margin
                )
                futures.append(future)
            
            # Collect results
            for i, future in enumerate(as_completed(futures)):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if progress_callback:
                        progress = min(int((i + 1) / len(chunks) * 70) + 5, 75)
                        progress_callback(progress)
                        logger.info(f"Progress: {progress}% ({i + 1}/{len(chunks)} chunks)")
                        
                except Exception as e:
                    logger.error(f"Error processing chunk {i}: {str(e)}")
                    raise
        
        # Sort results by start time
        results.sort(key=lambda x: x['start_time'])
        
        # Create video from all frames
        logger.info("Creating video...")
        if progress_callback:
            progress_callback(80)
            
        try:
            # Collect all frame paths
            all_frames = []
            for result in results:
                all_frames.extend(result['frames'])
            
            # Create video
            create_video_from_frames(
                frames=all_frames,
                audio_path=audio_path,
                output_path=output_path,
                fps=fps,
                progress_callback=progress_callback
            )
            
            end_time = time.time()
            total_time = end_time - start_time
            logger.info(f"Video successfully created at {output_path}")
            logger.info(f"Total processing time: {total_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error creating video: {str(e)}")
            raise
        finally:
            # Cleanup temporary files
            for result in results:
                for frame in result['frames']:
                    try:
                        os.remove(frame)
                    except Exception as e:
                        logger.warning(f"Error removing temporary file {frame}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in process_audio_visualization: {str(e)}", exc_info=True)
        raise