# utils/theme_manager.py - Theme Manager that combines both implementations
import os
import json
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

# Get logger
logger = logging.getLogger('BCApp.ThemeManager')

class ThemeManager:
    """Manager for application themes and styling."""
    
    # Theme definitions from your existing implementation
    THEMES = {
        'light': {
            'window': '#F0F0F0',
            'text': '#202020',
            'accent': '#0078D7',
            'highlight': '#E5F1FB',
            'sidebar': '#E0E0E0',
            'button': '#DDDDDD',
            'button_text': '#202020',
        },
        'dark': {
            'window': '#2D2D30',
            'text': '#FFFFFF',
            'accent': '#007ACC',
            'highlight': '#3E3E42',
            'sidebar': '#252526',
            'button': '#333333',
            'button_text': '#FFFFFF',
        },
        'blue': {
            'window': '#ECF4FF',
            'text': '#333333',
            'accent': '#1E88E5',
            'highlight': '#BBDEFB',
            'sidebar': '#DCEDC8',
            'button': '#90CAF9',
            'button_text': '#333333',
        }
    }
    
    def __init__(self, app=None, config=None):
        """
        Initialize the theme manager.
        
        Args:
            app: QApplication instance
            config: Configuration manager instance
        """
        self.app = app
        self.config = config
        self.current_theme_name = "Light"  # Default theme
        
        # Available themes (name -> stylesheet file)
        self.themes = {
            "Light": "light.qss",
            "Dark": "dark.qss",
            "Blue": "blue.qss",
            "High Contrast": "high_contrast.qss"
        }
        
        # Theme-specific colors for programmatic use (Convert your existing THEMES to title case keys)
        self.theme_colors = {
            "Light": {
                "primary": "#0078d7",
                "secondary": "#5c5c5c",
                "background": "#f0f0f0",
                "text": "#333333",
                "success": "#107c10",
                "warning": "#ff8c00",
                "error": "#e81123",
                # Add your existing light theme colors 
                "window": self.THEMES['light']['window'],
                "accent": self.THEMES['light']['accent'],
                "highlight": self.THEMES['light']['highlight'],
                "sidebar": self.THEMES['light']['sidebar'],
                "button": self.THEMES['light']['button'],
                "button_text": self.THEMES['light']['button_text']
            },
            "Dark": {
                "primary": "#3a96dd",
                "secondary": "#a0a0a0",
                "background": "#1e1e1e",
                "text": "#ffffff",
                "success": "#16c60c",
                "warning": "#ffb900",
                "error": "#ff4343",
                # Add your existing dark theme colors
                "window": self.THEMES['dark']['window'],
                "accent": self.THEMES['dark']['accent'],
                "highlight": self.THEMES['dark']['highlight'],
                "sidebar": self.THEMES['dark']['sidebar'],
                "button": self.THEMES['dark']['button'],
                "button_text": self.THEMES['dark']['button_text']
            },
            "Blue": {
                "primary": "#0063B1",
                "secondary": "#4894FE",
                "background": "#EFF6FC",
                "text": "#333333",
                "success": "#107c10",
                "warning": "#ff8c00",
                "error": "#e81123",
                # Add your existing blue theme colors
                "window": self.THEMES['blue']['window'],
                "accent": self.THEMES['blue']['accent'],
                "highlight": self.THEMES['blue']['highlight'],
                "sidebar": self.THEMES['blue']['sidebar'],
                "button": self.THEMES['blue']['button'],
                "button_text": self.THEMES['blue']['button_text']
            },
            "High Contrast": {
                "primary": "#1aebff",
                "secondary": "#ffff00",
                "background": "#000000",
                "text": "#ffffff",
                "success": "#3ff23f",
                "warning": "#ffff00",
                "error": "#ff0000"
            }
        }
        
        # Load last used theme from config
        if self.config:
            self.current_theme_name = self.config.get_setting("theme", "Light")
            logger.info(f"Loaded theme preference from config: {self.current_theme_name}")
    
    def apply_theme(self, theme_name):
        """
        Apply a theme to the application.
        Combined implementation that supports both methods.
        
        Args:
            theme_name: Name of the theme to apply
            
        Returns:
            True if theme was applied successfully, False otherwise
        """
        # First normalize the theme name for lookup
        theme_name_lower = theme_name.lower()
        theme_name_title = theme_name.title()
        
        # Try to find the theme in our theme dictionaries (using case-insensitive comparison)
        if theme_name_lower in [t.lower() for t in self.THEMES.keys()]:
            # Use your existing implementation
            logger.debug(f"Applying theme using basic palette approach: {theme_name}")
            
            # Find the actual theme key with the correct case
            for key in self.THEMES.keys():
                if key.lower() == theme_name_lower:
                    theme_name_lower = key
                    break
                    
            # Apply palette colors from your existing implementation
            theme = self.THEMES.get(theme_name_lower, self.THEMES['light'])
            
            # Create a palette
            palette = QPalette()
            
            # Set colors based on theme
            palette.setColor(QPalette.Window, QColor(theme['window']))
            palette.setColor(QPalette.WindowText, QColor(theme['text']))
            palette.setColor(QPalette.Base, QColor(theme['window']))
            palette.setColor(QPalette.AlternateBase, QColor(theme['highlight']))
            palette.setColor(QPalette.ToolTipBase, QColor(theme['window']))
            palette.setColor(QPalette.ToolTipText, QColor(theme['text']))
            palette.setColor(QPalette.Text, QColor(theme['text']))
            palette.setColor(QPalette.Button, QColor(theme['button']))
            palette.setColor(QPalette.ButtonText, QColor(theme['button_text']))
            palette.setColor(QPalette.BrightText, Qt.white)
            palette.setColor(QPalette.Link, QColor(theme['accent']))
            palette.setColor(QPalette.Highlight, QColor(theme['accent']))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            
            # Apply palette to application
            if self.app:
                self.app.setPalette(palette)
                
            # Update current theme
            self.current_theme_name = theme_name_title
            
            # Update config if available
            if self.config:
                self.config.set_setting("theme", theme_name_title)
                
            return True
        
        # Try the stylesheet approach from my implementation
        if theme_name_title in self.themes:
            try:
                # Find the stylesheet file
                stylesheet_file = self.themes[theme_name_title]
                stylesheet_path = self._get_stylesheet_path(stylesheet_file)
                
                if not stylesheet_path or not os.path.exists(stylesheet_path):
                    logger.error(f"Stylesheet file not found: {stylesheet_path}")
                    return False
                
                # Apply stylesheet to the application
                if self.app:
                    with open(stylesheet_path, 'r') as f:
                        stylesheet = f.read()
                    self.app.setStyleSheet(stylesheet)
                    logger.info(f"Applied theme: {theme_name_title}")
                    
                    # Update current theme
                    self.current_theme_name = theme_name_title
                    
                    # Save to config if available
                    if self.config:
                        self.config.set_setting("theme", theme_name_title)
                        
                    return True
                else:
                    logger.warning("No QApplication instance provided, cannot apply stylesheet")
                    return False
                    
            except Exception as e:
                logger.error(f"Error applying theme '{theme_name_title}': {str(e)}")
                return False
        
        # If we get here, theme wasn't found
        logger.warning(f"Theme '{theme_name}' not found. Available themes: "
                      f"{list(self.THEMES.keys())} or {list(self.themes.keys())}")
        return False
        
    def get_available_themes(self):
        """
        Get the names of all available themes.
        
        Returns:
            List of theme names
        """
        # Combine themes from both implementations, with proper title case
        # Return unique set with title case for consistency
        theme_list = set(self.themes.keys())
        return sorted(list(theme_list))
    
    def get_current_theme(self):
        """
        Get the name of the currently applied theme.
        
        Returns:
            Name of the current theme
        """
        return self.current_theme_name
    
    def get_color(self, color_name):
        """
        Get a color value from the current theme.
        
        Args:
            color_name: Name of the color (e.g., "primary", "background")
            
        Returns:
            Hex color value, or empty string if not found
        """
        try:
            if self.current_theme_name in self.theme_colors:
                theme_palette = self.theme_colors[self.current_theme_name]
                return theme_palette.get(color_name, "")
            return ""
        except Exception as e:
            logger.error(f"Error getting color '{color_name}': {str(e)}")
            return ""
    
    def get_icon_path(self, icon_name, themed=True):
        """
        Get the path to an icon, optionally using theme-specific version.
        
        Args:
            icon_name: Name of the icon file (e.g., "save.png")
            themed: Whether to look for a theme-specific version
            
        Returns:
            Path to the icon file
        """
        try:
            from utils.general_utils import get_resource_path
            
            if themed:
                # Check for theme-specific icon first
                theme_icon_path = get_resource_path(f"icons/{self.current_theme_name.lower()}/{icon_name}")
                if os.path.exists(theme_icon_path):
                    return theme_icon_path
            
            # Fall back to default icon
            return get_resource_path(f"icons/{icon_name}")
        except Exception as e:
            logger.error(f"Error getting icon path for '{icon_name}': {str(e)}")
            return ""
    
    def _get_stylesheet_path(self, stylesheet_file):
        """
        Get the full path to a stylesheet file.
        
        Args:
            stylesheet_file: Name of the stylesheet file
            
        Returns:
            Full path to the stylesheet file
        """
        try:
            from utils.general_utils import get_resource_path
            
            # Check resources/themes directory
            stylesheet_path = get_resource_path(f"themes/{stylesheet_file}")
            
            # If not found, check resources/styles directory
            if not os.path.exists(stylesheet_path):
                stylesheet_path = get_resource_path(f"styles/{stylesheet_file}")
            
            return stylesheet_path
        except Exception as e:
            logger.error(f"Error getting stylesheet path for '{stylesheet_file}': {str(e)}")
            return ""