from collections.abc import Callable

from PyQt6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLabel,
)


class MainWindow(QMainWindow):
    def __init__(self, client_factory, on_submit: Callable):
        super().__init__()
        self.client_factory = client_factory
        self.on_submit = on_submit

        self.setWindowTitle("Anki AI - Update Your Flashcards with AI")
        screen = QApplication.primaryScreen().geometry()
        width = 1100
        height = 780
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Configuration:"))
        self.config_selector = QComboBox()
        self.config_selector.currentTextChanged.connect(self._on_config_changed)
        controls.addWidget(self.config_selector)
        self.manage_button = QPushButton("Manage…")
        self.manage_button.clicked.connect(self._open_config_manager)
        controls.addWidget(self.manage_button)
        controls.addStretch()
        self.layout.addLayout(controls)

        client_ui_container = QWidget()
        self.client_ui_layout = QVBoxLayout(client_ui_container)
        self.client_ui_layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(client_ui_container)

        self.current_client_widget = None

        buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.close)
        self.layout.addWidget(button_box)

        self._refresh_config_selector()

    # Config management -------------------------------------------------

    def _refresh_config_selector(self) -> None:
        names = self.client_factory.list_config_names()
        current = self.client_factory.active_config_name()
        self.config_selector.blockSignals(True)
        self.config_selector.clear()
        self.config_selector.addItems(names)
        if current and current in names:
            self.config_selector.setCurrentText(current)
        elif names:
            self.config_selector.setCurrentIndex(0)
            current = names[0]
            self.client_factory.set_active_config(current)
        self.config_selector.blockSignals(False)
        self._reload_runtime_panel()

    def _on_config_changed(self, config_name: str) -> None:
        if not config_name:
            return
        self.client_factory.set_active_config(config_name)
        self._reload_runtime_panel()

    def _reload_runtime_panel(self) -> None:
        if self.current_client_widget:
            self.client_ui_layout.removeWidget(self.current_client_widget)
            self.current_client_widget.deleteLater()
            self.current_client_widget = None
        self.current_client_widget = self.client_factory.make_runtime_panel()
        if self.current_client_widget is not None:
            self.client_ui_layout.addWidget(self.current_client_widget)

    def _open_config_manager(self) -> None:
        if self.client_factory.open_config_manager(self):
            self._refresh_config_selector()

    # Acceptance --------------------------------------------------------

    def _accept(self) -> None:
        if self.current_client_widget and self.current_client_widget.accept():
            self.on_submit()
