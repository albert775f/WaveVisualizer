import os
import uuid
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, flash, redirect, url_for
import tempfile
from werkzeug.utils import secure_filename
from utils.audio_processor import process_audio_visualization

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure upload settings
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'audio_viz_uploads')
OUTPUT_FOLDER = os.path.join(tempfile.gettempdir(), 'audio_viz_output')
ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload size

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_audio_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_files():
    # Check if audio file was uploaded
    if 'audio_file' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio_file']
    if audio_file.filename == '':
        return jsonify({'error': 'No audio file selected'}), 400
    
    if not allowed_audio_file(audio_file.filename):
        return jsonify({'error': 'Invalid audio file format. Please upload a WAV file.'}), 400

    # Check if image file was uploaded
    if 'image_file' not in request.files:
        return jsonify({'error': 'No background image provided'}), 400
    
    image_file = request.files['image_file']
    if image_file.filename == '':
        return jsonify({'error': 'No background image selected'}), 400
    
    if not allowed_image_file(image_file.filename):
        return jsonify({'error': 'Invalid image file format. Please upload a JPG or PNG file.'}), 400

    # Generate unique filenames
    session_id = str(uuid.uuid4())
    audio_filename = f"{session_id}_{secure_filename(audio_file.filename)}"
    image_filename = f"{session_id}_{secure_filename(image_file.filename)}"
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
    
    # Save uploaded files
    audio_file.save(audio_path)
    image_file.save(image_path)
    
    # Get visualization color from form
    visualization_color = request.form.get('visualization_color', '#00FFFF')  # Default to cyan
    
    try:
        # Process the audio and image to create visualization
        output_filename = f"{session_id}_output.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        # Process audio visualization
        process_audio_visualization(
            audio_path=audio_path,
            image_path=image_path,
            output_path=output_path,
            color=visualization_color
        )
        
        return jsonify({
            'success': True,
            'message': 'Video generated successfully!',
            'output_file': output_filename
        })
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
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
