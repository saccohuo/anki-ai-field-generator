from collections.abc import Callable
from pathlib import Path
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtGui import QTextDocument


class ProgressDialog(QDialog):
    def __init__(self, worker: QThread, success_callback: Callable, *, suppress_front: bool = False):
        super().__init__()
        self.success_callback = success_callback
        self.setWindowTitle("Processing")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
        self.resize(400, 250)
        self._has_error = False

        self.layout = QVBoxLayout()

        self.label = QLabel("Starting processing...")
        self.label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)
        self.background_button = QPushButton("后台运行")
        self.background_button.clicked.connect(self._on_background)
        self.resume_button = QPushButton("Continue")
        self.resume_button.clicked.connect(self.resume)
        self.resume_button.hide()
        self.copy_button = QPushButton("Copy Error")
        self.copy_button.clicked.connect(self.copy_error)
        self.copy_button.hide()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close_dialog)
        self.close_button.hide()

        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.label)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.background_button)
        button_layout.addWidget(self.resume_button)
        button_layout.addWidget(self.copy_button)
        button_layout.addWidget(self.close_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.worker = worker
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.complete)
        self.worker.error.connect(self.error)
        conflict_handler = getattr(self.worker, "conflict_detected", None)
        if conflict_handler is not None:
            conflict_handler.connect(self.handle_conflict)
        self.suppress_front = suppress_front
        if suppress_front:
            # Request minimized state before the first show to avoid activation.
            self.setWindowState(Qt.WindowState.WindowMinimized)
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._log_event(
            "dialog_init",
            {
                "suppress_front": suppress_front,
                "minimized": self.isMinimized(),
            },
        )
        self.worker.start()

    def update_progress(self, value, text):
        if getattr(self, "suppress_front", False) and not self.isMinimized():
            try:
                self.showMinimized()
            except RuntimeError:
                pass
        self._log_event(
            "progress",
            {
                "value": value,
                "text": text,
                "suppress_front": getattr(self, "suppress_front", False),
                "minimized": self.isMinimized(),
            },
        )
        self.progress_bar.setValue(value)
        self.label.setText(text)

    def complete(self):
        if getattr(self.worker, "cancelled", False):
            self.hide()
            self._safe_close()
            return
        if self._has_error:
            return
        self.progress_bar.setValue(100)
        summary = getattr(self.worker, "note_error_summary", "") or ""
        if summary:
            self.label.setText(summary)
        else:
            self.label.setText("Processing complete!")
        self.cancel_button.hide()
        self.resume_button.hide()
        self.copy_button.setVisible(bool(summary))
        self.background_button.hide()
        self.close_button.show()
        self.success_callback()
        if summary:
            if getattr(self, "suppress_front", False):
                self.hide()
                self._safe_close()
                return
            self.showNormal()
            self.raise_()
            self.activateWindow()
            return
        self.hide()
        self._safe_close()
        self._log_event("complete", {"suppress_front": getattr(self, "suppress_front", False)})

    def error(self, text):
        self._has_error = True
        if self.isMinimized() and not getattr(self, "suppress_front", False):
            self.showNormal()
        self.label.setText(f"<b>Error:</b> {text}")
        self.resume_button.hide()
        self.copy_button.show()
        self.cancel_button.show()
        self.background_button.hide()
        self.close_button.show()
        self._log_event(
            "error",
            {
                "text": text,
                "suppress_front": getattr(self, "suppress_front", False),
                "minimized": self.isMinimized(),
            },
        )

    def resume(self):
        self.resume_button.hide()
        self.copy_button.hide()

    def copy_error(self):
        doc = QTextDocument()
        doc.setHtml(self.label.text())
        QApplication.clipboard().setText(doc.toPlainText())

    def cancel(self):
        if hasattr(self.worker, "requestInterruption"):
            self.worker.requestInterruption()
        self.label.setText("Cancelling...")
        self.hide()
        self._safe_close()

    def close_dialog(self):
        self._safe_close()

    def _safe_close(self) -> None:
        """Close the dialog without raising if Qt already destroyed it."""
        try:
            QDialog.close(self)
        except RuntimeError:
            pass

    def _on_background(self) -> None:
        self.suppress_front = True
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        try:
            self.showMinimized()
        except RuntimeError:
            pass
        self._log_event(
            "background_clicked",
            {"suppress_front": True, "minimized": self.isMinimized()},
        )

    def handle_conflict(self, payload: dict):
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        dialog = ConflictDialog(payload, self)
        decision = dialog.exec_decision()
        conflict_signal = getattr(self.worker, "conflict_decision", None)
        if conflict_signal is not None:
            conflict_signal.emit(payload.get("note_id"), decision)
        if decision == "abort" and hasattr(self.worker, "requestInterruption"):
            self.worker.requestInterruption()
        self._log_event(
            "conflict_dialog_decision",
            {"decision": decision, "suppress_front": getattr(self, "suppress_front", False)},
        )

    def _log_event(self, label: str, data: Optional[dict] = None) -> None:
        log_path = Path(__file__).with_name("anki_ai_runtime.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = data or {}
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] progress_dialog {label} {payload}\n")
        except Exception:
            pass


class ConflictDialog(QDialog):
    def __init__(self, payload: dict, parent: Optional[QDialog] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Note Conflict Detected")
        self.decision = "abort"
        layout = QVBoxLayout(self)
        note_id = payload.get("note_id")
        section = payload.get("section", "")
        header = QLabel(
            f"笔记 {note_id} 在 {section} 阶段检测到字段冲突。请选择如何处理。"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        details = QTextEdit()
        details.setReadOnly(True)
        lines: list[str] = []
        fields = payload.get("fields", {})
        for field_name, values in fields.items():
            original = values.get("original", "")
            current = values.get("current", "")
            generated = values.get("generated", "")
            snippet = (
                f"字段: {field_name}\n"
                f"初始值: {original}\n"
                f"当前值: {current}\n"
                f"新生成: {generated}"
            )
            lines.append(snippet)
        details.setPlainText("\n\n".join(lines))
        layout.addWidget(details)

        buttons = QDialogButtonBox()
        overwrite_button = buttons.addButton(
            "覆盖当前内容", QDialogButtonBox.ButtonRole.AcceptRole
        )
        skip_button = buttons.addButton(
            "跳过此笔记", QDialogButtonBox.ButtonRole.DestructiveRole
        )
        cancel_button = buttons.addButton(
            "取消任务", QDialogButtonBox.ButtonRole.RejectRole
        )
        buttons.accepted.connect(self._accept_overwrite)
        skip_button.clicked.connect(self._choose_skip)
        cancel_button.clicked.connect(self._choose_abort)
        layout.addWidget(buttons)

    def _accept_overwrite(self) -> None:
        self.decision = "overwrite"
        self.accept()

    def _choose_skip(self) -> None:
        self.decision = "skip"
        self.accept()

    def _choose_abort(self) -> None:
        self.decision = "abort"
        self.reject()

    def exec_decision(self) -> str:
        self.exec()
        return self.decision
