"""设置对话框"""
import os
import tkinter as tk
from tkinter import filedialog, colorchooser

# 统一样式常量
_PAD = {'padx': 6, 'pady': 3}
_ENTRY_W = 28
_SPIN_W = 26


class SettingsDialog:
    """设置对话框 - 通过GUI配置所有参数"""

    def __init__(self, parent, current_config, app_dir, on_readme=None):
        self.app_dir = app_dir
        self.result = None
        self.on_readme = on_readme
        cfg = current_config

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("喝水提醒 - 设置")
        self.dialog.resizable(False, False)
        self.dialog.attributes("-topmost", True)
        self.dialog.grab_set()
        self.dialog.configure(bg='#f0f0f0')

        outer = tk.Frame(self.dialog, bg='#f0f0f0', padx=12, pady=8)
        outer.pack(fill=tk.BOTH, expand=True)

        # ── 外观设置 ──
        grp1 = tk.LabelFrame(outer, text=" 外观 ", padx=8, pady=6, bg='#f0f0f0')
        grp1.pack(fill=tk.X, pady=(0, 6))

        self.gif_path_var = tk.StringVar(value=cfg.get('gif_path', 'normal.gif'))
        self.reminder_gif_var = tk.StringVar(value=cfg.get('reminder_gif_path', 'touchhead.gif'))
        self.dfont_var = tk.IntVar(value=cfg.get('drink_font_size', 12))
        self.wfont_var = tk.IntVar(value=cfg.get('weather_font_size', 11))
        self.color_var = tk.StringVar(value=cfg.get('reminder_text_color', '(65, 112, 224, 1.0)'))

        r = 0
        tk.Label(grp1, text="默认GIF:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp1, textvariable=self.gif_path_var, width=_ENTRY_W).grid(row=r, column=1, **_PAD)
        tk.Button(grp1, text="浏览", width=4, command=lambda: self._browse(self.gif_path_var)).grid(row=r, column=2, **_PAD)
        r += 1
        tk.Label(grp1, text="提醒GIF:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp1, textvariable=self.reminder_gif_var, width=_ENTRY_W).grid(row=r, column=1, **_PAD)
        tk.Button(grp1, text="浏览", width=4, command=lambda: self._browse(self.reminder_gif_var)).grid(row=r, column=2, **_PAD)
        r += 1
        tk.Label(grp1, text="文字颜色:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        cf = tk.Frame(grp1, bg='#f0f0f0')
        cf.grid(row=r, column=1, sticky='w', **_PAD)
        self._color_preview = tk.Label(cf, width=3, relief='solid', bd=1)
        self._color_preview.pack(side=tk.LEFT, padx=(0, 4))
        tk.Entry(cf, textvariable=self.color_var, width=18).pack(side=tk.LEFT)
        tk.Button(grp1, text="选择", width=4, command=self._choose_color).grid(row=r, column=2, **_PAD)
        self._update_color_preview()
        self.color_var.trace_add('write', lambda *_: self._update_color_preview())
        r += 1
        tk.Label(grp1, text="提醒字体:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Spinbox(grp1, from_=8, to=24, textvariable=self.dfont_var, width=6).grid(row=r, column=1, sticky='w', **_PAD)
        r += 1
        tk.Label(grp1, text="天气字体:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Spinbox(grp1, from_=8, to=24, textvariable=self.wfont_var, width=6).grid(row=r, column=1, sticky='w', **_PAD)

        # ── 提醒设置 ──
        grp2 = tk.LabelFrame(outer, text=" 提醒 ", padx=8, pady=6, bg='#f0f0f0')
        grp2.pack(fill=tk.X, pady=(0, 6))

        self.interval_var = tk.IntVar(value=cfg.get('reminder_interval', 30))
        self.time_var = tk.IntVar(value=cfg.get('reminder_time', 60))
        self.count_var = tk.IntVar(value=cfg.get('reminder_count', 30))
        self.text_var = tk.StringVar(value=cfg.get('reminder_text', ''))
        self.to_time_var = tk.StringVar(value=cfg.get('to_time', '23:00'))

        r = 0
        # 间隔 / 时长 / 次数 放一行
        tk.Label(grp2, text="间隔(分):", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Spinbox(grp2, from_=1, to=120, textvariable=self.interval_var, width=6).grid(row=r, column=1, sticky='w', **_PAD)
        tk.Label(grp2, text="时长(秒):", bg='#f0f0f0').grid(row=r, column=2, sticky='w', **_PAD)
        tk.Spinbox(grp2, from_=3, to=120, textvariable=self.time_var, width=6).grid(row=r, column=3, sticky='w', **_PAD)
        tk.Label(grp2, text="次数:", bg='#f0f0f0').grid(row=r, column=4, sticky='w', **_PAD)
        tk.Spinbox(grp2, from_=1, to=100, textvariable=self.count_var, width=6).grid(row=r, column=5, sticky='w', **_PAD)
        r += 1
        tk.Label(grp2, text="提醒文字:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp2, textvariable=self.text_var, width=38).grid(row=r, column=1, columnspan=5, sticky='w', **_PAD)
        r += 1
        tk.Label(grp2, text="截止时间:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp2, textvariable=self.to_time_var, width=8).grid(row=r, column=1, sticky='w', **_PAD)
        tk.Label(grp2, text="(如 23:00)", fg='#888', bg='#f0f0f0').grid(row=r, column=2, columnspan=2, sticky='w', **_PAD)

        # ── 大号字幕设置 ──
        grp_sub = tk.LabelFrame(outer, text=" 大号字幕 ", padx=8, pady=6, bg='#f0f0f0')
        grp_sub.pack(fill=tk.X, pady=(0, 6))

        self.subtitle_enabled_var = tk.IntVar(value=cfg.get('subtitle_enabled', 0))
        self.subtitle_text_var = tk.StringVar(value=cfg.get('subtitle_text', '该喝水啦~'))
        self.subtitle_position_var = tk.StringVar(value=cfg.get('subtitle_position', 'right'))
        self.subtitle_font_var = tk.IntVar(value=cfg.get('subtitle_font_size', 128))

        r = 0
        tk.Checkbutton(grp_sub, text="启用大号字幕提醒", variable=self.subtitle_enabled_var, bg='#f0f0f0').grid(row=r, column=0, columnspan=2, sticky='w', **_PAD)
        r += 1
        tk.Label(grp_sub, text="字幕内容:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp_sub, textvariable=self.subtitle_text_var, width=_ENTRY_W).grid(row=r, column=1, sticky='w', **_PAD)
        r += 1
        tk.Label(grp_sub, text="显示位置:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        pos_frame = tk.Frame(grp_sub, bg='#f0f0f0')
        pos_frame.grid(row=r, column=1, sticky='w', **_PAD)
        for text, val in [("左侧", "left"), ("右侧", "right"), ("顶部", "top"), ("底部", "bottom")]:
            tk.Radiobutton(pos_frame, text=text, variable=self.subtitle_position_var, value=val, bg='#f0f0f0').pack(side=tk.LEFT, padx=2)
        r += 1
        tk.Label(grp_sub, text="字体大小:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Spinbox(grp_sub, from_=20, to=120, textvariable=self.subtitle_font_var, width=6).grid(row=r, column=1, sticky='w', **_PAD)

        # ── 天气设置 ──
        grp3 = tk.LabelFrame(outer, text=" 天气 ", padx=8, pady=6, bg='#f0f0f0')
        grp3.pack(fill=tk.X, pady=(0, 6))

        self.weather_var = tk.StringVar(value=cfg.get('weather', '110000'))
        self.key_var = tk.StringVar(value=cfg.get('weather_key', ''))

        r = 0
        tk.Label(grp3, text="城市代码:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp3, textvariable=self.weather_var, width=_ENTRY_W).grid(row=r, column=1, sticky='w', **_PAD)
        r += 1
        tk.Label(grp3, text="API Key:", bg='#f0f0f0').grid(row=r, column=0, sticky='w', **_PAD)
        tk.Entry(grp3, textvariable=self.key_var, width=_ENTRY_W, show='*').grid(row=r, column=1, sticky='w', **_PAD)

        # ── 其他 + 按钮 ──
        bottom = tk.Frame(outer, bg='#f0f0f0')
        bottom.pack(fill=tk.X, pady=(2, 0))

        self.autostart_var = tk.IntVar(value=cfg.get('auto_start', 1))
        tk.Checkbutton(bottom, text="开机自启动", variable=self.autostart_var, bg='#f0f0f0').pack(side=tk.LEFT)

        if self.on_readme:
            tk.Button(bottom, text="使用说明", width=8, command=self.on_readme).pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(bottom, text="取消", width=8, command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(bottom, text="保存", width=8, command=self._save).pack(side=tk.RIGHT)

        # 居中显示
        self.dialog.update_idletasks()
        w = self.dialog.winfo_reqwidth()
        h = self.dialog.winfo_reqheight()
        x = (self.dialog.winfo_screenwidth() - w) // 2
        y = (self.dialog.winfo_screenheight() - h) // 2
        self.dialog.geometry(f'{w}x{h}+{x}+{y}')

    def _update_color_preview(self):
        try:
            vals = self.color_var.get().strip('()').split(',')
            r, g, b = int(float(vals[0])), int(float(vals[1])), int(float(vals[2]))
            self._color_preview.configure(bg=f'#{r:02x}{g:02x}{b:02x}')
        except:
            pass

    def _browse(self, var):
        path = filedialog.askopenfilename(
            initialdir=self.app_dir,
            title="选择GIF文件",
            filetypes=(("GIF files", "*.gif"), ("All files", "*.*"))
        )
        if path:
            try:
                if os.path.commonpath([path, self.app_dir]) == self.app_dir:
                    path = os.path.relpath(path, self.app_dir)
            except ValueError:
                pass
            var.set(path)

    def _choose_color(self):
        try:
            vals = self.color_var.get().strip('()').split(',')
            r, g, b = int(float(vals[0])), int(float(vals[1])), int(float(vals[2]))
            init = f'#{r:02x}{g:02x}{b:02x}'
        except:
            init = '#4170e0'
        color = colorchooser.askcolor(color=init, title="选择提醒文字颜色")
        if color[0]:
            r, g, b = [int(c) for c in color[0]]
            self.color_var.set(f'({r}, {g}, {b}, 1.0)')

    def _save(self):
        self.result = {
            'gif_path': self.gif_path_var.get(),
            'reminder_gif_path': self.reminder_gif_var.get(),
            'reminder_interval': self.interval_var.get(),
            'reminder_time': self.time_var.get(),
            'reminder_count': self.count_var.get(),
            'reminder_text': self.text_var.get(),
            'reminder_text_color': self.color_var.get(),
            'to_time': self.to_time_var.get(),
            'weather': self.weather_var.get(),
            'weather_key': self.key_var.get(),
            'drink_font_size': self.dfont_var.get(),
            'weather_font_size': self.wfont_var.get(),
            'auto_start': self.autostart_var.get(),
            'subtitle_enabled': self.subtitle_enabled_var.get(),
            'subtitle_text': self.subtitle_text_var.get(),
            'subtitle_position': self.subtitle_position_var.get(),
            'subtitle_font_size': self.subtitle_font_var.get(),
        }
        self.dialog.destroy()

    def _cancel(self):
        self.result = None
        self.dialog.destroy()

    def show(self):
        """显示对话框并等待结果"""
        self.dialog.wait_window()
        return self.result
