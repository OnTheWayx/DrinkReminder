import tkinter as tk
from tkinter import messagebox, filedialog
import os
import time
import threading
from PIL import Image, ImageTk, ImageSequence
import sys
from datetime import datetime
import requests
import pystray
from config_manager import ConfigManager
from settings_dialog import SettingsDialog

def resource_path(relative_path):
    """获取内置资源的绝对路径（兼容 PyInstaller 打包和源码运行）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，内置资源解压到 sys._MEIPASS 临时目录
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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
        self.config_manager = ConfigManager()
        self.tray_icon = None
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
        self.hidden_anim_id = None
        self.hidden_anim_step = 0
        
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
        self.dragged = False  # 标记是否发生了实际拖拽

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

        # 创建系统托盘图标
        self.create_tray_icon()
        
    def load_or_create_config(self):
        """加载或创建配置"""
        cfg = self.config_manager.load()

        self.interval = int(cfg.get('reminder_interval', 30))
        self.count = int(cfg.get('reminder_count', 30))

        # 验证提醒时长
        try:
            rt = int(cfg.get('reminder_time', 60))
            rt = max(3, min(120, rt))
            rt_ms = rt * 1000
            max_rt = (self.interval * 60 - 1) * 1000
            self.reminder_time = min(rt_ms, max_rt)
        except ValueError:
            self.reminder_time = 60000

        self.reminder_text = cfg.get('reminder_text', '该喝水了哦宝宝！记得保持水分充足哦~')

        gif_path = cfg.get('gif_path', 'normal.gif')
        self.gif_path = self._resolve_gif_path(gif_path)

        reminder_gif_path = cfg.get('reminder_gif_path', 'touchhead.gif')
        self.reminder_gif_path = self._resolve_gif_path(reminder_gif_path)

        # 解析颜色
        color_str = cfg.get('reminder_text_color', '(65, 112, 224, 1.0)')
        try:
            vals = color_str.strip('()').split(',')
            r, g, b, a = [float(v.strip()) for v in vals]
            r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
            self.reminder_text_color = f'#{r:02x}{g:02x}{b:02x}'
        except:
            self.reminder_text_color = '#4170e0'

        self.to_time = cfg.get('to_time', '23:00')
        self.weather = str(cfg.get('weather', '110000'))
        self.drink_font_size = int(cfg.get('drink_font_size', 12))
        self.weather_font_size = int(cfg.get('weather_font_size', 11))
        self.weather_key = cfg.get('weather_key', '')
        self.auto_start = str(cfg.get('auto_start', 1))
        self.window_x = int(cfg.get('window_x', 720))
        self.window_y = int(cfg.get('window_y', 360))

    def _resolve_gif_path(self, gif_path):
        """解析GIF路径：优先使用外部文件，找不到则回退到内置资源"""
        if os.path.isabs(gif_path):
            if os.path.exists(gif_path):
                return gif_path
            # 绝对路径不存在，尝试内置资源
            return resource_path(os.path.basename(gif_path))
        # 相对路径：先查 app_dir（用户自定义），再查内置资源
        external = os.path.join(self.app_dir, gif_path)
        if os.path.exists(external):
            return external
        return resource_path(gif_path)

    def save_config(self):
        """保存配置到加密文件"""
        # 获取gif相对路径
        gif_rel = os.path.basename(self.gif_path) if self.gif_path.startswith(self.app_dir) else self.gif_path
        rgif_rel = os.path.basename(self.reminder_gif_path) if self.reminder_gif_path.startswith(self.app_dir) else self.reminder_gif_path

        # 将hex颜色转回RGBA字符串
        try:
            c = self.reminder_text_color.lstrip('#')
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            color_str = f'({r}, {g}, {b}, 1.0)'
        except:
            color_str = '(65, 112, 224, 1.0)'

        cfg = {
            'gif_path': gif_rel,
            'reminder_gif_path': rgif_rel,
            'reminder_interval': self.interval,
            'reminder_time': self.reminder_time // 1000,
            'reminder_count': self.count,
            'reminder_text': self.reminder_text,
            'reminder_text_color': color_str,
            'to_time': self.to_time,
            'weather': self.weather,
            'weather_key': self.weather_key,
            'drink_font_size': self.drink_font_size,
            'weather_font_size': self.weather_font_size,
            'auto_start': int(self.auto_start),
            'window_x': self.window_x,
            'window_y': self.window_y
        }
        self.config_manager.save(cfg)

    def create_tray_icon(self):
        """创建系统托盘图标"""
        # 创建一个简单的图标（蓝色水滴形状）
        icon_image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(icon_image)
        # 画一个蓝色圆形作为图标
        draw.ellipse([8, 8, 56, 56], fill=(65, 112, 224, 255))
        draw.ellipse([20, 20, 44, 44], fill=(120, 170, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem('设置', self._on_tray_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('退出', self._on_tray_quit)
        )

        self.tray_icon = pystray.Icon("DrinkReminder", icon_image, "喝水提醒", menu)
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def _on_tray_settings(self, icon=None, item=None):
        """系统托盘 - 设置"""
        self.root.after(0, self._show_settings_dialog)

    def _show_settings_dialog(self):
        """显示设置对话框"""
        # 获取当前配置
        try:
            c = self.reminder_text_color.lstrip('#')
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            color_str = f'({r}, {g}, {b}, 1.0)'
        except:
            color_str = '(65, 112, 224, 1.0)'

        current = {
            'gif_path': os.path.basename(self.gif_path) if self.gif_path.startswith(self.app_dir) else self.gif_path,
            'reminder_gif_path': os.path.basename(self.reminder_gif_path) if self.reminder_gif_path.startswith(self.app_dir) else self.reminder_gif_path,
            'reminder_interval': self.interval,
            'reminder_time': self.reminder_time // 1000,
            'reminder_count': self.count,
            'reminder_text': self.reminder_text,
            'reminder_text_color': color_str,
            'to_time': self.to_time,
            'weather': self.weather,
            'weather_key': self.weather_key,
            'drink_font_size': self.drink_font_size,
            'weather_font_size': self.weather_font_size,
            'auto_start': int(self.auto_start),
        }

        dialog = SettingsDialog(self.root, current, self.app_dir)
        result = dialog.show()

        if result:
            # 应用新配置
            self.interval = result['reminder_interval']
            self.count = result['reminder_count']
            self.reminder_text = result['reminder_text']
            self.to_time = result['to_time']
            self.weather = str(result['weather'])
            self.weather_key = result['weather_key']
            self.drink_font_size = result['drink_font_size']
            self.weather_font_size = result['weather_font_size']
            self.auto_start = str(result['auto_start'])

            # GIF路径
            gif_path = result['gif_path']
            self.gif_path = self._resolve_gif_path(gif_path)
            rgif_path = result['reminder_gif_path']
            self.reminder_gif_path = self._resolve_gif_path(rgif_path)

            # 颜色
            try:
                vals = result['reminder_text_color'].strip('()').split(',')
                r, g, b, a = [float(v.strip()) for v in vals]
                r, g, b = max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))
                self.reminder_text_color = f'#{r:02x}{g:02x}{b:02x}'
            except:
                pass

            # 提醒时长
            rt = max(3, min(120, result['reminder_time']))
            rt_ms = rt * 1000
            max_rt = (self.interval * 60 - 1) * 1000
            self.reminder_time = min(rt_ms, max_rt)

            self.save_config()
            self.setup_auto_start()

            # 取消现有动画定时器，防止重复叠加导致动画加速
            if self.animation_id:
                self.root.after_cancel(self.animation_id)
                self.animation_id = None

            # 重新加载GIF
            self.load_gif()
            self.load_reminder_gif()

            if self.weather != '0':
                self.update_weather_info()

            messagebox.showinfo("成功", "设置已保存！部分设置需要重启程序后生效。")

    def _on_tray_quit(self, icon=None, item=None):
        """系统托盘 - 退出"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self._do_quit)

    def _do_quit(self):
        """执行退出"""
        self.save_config()
        self.root.quit()
        self.root.destroy()
    
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
        # 如果没有发生实际拖拽，不需要判断保存
        if not self.dragged:
            return
        self.dragged = False

        # 如果在隐藏模式下拖拽（可能由切换前的鼠标按下事件触发），标记hidden_dragged
        if self.hidden_mode:
            self.hidden_dragged = True

        # 获取当前窗口位置
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()

        window_width = 100
        window_height = 100

        # 定义可见区域的最小像素数（窗口至少要有这么多像素可见才保存）
        min_visible = 100

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
        # 模式切换后窗口位置/大小已变，重新校准拖拽起点，防止后续拖拽位置突变
        self.start_x = event.x_root
        self.start_y = event.y_root

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
        # 隐藏状态 Canvas 的固定尺寸
        canvas_w, canvas_h = 35, 22

        # 先预算隐藏状态的目标位置，判断是否在屏幕内
        normal_x = self.root.winfo_x()
        normal_y = self.root.winfo_y()
        normal_w = self.root.winfo_width()
        normal_h = self.root.winfo_height()
        center_x = normal_x + normal_w // 2
        center_y = normal_y + normal_h // 2
        hidden_x = center_x - canvas_w // 2
        hidden_y = center_y - canvas_h // 2

        # 检查隐藏状态是否完全在屏幕外
        virtual_left, virtual_top, virtual_right, virtual_bottom = self._get_virtual_screen_bounds()
        if (hidden_x + canvas_w <= virtual_left or
                hidden_x >= virtual_right or
                hidden_y + canvas_h <= virtual_top or
                hidden_y >= virtual_bottom):
            # 隐藏状态会完全处于屏幕外，不进入隐藏状态
            return

        self.hidden_mode = True
        self.hidden_dragged = False  # 标记隐藏状态期间是否被拖拽过

        # 记录正常状态的窗口位置，用于退出隐藏时恢复
        self.normal_window_x = normal_x
        self.normal_window_y = normal_y

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
        canvas_w, canvas_h = 35, 22
        radius = 10

        self.hidden_canvas_widget = tk.Canvas(
            self.root,
            bg=transparent_color,
            highlightthickness=0,
            width=canvas_w,
            height=canvas_h,
        )
        # 绘制圆角矩形背景（Canvas背景是透明色，只有圆角矩形区域可见）
        self._draw_rounded_rect(self.hidden_canvas_widget, 0, 0, canvas_w, canvas_h, radius, fill=bg_color, outline=bg_color)
        # 绘制三个递增大小的z，使用tag标记以便动画控制显隐
        self.hidden_canvas_widget.create_text(8, 17, text="z", font=("Arial", 6), fill=text_color, anchor="s", tags="z1")
        self.hidden_canvas_widget.create_text(17, 17, text="z", font=("Arial", 8), fill=text_color, anchor="s", tags="z2")
        self.hidden_canvas_widget.create_text(27, 17, text="z", font=("Arial", 11), fill=text_color, anchor="s", tags="z3")

        # 绑定事件
        self.hidden_canvas_widget.bind("<Button-1>", self.start_drag)
        self.hidden_canvas_widget.bind("<B1-Motion>", self.drag_window)
        self.hidden_canvas_widget.bind("<ButtonRelease-1>", self._hidden_save_position)
        self.hidden_canvas_widget.bind("<Double-Button-1>", self.on_double_click)

        self.hidden_canvas_widget.pack()

        # 将窗口背景和透明色都设为同一颜色，这样Canvas圆角外的区域会透明
        self.root.config(bg=transparent_color)
        self.root.wm_attributes("-transparentcolor", transparent_color)
        # 设置半透明
        self.root.attributes("-alpha", 0.6)

        # 以正常状态中心点定位隐藏状态（使用预算好的位置）
        self.root.geometry(f"+{hidden_x}+{hidden_y}")

        # 启动z文字动画
        self.hidden_anim_step = 0
        self.animate_hidden_z()

    def animate_hidden_z(self):
        """隐藏状态下z文字的逐步显示动画"""
        if not self.hidden_mode or self.hidden_canvas_widget is None:
            return
        self.hidden_anim_step = (self.hidden_anim_step % 3) + 1
        # step 1: 只显示z1, step 2: 显示z1+z2, step 3: 显示z1+z2+z3
        self.hidden_canvas_widget.itemconfigure("z1", state='normal')
        self.hidden_canvas_widget.itemconfigure("z2", state='normal' if self.hidden_anim_step >= 2 else 'hidden')
        self.hidden_canvas_widget.itemconfigure("z3", state='normal' if self.hidden_anim_step >= 3 else 'hidden')
        self.hidden_anim_id = self.root.after(1200, self.animate_hidden_z)

    def _hidden_save_position(self, event):
        """隐藏状态下的鼠标释放处理"""
        if self.dragged:
            self.hidden_dragged = True  # 记录隐藏状态期间发生了拖拽
            # 隐藏状态下拖拽后也保存位置
            self.save_position(event)

    def exit_hidden_mode(self):
        """退出隐藏状态"""
        # 记录隐藏状态的窗口中心点（用于定位正常状态）
        hidden_x = self.root.winfo_x()
        hidden_y = self.root.winfo_y()
        hidden_w = self.root.winfo_width()
        hidden_h = self.root.winfo_height()
        hidden_center_x = hidden_x + hidden_w // 2
        hidden_center_y = hidden_y + hidden_h // 2

        self.hidden_mode = False

        # 取消z文字动画
        if self.hidden_anim_id:
            self.root.after_cancel(self.hidden_anim_id)
            self.hidden_anim_id = None

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

        # 定位正常状态窗口
        if hasattr(self, 'hidden_dragged') and self.hidden_dragged:
            # 隐藏状态期间被拖拽过，以隐藏状态的中心点定位正常状态
            self.root.update_idletasks()
            normal_w = self.root.winfo_width()
            normal_h = self.root.winfo_height()
            new_x = hidden_center_x - normal_w // 2
            new_y = hidden_center_y - normal_h // 2
            self.root.geometry(f"+{new_x}+{new_y}")
            # 更新保存的位置
            self.window_x = new_x
            self.window_y = new_y
            self.save_config()
        else:
            # 隐藏状态期间没有被拖拽，恢复到进入隐藏前的正常位置
            restore_x = getattr(self, 'normal_window_x', self.window_x)
            restore_y = getattr(self, 'normal_window_y', self.window_y)
            self.root.geometry(f"+{restore_x}+{restore_y}")

        # 重新启动GIF动画
        self.current_frame = 0
        self.animate_gif()

    def start_drag(self, event):
        """开始拖拽"""
        # 使用屏幕绝对坐标，避免模式切换后控件坐标系不一致导致位置突变
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.dragged = False  # 重置拖拽标记

    def drag_window(self, event):
        """拖拽窗口"""
        dx = event.x_root - self.start_x
        dy = event.y_root - self.start_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy

        self.root.geometry(f"+{x}+{y}")
        self.start_x = event.x_root
        self.start_y = event.y_root
        self.dragged = True  # 标记发生了实际拖拽
    
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
        try:
            self.root.mainloop()
        finally:
            if self.tray_icon:
                self.tray_icon.stop()


def main():
    app = HydrationReminder()
    app.run()

if __name__ == "__main__":
    main()
