import os
import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Preset(db.Model):
    """Visualization preset settings that users can save and reuse"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Visualization settings
    color = db.Column(db.String(20), default="#00FFFF")  # Color of bars
    bar_count = db.Column(db.Integer, default=64)  # Number of bars
    bar_width_ratio = db.Column(db.Float, default=0.8)  # Ratio of bar width to spacing
    bar_height_scale = db.Column(db.Float, default=1.0)  # Multiplier for bar height
    
    # Effects settings
    glow_effect = db.Column(db.Boolean, default=False)  # Add glow around bars
    glow_intensity = db.Column(db.Float, default=0.5)  # Intensity of glow effect
    
    # Animation settings
    responsiveness = db.Column(db.Float, default=1.0)  # How responsive bars are to audio
    smoothing = db.Column(db.Float, default=0.2)  # Smoothing between frames
    
    # Position settings
    vertical_position = db.Column(db.Float, default=0.5)  # 0.0 = top, 1.0 = bottom
    horizontal_margin = db.Column(db.Float, default=0.1)  # Margin from sides (0.0-0.5)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'color': self.color,
            'bar_count': self.bar_count,
            'bar_width_ratio': self.bar_width_ratio,
            'bar_height_scale': self.bar_height_scale,
            'glow_effect': self.glow_effect,
            'glow_intensity': self.glow_intensity,
            'responsiveness': self.responsiveness,
            'smoothing': self.smoothing,
            'vertical_position': self.vertical_position,
            'horizontal_margin': self.horizontal_margin
        }

class AudioFile(db.Model):
    """Uploaded audio files"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)  # Size in bytes
    duration = db.Column(db.Float)  # Duration in seconds
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ImageFile(db.Model):
    """Uploaded background images"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    file_size = db.Column(db.Integer)  # Size in bytes
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class OutputVideo(db.Model):
    """Generated output videos"""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    audio_file_id = db.Column(db.Integer, db.ForeignKey('audio_file.id'))
    image_file_id = db.Column(db.Integer, db.ForeignKey('image_file.id'))
    preset_id = db.Column(db.Integer, db.ForeignKey('preset.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    audio_file = db.relationship('AudioFile', backref='videos')
    image_file = db.relationship('ImageFile', backref='videos')
    preset = db.relationship('Preset', backref='videos')