import os
import uuid
import logging
import datetime
import json
from flask import Flask, render_template, request, send_from_directory, flash, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from utils.audio_processor import process_audio_visualization

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure upload settings - use absolute paths for more reliability
base_dir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(base_dir, 'uploads')
AUDIO_FOLDER = os.path.join(UPLOAD_FOLDER, 'audio')
IMAGE_FOLDER = os.path.join(UPLOAD_FOLDER, 'images')
OUTPUT_FOLDER = os.path.join(base_dir, 'output')
METADATA_FILE = os.path.join(base_dir, 'metadata.json')

ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB max audio file size
MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5 MB max image file size

# Create necessary directories
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configure Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['IMAGE_FOLDER'] = IMAGE_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_AUDIO_SIZE  # Set to the largest allowed file

# Initialize metadata file if it doesn't exist
if not os.path.exists(METADATA_FILE):
    with open(METADATA_FILE, 'w') as f:
        json.dump({
            'audio_files': [],
            'image_files': [],
            'output_files': []
        }, f)


def allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


# Helper functions to manage metadata
def get_metadata():
    try:
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file is missing or corrupted, create a new one
        metadata = {
            'audio_files': [],
            'image_files': [],
            'output_files': []
        }
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f)
        return metadata

def save_metadata(metadata):
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)

def format_file_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

@app.route('/')
def index():
    # Redirect to the library page
    return redirect(url_for('library'))

@app.route('/library')
def library():
    """Media library page for managing files"""
    # Get metadata for all files
    metadata = get_metadata()
    
    return render_template('library.html', 
                          audio_files=metadata['audio_files'],
                          image_files=metadata['image_files'],
                          output_files=metadata['output_files'])

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    """Handle audio file upload"""
    try:
        # Check if audio file was uploaded
        if 'audio_file' not in request.files:
            flash('No audio file provided', 'error')
            return redirect(url_for('library'))
            
        audio_file = request.files['audio_file']
        if not audio_file.filename or audio_file.filename == '':
            flash('No audio file selected', 'error')
            return redirect(url_for('library'))
            
        # Validate file type
        if not allowed_audio_file(audio_file.filename):
            flash('Only WAV audio files are allowed', 'error')
            return redirect(url_for('library'))
            
        # Check file size
        file_size = 0
        audio_file.seek(0, os.SEEK_END)
        file_size = audio_file.tell()
        audio_file.seek(0)  # Reset file pointer
        
        if file_size > MAX_AUDIO_SIZE:
            flash(f'Audio file too large. Maximum size is {format_file_size(MAX_AUDIO_SIZE)}', 'error')
            return redirect(url_for('library'))
            
        # Generate a unique filename
        unique_id = str(uuid.uuid4())
        original_ext = audio_file.filename.rsplit('.', 1)[1].lower()
        audio_filename = f"{unique_id}.{original_ext}"
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        
        # Get display name from form or use original filename
        display_name = request.form.get('audio_name', '').strip()
        if not display_name:
            display_name = os.path.splitext(audio_file.filename)[0]
            
        # Save the file
        logger.info(f"Saving audio file: {audio_path}")
        audio_file.save(audio_path)
        
        # Update metadata
        metadata = get_metadata()
        metadata['audio_files'].append({
            'filename': audio_filename,
            'display_name': display_name,
            'original_name': audio_file.filename,
            'size': format_file_size(file_size),
            'uploaded_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_metadata(metadata)
        
        flash('Audio file uploaded successfully', 'success')
        return redirect(url_for('library'))
        
    except Exception as e:
        logger.error(f"Error uploading audio: {str(e)}", exc_info=True)
        flash(f'Error uploading audio file: {str(e)}', 'error')
        return redirect(url_for('library'))

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """Handle image file upload"""
    try:
        # Check if image file was uploaded
        if 'image_file' not in request.files:
            flash('No image file provided', 'error')
            return redirect(url_for('library'))
            
        image_file = request.files['image_file']
        if not image_file.filename or image_file.filename == '':
            flash('No image file selected', 'error')
            return redirect(url_for('library'))
            
        # Validate file type
        if not allowed_image_file(image_file.filename):
            flash('Only JPG and PNG images are allowed', 'error')
            return redirect(url_for('library'))
            
        # Check file size
        file_size = 0
        image_file.seek(0, os.SEEK_END)
        file_size = image_file.tell()
        image_file.seek(0)  # Reset file pointer
        
        if file_size > MAX_IMAGE_SIZE:
            flash(f'Image file too large. Maximum size is {format_file_size(MAX_IMAGE_SIZE)}', 'error')
            return redirect(url_for('library'))
            
        # Generate a unique filename
        unique_id = str(uuid.uuid4())
        original_ext = image_file.filename.rsplit('.', 1)[1].lower()
        image_filename = f"{unique_id}.{original_ext}"
        image_path = os.path.join(IMAGE_FOLDER, image_filename)
        
        # Get display name from form or use original filename
        display_name = request.form.get('image_name', '').strip()
        if not display_name:
            display_name = os.path.splitext(image_file.filename)[0]
            
        # Save the file
        logger.info(f"Saving image file: {image_path}")
        image_file.save(image_path)
        
        # Update metadata
        metadata = get_metadata()
        metadata['image_files'].append({
            'filename': image_filename,
            'display_name': display_name,
            'original_name': image_file.filename,
            'size': format_file_size(file_size),
            'uploaded_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_metadata(metadata)
        
        flash('Image file uploaded successfully', 'success')
        return redirect(url_for('library'))
        
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}", exc_info=True)
        flash(f'Error uploading image file: {str(e)}', 'error')
        return redirect(url_for('library'))

@app.route('/create_video', methods=['POST'])
def create_video():
    """Create a video from selected audio and image files"""
    try:
        # Get selected files from the form
        audio_filename = request.form.get('audio_filename')
        image_filename = request.form.get('image_filename')
        visualization_color = request.form.get('visualization_color', '#00FFFF')
        output_name = request.form.get('output_name', '').strip()
        
        if not audio_filename or not image_filename:
            flash('Please select both an audio file and a background image', 'error')
            return redirect(url_for('library'))
            
        # Get full paths to files
        audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
        image_path = os.path.join(IMAGE_FOLDER, image_filename)
        
        # Check if files exist
        if not os.path.exists(audio_path):
            flash('The selected audio file could not be found', 'error')
            return redirect(url_for('library'))
            
        if not os.path.exists(image_path):
            flash('The selected background image could not be found', 'error')
            return redirect(url_for('library'))
            
        # Generate a unique filename for output
        unique_id = str(uuid.uuid4())
        output_filename = f"{unique_id}.mp4"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        # Process the visualization
        logger.info(f"Creating visualization with color: {visualization_color}")
        process_audio_visualization(
            audio_path=audio_path,
            image_path=image_path,
            output_path=output_path,
            color=visualization_color
        )
        
        # Get display name for the output file
        if not output_name:
            # If no name provided, use audio + image names
            metadata = get_metadata()
            audio_info = next((a for a in metadata['audio_files'] if a['filename'] == audio_filename), None)
            image_info = next((i for i in metadata['image_files'] if i['filename'] == image_filename), None)
            
            audio_name = audio_info['display_name'] if audio_info else 'Audio'
            image_name = image_info['display_name'] if image_info else 'Image'
            output_name = f"{audio_name} + {image_name}"
        
        # Update metadata
        metadata = get_metadata()
        metadata['output_files'].append({
            'filename': output_filename,
            'display_name': output_name,
            'audio_filename': audio_filename,
            'image_filename': image_filename,
            'color': visualization_color,
            'created_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        save_metadata(metadata)
        
        flash('Video created successfully!', 'success')
        return redirect(url_for('library'))
        
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}", exc_info=True)
        flash(f'Error creating video: {str(e)}', 'error')
        return redirect(url_for('library'))


@app.route('/download/<filename>')
def download_file(filename):
    """Download an output video file"""
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)

@app.route('/get_image/<filename>')
def get_image(filename):
    """Serve an image file for display"""
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)

@app.route('/delete_audio/<filename>')
def delete_audio(filename):
    """Delete an audio file"""
    try:
        file_path = os.path.join(AUDIO_FOLDER, filename)
        
        # Check if file exists
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Update metadata
            metadata = get_metadata()
            metadata['audio_files'] = [f for f in metadata['audio_files'] if f['filename'] != filename]
            save_metadata(metadata)
            
            flash('Audio file deleted successfully', 'success')
        else:
            flash('Audio file not found', 'error')
            
        return redirect(url_for('library'))
    except Exception as e:
        logger.error(f"Error deleting audio file: {str(e)}", exc_info=True)
        flash(f'Error deleting audio file: {str(e)}', 'error')
        return redirect(url_for('library'))

@app.route('/delete_image/<filename>')
def delete_image(filename):
    """Delete an image file"""
    try:
        file_path = os.path.join(IMAGE_FOLDER, filename)
        
        # Check if file exists
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Update metadata
            metadata = get_metadata()
            metadata['image_files'] = [f for f in metadata['image_files'] if f['filename'] != filename]
            save_metadata(metadata)
            
            flash('Image file deleted successfully', 'success')
        else:
            flash('Image file not found', 'error')
            
        return redirect(url_for('library'))
    except Exception as e:
        logger.error(f"Error deleting image file: {str(e)}", exc_info=True)
        flash(f'Error deleting image file: {str(e)}', 'error')
        return redirect(url_for('library'))

@app.route('/delete_video/<filename>')
def delete_video(filename):
    """Delete a video file"""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        
        # Check if file exists
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Update metadata
            metadata = get_metadata()
            metadata['output_files'] = [f for f in metadata['output_files'] if f['filename'] != filename]
            save_metadata(metadata)
            
            flash('Video deleted successfully', 'success')
        else:
            flash('Video file not found', 'error')
            
        return redirect(url_for('library'))
    except Exception as e:
        logger.error(f"Error deleting video file: {str(e)}", exc_info=True)
        flash(f'Error deleting video file: {str(e)}', 'error')
        return redirect(url_for('library'))

# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Please check size limits.', 'error')
    return redirect(url_for('library'))

@app.errorhandler(500)
def internal_server_error(error):
    flash('An internal server error occurred. Please try again.', 'error')
    return redirect(url_for('library'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
