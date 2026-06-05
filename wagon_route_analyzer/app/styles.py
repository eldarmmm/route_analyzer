"""QSS-стили интерфейса приложения."""

STYLE = """
QMainWindow, QWidget {
    background-color: #0f1117;
    color: #e2e8f0;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #2d3748;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    background-color: #161b27;
    font-weight: 600;
    color: #90cdf4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLineEdit, QDateEdit {
    background-color: #1a2035;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 7px 10px;
    color: #e2e8f0;
    font-size: 13px;
}
QLineEdit:focus, QDateEdit:focus { border-color: #4299e1; }
QPushButton#runBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2b6cb0,stop:1 #3182ce);
    color: white; border: none; border-radius: 8px;
    padding: 12px 24px; font-size: 14px; font-weight: 700;
}
QPushButton#runBtn:hover  { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3182ce,stop:1 #4299e1); }
QPushButton#runBtn:pressed { background: #2c5282; }
QPushButton#runBtn:disabled { background: #2d3748; color: #718096; }
QPushButton#exportBtn {
    background-color: #276749; color: white; border: none;
    border-radius: 8px; padding: 10px 20px; font-size: 13px; font-weight: 600;
}
QPushButton#exportBtn:hover    { background-color: #2f855a; }
QPushButton#exportBtn:pressed  { background-color: #1c4532; }
QPushButton#exportBtn:disabled { background-color: #2d3748; color: #718096; }
QProgressBar {
    border: 1px solid #2d3748; border-radius: 6px;
    background-color: #1a2035; height: 18px;
    text-align: center; color: #e2e8f0; font-size: 11px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2b6cb0,stop:1 #4299e1);
    border-radius: 5px;
}
QTableWidget {
    background-color: #161b27; border: 1px solid #2d3748;
    border-radius: 8px; gridline-color: #2d3748;
    color: #e2e8f0; font-size: 12px;
}
QTableWidget::item { padding: 6px 8px; }
QTableWidget::item:selected { background-color: #2b4a7a; color: #fff; }
QHeaderView::section {
    background-color: #1e2a3d; color: #90cdf4;
    padding: 8px 10px; border: none;
    border-right: 1px solid #2d3748;
    border-bottom: 1px solid #2d3748;
    font-weight: 600; font-size: 12px;
}
QTextEdit {
    background-color: #0d1117; border: 1px solid #2d3748;
    border-radius: 6px; color: #68d391;
    font-family: 'Consolas','Courier New',monospace;
    font-size: 12px; padding: 8px;
}
QTabWidget::pane { border: 1px solid #2d3748; border-radius: 8px; background-color: #161b27; }
QTabBar::tab {
    background-color: #1a2035; color: #a0aec0;
    padding: 8px 20px; border-top-left-radius: 6px;
    border-top-right-radius: 6px; margin-right: 2px;
}
QTabBar::tab:selected { background-color: #2b4a7a; color: #90cdf4; font-weight: 600; }
QLabel#statLabel {
    background-color: #1a2035; border: 1px solid #2d3748;
    border-radius: 8px; padding: 10px 16px;
}
QLabel#titleLabel  { font-size: 22px; font-weight: 700; color: #90cdf4; }
QLabel#subtitleLabel { font-size: 12px; color: #718096; }
"""
