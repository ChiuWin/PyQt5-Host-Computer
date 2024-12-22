import sys
import ui
from PyQt5.QtWidgets import QMainWindow,QTextEdit
from PyQt5.QtCore import Qt,QTimer
import time
import serial
import struct
from PyQt5.QtWidgets import QMessageBox
import csv

import pyocd
from pyocd.core.helpers import ConnectHelper
from pyocd.core.memory_map import MemoryType

#对print进行重定向
class QTextEditStream:
    def __init__(self, text_edit: QTextEdit):
        """ 初始化并设置 QTextEdit 控件 """
        self.text_edit = text_edit

    def write(self, text: str):
        """ 重定向输出内容到 QTextEdit """
        self.text_edit.append(text)  # 追加输出

    def flush(self):
        """ flush() 是标准输出流所需的方法，通常不需要实现具体操作 """
        pass

# class Board2PC:
#     """下位机到上位机的通信协议类"""
#     def __init__(self, timestamp2=0, stopFlag_=0, move_=0):
#         self.timestamp2 = timestamp2
#         self.stopFlag_ = stopFlag_
#         self.move_ = move_

class Board2PC:
    """下位机到上位机的通信协议类"""

    def __init__(self, timestamp2=0, stopFlag_=0, move_=0):
        self.timestamp2 = timestamp2
        self.stopFlag_ = stopFlag_
        self.move_ = move_

    def to_bytes(self):
        """ 将数据打包成二进制字节流，准备发送 """
        return struct.pack('<I BB', self.timestamp2, self.stopFlag_, self.move_)

    @classmethod
    def from_bytes(cls, data):
        """ 从接收到的字节流中解析数据 """
        timestamp2, stopFlag_, move_ = struct.unpack('<I BB', data)
        return cls(timestamp2, stopFlag_, move_)

    def __repr__(self):
        """ 类的字符串表示 """
        return f"Board2PC(timestamp2={self.timestamp2}, stopFlag_={self.stopFlag_}, move_={self.move_})"






    # def update_move_2(self, move_2_value):
    #     """ 更新 move_2 的值，并根据其值在仪表盘上显示方向 """
    #     self.move_ = move_2_value
    #     self.update_button_color()

    # def update_button_color(self):
    #     """ 根据 self.move_ 的值动态更新按钮颜色 """
    #     if self.move_ == 0:
    #         self.pushButton_stop.setStyleSheet("background-color: red;")  # 红色
    #     elif self.move_ == 1:
    #         self.pushButton_forward.setStyleSheet("background-color: red;")  # 红色
    #     elif self.move_ == 2:
    #         self.pushButton_back.setStyleSheet("background-color: green;")  # 绿色
    #     elif self.move_ == 3:
    #         self.pushButton_left.setStyleSheet("background-color: blue;")  # 蓝色
    #     elif self.move_ == 4:
    #         self.pushButton_right.setStyleSheet("background-color: yellow;")  # 黄色

class ToolUi(QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        super(ToolUi, self).__init__()
        self.setupUi(self)


        # 用于存储每次 stopFlag_2 从 1 变为 0 的时间戳
        self.timestamp_list = []  

        # 初始化PC2Board设置
        self.ser = None
        self.timestamp = int(time.time())  # 初始化时间戳
        self.connect_ = 1  # 表示连接状态，0断开，1链接  默认未连接
        self.move_ = 0  # 初始静止
        self.mode_ = 0  # 表示模式，0遥控，1循迹，默认遥控
        self.supercap_ = 0  # 是否加速，0不加速，1加速
        self.speed_ = 1  # 速度分为1,2,3,4档，初始为1档
        self.stoptime_ = 10  # 停靠时间（单位秒）

        # 初始化Board2PC设置
        self.timestamp2 = 0 #初始化时间
        self.stopFlag_2 = 0 #初始前进
        self.move_2 = 0 #初始停止


        print("=== PyOCD 调试界面 ===")
        print("正在连接到 DAPLink 设备，请稍候...")

        # 自动连接到设备
        self.session = ConnectHelper.session_with_chosen_probe()
        if self.session is None:
            print("未找到任何支持的调试器设备，请检查连接。")
            sys.exit(1)
        



        # 连接comboBox_mode的变化信号
        self.comboBox_mode.currentIndexChanged.connect(self.update_mode)

        # 连接spinBox_setcarspeed和spinBox_setstoptime的值变化信号
        self.spinBox_setcarspeed.valueChanged.connect(self.update_speed)
        self.spinBox_setstoptime.valueChanged.connect(self.update_stoptime)

        # 串口连接控制按钮
        self.radioButton_openuart.toggled.connect(self.toggle_serial_port)

        # ComboBox 变化时检测条件是否满足
        self.comboBox_botelv.currentIndexChanged.connect(self.check_serial_conditions)
        self.comboBox_shujuwei.currentIndexChanged.connect(self.check_serial_conditions)
        self.comboBox_jiaoyanwei.currentIndexChanged.connect(self.check_serial_conditions)
        self.comboBox_tingzhiwei.currentIndexChanged.connect(self.check_serial_conditions)
        self.comboBox_duankou.currentIndexChanged.connect(self.check_serial_conditions)

        # 初始化定时器，每秒钟触发一次发送数据的函数
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.send_periodic_data)
        self.timer.timeout.connect(self.receive_data)  # 每秒触发一次接收数据

        self.timer.timeout.connect(self.ocd_send)
        self.timer.timeout.connect(self.ocd_receive) # 每秒触发一次ocd

        # 启动定时器，但初始时不启动数据发送
        self.timer.start(1000)  # 每1000毫秒触发一次

        # 默认检查条件并打开串口
        self.check_serial_conditions()


        # 监听控制台信号
        self.pushButton_goforward.pressed.connect(self.set_move_forward)
        self.pushButton_backup.pressed.connect(self.set_move_backup)
        self.pushButton_turnleft.pressed.connect(self.set_move_turnleft)
        self.pushButton_turnright.pressed.connect(self.set_move_turnright)
        self.pushButton_speedup.pressed.connect(self.set_supercap_speedup)

        self.pushButton_goforward.released.connect(self.reset_move)
        self.pushButton_backup.released.connect(self.reset_move)
        self.pushButton_turnleft.released.connect(self.reset_move)
        self.pushButton_turnright.released.connect(self.reset_move)

        self.pushButton_export.clicked.connect(self.export_data_to_csv)

        # 初始化按钮颜色
        self.reset_button_colors()

        self.pushButton_slow.setStyleSheet("background-color: blue")
        self.pushButton_stop.setStyleSheet("background-color: blue")

        # 设置将 print 输出重定向到 textEdit_1
        self.text_edit_stream = QTextEditStream(self.textEdit_1)  # 假设你的 UI 中有 textEdit_1
        sys.stdout = self.text_edit_stream  # 重定向标准输出


    def ocd_send(self):
        try:
            with self.session:
                target = self.session.target
                target.resume()  # 确保目标处于运行状态

                print("成功连接到设备！")
                print(f"设备名称: {self.session.board.target_type}")
                
                # 发送数据地址
                # 在实际应用中，你可能需要发送多个数据地址，或者发送不同的数据类型。
                # 比如：整数、浮动值、字节流等。

                # 假设我们有几个需要发送的数据
                data_to_send_1 = 0x12345678  # 要发送的32位数据
                data_to_send_2 = 0xA5       # 要发送的8位数据
                data_to_send_3 = 0x01       # 要发送的8位数据

                # 发送数据到目标设备
                #timestamp
                try:
                    addr_1 = 0x20000814  # 地址1，假设我们发送32位数据
                    target.write32(addr_1, 5)  # 写入32位数据
                    print(f"发送数据到地址 0x{addr_1:08X}: 0x{data_to_send_1:08X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_1} 时出错: {str(e)}")

                #connect_
                try:
                    addr_2 = 0x200003A0  # 地址2，假设我们发送8位数据
                    target.write8(addr_2, data_to_send_2)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_2:08X}: 0x{data_to_send_2:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_2} 时出错: {str(e)}")

                try:
                    addr_3 = 0x200003A1  # 地址3，假设我们发送8位数据
                    target.write8(addr_3, data_to_send_3)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_3:08X}: 0x{data_to_send_3:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_3} 时出错: {str(e)}")

                try:
                    addr_3 = 0x200003A1  # 地址3，假设我们发送8位数据
                    target.write8(addr_3, data_to_send_3)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_3:08X}: 0x{data_to_send_3:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_3} 时出错: {str(e)}")


                try:
                    addr_3 = 0x200003A1  # 地址3，假设我们发送8位数据
                    target.write8(addr_3, data_to_send_3)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_3:08X}: 0x{data_to_send_3:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_3} 时出错: {str(e)}")

                try:
                    addr_3 = 0x200003A1  # 地址3，假设我们发送8位数据
                    target.write8(addr_3, data_to_send_3)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_3:08X}: 0x{data_to_send_3:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_3} 时出错: {str(e)}")


                try:
                    addr_3 = 0x200003A1  # 地址3，假设我们发送8位数据
                    target.write8(addr_3, data_to_send_3)  # 写入8位数据
                    print(f"发送数据到地址 0x{addr_3:08X}: 0x{data_to_send_3:02X}")
                except Exception as e:
                    print(f"发送数据到地址 0x{addr_3} 时出错: {str(e)}")                    

        except Exception as e:
            print(f"调试器会话出错: {str(e)}")



    def ocd_receive(self):
        try:
            with self.session:
                target = self.session.target
                target.resume()  # 确保目标处于运行状态

                # print("成功连接到设备！")
                # print(f"设备名称: {self.session.board.target_type}")
                
                # #接收数据地址
                # address1 = 0x2000039C
                # address2 = 0x200003A0
                # address3 = 0x200003A1

                try:
                    addr = 0x2000080C#int(str(address1), 16)
                    value = target.read32(addr)  # 读取指定地址的数据（32位）
                    print(f"地址 0x{addr:08X} 的数据: 0x{value:08X}")
                except ValueError:
                    print("输入的地址无效，请重新输入。")
                except Exception as e:
                    print(f"读取地址 0x{addr} 时出错: {str(e)}")
                


                try:
                    addr = 0x20000814#int(str(address2), 16)
                    value = target.read8(addr)  # 读取指定地址的数据（8位）
                    print(f"地址 0x{addr:08X} 的数据: 0x{value:08X}")
                except ValueError:
                    print("输入的地址无效，请重新输入。")
                except Exception as e:
                    print(f"读取地址 0x{addr} 时出错: {str(e)}")

                try:
                    addr = 0x20000811#int(str(address3), 16)
                    value = target.read8(addr)  # 读取指定地址的数据（8位）
                    print(f"地址 0x{addr:08X} 的数据: 0x{value:08X}")
                except ValueError:
                    print("输入的地址无效，请重新输入。")
                except Exception as e:
                    print(f"读取地址 0x{addr} 时出错: {str(e)}")

        except Exception as e:
            print(f"调试器会话出错: {str(e)}")




    def update_mode(self):
        """ 更新mode_值，遥控模式为0，循迹模式为1 """
        selected_mode = self.comboBox_mode.currentText()
        if selected_mode == "遥控模式":
            self.mode_ = 0
            self.move_ = 0 #每次遥控初始状态为停止
            self.pushButton_stop.setStyleSheet("background-color: blue")
            self.pushButton_forward.setStyleSheet("")
            self.pushButton_back.setStyleSheet("")
            self.pushButton_left.setStyleSheet("")
            self.pushButton_right.setStyleSheet("")
            print("当前模式：遥控模式")
        elif selected_mode == "循迹模式":
            self.mode_ = 1
            print("当前模式：循迹模式")

    def update_speed(self):
        """ 更新speed_的值 """
        self.speed_ = self.spinBox_setcarspeed.value()  # 获取车速值
        print(f"当前车速：{self.speed_}")
        if self.speed_ > 2 or self.supercap_ == 1 :
            self.pushButton_fast.setStyleSheet("background-color: blue")
            self.pushButton_slow.setStyleSheet("")
        elif self.speed_ <= 2 and self.supercap_ == 0 :
            self.pushButton_fast.setStyleSheet("")
            self.pushButton_slow.setStyleSheet("background-color: blue")

    def update_stoptime(self):
        """ 更新stoptime_的值 """
        self.stoptime_ = self.spinBox_setstoptime.value()  # 获取停靠时间值
        print(f"当前停靠时间：{self.stoptime_}")


    def check_serial_conditions(self):
        """ 检查串口条件，决定是否打开或关闭串口 """
        baudrate = self.comboBox_botelv.currentText()  # 波特率
        data_bits = self.comboBox_shujuwei.currentText()  # 数据位
        parity = self.comboBox_jiaoyanwei.currentText()  # 校验位
        stop_bits = self.comboBox_tingzhiwei.currentText()  # 停止位
        port = self.comboBox_duankou.currentText()  # 串口端口

        if baudrate == '9600' and data_bits == '8' and parity == '0' and stop_bits == '1' and port == 'COM2':
            # 满足条件，打开串口
            if self.ser is None:
                self.ser = self.init_serial_port(port='COM2', baudrate=9600)
                self.connect_ = 1
                print("已连接")
        else:
            # 不满足条件，关闭串口
            if self.ser:
                self.ser.close()
                self.ser = None
                self.connect_ = 0
                print("未连接")
                

    def toggle_serial_port(self):
        """ 控制串口打开和关闭 """
        if self.radioButton_openuart.isChecked():
            self.check_serial_conditions()  # 检查条件并决定是否打开串口
        else:
            if self.ser:
                self.ser.close()
                self.ser = None
                # self.pushButton_stopstate.setStyleSheet("")
                # self.pushButton_fast.setStyleSheet("")
                # self.pushButton_slow.setStyleSheet("")
                # self.pushButton_slow.setStyleSheet("")
                print("未连接")

    def init_serial_port(self, port='COM2', baudrate=9600, parity='N', data_bits=8, stop_bits=1):
        """ 初始化串口 """
        try:
            ser = serial.Serial(port=port, baudrate=baudrate, parity=parity,
                                bytesize=data_bits, stopbits=stop_bits)
            return ser
        except serial.SerialException as e:
            print(f"串口打开失败: {e}")
            return None

    def send_periodic_data(self):
        """ 定时发送数据 """
        self.timestamp = int(time.time())  # 获取当前的时间戳
        if self.ser:
            data = struct.pack(
                '<I 6B',  # 包含一个uint32_t 和五个uint8_t
                self.timestamp,
                self.connect_,
                self.move_,
                self.mode_,
                self.supercap_,
                self.speed_,
                self.stoptime_
            )
            self.ser.write(data)

            # print("已发送数据")
        else:
            print("串口未连接，无法发送数据")



    # def set_values(self, timestamp=None, connect_=None, move_=None, mode_=None, supercap_=None, speed_=None,
    #                stoptime_=None):
    #     """
    #     设置串口配置相关的参数。如果某个值为 None，则不更新该值。
    #     """
    #     if timestamp is not None:
    #         self.timestamp = timestamp
    #     if connect_ is not None:
    #         self.connect_ = connect_
    #     if move_ is not None:
    #         self.move_ = move_
    #     if mode_ is not None:
    #         self.mode_ = mode_
    #     if supercap_ is not None:
    #         self.supercap_ = supercap_
    #     if speed_ is not None:
    #         self.speed_ = speed_
    #     if stoptime_ is not None:
    #         self.stoptime_ = stoptime_



    def keyPressEvent(self, event):
        """ 重载按键事件 """
        if(self.mode_ == 0 and self.connect_ == 1):
            if event.key() == Qt.Key_W:
                self.pushButton_goforward.setStyleSheet("background-color: green")
                self.pushButton_forward.setStyleSheet("background-color: blue")
                self.pushButton_stop.setStyleSheet("")
                self.move_ = 1  # 前进
                print("前进 (W)")

            elif event.key() == Qt.Key_S:
                self.pushButton_backup.setStyleSheet("background-color: green")
                self.pushButton_back.setStyleSheet("background-color: blue")
                self.pushButton_stop.setStyleSheet("")
                self.move_ = 2  # 后退
                print("后退 (S)")

            elif event.key() == Qt.Key_A:
                self.pushButton_turnleft.setStyleSheet("background-color: green")
                self.pushButton_left.setStyleSheet("background-color: blue")
                self.pushButton_stop.setStyleSheet("")
                self.move_ = 3  # 左转
                print("左转 (A)")

            elif event.key() == Qt.Key_D:
                self.pushButton_turnright.setStyleSheet("background-color: green")
                self.pushButton_right.setStyleSheet("background-color: blue")
                self.pushButton_stop.setStyleSheet("")
                self.move_ = 4  # 右转
                print("右转 (D)")

            elif event.key() == Qt.Key_J:
                if(self.mode_ == 0):
                    self.supercap_ = 1- self.supercap_#切换加速状态
                    print("切换加速模式(J)")
                    if(self.supercap_ == 0):
                        self.pushButton_speedup.setStyleSheet("")
                        if(self.speed_ <= 2):
                            self.pushButton_slow.setStyleSheet("background-color: blue")
                            self.pushButton_fast.setStyleSheet("")
                        print("未加速")
                    elif(self.supercap_ == 1):
                        self.pushButton_speedup.setStyleSheet("background-color: green")
                        self.pushButton_fast.setStyleSheet("background-color: blue")
                        self.pushButton_slow.setStyleSheet("")
                        print("已加速")
                elif(self.mode_ == 1):
                    print("Invalid:只有遥控模式才可加速")


    def keyReleaseEvent(self, event):
        """ 重载按键松开事件，按键松开时恢复原颜色并重置move_ """
        if(self.mode_ == 0 and self.connect_ == 1):
            if event.key() == Qt.Key_W:
                self.pushButton_goforward.setStyleSheet("")
                self.pushButton_forward.setStyleSheet("")
                self.pushButton_stop.setStyleSheet("background-color: blue")
                self.move_ = 0  # 恢复为初始状态
                print("停止!!!!!!!")

            elif event.key() == Qt.Key_S:
                self.pushButton_backup.setStyleSheet("")
                self.pushButton_back.setStyleSheet("")
                self.pushButton_stop.setStyleSheet("background-color: blue")
                self.move_ = 0  # 恢复为初始状态
                # print("停止")

            elif event.key() == Qt.Key_A:
                self.pushButton_turnleft.setStyleSheet("")
                self.pushButton_left.setStyleSheet("")
                self.pushButton_stop.setStyleSheet("background-color: blue")
                self.move_ = 0  # 恢复为初始状态
                # print("停止")

            elif event.key() == Qt.Key_D:
                self.pushButton_turnright.setStyleSheet("")
                self.pushButton_right.setStyleSheet("")

                self.pushButton_stop.setStyleSheet("background-color: blue")
                self.move_ = 0  # 恢复为初始状态
                # print("停止")

            # elif event.key() == Qt.Key_J:
            #     self.pushButton_turnspeed.setStyleSheet("")

    def reset_button_colors(self):
        """ 初始化时将所有按钮颜色重置 """
        self.pushButton_goforward.setStyleSheet("")
        self.pushButton_backup.setStyleSheet("")
        self.pushButton_turnleft.setStyleSheet("")
        self.pushButton_turnright.setStyleSheet("")
        self.pushButton_speedup.setStyleSheet("")

    def set_move_forward(self):
        """前进按钮点击"""
        if(self.mode_ == 0 and self.connect_ == 1):
            self.pushButton_goforward.setStyleSheet("background-color: green")
            self.pushButton_forward.setStyleSheet("background-color: blue")
            self.pushButton_stop.setStyleSheet("")
            self.move_ = 1  # 前进
            print("前进 (W)")

    def set_move_backup(self):
        if(self.mode_ == 0 and self.connect_ == 1):
            self.pushButton_backup.setStyleSheet("background-color: green")
            self.pushButton_back.setStyleSheet("background-color: blue")
            self.pushButton_stop.setStyleSheet("")
            self.move_ = 2  # 后退
            print("后退 (S)")

    def set_move_turnleft(self):
        if(self.mode_ == 0 and self.connect_ == 1):
            self.pushButton_turnleft.setStyleSheet("background-color: green")
            self.pushButton_left.setStyleSheet("background-color: blue")
            self.pushButton_stop.setStyleSheet("")
            self.move_ = 3  # 左转
            print("左转 (A)")

    def set_move_turnright(self):
        if(self.mode_ == 0 and self.connect_ == 1):
            self.pushButton_turnright.setStyleSheet("background-color: green")
            self.pushButton_right.setStyleSheet("background-color: blue")
            self.pushButton_stop.setStyleSheet("")
            self.move_ = 4  # 右转
            print("右转 (D)")

    def set_supercap_speedup(self):
        if(self.mode_ == 0 and self.connect_ == 1):
            self.supercap_ = 1- self.supercap_#切换加速状态
            print("切换加速模式(J)")
            if(self.supercap_ == 0):
                self.pushButton_speedup.setStyleSheet("")
                if(self.speed_==1 or self.speed_==2):
                    self.pushButton_fast.setStyleSheet("")
                    self.pushButton_slow.setStyleSheet("background-color: blue")
                print("未加速")
            elif(self.supercap_ == 1):
                self.pushButton_speedup.setStyleSheet("background-color: green")
                self.pushButton_fast.setStyleSheet("background-color: blue")
                self.pushButton_slow.setStyleSheet("")
                print("已加速")
        elif(self.mode_ == 1 and self.connect_ == 1):
            print("Invalid:只有遥控模式才可加速")

    def reset_move(self):
        if(self.mode_ == 0 and self.connect_ == 1):
            self.pushButton_goforward.setStyleSheet("")
            self.pushButton_backup.setStyleSheet("")
            self.pushButton_turnleft.setStyleSheet("")
            self.pushButton_turnright.setStyleSheet("")
            self.pushButton_back.setStyleSheet("")
            self.pushButton_forward.setStyleSheet("")
            self.pushButton_right.setStyleSheet("")
            self.pushButton_left.setStyleSheet("")
            self.pushButton_stop.setStyleSheet("background-color: blue")
            self.move_ = 0  # 恢复为初始状态
            print("停止")        

    def receive_data(self):
        """ 从串口接收数据并解析 """
        if self.ser and self.ser.in_waiting > 0:
        # if (1):
            # 如果串口有数据待接收
            data = self.ser.read(6)  # 假设结构体大小是 6 字节
            if len(data) == 6:
            # if(1):
                # 如果接收到的字节流长度是 6 字节（符合 Board2PC_t 结构体大小）
                board_data = Board2PC.from_bytes(data)
                
                # 将接收到的数据映射到PC机内的变量
                #TODO:待处理
                self.timestamp2 = board_data.timestamp2
                if(self.mode_ == 1):
                    # self.stopFlag_2 = board_data.stopFlag_ 
                    if(board_data.stopFlag_ == 0): # 检查 stopFlag_2 状态
                        if(self.stopFlag_2 == 1):
                            # stopFlag_2 从 1 变为 0，记录当前时间
                            # current_time = time.time()  # 获取当前时间戳
                            # self.timestamp_list.append(current_time)  # 记录到列表
                            # self.textEdit_2.append(f"时间记录：{current_time}")

                            # 将接收到的数据映射到PC机内的变量
                            current_time = time.time()
                            # 将时间戳转换为本地时间（年-月-日 时:分:秒）
                            current_time = time.localtime(current_time)  # 转换为结构体格式
                            formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', current_time)  # 格式化为字符串
                            
                            # 将记录的时间输出到 textEdit_2 控件中
                            self.textEdit_2.append(f"时间记录：{formatted_time}")
                            # 记录到时间列表
                            self.timestamp_list.append(formatted_time)


                        self.stopFlag_2 = 0
                        self.pushButton_stopstate.setStyleSheet("background-color: blue;")
                        self.pushButton_runstate.setStyleSheet("")
                    else:
                        self.stopFlag_2 = 1
                        self.pushButton_stopstate.setStyleSheet("")
                        self.pushButton_runstate.setStyleSheet("background-color: blue;")

                    # self.move_2 = board_data.move_
                    if(board_data.move_ == 0):
                        self.move_2 = 0
                        self.pushButton_stop.setStyleSheet("background-color: blue;")
                        self.pushButton_forward.setStyleSheet("")
                        self.pushButton_back.setStyleSheet("")
                        self.pushButton_left.setStyleSheet("")
                        self.pushButton_right.setStyleSheet("")
                    elif(board_data.move_ == 1):
                        self.move_2 = 1
                        self.pushButton_stop.setStyleSheet("")
                        self.pushButton_forward.setStyleSheet("background-color: blue;")
                        self.pushButton_back.setStyleSheet("")
                        self.pushButton_left.setStyleSheet("")
                        self.pushButton_right.setStyleSheet("") 
                    elif(board_data.move_ == 2):
                        self.move_2 = 2
                        self.pushButton_stop.setStyleSheet("")
                        self.pushButton_forward.setStyleSheet("")
                        self.pushButton_back.setStyleSheet("background-color: blue;")
                        self.pushButton_left.setStyleSheet("")
                        self.pushButton_right.setStyleSheet("")                                            
                    elif(board_data.move_ == 3):
                        self.move_2 = 3
                        self.pushButton_stop.setStyleSheet("")
                        self.pushButton_forward.setStyleSheet("")
                        self.pushButton_back.setStyleSheet("")
                        self.pushButton_left.setStyleSheet("background-color: blue;")
                        self.pushButton_right.setStyleSheet("")
                    elif(board_data.move_ == 4):
                        self.move_2 = 4
                        self.pushButton_stop.setStyleSheet("")
                        self.pushButton_forward.setStyleSheet("")
                        self.pushButton_back.setStyleSheet("")
                        self.pushButton_left.setStyleSheet("")
                        self.pushButton_right.setStyleSheet("background-color: blue;")

                # 显示接收到的数据
                self.textEdit_1.append(f"接收到数据: {board_data}")
            else:
                print("接收数据不完整")
        else:
            if(self.connect_):
                print("下位机没有发送数据")
                if(self.mode_ == 1):
                    self.pushButton_stopstate.setStyleSheet("")
                    self.pushButton_runstate.setStyleSheet("")
    # def read_serial_data(self):
    # #从串口读取数据并解析
    #     if self.ser and self.ser.in_waiting > 0:
    #         # 读取接收到的数据（假设结构体长度为8字节）
    #         data = self.ser.read(8)  # 假设数据是8字节
    #         if len(data) == 8:
    #             # 解包数据（<I B B 表示 uint32_t 和两个 uint8_t）
    #             board_data = struct.unpack('<IBB', data)
    #             timestamp2, stopFlag_, move_ = board_data
    #             print(f"接收到的数据 - 时间戳: {timestamp2}, 停止标志: {stopFlag_}, 移动状态: {move_}")

    #             # 将接收到的数据传递给 QTextEdit 显示
    #             self.textEdit_1.append(f"时间戳: {timestamp2}, 停止标志: {stopFlag_}, 移动状态: {move_}")

    def export_data_to_csv(self):
        """ 导出时间戳数据到 CSV 文件 """
        # self.timestamp_list
        try:
            # 定义 CSV 文件的文件名
            file_name = "StopTime.csv"
            # 打开 CSV 文件（以写入模式），并写入数据
            with open(file_name, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp"])  # 写入表头
                for timestamp in self.timestamp_list:
                    writer.writerow([timestamp])  # 写入每一条时间记录

            # 弹出提示框提示导出成功
            QMessageBox.information(self, "导出成功", f"时间序列已成功导出到 {file_name}")
        
        except Exception as e:
            # 弹出错误提示框
            QMessageBox.critical(self, "导出失败", f"导出失败：{str(e)}")    