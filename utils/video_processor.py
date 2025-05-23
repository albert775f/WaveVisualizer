import os
import subprocess
import logging
import tempfile
import time

logger = logging.getLogger(__name__)

def create_video_from_frames(frames, audio_path, output_path, fps=30, progress_callback=None):
    """Create video from frames with audio"""
    try:
        logger.info("Starting video creation...")
        start_time = time.time()
        
        # Create temporary directory for sorted frames
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Sort frames by timestamp
            sorted_frames = sorted(frames, key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
            
            # Create video using FFmpeg with hardware acceleration if available
            hw_accel = _detect_hardware_accel()
            logger.info(f"Using hardware acceleration: {hw_accel}")
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-framerate', str(fps),
                '-i', os.path.join(temp_dir, 'frame_%d.png'),
                '-i', audio_path,
                '-c:v', 'h264_nvenc' if hw_accel == 'nvenc' else 'h264_qsv' if hw_accel == 'qsv' else 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                output_path
            ]
            
            # Add hardware acceleration parameters if available
            if hw_accel == 'nvenc':
                cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])
            elif hw_accel == 'qsv':
                cmd.extend(['-hwaccel', 'qsv', '-hwaccel_output_format', 'qsv'])
            
            # Copy frames to temporary directory with sequential numbering
            for i, frame in enumerate(sorted_frames, 1):
                new_path = os.path.join(temp_dir, f'frame_{i}.png')
                os.link(frame, new_path)
            
            # Run FFmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    if 'frame=' in output:
                        try:
                            frame_num = int(output.split('frame=')[1].split()[0])
                            if progress_callback:
                                progress = min(80 + int(frame_num / len(frames) * 20), 100)
                                progress_callback(progress)
                        except:
                            pass
            
            # Check for errors
            if process.returncode != 0:
                error = process.stderr.read()
                raise Exception(f"FFmpeg error: {error}")
            
            end_time = time.time()
            logger.info(f"Video created in {end_time - start_time:.2f} seconds")
            
        finally:
            # Cleanup temporary directory
            for file in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except Exception as e:
                    logger.warning(f"Error removing temporary file: {e}")
            try:
                os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f"Error removing temporary directory: {e}")
                
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        raise

def _detect_hardware_accel():
    """Detect available hardware acceleration"""
    try:
        # Check for NVIDIA GPU
        nvidia_check = subprocess.run(['nvidia-smi'], capture_output=True)
        if nvidia_check.returncode == 0:
            return 'nvenc'
            
        # Check for Intel QuickSync
        qsv_check = subprocess.run(['vainfo'], capture_output=True)
        if qsv_check.returncode == 0 and 'VAEntrypointEncSlice' in qsv_check.stdout.decode():
            return 'qsv'
            
    except:
        pass
        
    return None