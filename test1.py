import ui
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.QtCore import Qt, QTimer
import time
import pyocd
from pyocd.core.helpers import ConnectHelper
from pyocd.core.memory_map import MemoryType
from datetime import datetime

class ToolUi(QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        super(ToolUi, self).__init__()
        self.setupUi(self)

        # 初始化 PyOCD 设置
        self.session = None  # 保存 PyOCD 会话
        self.timestamp_list = []  # 用于记录时间的列表
        self.connect_ = 1  # 示例值
        self.move_ = 0
        self.mode_ = 1  # 默认模式
        self.supercap_ = 100
        self.speed_ = 50
        self.stoptime_ = 5

        # 设置定时器，每秒钟获取一次数据
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_data_from_device)  # 每秒获取数据
        self.timer.start(1000)  # 每1000ms触发一次

        # 连接按钮的事件
        self.radioButton_openuart.toggled.connect(self.toggle_serial_port)

        # 使用 PyOCD 连接设备
        self.connect_device()

    def connect_device(self):
        """连接到目标设备"""
        try:
            print("正在连接到设备...")
            self.session = ConnectHelper.session_with_chosen_probe()
            if not self.session:
                print("未找到设备，请检查连接。")
                return

            self.target = self.session.target
            self.target.resume()  # 确保目标处于运行状态
            print(f"设备连接成功：{self.session.board.target_type}")
            self.pushButton_runstate.setStyleSheet("background-color: blue;")  # 显示连接状态

        except Exception as e:
            print(f"连接设备时出错: {str(e)}")
            self.pushButton_runstate.setStyleSheet("background-color: red;")  # 显示连接失败

    def fetch_data_from_device(self):
        """从设备读取实时数据并更新界面"""
        if not self.session:
            return

        try:
            # 读取设备的内存或寄存器数据
            address = 0x20000000  # 这里是示例地址，根据实际需求调整
            data = self.target.read32(address)  # 从设备的指定地址读取32位数据
            print(f"读取的设备数据: 0x{data:08X}")

            # 记录当前时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"时间记录：{current_time}")

            # 将数据和时间记录存入列表
            self.timestamp_list.append(current_time)

            # 更新 GUI 控件显示
            self.textEdit_2.append(f"时间记录：{current_time} 数据：0x{data:08X}")

        except Exception as e:
            print(f"从设备读取数据时出错: {str(e)}")

    def toggle_serial_port(self):
        """根据 radioButton 的状态来打开或关闭设备连接"""
        if self.radioButton_openuart.isChecked():
            # 如果 radioButton_openuart 被选中，连接设备
            self.connect_device()
        else:
            # 如果 radioButton_closeuart 被选中，关闭设备连接
            if self.session:
                self.session.close()
                print("设备连接已关闭")
                self.pushButton_runstate.setStyleSheet("background-color: red;")  # 显示连接断开

    def closeEvent(self, event):
        """当窗口关闭时，关闭设备连接"""
        if self.session:
            self.session.close()
        event.accept()
