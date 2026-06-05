"""Переиспользуемые GUI-виджеты."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QPushButton, QMenu, QWidget, QVBoxLayout, QListWidget,
    QListWidgetItem, QWidgetAction,
)

class MultiSelectButton(QPushButton):
    """
    Кнопка которая при нажатии показывает выпадающий список с чекбоксами.
    Позволяет выбирать несколько значений одновременно.
    """
    selectionChanged = pyqtSignal()

    COMBO_STYLE = """
        QListWidget {
            background:#1a2035; color:#e2e8f0;
            border:1px solid #4299e1; border-radius:6px;
            padding:4px; font-size:12px;
            outline: none;
        }
        QListWidget::item {
            padding:5px 8px; border-radius:4px;
        }
        QListWidget::item:hover { background:#2b4a7a; }
        QListWidget::item:selected { background:transparent; }
        QPushButton#clearBtn {
            background:#2d3748; color:#a0aec0; border:none;
            border-radius:4px; padding:4px 10px; font-size:11px;
        }
        QPushButton#clearBtn:hover { background:#4a5568; color:#e2e8f0; }
    """

    def __init__(self, placeholder="Все", parent=None):
        super().__init__(parent)
        self.placeholder  = placeholder
        self._items       = []   # все доступные значения
        self._checked     = set() # выбранные значения
        self._popup       = None
        self._list_widget = None
        self._updating    = False
        self.setText(placeholder)
        self.setStyleSheet(
            "QPushButton { background:#1a2035; color:#e2e8f0; border:1px solid #2d3748;"
            " border-radius:6px; padding:5px 12px; text-align:left; font-size:12px; }"
            "QPushButton:hover { border-color:#4299e1; }"
            "QPushButton::menu-indicator { width:0; }")
        self.clicked.connect(self._show_popup)

    def set_items(self, items):
        """Устанавливает список доступных значений."""
        self._items   = list(items)
        self._checked = set()
        self._update_label()
        if self._list_widget:
            self._rebuild_list()

    def selected(self):
        """Возвращает set выбранных значений (пустой = все)."""
        return set(self._checked)

    def _update_label(self):
        if not self._checked:
            self.setText(self.placeholder)
        elif len(self._checked) == len(self._items):
            self.setText("Все")
        elif len(self._checked) <= 2:
            self.setText(', '.join(sorted(self._checked)))
        else:
            self.setText(f"Выбрано: {len(self._checked)}")

    def _show_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
            return

        popup = QMenu(self)
        popup.setStyleSheet(
            "QMenu { background:#1a2035; border:1px solid #4299e1;"
            " border-radius:8px; padding:4px; }"
            "QMenu::separator { height:1px; background:#2d3748; margin:4px 0; }")

        # Контейнер с кнопкой сброса + список
        container = QWidget()
        container.setStyleSheet(self.COMBO_STYLE)
        vlay = QVBoxLayout(container)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Кнопка "Сбросить всё"
        clear_btn = QPushButton("✕  Сбросить")
        clear_btn.setObjectName("clearBtn")
        clear_btn.clicked.connect(lambda: self._clear_all(lw))
        vlay.addWidget(clear_btn)

        # Список с чекбоксами
        lw = QListWidget()
        lw.setStyleSheet(self.COMBO_STYLE)
        lw.setFixedHeight(min(len(self._items) * 28 + 8, 280))
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_widget = lw
        self._rebuild_list()
        lw.itemChanged.connect(self._on_item_changed)
        vlay.addWidget(lw)

        container.setFixedWidth(240)

        action = QWidgetAction(popup)
        action.setDefaultWidget(container)
        popup.addAction(action)

        # Показываем под кнопкой
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup = popup
        popup.exec_(pos)

    def _rebuild_list(self):
        lw = self._list_widget
        lw.blockSignals(True)
        lw.clear()
        for val in self._items:
            item = QListWidgetItem(str(val))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if val in self._checked else Qt.Unchecked)
            lw.addItem(item)
        lw.blockSignals(False)

    def _on_item_changed(self, item):
        if self._updating:
            return
        val = item.text()
        if item.checkState() == Qt.Checked:
            self._checked.add(val)
        else:
            self._checked.discard(val)
        self._update_label()
        self.selectionChanged.emit()

    def _clear_all(self, lw):
        self._updating = True
        self._checked.clear()
        for i in range(lw.count()):
            lw.item(i).setCheckState(Qt.Unchecked)
        self._updating = False
        self._update_label()
        self.selectionChanged.emit()
