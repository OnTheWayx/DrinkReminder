import tkinter as tk
from tkinter import messagebox, filedialog
import configparser
import os
import time
import threading
from PIL import Image, ImageTk, ImageSequence
import sys
from datetime import datetime
import requests

class HydrationReminder:
    def __init__(self):
        # 获取程序所在目录
        # 如果是打包后的 exe 程序，使用 sys.executable 获取 exe 所在目录
        # 如果是源码运行，使用 __file__ 获取脚本所在目录
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 程序
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # 源码运行
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 初始化配置
        self.config_file = os.path.join(self.app_dir, "hydration_config.ini")
        self.load_or_create_config()
        
        # 检查GIF文件是否存在
        if not os.path.exists(self.gif_path):
            messagebox.showerror("错误", f"GIF文件不存在: {self.gif_path}\n\n请确保配置文件中的GIF路径正确。")
            sys.exit(1)  # 终止程序
        
        # 初始化主窗口（完全透明背景，无边框）
        self.root = tk.Tk()
        self.root.title("")
        self.root.overrideredirect(True)  # 无边框窗口
        self.root.attributes("-topmost", True)  # 置顶
        self.root.resizable(False, False)
        
        # 设置透明度
        self.root.attributes("-alpha", 0.8)
        
        # 设置窗口背景为透明
        self.root.config(bg='white')  # 使用白色作为透明色
        self.root.wm_attributes("-transparentcolor", 'white')  # 设置白色为透明色
        
        # 创建GIF动画标签（直接在根窗口上）
        self.gif_label = tk.Label(self.root, bg='white', highlightthickness=0)
        self.gif_label.pack()
        
        # 创建提示标签（初始为空，隐藏）
        self.label = tk.Label(
            self.root,
            text="",
            font=("Arial", self.drink_font_size, "bold"),
            fg="white",
            bg="white",
            wraplength=200,
            padx=5,
            pady=5
        )
        # 不立即打包标签，只在需要时显示
        self.label_visible = False
        
        # 初始化提醒状态
        self.reminder_active = False
        self.reminder_thread = None

        # 隐藏状态
        self.hidden_mode = False
        self.hidden_canvas_widget = None
        
        # 动画控制变量
        self.animation_id = None
        
        # 创建天气 Canvas（用于绘制带描边的文字）
        self.weather_canvas = tk.Canvas(
            self.root,
            bg='white',  # 白色背景与窗口透明色一致
            highlightthickness=0,
            width=340,
            height=60
        )
        # 不立即打包，只在需要时显示
        self.weather_canvas_visible = False
        
        # 加载 GIF
        self.load_gif()
        # 加载提醒时的GIF
        self.load_reminder_gif()
        
        # 初始化天气缓存（两个独立缓存，互不影响）
        self._now_weather_text = ''
        self._tomorrow_weather_text = ''
        
        # 记录上一次更新明日天气的时间
        self._last_forecast_update_time = None
        
        # 初始化天气信息
        if self.weather != '0':
            self.update_weather_info()
            # 启动定时更新：现在天气每 30 分钟更新，明日天气每 2 小时更新
            self.schedule_weather_updates()
        
        # 记录初始位置
        self.start_x = 0
        self.start_y = 0
        
        # 绑定拖拽事件到GIF标签
        self.gif_label.bind("<Button-1>", self.start_drag)
        self.gif_label.bind("<B1-Motion>", self.drag_window)
        self.gif_label.bind("<ButtonRelease-1>", self.save_position)  # 添加释放鼠标事件
        self.gif_label.bind("<Double-Button-1>", self.on_double_click)  # 双击切换隐藏状态
        
        # 定位窗口到上次保存的位置或默认位置
        self.position_window()
        
        # 启动提醒线程
        self.start_reminder_thread()
        
        # 设置开机自启动
        self.setup_auto_start()
        
    def load_or_create_config(self):
        """加载或创建配置文件"""
        self.config = configparser.ConfigParser()
        
        if not os.path.exists(self.config_file):
            # 创建默认配置
            self.config['Settings'] = {
                'reminder_interval': '30',  # 默认30分钟
                'reminder_count': '10',     # 默认10次
                'reminder_text': '该喝水了！记得保持水分充足哦~',
                'gif_path': 'pika.gif',  # 默认使用pika.gif
                'reminder_gif_path': 'pika.gif',  # 默认使用pika.gif作为提醒时的GIF
                'window_x': '-1',           # 默认x坐标
                'window_y': '-1'            # 默认y坐标
            }
            self.save_config()
        else:
            # 读取现有配置文件，保留所有内容
            self.config.read(self.config_file, encoding='utf-8')
            
            # 确保必要的配置项存在，如果不存在则添加默认值
            if not self.config.has_section('Settings'):
                self.config.add_section('Settings')
                
            if not self.config.has_option('Settings', 'reminder_interval'):
                self.config.set('Settings', 'reminder_interval', '30')
            if not self.config.has_option('Settings', 'reminder_count'):
                self.config.set('Settings', 'reminder_count', '10')
            if not self.config.has_option('Settings', 'reminder_text'):
                self.config.set('Settings', 'reminder_text', '该喝水了！记得保持水分充足哦~')
            if not self.config.has_option('Settings', 'gif_path'):
                self.config.set('Settings', 'gif_path', os.path.join(self.app_dir, 'drink.gif'))
            if not self.config.has_option('Settings', 'window_x'):
                self.config.set('Settings', 'window_x', '-1')
            if not self.config.has_option('Settings', 'window_y'):
                self.config.set('Settings', 'window_y', '-1')
            if not self.config.has_option('Settings', 'reminder_gif_path'):
                self.config.set('Settings', 'reminder_gif_path', 'pika.gif')
            if not self.config.has_option('Settings', 'reminder_text_color'):
                self.config.set('Settings', 'reminder_text_color', '(255, 255, 255, 1.0)')
            if not self.config.has_option('Settings', 'to_time'):
                self.config.set('Settings', 'to_time', '23:59')
            if not self.config.has_option('Settings', 'weather'):
                self.config.set('Settings', 'weather', '0')
            if not self.config.has_option('Settings', 'drink_font_size'):
                self.config.set('Settings', 'drink_font_size', '12')
            if not self.config.has_option('Settings', 'weather_font_size'):
                self.config.set('Settings', 'weather_font_size', '11')
            if not self.config.has_option('Settings', 'weather_key'):
                self.config.set('Settings', 'weather_key', '')
            if not self.config.has_option('Settings', 'auto_start'):
                self.config.set('Settings', 'auto_start', '0')
            if not self.config.has_option('Settings', 'reminder_time'):
                self.config.set('Settings', 'reminder_time', '8')
        
        # 读取配置值
        self.interval = int(self.config.get('Settings', 'reminder_interval', fallback='30'))
        self.count = int(self.config.get('Settings', 'reminder_count', fallback='10'))
        
        # 读取并验证提醒时长
        try:
            reminder_time = int(self.config.get('Settings', 'reminder_time', fallback='8'))
            # 确保在有效范围内 3-120 秒
            reminder_time = max(3, min(120, reminder_time))
            # 转换为毫秒
            reminder_time_ms = reminder_time * 1000
            # 确保不大于提醒间隔-1（转换为毫秒）
            max_reminder_time = (self.interval * 60 - 1) * 1000
            self.reminder_time = min(reminder_time_ms, max_reminder_time)
        except ValueError:
            self.reminder_time = 8000
        self.reminder_text = self.config.get('Settings', 'reminder_text', fallback='该喝水了！记得保持水分充足哦~')
        gif_path = self.config.get('Settings', 'gif_path', fallback='pika.gif')
        # 检查路径是否为绝对路径，如果不是则使用相对路径
        if not os.path.isabs(gif_path):
            self.gif_path = os.path.join(self.app_dir, gif_path)
        else:
            self.gif_path = gif_path
        
        # 读取提醒时的GIF路径
        reminder_gif_path = self.config.get('Settings', 'reminder_gif_path', fallback='pika.gif')
        if not os.path.isabs(reminder_gif_path):
            self.reminder_gif_path = os.path.join(self.app_dir, reminder_gif_path)
        else:
            self.reminder_gif_path = reminder_gif_path
        
        # 读取提示语颜色
        reminder_text_color = self.config.get('Settings', 'reminder_text_color', fallback='(255, 255, 255, 1.0)')
        # 解析RGBA值
        try:
            # 移除括号并分割值
            color_values = reminder_text_color.strip('()').split(',')
            r, g, b, a = [float(val.strip()) for val in color_values]
            # 确保值在有效范围内
            r = max(0, min(255, int(r)))
            g = max(0, min(255, int(g)))
            b = max(0, min(255, int(b)))
            a = max(0, min(1.0, a))
            # 转换为十六进制颜色代码（Tkinter不直接支持RGBA）
            self.reminder_text_color = f'#{r:02x}{g:02x}{b:02x}'
        except Exception as e:
            # 如果解析失败，使用默认白色
            print(f"提示语颜色解析失败，使用默认白色: {e}")
            self.reminder_text_color = 'white'
        
        # 读取提醒截止时间
        self.to_time = self.config.get('Settings', 'to_time', fallback='23:59')
        
        # 读取天气配置
        self.weather = self.config.get('Settings', 'weather', fallback='0')
        
        # 读取字体大小配置
        self.drink_font_size = int(self.config.get('Settings', 'drink_font_size', fallback='12'))
        self.weather_font_size = int(self.config.get('Settings', 'weather_font_size', fallback='11'))
        
        # 读取天气 API key
        self.weather_key = self.config.get('Settings', 'weather_key', fallback='')
        
        # 读取开机自启动配置
        self.auto_start = self.config.get('Settings', 'auto_start', fallback='0')
        
        self.window_x = int(self.config.get('Settings', 'window_x', fallback='-1'))
        self.window_y = int(self.config.get('Settings', 'window_y', fallback='-1'))
        
    def save_config(self):
        """保存配置到文件，保留原有内容包括注释和换行"""
        # 读取原始文件内容
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []
        
        # 检查原始文件中哪些配置项已经存在
        existing_keys = set()
        in_settings_section = False
        
        for line in lines:
            if line.strip().lower() == '[settings]':
                in_settings_section = True
            elif line.strip().startswith('[') and line.strip().endswith(']'):
                in_settings_section = False
            elif in_settings_section and line.strip() and '=' in line and not line.strip().startswith('#'):
                key = line.strip().split('=')[0].strip()
                existing_keys.add(key)
        
        # 更新需要修改的键值对
        updated_lines = []
        in_settings_section = False
        # 用于跟踪已经处理过的配置项
        processed_keys = set()
        
        for line in lines:
            # 检查是否进入[Settings]节
            if line.strip().lower() == '[settings]':
                in_settings_section = True
                updated_lines.append(line)
            elif line.strip().startswith('[') and line.strip().endswith(']'):
                # 进入其他节
                in_settings_section = False
                updated_lines.append(line)
            elif in_settings_section and line.strip() and '=' in line and not line.strip().startswith('#'):
                # 提取键名
                key = line.strip().split('=')[0].strip()
                
                # 如果是配置项，并且还没有处理过
                if key in ['window_x', 'window_y', 'reminder_gif_path', 'reminder_text_color', 'to_time', 'weather', 'drink_font_size', 'weather_font_size', 'weather_key', 'auto_start']:
                    if key not in processed_keys:
                        # 更新配置项
                        if key == 'window_x':
                            updated_lines.append(f'window_x = {self.window_x}\n')
                        elif key == 'window_y':
                            updated_lines.append(f'window_y = {self.window_y}\n')
                        elif key == 'reminder_gif_path':
                            updated_lines.append(f'reminder_gif_path = {os.path.basename(self.reminder_gif_path)}\n')
                        elif key == 'reminder_text_color':
                            updated_lines.append(f'reminder_text_color = {self.config.get("Settings", "reminder_text_color", fallback="(255, 255, 255, 1.0)")}\n')
                        elif key == 'to_time':
                            updated_lines.append(f'to_time = {self.to_time}\n')
                        elif key == 'weather':
                            updated_lines.append(f'weather = {self.weather}\n')
                        elif key == 'drink_font_size':
                            updated_lines.append(f'drink_font_size = {self.drink_font_size}\n')
                        elif key == 'weather_font_size':
                            updated_lines.append(f'weather_font_size = {self.weather_font_size}\n')
                        elif key == 'weather_key':
                            updated_lines.append(f'weather_key = {self.weather_key}\n')
                        elif key == 'auto_start':
                            updated_lines.append(f'auto_start = {self.auto_start}\n')
                        processed_keys.add(key)
                else:
                    # 保留其他行不变
                    updated_lines.append(line)
            else:
                # 保留其他行不变
                updated_lines.append(line)
        
        # 如果没有找到window_x或window_y，在[Settings]节末尾添加
        content = ''.join(updated_lines)
        
        # 要添加的配置项
        config_items_to_add = []
        if 'window_x' not in existing_keys:
            config_items_to_add.append(f'window_x = {self.window_x}')
        if 'window_y' not in existing_keys:
            config_items_to_add.append(f'window_y = {self.window_y}')
        if 'reminder_gif_path' not in existing_keys:
            config_items_to_add.append(f'reminder_gif_path = {os.path.basename(self.reminder_gif_path)}')
        if 'reminder_text_color' not in existing_keys:
            config_items_to_add.append(f'reminder_text_color = {self.config.get("Settings", "reminder_text_color", fallback="(255, 255, 255, 1.0)")}')
        if 'to_time' not in existing_keys:
            config_items_to_add.append(f'to_time = {self.to_time}')
        if 'weather' not in existing_keys:
            config_items_to_add.append(f'weather = {self.weather}')
        if 'drink_font_size' not in existing_keys:
            config_items_to_add.append(f'drink_font_size = {self.drink_font_size}')
        if 'weather_font_size' not in existing_keys:
            config_items_to_add.append(f'weather_font_size = {self.weather_font_size}')
        if 'weather_key' not in existing_keys:
            config_items_to_add.append(f'weather_key = {self.weather_key}')
        if 'auto_start' not in existing_keys:
            config_items_to_add.append(f'auto_start = {self.auto_start}')
        
        # 如果有配置项需要添加
        if config_items_to_add:
            # 查找[Settings]节的位置
            settings_pos = content.find('[Settings]')
            if settings_pos != -1:
                # 找到节结束位置
                next_section_pos = content.find('[', settings_pos + 1)
                if next_section_pos == -1:
                    # 没有下一个节，添加到末尾
                    content += '\n' + '\n'.join(config_items_to_add) + '\n'
                else:
                    # 在下一节前插入
                    content = content[:next_section_pos] + '\n' + '\n'.join(config_items_to_add) + '\n' + content[next_section_pos:]
        
        # 写入更新后的内容
        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _get_virtual_screen_bounds(self):
        """获取虚拟屏幕边界（支持多显示器）

        在 Windows 上通过 ctypes 获取真实的虚拟屏幕范围，
        可以正确处理多显示器（包括左侧/上方扩展的负坐标显示器）。
        其他平台回退到基于主屏幕尺寸的估算。
        """
        try:
            import ctypes
            # SM_XVIRTUALSCREEN (76): 虚拟屏幕左边界
            # SM_YVIRTUALSCREEN (77): 虚拟屏幕上边界
            # SM_CXVIRTUALSCREEN (78): 虚拟屏幕总宽度
            # SM_CYVIRTUALSCREEN (79): 虚拟屏幕总高度
            user32 = ctypes.windll.user32
            virtual_left = user32.GetSystemMetrics(76)
            virtual_top = user32.GetSystemMetrics(77)
            virtual_width = user32.GetSystemMetrics(78)
            virtual_height = user32.GetSystemMetrics(79)
            virtual_right = virtual_left + virtual_width
            virtual_bottom = virtual_top + virtual_height
            return virtual_left, virtual_top, virtual_right, virtual_bottom
        except Exception:
            # 非 Windows 平台，使用主屏幕尺寸估算
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            return -screen_width, -screen_height, 2 * screen_width, 2 * screen_height

    def position_window(self):
        """定位窗口到上次保存的位置或默认位置"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 100  # GIF宽度
        window_height = 100  # GIF高度

        # 如果配置中有保存的位置，则使用保存的位置
        if self.window_x != -1 and self.window_y != -1:
            x = self.window_x
            y = self.window_y

            # 边界检查：确保窗口至少有一部分在虚拟屏幕内（支持多显示器）
            virtual_left, virtual_top, virtual_right, virtual_bottom = self._get_virtual_screen_bounds()
            min_visible = 20
            x = max(virtual_left - window_width + min_visible, min(x, virtual_right - min_visible))
            y = max(virtual_top, min(y, virtual_bottom - min_visible))
        else:
            # 否则设置为默认位置（屏幕右上角）
            x = screen_width - 150
            y = 20

        # 记录实际使用的位置，用于 save_position 的变化检测
        self.window_x = x
        self.window_y = y

        # 使用 Tkinter 的标准格式定位窗口（正确处理负坐标）
        self.root.geometry(f"+{x}+{y}")
    
    def save_position(self, event):
        """保存窗口当前位置到配置文件（仅在拖拽后触发）"""
        # 获取当前窗口位置
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()

        # 如果位置没有变化（只是点击，没有拖拽），不保存
        if current_x == self.window_x and current_y == self.window_y:
            return

        window_width = 100
        window_height = 100

        # 定义可见区域的最小像素数（窗口至少要有这么多像素可见才保存）
        min_visible = 20

        # 获取虚拟屏幕边界（支持多显示器）
        virtual_left, virtual_top, virtual_right, virtual_bottom = self._get_virtual_screen_bounds()

        # 检查窗口是否至少有一部分在虚拟屏幕范围内
        # 左方向：窗口右边缘必须在虚拟屏幕左边界右侧至少 min_visible 像素
        # 右方向：窗口左边缘必须在虚拟屏幕右边界左侧至少 min_visible 像素
        # 上方向：窗口下边缘必须在虚拟屏幕上边界下方至少 min_visible 像素
        # 下方向：窗口上边缘必须在虚拟屏幕下边界上方至少 min_visible 像素
        is_visible = (
            current_x + window_width > virtual_left + min_visible and   # 左边界检查
            current_x < virtual_right - min_visible and                 # 右边界检查
            current_y + window_height > virtual_top + min_visible and   # 上边界检查
            current_y < virtual_bottom - min_visible                    # 下边界检查
        )

        if is_visible:
            # 位置在有效范围内，保存到配置
            self.window_x = current_x
            self.window_y = current_y
            self.save_config()
        else:
            # 位置超出合理边界，不保存
            print(f"窗口位置超出合理边界，不保存：x={current_x}, y={current_y}")
    
    def load_gif(self):
        """加载GIF动画"""
        try:
            self.gif_image = Image.open(self.gif_path)
            self.gif_frames = []
            
            # 提取所有帧
            for frame in ImageSequence.Iterator(self.gif_image):
                frame_copy = frame.copy()
                frame_tk = ImageTk.PhotoImage(frame_copy.resize((100, 100), Image.Resampling.LANCZOS))
                self.gif_frames.append(frame_tk)
            
            # 显示第一帧
            self.gif_label.configure(image=self.gif_frames[0])
            
            # 开始动画
            self.current_frame = 0
            self.animate_gif()
        except Exception as e:
            # 如果GIF加载失败，显示错误信息
            self.gif_label.config(text="❌", font=("Arial", 50), bg="white", fg="red")
            print(f"GIF加载失败: {e}")
    
    def load_reminder_gif(self):
        """加载提醒时的GIF动画"""
        try:
            self.reminder_gif_image = Image.open(self.reminder_gif_path)
            self.reminder_gif_frames = []
            
            # 提取所有帧
            for frame in ImageSequence.Iterator(self.reminder_gif_image):
                frame_copy = frame.copy()
                frame_tk = ImageTk.PhotoImage(frame_copy.resize((100, 100), Image.Resampling.LANCZOS))
                self.reminder_gif_frames.append(frame_tk)
        except Exception as e:
            # 如果提醒GIF加载失败，使用普通GIF
            print(f"提醒GIF加载失败，使用普通GIF: {e}")
            if hasattr(self, 'gif_frames'):
                self.reminder_gif_frames = self.gif_frames
            else:
                self.reminder_gif_frames = []
    
    def update_weather_info(self, update_type='all'):
        """更新天气信息
        Args:
            update_type: 'now' - 只更新现在天气，'forecast' - 只更新明日天气，'all' - 更新全部
        """
        if self.weather == '0':
            return
        
        try:
            api_key = self.weather_key
            city_code = self.weather
            
            if not api_key:
                print("未设置天气 API key，请在配置文件中设置 weather_key")
                return
            
            city_name = ''
            
            # 根据更新类型处理
            if update_type == 'now':
                # 只更新现在天气：使用 extensions=base
                weather_url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city_code}&extensions=base"
                weather_response = requests.get(weather_url)
                weather_data = weather_response.json()
                
                if weather_data.get('status') == '1' and weather_data.get('infocode') == '10000':
                    lives = weather_data.get('lives', [])
                    if lives and len(lives) > 0:
                        current_weather = lives[0]
                        city_name = current_weather.get('city', '未知城市')
                        self._now_weather_text = f"{city_name}现在天气：{current_weather.get('weather')} {current_weather.get('temperature')}度\n"
            
            elif update_type == 'forecast':
                # 只更新明日天气：使用 extensions=all
                weather_url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city_code}&extensions=all"
                weather_response = requests.get(weather_url)
                weather_data = weather_response.json()
                
                if weather_data.get('status') == '1' and weather_data.get('infocode') == '10000':
                    forecasts = weather_data.get('forecasts')
                    if forecasts and len(forecasts) > 0:
                        forecast = forecasts[0]
                        city_name = forecast.get('city', '未知城市')
                        casts = forecast.get('casts', [])
                        if len(casts) > 1:
                            tomorrow = casts[1]
                            self._tomorrow_weather_text = f"{city_name}明日天气：{tomorrow.get('dayweather')} {tomorrow.get('nighttemp')}-{tomorrow.get('daytemp')}度\n"
            
            else:  # 'all' - 初始化时调用，需要同时获取两者
                # 1. 先获取实况天气
                now_url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city_code}&extensions=base"
                now_response = requests.get(now_url)
                now_data = now_response.json()
                
                if now_data.get('status') == '1' and now_data.get('infocode') == '10000':
                    lives = now_data.get('lives', [])
                    if lives and len(lives) > 0:
                        current_weather = lives[0]
                        city_name = current_weather.get('city', '未知城市')
                        self._now_weather_text = f"{city_name}现在天气：{current_weather.get('weather')} {current_weather.get('temperature')}度\n"
                
                # 2. 再获取预报天气
                forecast_url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}&city={city_code}&extensions=all"
                forecast_response = requests.get(forecast_url)
                forecast_data = forecast_response.json()
                
                if forecast_data.get('status') == '1' and forecast_data.get('infocode') == '10000':
                    forecasts = forecast_data.get('forecasts')
                    if forecasts and len(forecasts) > 0:
                        forecast = forecasts[0]
                        casts = forecast.get('casts', [])
                        if len(casts) > 1:
                            tomorrow = casts[1]
                            self._tomorrow_weather_text = f"{city_name}明日天气：{tomorrow.get('dayweather')} {tomorrow.get('nighttemp')}-{tomorrow.get('daytemp')}度\n"
            
            # 组合显示文本
            weather_text = ''
            if self._now_weather_text:
                weather_text += self._now_weather_text
            if self._tomorrow_weather_text:
                weather_text += self._tomorrow_weather_text
            
            # 更新天气 Canvas
            if weather_text:
                self.update_weather_canvas(weather_text)
                if not self.weather_canvas_visible:
                    self.gif_label.pack_forget()
                    self.weather_canvas.pack()
                    self.gif_label.pack()
                    self.weather_canvas_visible = True
            
        except Exception as e:
            print(f"获取天气信息失败：{e}")
            if self.weather_canvas_visible:
                self.weather_canvas.pack_forget()
                self.weather_canvas_visible = False
    
    def schedule_weather_updates(self):
        """安排天气定时更新"""
        # 更新现在天气（每 30 分钟）
        self.update_now_weather()
        # 更新明日天气（每 2 小时）
        self.update_forecast_weather()
    
    def update_now_weather(self):
        """定时更新现在天气"""
        if self.weather != '0':
            self.update_weather_info(update_type='now')
            # 30 分钟后再次更新
            self.root.after(1800000, self.update_now_weather)
    
    def update_forecast_weather(self):
        """定时更新明日天气 - 每分钟检查一次，满足条件时更新"""
        if self.weather != '0':
            current_time = datetime.now()
            current_day = current_time.day
            
            # 判断是否需要更新
            need_update = False
            
            if self._last_forecast_update_time is None:
                # 从未更新过，需要更新
                need_update = True
            else:
                # 计算距离上次更新的时间差（秒）
                time_diff = (current_time - self._last_forecast_update_time).total_seconds()
                last_day = self._last_forecast_update_time.day
                
                # 条件1：距离上次更新 >= 2小时（7200秒）
                if time_diff >= 7200:
                    need_update = True
                # 条件2：到了新的一天
                elif current_day != last_day:
                    need_update = True
            
            if need_update:
                # 执行更新
                self.update_weather_info(update_type='forecast')
                self._last_forecast_update_time = current_time
            
            # 每分钟检查一次
            self.root.after(60000, self.update_forecast_weather)
    
    def update_weather_canvas(self, weather_text):
        """更新天气 Canvas，绘制带描边的文字"""
        # 清空 Canvas
        self.weather_canvas.delete("all")
        
        # 文字样式
        font = ("Arial", self.weather_font_size, "bold")
        text_color = "#4170E0"  # 蓝色 (65, 112, 224)
        outline_color = "#000000"  # 黑色描边
        
        # 绘制描边文字（通过在不同位置绘制多次实现）
        offset = 1  # 描边偏移量
        positions = [
            (-offset, -offset), (offset, -offset),
            (-offset, offset), (offset, offset),
            (-offset, 0), (offset, 0),
            (0, -offset), (0, offset)
        ]
        
        # 分割文本为多行
        lines = weather_text.strip().split('\n')
        line_height = self.weather_font_size + 6  # 行高 = 字体大小 + 间距
        start_y = 8  # 起始 Y 坐标
        
        # 先绘制 8 个方向的描边
        for dx, dy in positions:
            y_offset = start_y + dy
            for i, line in enumerate(lines):
                self.weather_canvas.create_text(
                    10 + dx, y_offset + i * line_height,
                    text=line,
                    font=font,
                    fill=outline_color,
                    anchor="nw"
                )
        
        # 再绘制中间的蓝色文字
        y_offset = start_y
        for i, line in enumerate(lines):
            self.weather_canvas.create_text(
                10, y_offset + i * line_height,
                text=line,
                font=font,
                fill=text_color,
                anchor="nw"
            )
    
    def setup_auto_start(self):
        """设置开机自启动"""
        if self.auto_start == '1':
            self.enable_auto_start()
        elif self.auto_start == '0':
            self.disable_auto_start()
    
    def enable_auto_start(self):
        """启用开机自启动"""
        try:
            import winreg
            # 获取当前程序路径
            if getattr(sys, 'frozen', False):
                # 打包后的 exe 程序
                app_path = sys.executable
            else:
                # 源码运行，使用 python 解释器运行脚本
                app_path = f'python "{os.path.abspath(__file__)}"'
            
            # 打开注册表项
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            # 设置开机启动
            winreg.SetValueEx(key, "HydrationReminder", 0, winreg.REG_SZ, f'"{app_path}"')
            winreg.CloseKey(key)
            print("已启用开机自启动")
        except Exception as e:
            print(f"设置开机自启动失败：{e}")
    
    def disable_auto_start(self):
        """禁用开机自启动"""
        try:
            import winreg
            # 打开注册表项
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            
            # 删除开机启动项
            try:
                winreg.DeleteValue(key, "HydrationReminder")
                print("已禁用开机自启动")
            except FileNotFoundError:
                print("开机自启动项不存在")
            
            winreg.CloseKey(key)
        except Exception as e:
            print(f"禁用开机自启动失败：{e}")
    
    def animate_gif(self):
        """GIF动画循环"""
        if not self.reminder_active and hasattr(self, 'gif_frames') and len(self.gif_frames) > 0:
            self.gif_label.configure(image=self.gif_frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
            # 循环调用自身以继续动画
            self.animation_id = self.root.after(100, self.animate_gif)  # 100ms间隔
    
    def animate_reminder_gif(self):
        """提醒时的GIF动画循环"""
        if self.reminder_active and hasattr(self, 'reminder_gif_frames') and len(self.reminder_gif_frames) > 0:
            # 确保current_frame在有效范围内
            if self.current_frame >= len(self.reminder_gif_frames):
                self.current_frame = 0
            self.gif_label.configure(image=self.reminder_gif_frames[self.current_frame])
            self.current_frame = (self.current_frame + 1) % len(self.reminder_gif_frames)
            # 继续动画
            self.animation_id = self.root.after(100, self.animate_reminder_gif)
    
    def on_double_click(self, event):
        """双击切换隐藏状态（仅在正常状态或隐藏状态下有效）"""
        if self.reminder_active:
            # 喝水提醒状态下双击无效
            return
        if self.hidden_mode:
            self.exit_hidden_mode()
        else:
            self.enter_hidden_mode()

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """在Canvas上绘制圆角矩形"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1, x2, y1 + radius,
            x2, y2 - radius,
            x2, y2, x2 - radius, y2,
            x1 + radius, y2,
            x1, y2, x1, y2 - radius,
            x1, y1 + radius,
            x1, y1, x1 + radius, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def enter_hidden_mode(self):
        """进入隐藏状态"""
        self.hidden_mode = True

        # 取消GIF动画
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None

        # 隐藏GIF和天气
        self.gif_label.pack_forget()
        if self.weather_canvas_visible:
            self.weather_canvas.pack_forget()

        # 创建隐藏状态的Canvas（单一Canvas实现圆角背景+文字）
        if self.hidden_canvas_widget is not None:
            self.hidden_canvas_widget.destroy()

        # 使用特殊透明色作为Canvas背景，让圆角外的区域透明
        transparent_color = '#f0f0f0'
        bg_color = '#ffffff'
        text_color = '#4170E0'
        canvas_w, canvas_h = 100, 44
        radius = 12

        self.hidden_canvas_widget = tk.Canvas(
            self.root,
            bg=transparent_color,
            highlightthickness=0,
            width=canvas_w,
            height=canvas_h,
        )
        # 绘制圆角矩形背景（Canvas背景是透明色，只有圆角矩形区域可见）
        self._draw_rounded_rect(self.hidden_canvas_widget, 0, 0, canvas_w, canvas_h, radius, fill=bg_color, outline=bg_color)
        # 绘制三个递增大小的z
        self.hidden_canvas_widget.create_text(20, 34, text="z", font=("Arial", 14), fill=text_color, anchor="s")
        self.hidden_canvas_widget.create_text(50, 34, text="z", font=("Arial", 18), fill=text_color, anchor="s")
        self.hidden_canvas_widget.create_text(80, 34, text="z", font=("Arial", 24), fill=text_color, anchor="s")

        # 绑定事件
        self.hidden_canvas_widget.bind("<Button-1>", self.start_drag)
        self.hidden_canvas_widget.bind("<B1-Motion>", self.drag_window)
        self.hidden_canvas_widget.bind("<ButtonRelease-1>", self.save_position)
        self.hidden_canvas_widget.bind("<Double-Button-1>", self.on_double_click)

        self.hidden_canvas_widget.pack()

        # 将窗口背景和透明色都设为同一颜色，这样Canvas圆角外的区域会透明
        self.root.config(bg=transparent_color)
        self.root.wm_attributes("-transparentcolor", transparent_color)
        # 设置半透明
        self.root.attributes("-alpha", 0.6)

    def exit_hidden_mode(self):
        """退出隐藏状态"""
        self.hidden_mode = False

        # 隐藏Canvas
        if self.hidden_canvas_widget is not None:
            self.hidden_canvas_widget.pack_forget()

        # 恢复透明色设置
        self.root.config(bg='white')
        self.root.wm_attributes("-transparentcolor", 'white')

        # 恢复天气和GIF
        if self.weather_canvas_visible:
            self.weather_canvas.pack()
        self.gif_label.pack()

        # 恢复透明度
        self.root.attributes("-alpha", 0.8)

        # 重新启动GIF动画
        self.current_frame = 0
        self.animate_gif()

    def start_drag(self, event):
        """开始拖拽"""
        self.start_x = event.x
        self.start_y = event.y
    
    def drag_window(self, event):
        """拖拽窗口"""
        x = self.root.winfo_x() + event.x - self.start_x
        y = self.root.winfo_y() + event.y - self.start_y

        self.root.geometry(f"+{x}+{y}")
    
    def show_reminder(self):
        """显示提醒"""
        # 如果处于隐藏状态，先退出隐藏状态，提醒结束后会自动回到隐藏状态
        self._was_hidden = self.hidden_mode
        if self.hidden_mode:
            self.exit_hidden_mode()

        self.reminder_active = True
        
        # 取消之前的动画
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None
        
        # 切换到提醒GIF
        self.current_frame = 0
        self.animate_reminder_gif()
        
        # 显示提醒文本（放在GIF下方）
        self.label.config(text=self.reminder_text, fg=self.reminder_text_color)
        
        # 重新组织布局，让标签显示在GIF下方
        self.gif_label.pack_forget()
        self.gif_label.pack()
        self.label.pack(after=self.gif_label, side=tk.TOP, anchor=tk.CENTER)
        self.label_visible = True
        
        # 暂时增加透明度以便看清提醒
        self.root.attributes("-alpha", 1.0)
        
        # 使用配置的提醒时长自动隐藏提醒，恢复正常透明度
        self.root.after(self.reminder_time, self.hide_reminder)
    
    def hide_reminder(self):
        """隐藏提醒"""
        if self.label_visible:
            self.label.pack_forget()
            self.label_visible = False
        self.label.config(text="")
        self.root.attributes("-alpha", 0.8)
        self.reminder_active = False

        # 取消之前的动画
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None

        # 切换回普通GIF
        self.current_frame = 0
        self.gif_label.configure(image=self.gif_frames[0])
        # 重新开始普通GIF动画
        self.animate_gif()

        # 如果提醒前处于隐藏状态，恢复隐藏状态
        if getattr(self, '_was_hidden', False):
            self._was_hidden = False
            self.enter_hidden_mode()
    
    def reminder_worker(self):
        """提醒工作线程 - 无限循环，不退出"""
        count = 0
        last_day = datetime.now().day
        
        while True:
            current_datetime = datetime.now()
            current_day = current_datetime.day
            current_time = current_datetime.strftime('%H:%M')
            
            # 检查是否到了新的一天
            if current_day != last_day:
                # 新的一天开始，重置提醒次数
                count = 0
                last_day = current_day
                print(f"新的一天开始，重置提醒次数")
            
            # 检查当前时间是否超过提醒截止时间，超过的话不提醒，但不退出循环
            if current_time > self.to_time:
                # 超过截止时间，不提醒，继续等待新的一天
                time.sleep(self.interval * 60)
                continue
            
            # 检查是否在早上八点之前，八点前不进行提醒
            if current_datetime.hour < 8:
                # 早上八点前不提醒
                time.sleep(self.interval * 60)
                continue
            
            # 检查是否已经达到今天的提醒次数
            if count >= self.count:
                # 达到今天的提醒次数，不提醒，继续等待新的一天
                time.sleep(self.interval * 60)
                continue
            
            # 正常提醒流程
            time.sleep(self.interval * 60)
            
            # 再次检查时间，避免在睡眠期间超过截止时间
            current_datetime = datetime.now()
            current_time = current_datetime.strftime('%H:%M')
            
            # 再次检查是否到了新的一天
            if current_datetime.day != last_day:
                # 新的一天开始，重置提醒次数
                count = 0
                last_day = current_datetime.day
                print(f"新的一天开始，重置提醒次数")
            
            # 再次检查当前时间是否超过提醒截止时间
            if current_time > self.to_time:
                # 超过截止时间，不提醒
                continue
            
            # 再次检查是否在早上八点之前
            if current_datetime.hour < 8:
                # 早上八点前不提醒
                continue
            
            # 再次检查是否已经达到今天的提醒次数
            if count >= self.count:
                # 达到今天的提醒次数，不提醒
                continue
            
            # 在主线程中更新GUI
            self.root.after(0, self.show_reminder)
            
            count += 1
    
    def start_reminder_thread(self):
        """启动提醒线程"""
        self.reminder_thread = threading.Thread(target=self.reminder_worker, daemon=True)
        self.reminder_thread.start()

    def run(self):
        """运行主循环"""
        self.root.mainloop()


def main():
    app = HydrationReminder()
    app.run()

if __name__ == "__main__":
    main()
