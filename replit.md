# Audio Spectrum Video Generator

## Overview

This application is a web-based tool that generates videos with audio spectrum visualizations overlaid on background images. Users can upload audio files (WAV format) and background images, customize visualization options, and download the resulting videos. The system processes the audio to extract frequency data and creates frame-by-frame visualizations that are combined into a video file.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application uses a Flask-based backend with a simple HTML/CSS/JavaScript frontend. The core functionality is implemented in Python, leveraging libraries for audio processing (librosa), visualization (matplotlib), and video generation (ffmpeg).

### Backend Architecture

- **Flask Web Application**: Handles HTTP requests, file uploads, and serves static content
- **Audio Processing Module**: Uses librosa to analyze audio files and generate visualization data
- **Video Generation**: Uses matplotlib for frame generation and ffmpeg for video assembly

The application follows a request-response pattern where:
1. User uploads files via the web interface
2. Server processes the audio and generates visualization frames
3. Frames are combined with the background image into a video
4. The resulting video is served back to the user for download

### Frontend Architecture

- **HTML Templates**: Simple Bootstrap-based UI with form elements for file upload and customization
- **JavaScript**: Handles form submission, displays progress information, and manages download of results
- **CSS**: Custom styling to enhance the Bootstrap defaults

## Key Components

### 1. Flask Application (`app.py` and `main.py`)

The main entry point and request handler. It:
- Initializes the Flask application
- Defines routes for the web interface
- Handles file uploads and validation
- Manages temporary file storage
- Sets up configuration (e.g., upload limits, allowed file types)

### 2. Audio Processing (`utils/audio_processor.py`)

Core functionality for generating visualizations. It:
- Loads audio files using librosa
- Processes audio data to extract frequency information
- Generates visualization frames using matplotlib
- Combines frames with background images
- Uses ffmpeg to assemble the final video

### 3. Web Frontend (`templates/index.html`, `static/js/main.js`, `static/css/style.css`)

User interface components that:
- Provide file upload forms
- Allow customization of visualization parameters
- Display processing status and progress
- Handle download of completed videos
- Show error messages when issues occur

## Data Flow

1. **Input**: 
   - WAV audio file uploaded by user
   - Background image (JPG/PNG) uploaded by user
   - Customization parameters (colors, FPS)

2. **Processing**:
   - Files are saved to temporary storage
   - Audio is analyzed with librosa to extract frequency data
   - Visualization frames are generated with matplotlib
   - Frames are combined with the background image

3. **Output**:
   - MP4 video file with audio visualization
   - Made available for download to the user

## External Dependencies

### Core Python Libraries
- **Flask**: Web framework
- **Librosa**: Audio analysis
- **Matplotlib**: Visualization generation
- **NumPy**: Numerical processing
- **FFmpeg-Python**: Video generation
- **Werkzeug**: File handling utilities

### External Services
- **Bootstrap CDN**: UI framework loaded from CDN
- **Font Awesome CDN**: Icons loaded from CDN

## Deployment Strategy

The application is configured to run on Replit with:
- **Gunicorn**: WSGI HTTP server to handle production traffic
- **Port configuration**: Binds to 0.0.0.0:5000
- **Nix packages**: Required system dependencies (cairo, ffmpeg-full, etc.)

The deployment uses the following settings:
- Auto-scaling enabled
- Port 5000 exposed for web traffic
- Workflow configured to automatically start the application

### Development vs Production

- **Development**: Uses Flask's built-in development server with debug mode
- **Production**: Uses Gunicorn with multiple workers and port reuse

### Data Storage

- The application uses temporary file storage for processing
- No persistent database is currently implemented
- Files are stored in the system's temporary directory
- Consider implementing proper storage for a production environment

## Future Enhancements

1. **User Authentication**: Add user accounts to save generated videos
2. **Database Integration**: Store user preferences and history
3. **Additional Visualization Types**: Support more visualization styles beyond basic spectrum
4. **Audio Format Support**: Expand beyond WAV to support MP3, FLAC, etc.
5. **Enhanced Customization**: More options for colors, effects, and visualization styles