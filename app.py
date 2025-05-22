import os
import uuid
import logging
import time
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory, flash, redirect, url_for
import tempfile
import shutil
from werkzeug.utils import secure_filename
from utils.audio_processor import process_audio_visualization

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure upload settings
# Use simple directory paths
UPLOAD_FOLDER = './uploads'
OUTPUT_FOLDER = './output'
ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
# Reduce max size to avoid timeouts
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB max upload size

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Clean any previous files to avoid disk space issues
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Increase request timeouts and buffer size
from werkzeug.serving import WSGIRequestHandler
WSGIRequestHandler.protocol_version = "HTTP/1.1"


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
        
        # Check if audio file was uploaded
        if 'audio_file' not in request.files:
            logger.warning("No audio file provided in request")
            flash('No audio file provided', 'error')
            return redirect(url_for('index'))
        
        audio_file = request.files['audio_file']
        if not audio_file.filename or audio_file.filename == '':
            logger.warning("Empty audio filename")
            flash('No audio file selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_audio_file(audio_file.filename or ''):
            logger.warning(f"Invalid audio format: {audio_file.filename}")
            flash('Invalid audio file format. Please upload a WAV file.', 'error')
            return redirect(url_for('index'))

        # Check if image file was uploaded
        if 'image_file' not in request.files:
            logger.warning("No image file provided in request")
            flash('No background image provided', 'error')
            return redirect(url_for('index'))
        
        image_file = request.files['image_file']
        if not image_file.filename or image_file.filename == '':
            logger.warning("Empty image filename")
            flash('No background image selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_image_file(image_file.filename or ''):
            logger.warning(f"Invalid image format: {image_file.filename}")
            flash('Invalid image file format. Please upload a JPG or PNG file.', 'error')
            return redirect(url_for('index'))

        # Generate unique filenames
        session_id = str(uuid.uuid4())
        
        # Make sure filenames are not None before secure_filename
        audio_file_name = audio_file.filename if audio_file.filename else ''
        image_file_name = image_file.filename if image_file.filename else ''
        
        audio_filename = f"{session_id}_{secure_filename(audio_file_name)}"
        image_filename = f"{session_id}_{secure_filename(image_file_name)}"
        
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        
        logger.debug(f"Saving audio to {audio_path}")
        logger.debug(f"Saving image to {image_path}")
        
        # Save uploaded files
        audio_file.save(audio_path)
        image_file.save(image_path)
        
        if not os.path.exists(audio_path):
            logger.error(f"Failed to save audio file to {audio_path}")
            flash('Failed to save audio file', 'error')
            return redirect(url_for('index'))
            
        if not os.path.exists(image_path):
            logger.error(f"Failed to save image file to {image_path}")
            flash('Failed to save image file', 'error')
            return redirect(url_for('index'))
        
        # Get visualization color from form
        visualization_color = request.form.get('visualization_color', '#00FFFF')  # Default to cyan
        logger.info(f"Using visualization color: {visualization_color}")
        
        # Process the audio and image to create visualization
        output_filename = f"{session_id}_output.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        logger.info("Starting audio visualization processing")
        
        # Process audio visualization
        process_audio_visualization(
            audio_path=audio_path,
            image_path=image_path,
            output_path=output_path,
            color=visualization_color
        )
        
        logger.info(f"Video generated successfully: {output_filename}")
        
        # Redirect to a success page
        return render_template('success.html', filename=output_filename)
        
    except Exception as e:
        logger.error(f"Error during upload/processing: {str(e)}", exc_info=True)
        flash(f'Error processing files: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)


@app.route('/check_progress/<session_id>')
def check_progress(session_id):
    # In a real application, you might have a database to track progress
    # For this simple implementation, we just check if the output file exists
    output_filename = f"{session_id}_output.mp4"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
    
    if os.path.exists(output_path):
        return jsonify({
            'status': 'complete',
            'output_file': output_filename
        })
    else:
        return jsonify({
            'status': 'processing'
        })


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
