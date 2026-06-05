"""Entry point for the Wagon Route Analyzer application."""

import sys
from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Wagon Route Analyzer')
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
