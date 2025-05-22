document.addEventListener('DOMContentLoaded', function() {
    // Initialization code goes here
    
    // Setup form submission with progress for visualization creation
    const createForm = document.getElementById('createForm');
    if (createForm) {
        createForm.addEventListener('submit', function(e) {
            // Show loading indicator
            const submitBtn = document.querySelector('#createForm button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
                submitBtn.disabled = true;
            }
        });
    }
    
    // Color picker preview update
    const colorInput = document.getElementById('color');
    if (colorInput) {
        colorInput.addEventListener('input', function(e) {
            updateColorPreview(this.value);
        });
    }
    
    // Glow effect toggle
    const glowToggle = document.getElementById('glow_effect');
    if (glowToggle) {
        glowToggle.addEventListener('change', function() {
            toggleGlowSettings(this.checked);
        });
    }
    
    // Helper functions for preset form
    window.updateColorPreview = function(color) {
        const preview = document.getElementById('colorPreview');
        if (preview) {
            preview.style.backgroundColor = color;
        }
        const textInput = document.getElementById('colorText');
        if (textInput) {
            textInput.value = color;
        }
    };
    
    window.updateColorInput = function(text) {
        const picker = document.getElementById('color');
        if (picker) {
            picker.value = text;
            updateColorPreview(text);
        }
    };
    
    window.toggleGlowSettings = function(enabled) {
        const glowSettings = document.getElementById('glowSettings');
        if (glowSettings) {
            if (enabled) {
                glowSettings.classList.remove('d-none');
            } else {
                glowSettings.classList.add('d-none');
            }
        }
    };
    
    // AJAX file deletion handlers
    const deleteButtons = document.querySelectorAll('.delete-file-btn');
    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this file?')) {
                e.preventDefault();
            }
        });
    });
});

// Reset UI
function resetUI() {
    const submitBtn = document.querySelector('#createForm button[type="submit"]');
    if (submitBtn) {
        submitBtn.innerHTML = 'Generate Visualization';
        submitBtn.disabled = false;
    }
    
    const errorElement = document.getElementById('error-message');
    if (errorElement) {
        errorElement.style.display = 'none';
    }
}

// Show error message
function showError(message) {
    const errorElement = document.getElementById('error-message');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
    resetUI();
}

// File size validation
function validateFileSize(input, maxSizeMB) {
    const maxSize = maxSizeMB * 1024 * 1024; // Convert to bytes
    if (input.files[0] && input.files[0].size > maxSize) {
        alert(`File size exceeds ${maxSizeMB}MB limit. Please choose a smaller file.`);
        input.value = '';
        return false;
    }
    return true;
}