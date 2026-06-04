import os
import sys
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox,
    QMessageBox, QTabWidget, QWidget, QSizePolicy, QSpacerItem, QToolButton, QStyle
)
from PyQt5.QtCore import Qt, QCoreApplication, QProcess, pyqtSignal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ui.base_window import BaseWindow
from utils import ConfigManager


class SettingsWindow(BaseWindow):
    settings_closed = pyqtSignal()
    settings_saved = pyqtSignal()

    def __init__(self):
        """Initialize the settings window."""
        super().__init__('Settings', 700, 700)
        self.schema = ConfigManager.get_schema()
        self.init_settings_ui()

    def init_settings_ui(self):
        """Initialize the settings user interface."""
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        self.create_tabs()
        self.create_buttons()

    def create_tabs(self):
        """Create tabs for each category in the schema."""
        for category, settings in self.schema.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            tab.setLayout(tab_layout)
            self.tabs.addTab(tab, category.replace('_', ' ').capitalize())

            self.create_settings_widgets(tab_layout, category, settings)
            tab_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def create_settings_widgets(self, layout, category, settings):
        """Create widgets for each setting in a category."""
        for sub_category, sub_settings in settings.items():
            if isinstance(sub_settings, dict) and 'value' in sub_settings:
                self.add_setting_widget(layout, sub_category, sub_settings, category)
            else:
                for key, meta in sub_settings.items():
                    self.add_setting_widget(layout, key, meta, category, sub_category)

    def create_buttons(self):
        """Create reset and save buttons."""
        reset_button = QPushButton('Reset to saved settings')
        reset_button.clicked.connect(self.reset_settings)
        self.main_layout.addWidget(reset_button)

        save_button = QPushButton('Save')
        save_button.clicked.connect(self.save_settings)
        self.main_layout.addWidget(save_button)

    def add_setting_widget(self, layout, key, meta, category, sub_category=None):
        """Add a setting widget to the layout."""
        item_layout = QHBoxLayout()
        label = QLabel(f"{key.replace('_', ' ').capitalize()}:")
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        widget = self.create_widget_for_type(key, meta, category, sub_category)
        if not widget:
            return

        help_button = self.create_help_button(meta.get('description', ''))

        item_layout.addWidget(label)
        item_layout.addWidget(widget)
        item_layout.addWidget(help_button)
        layout.addLayout(item_layout)

        widget_name = f"{category}_{sub_category}_{key}_input" if sub_category else f"{category}_{key}_input"
        label_name = f"{category}_{sub_category}_{key}_label" if sub_category else f"{category}_{key}_label"
        help_name = f"{category}_{sub_category}_{key}_help" if sub_category else f"{category}_{key}_help"

        label.setObjectName(label_name)
        help_button.setObjectName(help_name)
        widget.setObjectName(widget_name)

    def create_widget_for_type(self, key, meta, category, sub_category):
        """Create a widget based on the meta type."""
        meta_type = meta.get('type')
        current_value = self.get_config_value(category, sub_category, key, meta)

        if meta_type == 'bool':
            return self.create_checkbox(current_value)
        elif meta_type == 'str' and 'options' in meta:
            return self.create_combobox(current_value, meta['options'])
        elif meta_type == 'str':
            return QLineEdit(current_value or '')
        elif meta_type in ['int', 'float']:
            return QLineEdit(str(current_value))
        return None

    def create_checkbox(self, value):
        widget = QCheckBox()
        widget.setChecked(value)
        return widget

    def create_combobox(self, value, options):
        widget = QComboBox()
        widget.addItems(options)
        widget.setCurrentText(value)
        return widget

    def create_help_button(self, description):
        help_button = QToolButton()
        help_button.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxQuestion))
        help_button.setAutoRaise(True)
        help_button.setToolTip(description)
        help_button.setCursor(Qt.PointingHandCursor)
        help_button.setFocusPolicy(Qt.TabFocus)
        help_button.clicked.connect(lambda: self.show_description(description))
        return help_button

    def get_config_value(self, category, sub_category, key, meta):
        if sub_category:
            return ConfigManager.get_config_value(category, sub_category, key) or meta['value']
        return ConfigManager.get_config_value(category, key) or meta['value']

    def show_description(self, description):
        QMessageBox.information(self, 'Description', description)

    def save_settings(self):
        """Save the settings to the config file."""
        self.iterate_settings(self.save_setting)
        ConfigManager.save_config()
        QMessageBox.information(self, 'Settings Saved', 'Settings have been saved. The application will now restart.')
        self.settings_saved.emit()
        self.close()

    def save_setting(self, widget, category, sub_category, key, meta):
        value = self.get_widget_value_typed(widget, meta.get('type'))
        if sub_category:
            ConfigManager.set_config_value(value, category, sub_category, key)
        else:
            ConfigManager.set_config_value(value, category, key)

    def reset_settings(self):
        """Reset the settings to the saved values."""
        ConfigManager.reload_config()
        self.update_widgets_from_config()

    def update_widgets_from_config(self):
        self.iterate_settings(self.update_widget_value)

    def update_widget_value(self, widget, category, sub_category, key, meta):
        if sub_category:
            config_value = ConfigManager.get_config_value(category, sub_category, key)
        else:
            config_value = ConfigManager.get_config_value(category, key)
        self.set_widget_value(widget, config_value, meta.get('type'))

    def set_widget_value(self, widget, value, value_type):
        if isinstance(widget, QCheckBox):
            widget.setChecked(value)
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value) if value is not None else '')

    def get_widget_value_typed(self, widget, value_type):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QComboBox):
            return widget.currentText() or None
        elif isinstance(widget, QLineEdit):
            text = widget.text()
            if value_type == 'int':
                return int(text) if text else None
            elif value_type == 'float':
                return float(text) if text else None
            else:
                return text or None
        return None

    def iterate_settings(self, func):
        """Iterate over all settings and apply a function to each."""
        for category, settings in self.schema.items():
            for sub_category, sub_settings in settings.items():
                if isinstance(sub_settings, dict) and 'value' in sub_settings:
                    widget = self.findChild(QWidget, f"{category}_{sub_category}_input")
                    if widget:
                        func(widget, category, None, sub_category, sub_settings)
                else:
                    for key, meta in sub_settings.items():
                        widget = self.findChild(QWidget, f"{category}_{sub_category}_{key}_input")
                        if widget:
                            func(widget, category, sub_category, key, meta)

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            'Close without saving?',
            'Are you sure you want to close without saving?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            ConfigManager.reload_config()
            self.update_widgets_from_config()
            self.settings_closed.emit()
            super().closeEvent(event)
        else:
            event.ignore()
