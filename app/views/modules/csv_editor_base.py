from PyQt5.QtWidgets import QVBoxLayout, QTableWidget, QHeaderView
from PyQt5.QtCore import Qt

class CsvEditorBase:
    def __init__(self):
        """Minimal constructor."""
        # self.table is created in _create_table_section
        pass

    def _create_table_section(self, main_layout: QVBoxLayout):
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setGridStyle(Qt.PenStyle.SolidLine)
        # MODIFIED STYLESHEET
        self.table.setStyleSheet("""
            QTableWidget { 
                gridline-color: #dee2e6; 
                background-color: white; 
                alternate-background-color: #f8f9fa; 
                selection-background-color: #007bff; 
                border: 2px solid #dee2e6; 
                border-radius: 8px; 
            }
            QTableWidget::item { 
                padding: 10px; 
                border-bottom: 1px solid #e9ecef; 
                font-size: 10pt; 
            }
            QTableWidget::item:selected { 
                background-color: #007bff; 
                color: white; 
            }
            QTableWidget::item:hover { 
                background-color: #e3f2fd; 
            }
            QHeaderView::section { 
                background-color: #e9ecef; 
                padding: 12px; 
                border: 1px solid #dee2e6; 
                font-weight: bold; 
                font-size: 11pt; 
                color: #495057; 
            }
            QHeaderView::section:hover { 
                background-color: #dee2e6; 
            }
            /* ADDED: Specific style for the vertical header to ensure visibility */
            QHeaderView::section:vertical {
                text-align: right;
                padding-right: 8px;
                color: #212529; /* Darker color for numbers */
                font-weight: normal;
                font-size: 10pt;
            }
        """)
        self.table.setSortingEnabled(True)
        self.table.cellChanged.connect(self.on_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # ADDED: Explicitly ensure the vertical header is visible
        self.table.verticalHeader().setVisible(True)
        
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        main_layout.addWidget(self.table)

    def on_cell_changed(self, row, column):
        """Minimal handler for cellChanged signal."""
        pass

    def on_cell_double_clicked(self, row, column):
        """Minimal handler for cellDoubleClicked signal."""
        pass
