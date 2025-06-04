def init_ui(self):
        self.logger.debug(f"{self.MODULE_DISPLAY_NAME} init_ui: Starting UI initialization (overwrite method).")

        content_area = self.get_content_container()

        # Clear existing layout from content_area to prevent issues if init_ui is called multiple times
        existing_layout = content_area.layout()
        if existing_layout:
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            existing_layout.deleteLater()

        content_area_layout = QVBoxLayout(content_area) # Set new layout for content_area
        content_area.setLayout(content_area_layout)

        content_area_layout.setContentsMargins(0,0,0,0)
        content_area_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        form_scroll_content_widget = QWidget()
        content_layout = QVBoxLayout(form_scroll_content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(15, 15, 15, 15)

        # --- Custom Header Elements Integration ---
        self.logo_label = QLabel()
        logo_resource_path = "images/logo.png"
        final_logo_path = None
        if self.main_window and hasattr(self.main_window, 'config') and hasattr(self.main_window.config, 'get_resource_path') and callable(self.main_window.config.get_resource_path):
            final_logo_path = self.main_window.config.get_resource_path(logo_resource_path)
        elif self.config and hasattr(self.config, 'get_resource_path') and callable(self.config.get_resource_path):
             final_logo_path = self.config.get_resource_path(logo_resource_path)
        else:
            script_dir_try = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else "."
            path_options = [
                os.path.join(self._data_path, "logo.png"), os.path.join(script_dir_try, "logo.png"),
                os.path.join(script_dir_try, "..", "resources", "images", "logo.png"),
                os.path.join(script_dir_try, "..", "..", "resources", "images", "logo.png"), "logo.png"
            ]
            for path_try in path_options:
                if os.path.exists(path_try): final_logo_path = path_try; break
        if final_logo_path and os.path.exists(final_logo_path):
            logo_pixmap = QPixmap(final_logo_path)
            if not logo_pixmap.isNull():
                self.logo_label.setPixmap(logo_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else: self.logo_label.setText("LogoErr")
        else: self.logo_label.setText("Logo")

        sp_connected = False
        current_sp_manager_for_status = self.sharepoint_manager_enhanced or self.sharepoint_manager_original_ref
        if current_sp_manager_for_status and hasattr(current_sp_manager_for_status, 'is_operational'):
            try: sp_connected = current_sp_manager_for_status.is_operational
            except Exception as e_sp_op: self.logger.debug(f"Error checking SP op status: {e_sp_op}")
        sp_status_text = "🌐 SP Connected" if sp_connected else "📱 Local"
        if self.sharepoint_manager_enhanced: sp_status_text += " (E)"
        self.sp_status_label_ui = QLabel(sp_status_text)
        self.sp_status_label_ui.setStyleSheet("color: #495057; font-size: 9pt; font-style: italic;")

        base_header_layout = self.get_base_header_layout()
        if base_header_layout:
            # Clear existing custom widgets from header (defensive)
            widgets_to_remove = []
            for i in range(base_header_layout.count()):
                item = base_header_layout.itemAt(i)
                if item and item.widget():
                     if item.widget().objectName() == "deal_form_logo" or item.widget().objectName() == "deal_form_sp_status":
                        widgets_to_remove.append(item.widget())
            for widget in widgets_to_remove:
                base_header_layout.removeWidget(widget)
                widget.deleteLater()

            self.logo_label.setObjectName("deal_form_logo")
            self.sp_status_label_ui.setObjectName("deal_form_sp_status")
            base_header_layout.insertWidget(0, self.logo_label)
            base_header_layout.insertSpacing(1, 10)
            base_header_layout.addWidget(self.sp_status_label_ui)
        else:
            self.logger.warning("Could not get base_header_layout to add custom header elements.")

        # Customer & Salesperson Group
        customer_sales_group = QGroupBox("Customer & Salesperson")
        cs_layout = QHBoxLayout(customer_sales_group)
        self.customer_name = QLineEdit()
        self.customer_name.setClearButtonEnabled(True)
        self.customer_name.setPlaceholderText("Customer Name")
        self.customer_name_completer = QCompleter([])
        self.customer_name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.customer_name_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.customer_name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.customer_name.setCompleter(self.customer_name_completer)
        cs_layout.addWidget(self.customer_name)
        self.salesperson = QLineEdit()
        self.salesperson.setClearButtonEnabled(True)
        self.salesperson.setPlaceholderText("Salesperson")
        self.salesperson_completer = QCompleter([])
        self.salesperson_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.salesperson_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.salesperson_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.salesperson.setCompleter(self.salesperson_completer)
        cs_layout.addWidget(self.salesperson)
        content_layout.addWidget(customer_sales_group)

        # Item Sections (Equipment, Trades, Parts)
        item_sections_layout = QVBoxLayout() # This layout will hold the group boxes
        item_sections_layout.addWidget(self._create_equipment_section())
        item_sections_layout.addWidget(self._create_trade_section())
        item_sections_layout.addWidget(self._create_parts_section())
        content_layout.addLayout(item_sections_layout)

        # Work Order Options & Notes
        work_notes_layout = QHBoxLayout()
        work_notes_layout.addWidget(self._create_work_order_options_section(), 1)
        work_notes_layout.addWidget(self._create_notes_section(), 1)
        content_layout.addLayout(work_notes_layout)

        # Actions Group
        actions_groupbox = QGroupBox("Actions")
        main_actions_layout = QHBoxLayout(actions_groupbox)
        self.delete_line_btn = QPushButton("Delete Selected Line")
        # ... (rest of button initializations and adding to main_actions_layout as in the file)
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        self.delete_line_btn.setIcon(icon); self.delete_line_btn.setIconSize(QSize(16, 16))
        self.delete_line_btn.setToolTip("Delete the selected line from any list above")
        main_actions_layout.addWidget(self.delete_line_btn)
        main_actions_layout.addStretch(1)
        self.save_draft_btn = QPushButton("Save Draft")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        self.save_draft_btn.setIcon(icon); self.save_draft_btn.setIconSize(QSize(16, 16))
        main_actions_layout.addWidget(self.save_draft_btn)
        self.load_draft_btn = QPushButton("Load Draft")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        self.load_draft_btn.setIcon(icon); self.load_draft_btn.setIconSize(QSize(16, 16))
        main_actions_layout.addWidget(self.load_draft_btn)
        main_actions_layout.addSpacing(20)
        self.generate_csv_btn = QPushButton("Export CSV")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.generate_csv_btn.setIcon(icon); self.generate_csv_btn.setIconSize(QSize(16, 16))
        main_actions_layout.addWidget(self.generate_csv_btn)
        self.generate_email_btn = QPushButton("Generate Email")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        self.generate_email_btn.setIcon(icon); self.generate_email_btn.setIconSize(QSize(16, 16))
        main_actions_layout.addWidget(self.generate_email_btn)
        self.generate_both_btn = QPushButton("Generate All")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        self.generate_both_btn.setIcon(icon); self.generate_both_btn.setIconSize(QSize(16,16))
        main_actions_layout.addWidget(self.generate_both_btn)
        self.reset_btn = QPushButton("Reset Form")
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        self.reset_btn.setIcon(icon); self.reset_btn.setIconSize(QSize(16,16))
        self.reset_btn.setObjectName("reset_btn")
        main_actions_layout.addWidget(self.reset_btn)
        content_layout.addWidget(actions_groupbox)

        content_layout.addStretch(1)

        scroll_area.setWidget(form_scroll_content_widget)
        content_area_layout.addWidget(scroll_area)

        self._apply_styles()

        # Connect signals
        self.customer_name.editingFinished.connect(self.on_customer_field_changed)
        self.equipment_product_name.editingFinished.connect(self._on_equipment_product_name_selected)
        self.equipment_product_name_completer.activated.connect(self._on_equipment_product_name_selected_from_completer)
        self.equipment_product_code.editingFinished.connect(self._on_equipment_product_code_selected)
        self.part_number.editingFinished.connect(self._on_part_number_selected)

        self.delete_line_btn.clicked.connect(self.delete_selected_list_item)
        self.save_draft_btn.clicked.connect(self.save_draft)
        self.load_draft_btn.clicked.connect(self.load_draft)
        self.generate_csv_btn.clicked.connect(self.generate_csv_action)
        self.generate_email_btn.clicked.connect(self.generate_email)
        self.generate_both_btn.clicked.connect(self.generate_csv_and_email)
        self.reset_btn.clicked.connect(self.reset_form)

        self.logger.debug(f"{self.MODULE_DISPLAY_NAME} init_ui: UI setup complete (overwrite method).")
