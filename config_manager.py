"""加密配置管理器"""
import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class ConfigManager:
    """加密配置管理器 - 将配置加密保存到用户目录"""

    DEFAULT_CONFIG = {
        'gif_path': 'normal.gif',
        'reminder_gif_path': 'touchhead.gif',
        'reminder_interval': 30,
        'reminder_time': 60,
        'reminder_count': 30,
        'reminder_text': '该喝水了哦宝宝！记得保持水分充足哦~',
        'reminder_text_color': '(65, 112, 224, 1.0)',
        'to_time': '23:00',
        'weather': '110000',
        'weather_key': '',
        'drink_font_size': 12,
        'weather_font_size': 11,
        'auto_start': 1,
        'window_x': 720,
        'window_y': 360,
        'subtitle_enabled': 0,
        'subtitle_text': '该喝水啦~',
        'subtitle_position': 'right',
        'subtitle_font_size': 64
    }

    def __init__(self):
        self.config_dir = os.path.join(os.getenv('APPDATA'), 'DrinkReminder')
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, 'config.dat')
        self.cipher = self._create_cipher()

    def _create_cipher(self):
        """基于机器特征创建加密器"""
        import uuid
        machine_id = str(uuid.getnode()).encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'drink_reminder_salt_v1',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(machine_id))
        return Fernet(key)

    def load(self):
        """加载配置，不存在则返回默认配置"""
        if not os.path.exists(self.config_file):
            config = self.DEFAULT_CONFIG.copy()
            self.save(config)
            return config
        try:
            with open(self.config_file, 'rb') as f:
                encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            config = json.loads(decrypted.decode('utf-8'))
            # 补全缺失的配置项
            for key, val in self.DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = val
            return config
        except Exception as e:
            print(f"配置加载失败，使用默认配置: {e}")
            return self.DEFAULT_CONFIG.copy()

    def save(self, config):
        """保存配置"""
        try:
            data = json.dumps(config, ensure_ascii=False, indent=2)
            encrypted = self.cipher.encrypt(data.encode('utf-8'))
            with open(self.config_file, 'wb') as f:
                f.write(encrypted)
        except Exception as e:
            print(f"配置保存失败: {e}")
