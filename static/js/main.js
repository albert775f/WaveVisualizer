document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const uploadForm = document.getElementById('upload-form');
    const uploadContainer = document.getElementById('upload-container');
    const processingContainer = document.getElementById('processing-container');
    const successContainer = document.getElementById('success-container');
    const errorContainer = document.getElementById('error-container');
    const errorMessage = document.getElementById('error-message');
    const downloadLink = document.getElementById('download-link');
    const createNewBtn = document.getElementById('create-new-btn');
    const tryAgainBtn = document.getElementById('try-again-btn');
    const progressBar = document.getElementById('progress-bar');
    
    // Session identifier
    let sessionId = null;
    
    // Helper function for API calls with retry
    const fetchWithRetry = (url, options, retries = 3, backoff = 300) => {
        return new Promise((resolve, reject) => {
            const controller = new AbortController();
            const timeout = setTimeout(() => {
                controller.abort();
            }, 30000); // 30 second timeout
            
            const makeRequest = (attemptsLeft) => {
                fetch(url, {...options, signal: controller.signal})
                    .then(response => {
                        clearTimeout(timeout);
                        resolve(response);
                    })
                    .catch(error => {
                        console.log(`Fetch attempt failed: ${error.message}`);
                        
                        if (attemptsLeft > 0) {
                            setTimeout(() => {
                                console.log(`Retrying... ${attemptsLeft} attempts left`);
                                makeRequest(attemptsLeft - 1);
                            }, backoff);
                        } else {
                            clearTimeout(timeout);
                            reject(error);
                        }
                    });
            };
            
            makeRequest(retries);
        });
    };
    
    // Multi-step upload process
    const uploadFiles = async () => {
        try {
            // Validate files
            const audioFile = document.getElementById('audio-file').files[0];
            const imageFile = document.getElementById('image-file').files[0];
            const visualizationColor = document.getElementById('visualization-color').value;
            
            if (!audioFile) {
                showError('Please select an audio file');
                return;
            }
            
            if (!imageFile) {
                showError('Please select a background image');
                return;
            }
            
            // Show processing UI and reset previous errors
            uploadContainer.classList.add('d-none');
            processingContainer.classList.remove('d-none');
            progressBar.style.width = '0%';
            errorContainer.classList.add('d-none');
            
            // Step 1: Get session ID
            updateProgress('Preparing upload...', 5);
            const prepareResponse = await fetchWithRetry('/prepare_upload', { method: 'POST' });
            
            if (!prepareResponse.ok) {
                throw new Error('Failed to prepare upload');
            }
            
            const prepareData = await prepareResponse.json();
            if (prepareData.error) {
                throw new Error(prepareData.error);
            }
            
            sessionId = prepareData.session_id;
            console.log(`Session created: ${sessionId}`);
            
            // Step 2: Upload audio file
            updateProgress('Uploading audio file...', 20);
            const audioFormData = new FormData();
            audioFormData.append('audio_file', audioFile);
            
            const audioResponse = await fetchWithRetry(`/upload_audio/${sessionId}`, {
                method: 'POST',
                body: audioFormData
            });
            
            if (!audioResponse.ok) {
                throw new Error('Failed to upload audio file');
            }
            
            const audioData = await audioResponse.json();
            if (audioData.error) {
                throw new Error(audioData.error);
            }
            
            console.log('Audio uploaded successfully');
            
            // Step 3: Upload image file
            updateProgress('Uploading background image...', 40);
            const imageFormData = new FormData();
            imageFormData.append('image_file', imageFile);
            
            const imageResponse = await fetchWithRetry(`/upload_image/${sessionId}`, {
                method: 'POST',
                body: imageFormData
            });
            
            if (!imageResponse.ok) {
                throw new Error('Failed to upload image file');
            }
            
            const imageData = await imageResponse.json();
            if (imageData.error) {
                throw new Error(imageData.error);
            }
            
            console.log('Image uploaded successfully');
            
            // Step 4: Process files
            updateProgress('Processing visualization...', 60);
            const processFormData = new FormData();
            processFormData.append('visualization_color', visualizationColor);
            
            const processResponse = await fetchWithRetry(`/process/${sessionId}`, {
                method: 'POST',
                body: processFormData
            });
            
            if (!processResponse.ok) {
                throw new Error('Failed to process files');
            }
            
            const processData = await processResponse.json();
            if (processData.error) {
                throw new Error(processData.error);
            }
            
            console.log('Processing completed successfully');
            
            // Update UI with success
            progressBar.style.width = '100%';
            processingContainer.classList.add('d-none');
            successContainer.classList.remove('d-none');
            
            // Set download link
            downloadLink.href = `/download/${processData.output_file}`;
            
        } catch (error) {
            console.error('Error:', error);
            showError(error.message || 'An unexpected error occurred. Please try again.');
        }
    };
    
    // Helper function to update progress
    const updateProgress = (message, percent) => {
        document.querySelector('#processing-container h4').textContent = message;
        progressBar.style.width = `${percent}%`;
    };
    
    // Form submission handler
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Disable the button to prevent multiple submissions
        const submitButton = document.getElementById('generate-btn');
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        
        // Start the upload process
        uploadFiles().finally(() => {
            // Re-enable the button when done
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-wand-magic-sparkles me-2"></i>Generate Video';
        });
    });
    
    // Create new button handler
    createNewBtn.addEventListener('click', function() {
        resetUI();
    });
    
    // Try again button handler
    tryAgainBtn.addEventListener('click', function() {
        resetUI();
    });
    
    // Reset UI to initial state
    function resetUI() {
        uploadForm.reset();
        uploadContainer.classList.remove('d-none');
        processingContainer.classList.add('d-none');
        successContainer.classList.add('d-none');
        errorContainer.classList.add('d-none');
        sessionId = null;
    }
    
    // Show error message
    function showError(message) {
        processingContainer.classList.add('d-none');
        errorContainer.classList.remove('d-none');
        errorMessage.textContent = message;
    }
    
    // Simulate progress with periodic backend checks
    function startProgressSimulation() {
        let progress = 10;
        progressBar.style.width = `${progress}%`;
        
        // Increase progress gradually while checking the real progress
        const progressInterval = setInterval(() => {
            // Increase simulated progress (slower as it gets higher)
            if (progress < 30) {
                progress += 5;
            } else if (progress < 60) {
                progress += 3;
            } else if (progress < 80) {
                progress += 1;
            } else if (progress < 90) {
                progress += 0.5;
            }
            
            if (progress > 95) {
                progress = 95; // Cap at 95% until we get confirmation
            }
            
            progressBar.style.width = `${progress}%`;
            
            // If we have a session ID, check real progress
            if (sessionId) {
                checkProgress(sessionId).then(status => {
                    if (status === 'complete') {
                        progressBar.style.width = '100%';
                        clearInterval(progressInterval);
                    }
                });
            }
        }, 1000);
        
        // Safety timeout to clear interval after 5 minutes
        setTimeout(() => {
            clearInterval(progressInterval);
        }, 5 * 60 * 1000);
    }
    
    // Check progress with backend
    async function checkProgress(sessionId) {
        try {
            const response = await fetch(`/check_progress/${sessionId}`);
            const data = await response.json();
            
            if (data.status === 'complete') {
                return 'complete';
            }
            return 'processing';
        } catch (error) {
            console.error('Error checking progress:', error);
            return 'error';
        }
    }
    
    // File input validation
    const audioFileInput = document.getElementById('audio-file');
    const imageFileInput = document.getElementById('image-file');
    const generateBtn = document.getElementById('generate-btn');
    
    audioFileInput.addEventListener('change', function() {
        validateFileSize(this, 25); // 25MB limit
    });
    
    imageFileInput.addEventListener('change', function() {
        validateFileSize(this, 5); // 5MB limit for images
    });
    
    // Add loading state to button during submission
    uploadForm.addEventListener('submit', function() {
        const btn = document.getElementById('generate-btn');
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
        btn.disabled = true;
    });
    
    function validateFileSize(input, maxSizeMB) {
        if (input.files && input.files[0]) {
            const fileSize = input.files[0].size / (1024 * 1024); // Convert to MB
            if (fileSize > maxSizeMB) {
                alert(`File size exceeds ${maxSizeMB}MB limit. Please choose a smaller file.`);
                input.value = ''; // Clear the input
            }
        }
    }
});
