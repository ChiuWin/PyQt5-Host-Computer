#pyocd
import sys
import pyocd
from pyocd.core.helpers import ConnectHelper
from pyocd.core.memory_map import MemoryType

def main():
    print("=== PyOCD 调试界面 ===")
    print("正在连接到 DAPLink 设备，请稍候...")

    # 自动连接到设备
    session = ConnectHelper.session_with_chosen_probe()
    if session is None:
        print("未找到任何支持的调试器设备，请检查连接。")
        sys.exit(1)

    # 打开调试会话
    try:
        with session:
            target = session.target
            target.resume()  # 确保目标处于运行状态

            print("成功连接到设备！")
            print(f"设备名称: {session.board.target_type}")
            print("请输入要读取的内存地址（十六进制，输入 'exit' 退出）：")

            while True:
                address = input("> 地址: 0x").strip()
                if address.lower() == "exit":
                    print("退出调试界面。")
                    break
                
                try:
                    addr = int(address, 16)
                    value = target.read32(addr)  # 读取指定地址的数据（32位）
                    print(f"地址 0x{addr:08X} 的数据: 0x{value:08X}")
                except ValueError:
                    print("输入的地址无效，请重新输入。")
                except Exception as e:
                    print(f"读取地址 0x{address} 时出错: {str(e)}")
    except Exception as e:
        print(f"调试器会话出错: {str(e)}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
