# إعدادات نظام SilentTrack
import os
import platform

class Config:
    # إعدادات قاعدة البيانات
    DATABASE_PATH = 'silenttrack.db'
    
    # إعدادات Tesseract OCR
    # على Linux/Raspberry Pi، عادة ما يكون Tesseract في المسار التالي
    if platform.system() == 'Linux':
        TESSERACT_CMD = '/usr/bin/tesseract'
    else:
        # Windows (للتوافق مع بيئات التطوير)
        TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # إعدادات الكاميرا
    CAMERA_INDEX = 0  # 0 للكاميرا الافتراضية (/dev/video0 على Raspberry Pi)
    RTSP_URL = None   # رابط RTSP للكاميرا الشبكية (مثال: rtsp://username:password@ip:port/stream)
    CAMERA_WIDTH = 1280
    CAMERA_HEIGHT = 720
    
    # إعدادات النظام
    SECRET_KEY = 'silenttrack_secret_key_2024'
    DEBUG = True
    
    # إعدادات OCR
    # تكوين OCR للوحات السعودية (أرقام وإنجليزية)
    OCR_CONFIG = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    
    # إعدادات الواجهة
    FRAME_UPDATE_INTERVAL = 500  # milliseconds
    MAX_FPS = 15
    
    @staticmethod
    def init_app(app):
        # إنشاء المجلدات المطلوبة
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        os.makedirs('static/images', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        os.makedirs('models', exist_ok=True)
        os.makedirs('uploads', exist_ok=True)  # مجلد لحفظ الصور الملتقطة
