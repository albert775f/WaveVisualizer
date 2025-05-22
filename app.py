import os
import uuid
import json
import tempfile
import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
import librosa

from models import db, Preset, AudioFile, ImageFile, OutputVideo
from utils.audio_processor import process_audio_visualization

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max upload size
app.config['UPLOAD_FOLDER_AUDIO'] = os.path.join(os.getcwd(), 'uploads', 'audio')
app.config['UPLOAD_FOLDER_IMAGES'] = os.path.join(os.getcwd(), 'uploads', 'images')
app.config['OUTPUT_FOLDER'] = os.path.join(os.getcwd(), 'output')

# Ensure directories exist
for folder in [app.config['UPLOAD_FOLDER_AUDIO'], app.config['UPLOAD_FOLDER_IMAGES'], app.config['OUTPUT_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# Allowed file extensions
ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}

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

@app.route('/upload/audio', methods=['POST'])
def upload_audio():
    """Handle audio file upload"""
    if 'audio' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.referrer or url_for('library'))
    
    file = request.files['audio']
    
    if file.filename == '':
        flash('No audio file selected', 'danger')
        return redirect(request.referrer or url_for('library'))
    
    if file and file.filename and allowed_audio_file(file.filename):
        # Create a unique filename
        filename = secure_filename(file.filename)
        display_name = filename
        unique_filename = f"{uuid.uuid4()}.wav"
        file_path = os.path.join(app.config['UPLOAD_FOLDER_AUDIO'], unique_filename)
        
        file.save(file_path)
        
        # Get audio info
        try:
            y, sr = librosa.load(file_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
            file_size = os.path.getsize(file_path)
            
            # Save to database
            audio_file = AudioFile()
            audio_file.filename = unique_filename
            audio_file.display_name = display_name
            audio_file.file_size = file_size
            audio_file.duration = duration
            db.session.add(audio_file)
            db.session.commit()
            
            flash('Audio file uploaded successfully', 'success')
        except Exception as e:
            flash(f'Error processing audio file: {str(e)}', 'danger')
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        flash('Invalid audio file format. Only WAV files are allowed.', 'danger')
    
    return redirect(request.referrer or url_for('library'))

@app.route('/upload/image', methods=['POST'])
def upload_image():
    """Handle image file upload"""
    if 'image' not in request.files:
        flash('No file part', 'danger')
        return redirect(request.referrer or url_for('library'))
    
    file = request.files['image']
    
    if file.filename == '':
        flash('No image file selected', 'danger')
        return redirect(request.referrer or url_for('library'))
    
    if file and allowed_image_file(file.filename):
        # Create a unique filename
        filename = secure_filename(file.filename)
        display_name = filename
        unique_filename = f"{uuid.uuid4()}.{filename.rsplit('.', 1)[1].lower()}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], unique_filename)
        
        file.save(file_path)
        
        # Get image info
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
            
            file_size = os.path.getsize(file_path)
            
            # Save to database
            image_file = ImageFile()
            image_file.filename = unique_filename
            image_file.display_name = display_name
            image_file.width = width
            image_file.height = height
            image_file.file_size = file_size
            db.session.add(image_file)
            db.session.commit()
            
            flash('Image file uploaded successfully', 'success')
        except Exception as e:
            flash(f'Error processing image file: {str(e)}', 'danger')
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        flash('Invalid image file format. Only JPG and PNG files are allowed.', 'danger')
    
    return redirect(request.referrer or url_for('library'))

@app.route('/create/video', methods=['POST'])
def create_video():
    """Create a video from selected audio and image files"""
    # Get form data
    audio_id = request.form.get('audio_id')
    image_id = request.form.get('image_id')
    preset_id = request.form.get('preset_id')
    
    if not audio_id:
        flash('No audio file selected', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    if not image_id:
        flash('No image file selected', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    # Get files from database
    audio_file = AudioFile.query.get_or_404(audio_id)
    image_file = ImageFile.query.get_or_404(image_id)
    preset = Preset.query.get_or_404(preset_id) if preset_id else Preset.query.first()
    
    audio_path = os.path.join(app.config['UPLOAD_FOLDER_AUDIO'], audio_file.filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image_file.filename)
    
    if not os.path.exists(audio_path):
        flash('Audio file not found on server', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    if not os.path.exists(image_path):
        flash('Image file not found on server', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    # Create a unique filename for the output video
    output_filename = f"{uuid.uuid4()}.mp4"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    
    try:
        # Process the audio and create the video
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
            horizontal_margin=preset.horizontal_margin
        )
        
        # Create output video record
        output_video = OutputVideo()
        output_video.filename = output_filename
        output_video.display_name = f"{audio_file.display_name}_{image_file.display_name}.mp4"
        output_video.audio_file_id = audio_file.id
        output_video.image_file_id = image_file.id
        output_video.preset_id = preset.id if preset_id else None
        db.session.add(output_video)
        db.session.commit()
        
        flash('Video created successfully', 'success')
        return redirect(url_for('library'))
    except Exception as e:
        flash(f'Error creating video: {str(e)}', 'danger')
        if os.path.exists(output_path):
            os.remove(output_path)
        return redirect(request.referrer or url_for('index'))

@app.route('/download/video/<filename>')
def download_file(filename):
    """Download an output video file"""
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)

@app.route('/images/<filename>')
def get_image(filename):
    """Serve an image file for display"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], filename))

@app.route('/delete/audio/<int:audio_id>', methods=['POST'])
def delete_audio(audio_id):
    """Delete an audio file"""
    audio_file = AudioFile.query.get_or_404(audio_id)
    
    # Delete the actual file
    file_path = os.path.join(app.config['UPLOAD_FOLDER_AUDIO'], audio_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete associated videos
    for video in audio_file.videos:
        video_path = os.path.join(app.config['OUTPUT_FOLDER'], video.filename)
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
    file_path = os.path.join(app.config['UPLOAD_FOLDER_IMAGES'], image_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete associated videos
    for video in image_file.videos:
        video_path = os.path.join(app.config['OUTPUT_FOLDER'], video.filename)
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
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], video_file.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete database record
    db.session.delete(video_file)
    db.session.commit()
    
    flash('Video deleted successfully', 'success')
    return redirect(url_for('library'))

@app.errorhandler(RequestEntityTooLarge)
def request_entity_too_large(error):
    flash('File too large. Maximum size is 32MB.', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f'Server Error: {error}')
    flash('An unexpected error occurred. Please try again.', 'danger')
    return redirect(request.referrer or url_for('index'))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default preset if none exists
    if Preset.query.count() == 0:
        default_preset = Preset(name="Default")
        db.session.add(default_preset)
        db.session.commit()