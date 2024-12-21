import PyQt5
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QObject, pyqtSignal
import sys
import toolui


class MainWindow(QObject):
    def __init__(self):
        super().__init__()
        self.tool_ui = toolui.ToolUi()  # Qt 界面实例

    def run(self):
        self.tool_ui.show()  # 显示界面


# 主程序入口
if __name__ == "__main__":
    app = PyQt5.QtWidgets.QApplication(sys.argv)
    ui = MainWindow()
    ui.run()  # ui就会显示出来
    sys.exit(app.exec_())
