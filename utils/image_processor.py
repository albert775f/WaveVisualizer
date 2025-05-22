import os
import numpy as np
from PIL import Image
import tempfile
import logging

logger = logging.getLogger(__name__)

def ensure_even_dimensions(image_path):
    """
    Makes sure image dimensions are even (required for H.264 encoding)
    
    Args:
        image_path: Path to the image file
    
    Returns:
        Tuple of (path to use, width, height) where path is either the original
        path if dimensions were already even, or a path to a temporary resized copy
    """
    try:
        # Open the image with PIL
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Check if dimensions are already even
            if width % 2 == 0 and height % 2 == 0:
                logger.info(f"Image dimensions already even: {width}x{height}")
                return image_path, width, height
            
            # Calculate new dimensions (always rounding down to keep it simple)
            new_width = width if width % 2 == 0 else width - 1
            new_height = height if height % 2 == 0 else height - 1
            
            logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height} for H.264 compatibility")
            
            # Create a resized copy - use simple bilinear resampling
            resized_img = img.resize((new_width, new_height))
            
            # Save to temp file
            temp_image_path = os.path.join(tempfile.gettempdir(), f"resized_h264_{os.path.basename(image_path)}")
            resized_img.save(temp_image_path)
            
            return temp_image_path, new_width, new_height
    
    except Exception as e:
        logger.error(f"Error processing image dimensions: {str(e)}")
        # Return original in case of error
        return image_path, 0, 0