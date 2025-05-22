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
    
    // Form submission handler
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate files before submission
        const audioFile = document.getElementById('audio-file').files[0];
        const imageFile = document.getElementById('image-file').files[0];
        
        if (!audioFile) {
            showError('Please select an audio file');
            return;
        }
        
        if (!imageFile) {
            showError('Please select a background image');
            return;
        }
        
        // Show processing UI
        uploadContainer.classList.add('d-none');
        processingContainer.classList.remove('d-none');
        progressBar.style.width = '0%';
        
        // Reset any previous errors
        errorContainer.classList.add('d-none');
        
        // Get form data
        const formData = new FormData(uploadForm);
        
        // Add timeout and retry logic for better reliability
        const fetchWithRetry = (url, options, retries = 3, backoff = 300) => {
            return new Promise((resolve, reject) => {
                const controller = new AbortController();
                const timeout = setTimeout(() => {
                    controller.abort();
                }, 60000); // 60 second timeout
                
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
        
        // Send AJAX request with retry mechanism
        fetchWithRetry('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                // Show error
                showError(data.error);
            } else {
                // Extract session ID from filename for progress checking
                const outputFile = data.output_file;
                sessionId = outputFile.split('_')[0];
                
                // Show success UI
                processingContainer.classList.add('d-none');
                successContainer.classList.remove('d-none');
                
                // Set download link
                downloadLink.href = `/download/${outputFile}`;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Network error or upload timeout. Please try again with smaller files or check your connection.');
        });
        
        // Start progress checking animation
        startProgressSimulation();
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
