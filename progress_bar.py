from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtCore import QThread, Qt


class ProgressDialog(QDialog):
    def __init__(self, worker: QThread):
        super().__init__()
        self.setWindowTitle("Processing")
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.resize(400, 250)

        self.layout = QVBoxLayout()

        self.label = QLabel("Starting processing...")
        self.label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.resume_button = QPushButton("Continue")
        self.resume_button.clicked.connect(self.resume)
        self.resume_button.hide()

        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.label)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.resume_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.worker = worker
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.complete)
        self.worker.error.connect(self.error)
        self.worker.start()

    def update_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.label.setText(text)

    def complete(self):
        self.label.setText("Processing complete!")
        self.accept()
        # self.cancel_button.setText("Close")

    def error(self, text):
        self.label.setText(f"<b>Error:</b> {text}")
        self.resume_button.show()

    def resume(self):
        self.resume_button.hide()
        self.worker.start()

    def cancel(self):
        if self.worker.isRunning():
            self.worker.terminate()  # Terminate the thread (not recommended for critical operations)
        self.reject()  # Close the dialog
