from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from aqt import QObject
from aqt.qt import (
    QSettings,
    QDialog,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    Qt,
    QDialogButtonBox,
    QScrollArea,
)
from PyQt6 import QtCore

from .llm_client import LLMClient
from .note_processor import NoteProcessor
from .progress_bar import ProgressDialog
from .settings import SettingsNames
from .two_col_layout import DynamicForm
from .ui_tools import UITools


# I think I should have:
# - something generic that adds menubar things
# - something generic that loads settings
# - ideally something generic-ish that passes information through
# - an action-custom dialog


class MyMeta(ABCMeta, type(QtCore.QObject)):
    pass


class ModifyCardsDialog(QDialog, metaclass=MyMeta):
    def __init__(self, app_settings: QSettings):
        super(ModifyCardsDialog, self).__init__()
        self.app_settings: QSettings = app_settings
        self._width = 500
        self.ui_tools: UITools = UITools(app_settings, self._width)

    def show(self, notes: list, on_submit: Callable):
        if self.layout() is not None:
            QWidget().setLayout(self.layout())  # Clears any existing layout
        card_fields = sorted({field for note in notes for field in note.keys()})

        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle("Anki AI - Modify Cards")
        self.resize(self._width * 2 + 20, 750)
        container_widget = QWidget()
        main_layout = QHBoxLayout(container_widget)

        left_container = QWidget()
        left_container.setMaximumWidth(self._width)
        left_layout = QVBoxLayout()
        left_container.setLayout(left_layout)

        self.add_api_key(left_layout)
        self.add_system_prompt(
            left_layout, self.system_prompt_description, self.system_prompt_placeholder
        )
        left_layout.addStretch()

        # Right Column
        right_container = QWidget()
        right_container.setMaximumWidth(self._width)
        right_layout = QVBoxLayout()
        right_container.setLayout(right_layout)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # User Prompt
        self.add_user_prompt(
            right_layout, self.user_prompt_description, self.user_prompt_placeholder
        )
        # Available Fields
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(
                f"Available fields: {', '.join(card_fields)}"
            )
        )

        # Destination Configuration
        right_layout.addWidget(
            self.ui_tools.create_label("Save the AI output to the Anki fields:")
        )
        right_layout.addWidget(
            self.ui_tools.create_descriptive_text(self.mapping_instruction_text)
        )
        two_col_form = DynamicForm(
            self.app_settings.value(
                SettingsNames.RESPONSE_KEYS_SETTING_NAME, type="QStringList"
            ),
            self.app_settings.value(
                SettingsNames.DESTINATION_FIELD_SETTING_NAME, type="QStringList"
            ),
            card_fields,
        )
        right_layout.addWidget(two_col_form)

        # Misc
        right_layout.addWidget(
            self.ui_tools.create_label(f"{len(notes)} cards selected. Modify cards?")
        )

        buttons = (
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(lambda: self.accept(on_submit, two_col_form))
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addWidget(left_container)
        main_layout.addWidget(right_container)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container_widget)

        final_layout = QVBoxLayout(self)
        final_layout.addWidget(scroll_area)
        self.setLayout(final_layout)
        super().show()

    @property
    @abstractmethod
    def system_prompt_description(self):
        """User friendly description for the system prompt"""

    @property
    @abstractmethod
    def system_prompt_placeholder(self):
        """Optional placeholder text for the system prompt"""

    @property
    @abstractmethod
    def user_prompt_description(self):
        """User friendly description for the user prompt"""

    @property
    @abstractmethod
    def user_prompt_placeholder(self):
        """Optional placeholder text for the user prompt"""

    @property
    def mapping_instruction_text(self):
        """User friendly description for the JSON key to Note field mapping instructions"""
        return """
        For each piece of information the AI gives you, type its label from the AI and select the Anki field where you want to save it.<br><br>
        <b>Example:</b> If you asked the AI for a German sentence and its translation, and your Anki fields are <code>de_sentence</code> and <code>en_sentence</code>, enter:
        <pre>exampleSentence de_sentence<br>translation en_sentence</pre>
        """

    def add_api_key(self, layout):
        layout.addWidget(self.ui_tools.create_label("OpenAI API Key:"))
        layout.addWidget(
            self.ui_tools.create_text_entry(SettingsNames.API_KEY_SETTING_NAME)
        )

    def add_system_prompt(
        self, layout, system_prompt_description, system_prompt_placeholder
    ):
        layout.addWidget(self.ui_tools.create_label("System Prompt:"))
        layout.addWidget(
            self.ui_tools.create_descriptive_text(system_prompt_description)
        )
        layout.addWidget(
            self.ui_tools.create_text_edit(
                SettingsNames.SYSTEM_PROMPT_SETTING_NAME,
                system_prompt_placeholder,
            )
        )

    def add_user_prompt(self, layout, user_prompt_description, user_prompt_placeholder):
        layout.addWidget(self.ui_tools.create_label("User Prompt:"))
        layout.addWidget(self.ui_tools.create_descriptive_text(user_prompt_description))
        layout.addWidget(
            self.ui_tools.create_text_edit(
                SettingsNames.USER_PROMPT_SETTING_NAME,
                user_prompt_placeholder,
            )
        )

    def accept(self, on_submit: Callable, two_col_form):
        """
        Saves settings when user accepts.
        """
        self.ui_tools.save_settings()
        keys, fields = two_col_form.get_inputs()
        self.app_settings.setValue(SettingsNames.RESPONSE_KEYS_SETTING_NAME, keys)
        self.app_settings.setValue(
            SettingsNames.DESTINATION_FIELD_SETTING_NAME,
            fields,
        )
        on_submit()
        super(ModifyCardsDialog, self).accept()


class ModifyCardsUI:

    def __init__(
        self,
        settings: QSettings,
        modify_cards_dialog: ModifyCardsDialog,
        llm_client: LLMClient,
    ):
        self.app_settings = settings
        self.modify_cards_dialog = modify_cards_dialog
        self.llm_client = llm_client

    def show(self, browser):
        notes = [
            browser.mw.col.get_note(note_id) for note_id in browser.selectedNotes()
        ]
        self.modify_cards_dialog.show(
            notes, lambda: self.on_submit(browser=browser, notes=notes)
        )

    def on_submit(self, browser, notes):
        note_processor = NoteProcessor(notes, self.llm_client, self.app_settings)
        dialog = ProgressDialog(note_processor)
        dialog.exec()
        browser.mw.reset()
