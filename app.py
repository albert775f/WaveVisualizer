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


@app.route('/')
def index():
    return render_template('index.html')


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
            
        # Check if filename exists before validation
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
            
        # Check if filename exists before validation
        if image_file.filename and not allowed_image_file(image_file.filename):
            flash('Only JPG and PNG images are allowed', 'error')
            return redirect(url_for('index'))
        
        # Create unique ID and save files
        unique_id = str(uuid.uuid4())
        audio_filename = unique_id + '_audio.wav'
        
        # Get file extension safely
        if image_file.filename and '.' in image_file.filename:
            ext = image_file.filename.rsplit('.', 1)[1].lower()
        else:
            ext = 'jpg'  # Default extension
            
        image_filename = unique_id + '_image.' + ext
        
        audio_path = os.path.join(UPLOAD_FOLDER, audio_filename)
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        
        logger.info(f"Saving files: {audio_path}, {image_path}")
        audio_file.save(audio_path)
        image_file.save(image_path)
        
        # Get color from form
        color = request.form.get('visualization_color', '#00FFFF')
        
        # Generate output path
        output_filename = unique_id + '_output.mp4'
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
        
        # Redirect to download page
        return render_template('success.html', filename=output_filename)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        flash('An error occurred while processing your files. Please try again.', 'error')
        return redirect(url_for('index'))


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)


# Simple route to check if a file exists
@app.route('/file_exists/<filename>')
def file_exists(filename):
    from flask import jsonify
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    exists = os.path.exists(file_path)
    return jsonify({"exists": exists})


# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    flash('File too large. Maximum size is 50MB.', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_server_error(error):
    flash('An internal server error occurred. Please try again.', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
