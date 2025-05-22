import os
import uuid
import logging
import tempfile
import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
import librosa
import shutil
import time

from models import db, Preset, AudioFile, ImageFile, OutputVideo
from utils.audio_processor import process_audio_visualization

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure upload settings - use absolute paths for more reliability
base_dir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(base_dir, 'uploads')
OUTPUT_FOLDER = os.path.join(base_dir, 'output')
ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB max upload size

# Create necessary directories with proper permissions
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)
    # Ensure proper permissions
    os.chmod(folder, 0o755)

# Configure Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def cleanup_old_files():
    """Clean up files older than 24 hours"""
    try:
        current_time = time.time()
        for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                if os.path.getmtime(filepath) < current_time - 86400:  # 24 hours
                    os.remove(filepath)
                    logger.info(f"Cleaned up old file: {filepath}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

def allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def get_metadata():
    """Get stored metadata about files"""
    try:
        with open('metadata.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'audio_files': [], 'image_files': [], 'output_files': []}

def save_metadata(metadata):
    """Save metadata to file"""
    with open('metadata.json', 'w') as f:
        json.dump(metadata, f)

def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0 or unit == 'GB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

@app.route('/')
def index():
    """Main page for audio visualization"""
    # Get presets from database
    presets = Preset.query.all()
    if not presets:
        # Create default preset if none exist
        default_preset = Preset()
        default_preset.name = "Default"
        db.session.add(default_preset)
        db.session.commit()
        presets = [default_preset]
    
    # Get audio and image files for dropdowns
    audio_files = AudioFile.query.all()
    image_files = ImageFile.query.all()
    
    return render_template('index.html', presets=presets, audio_files=audio_files, image_files=image_files)

@app.route('/library')
def library():
    """Media library page for managing files"""
    # Get files from database
    audio_files = AudioFile.query.order_by(AudioFile.created_at.desc()).all()
    image_files = ImageFile.query.order_by(ImageFile.created_at.desc()).all()
    output_files = OutputVideo.query.order_by(OutputVideo.created_at.desc()).all()
    
    return render_template('library.html', 
                           audio_files=audio_files, 
                           image_files=image_files, 
                           output_files=output_files)

@app.route('/presets')
def presets():
    """Manage visualization presets"""
    presets = Preset.query.order_by(Preset.created_at.desc()).all()
    return render_template('presets.html', presets=presets)

@app.route('/preset/new', methods=['GET', 'POST'])
def new_preset():
    """Create a new preset"""
    if request.method == 'POST':
        name = request.form.get('name', 'New Preset')
        
        # Create new preset with form data
        preset = Preset()
        preset.name = name
        preset.color = request.form.get('color', '#00FFFF')
        preset.bar_count = int(request.form.get('bar_count', 64))
        preset.bar_width_ratio = float(request.form.get('bar_width_ratio', 0.8))
        preset.bar_height_scale = float(request.form.get('bar_height_scale', 1.0))
        preset.glow_effect = 'glow_effect' in request.form
        preset.glow_intensity = float(request.form.get('glow_intensity', 0.5))
        preset.responsiveness = float(request.form.get('responsiveness', 1.0))
        preset.smoothing = float(request.form.get('smoothing', 0.2))
        preset.vertical_position = float(request.form.get('vertical_position', 0.5))
        preset.horizontal_margin = float(request.form.get('horizontal_margin', 0.1))
        
        db.session.add(preset)
        db.session.commit()
        
        flash(f'Preset "{name}" created successfully', 'success')
        return redirect(url_for('presets'))
    
    # Default preset as template
    default_preset = Preset.query.first()
    if not default_preset:
        default_preset = Preset()
        default_preset.name = "Default"
    return render_template('preset_form.html', preset=default_preset, is_new=True)

@app.route('/preset/edit/<int:preset_id>', methods=['GET', 'POST'])
def edit_preset(preset_id):
    """Edit an existing preset"""
    preset = Preset.query.get_or_404(preset_id)
    
    if request.method == 'POST':
        preset.name = request.form.get('name', preset.name)
        preset.color = request.form.get('color', preset.color)
        preset.bar_count = int(request.form.get('bar_count', preset.bar_count))
        preset.bar_width_ratio = float(request.form.get('bar_width_ratio', preset.bar_width_ratio))
        preset.bar_height_scale = float(request.form.get('bar_height_scale', preset.bar_height_scale))
        preset.glow_effect = 'glow_effect' in request.form
        preset.glow_intensity = float(request.form.get('glow_intensity', preset.glow_intensity))
        preset.responsiveness = float(request.form.get('responsiveness', preset.responsiveness))
        preset.smoothing = float(request.form.get('smoothing', preset.smoothing))
        preset.vertical_position = float(request.form.get('vertical_position', preset.vertical_position))
        preset.horizontal_margin = float(request.form.get('horizontal_margin', preset.horizontal_margin))
        
        db.session.commit()
        
        flash(f'Preset "{preset.name}" updated successfully', 'success')
        return redirect(url_for('presets'))
    
    return render_template('preset_form.html', preset=preset, is_new=False)

@app.route('/preset/delete/<int:preset_id>', methods=['POST'])
def delete_preset(preset_id):
    """Delete a preset"""
    preset = Preset.query.get_or_404(preset_id)
    name = preset.name
    
    # Don't delete the last preset
    if Preset.query.count() <= 1:
        flash('Cannot delete the last preset', 'danger')
        return redirect(url_for('presets'))
    
    db.session.delete(preset)
    db.session.commit()
    
    flash(f'Preset "{name}" deleted successfully', 'success')
    return redirect(url_for('presets'))

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and processing"""
    try:
        logger.info("Upload request received")
        
        # Check audio file
        if 'audio_file' not in request.files:
            flash('Please select an audio file', 'error')
            return redirect(url_for('index'))
            
        audio_file = request.files['audio_file']
        if audio_file.filename == '':
            flash('Please select an audio file', 'error')
            return redirect(url_for('index'))
            
        if audio_file.filename and not allowed_audio_file(audio_file.filename):
            flash('Only WAV audio files are allowed', 'error')
            return redirect(url_for('index'))
            
        # Check image file
        if 'image_file' not in request.files:
            flash('Please select a background image', 'error')
            return redirect(url_for('index'))
            
        image_file = request.files['image_file']
        if image_file.filename == '':
            flash('Please select a background image', 'error')
            return redirect(url_for('index'))
            
        if image_file.filename and not allowed_image_file(image_file.filename):
            flash('Only JPG and PNG images are allowed', 'error')
            return redirect(url_for('index'))
        
        # Create unique ID and save files
        unique_id = str(uuid.uuid4())
        audio_filename = secure_filename(unique_id + '_audio.wav')
        
        # Get file extension safely
        if image_file.filename and '.' in image_file.filename:
            ext = image_file.filename.rsplit('.', 1)[1].lower()
        else:
            ext = 'jpg'  # Default extension
            
        image_filename = secure_filename(unique_id + '_image.' + ext)
        
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        
        logger.info(f"Saving files: {audio_path}, {image_path}")
        audio_file.save(audio_path)
        image_file.save(image_path)
        
        # Get color from form
        color = request.form.get('visualization_color', '#00FFFF')
        
        # Generate output path
        output_filename = secure_filename(unique_id + '_output.mp4')
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        logger.info(f"Processing visualization with color: {color}")
        
        # Process visualization
        process_audio_visualization(
            audio_path=audio_path,
            image_path=image_path,
            output_path=output_path,
            color=color
        )
        
        logger.info(f"Video created: {output_filename}")
        
        # Clean up input files after processing
        os.remove(audio_path)
        os.remove(image_path)
        
        # Redirect to download page
        return render_template('success.html', filename=output_filename)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        flash('An error occurred while processing your files. Please try again.', 'error')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        flash('Error downloading file', 'error')
        return redirect(url_for('index'))

@app.route('/images/<filename>')
def get_image(filename):
    """Serve an image file for display"""
    return send_file(os.path.join(UPLOAD_FOLDER, filename))

@app.route('/delete/audio/<int:audio_id>', methods=['POST'])
def delete_audio(audio_id):
    """Delete an audio file"""
    audio_file = AudioFile.query.get_or_404(audio_id)
    
    # Delete the actual file
    file_path = os.path.join(UPLOAD_FOLDER, audio_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete associated videos
    for video in audio_file.videos:
        video_path = os.path.join(OUTPUT_FOLDER, video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        db.session.delete(video)
    
    # Delete database record
    db.session.delete(audio_file)
    db.session.commit()
    
    flash('Audio file deleted successfully', 'success')
    return redirect(url_for('library'))

@app.route('/delete/image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    """Delete an image file"""
    image_file = ImageFile.query.get_or_404(image_id)
    
    # Delete the actual file
    file_path = os.path.join(UPLOAD_FOLDER, image_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete associated videos
    for video in image_file.videos:
        video_path = os.path.join(OUTPUT_FOLDER, video.filename)
        if os.path.exists(video_path):
            os.remove(video_path)
        db.session.delete(video)
    
    # Delete database record
    db.session.delete(image_file)
    db.session.commit()
    
    flash('Image file deleted successfully', 'success')
    return redirect(url_for('library'))

@app.route('/delete/video/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    """Delete a video file"""
    video_file = OutputVideo.query.get_or_404(video_id)
    
    # Delete the actual file
    file_path = os.path.join(OUTPUT_FOLDER, video_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete database record
    db.session.delete(video_file)
    db.session.commit()
    
    flash('Video deleted successfully', 'success')
    return redirect(url_for('library'))

@app.errorhandler(RequestEntityTooLarge)
def request_entity_too_large(error):
    flash('File too large. Maximum size is 25MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal server error: {str(error)}")
    flash('An internal server error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default preset if none exists
    if Preset.query.count() == 0:
        default_preset = Preset(name="Default")
        db.session.add(default_preset)
        db.session.commit()

if __name__ == '__main__':
    # Clean up old files before starting
    cleanup_old_files()
    # Start the application
    app.run(host='0.0.0.0', port=5000, debug=False)