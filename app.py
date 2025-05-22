import os
import uuid
import logging
import base64
import json
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
# Use a project-local directory instead of system temp directory
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # 30 MB max upload size

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


@app.route('/prepare_upload', methods=['POST'])
def prepare_upload():
    """First step - create session ID and get ready for file upload"""
    try:
        # Create a new session ID
        session_id = str(uuid.uuid4())
        
        # Create session directory
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        logger.info(f"Created session: {session_id}")
        
        return jsonify({
            'success': True,
            'session_id': session_id
        })
    except Exception as e:
        logger.error(f"Error preparing upload session: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error preparing upload: {str(e)}'}), 500


@app.route('/upload_audio/<session_id>', methods=['POST'])
def upload_audio(session_id):
    """Second step - upload audio file"""
    try:
        # Validate session_id
        if not session_id or not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], session_id)):
            return jsonify({'error': 'Invalid session ID'}), 400
            
        # Check if audio file was uploaded
        if 'audio_file' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio_file']
        if not audio_file.filename or audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        if not allowed_audio_file(audio_file.filename or ''):
            return jsonify({'error': 'Invalid audio file format. Please upload a WAV file.'}), 400
            
        # Save audio file
        audio_file_name = audio_file.filename if audio_file.filename else ''
        audio_filename = f"audio_{secure_filename(audio_file_name)}"
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, audio_filename)
        
        logger.info(f"Saving audio file: {audio_path}")
        audio_file.save(audio_path)
        
        if not os.path.exists(audio_path):
            return jsonify({'error': 'Failed to save audio file'}), 500
            
        return jsonify({
            'success': True,
            'message': 'Audio file uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Error uploading audio: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error uploading audio: {str(e)}'}), 500


@app.route('/upload_image/<session_id>', methods=['POST'])
def upload_image(session_id):
    """Third step - upload image file"""
    try:
        # Validate session_id
        if not session_id or not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], session_id)):
            return jsonify({'error': 'Invalid session ID'}), 400
            
        # Check if image file was uploaded
        if 'image_file' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400
        
        image_file = request.files['image_file']
        if not image_file.filename or image_file.filename == '':
            return jsonify({'error': 'No image file selected'}), 400
        
        if not allowed_image_file(image_file.filename or ''):
            return jsonify({'error': 'Invalid image format. Please upload a JPG or PNG file.'}), 400
            
        # Save image file
        image_file_name = image_file.filename if image_file.filename else ''
        image_filename = f"image_{secure_filename(image_file_name)}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, image_filename)
        
        logger.info(f"Saving image file: {image_path}")
        image_file.save(image_path)
        
        if not os.path.exists(image_path):
            return jsonify({'error': 'Failed to save image file'}), 500
            
        return jsonify({
            'success': True,
            'message': 'Image file uploaded successfully'
        })
    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error uploading image: {str(e)}'}), 500


@app.route('/process/<session_id>', methods=['POST'])
def process_files(session_id):
    """Final step - process the files"""
    try:
        # Validate session_id
        session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        if not session_id or not os.path.exists(session_dir):
            return jsonify({'error': 'Invalid session ID'}), 400
            
        # Find files in the session directory
        files = os.listdir(session_dir)
        
        audio_file = None
        image_file = None
        
        for file in files:
            if file.startswith('audio_'):
                audio_file = file
            elif file.startswith('image_'):
                image_file = file
        
        if not audio_file:
            return jsonify({'error': 'Audio file not found. Please upload again.'}), 400
            
        if not image_file:
            return jsonify({'error': 'Image file not found. Please upload again.'}), 400
            
        # Get full paths
        audio_path = os.path.join(session_dir, audio_file)
        image_path = os.path.join(session_dir, image_file)
        
        # Get visualization color
        visualization_color = request.form.get('visualization_color', '#00FFFF')  # Default to cyan
        logger.info(f"Using visualization color: {visualization_color}")
        
        # Prepare output path
        output_filename = f"{session_id}_output.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        logger.info("Starting audio visualization processing")
        
        # Process the visualization
        process_audio_visualization(
            audio_path=audio_path,
            image_path=image_path,
            output_path=output_path,
            color=visualization_color
        )
        
        logger.info(f"Video generated successfully: {output_filename}")
        return jsonify({
            'success': True,
            'message': 'Video generated successfully!',
            'output_file': output_filename
        })
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error processing files: {str(e)}'}), 500


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
