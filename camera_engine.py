# محرك الكاميرا ومعالجة الصور
import cv2
import numpy as np
import pytesseract
import base64
import os
import time
from PIL import Image
from config import Config

class CameraEngine:
    def __init__(self):
        self.camera = None
        self.frame_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 2  # ثواني بين الاكتشافات
        self.camera_index = Config.CAMERA_INDEX
        self.rtsp_url = Config.RTSP_URL
        self.frame_rate = Config.MAX_FPS
        self.resolution = (Config.CAMERA_WIDTH, Config.CAMERA_HEIGHT)
        # محاولة تهيئة الكاميرا (لا نفشل إذا لم تكن متصلة)
        try:
            self._init_camera()
        except Exception as e:
            print(f"تحذير: لم يتم تهيئة الكاميرا في البداية: {e}")
            print("سيتم المحاولة مرة أخرى عند طلب الإطار الأول")
        
    def set_mode(self, mode):
        """تغيير وضع التشغيل (للتوافق مع API القديم)"""
        # تم إزالة وضع المحاكاة، يتم استخدام الكاميرا فقط
        if mode != 'camera':
            self._init_camera()
    
    def apply_settings(self, settings):
        """تطبيق إعدادات الكاميرا الجديدة"""
        need_reinit = False
        
        if 'index' in settings and int(settings['index']) != self.camera_index:
            self.camera_index = int(settings['index'])
            need_reinit = True
        
        if 'rtspUrl' in settings:
            new_rtsp = settings['rtspUrl'] if settings['rtspUrl'] else None
            if new_rtsp != self.rtsp_url:
                self.rtsp_url = new_rtsp
                need_reinit = True
        
        if 'frameRate' in settings:
            self.frame_rate = int(settings['frameRate'])
        
        if 'resolution' in settings:
            resolution_str = settings['resolution']
            if 'x' in resolution_str:
                width, height = map(int, resolution_str.split('x'))
                self.resolution = (width, height)
                need_reinit = True
        
        if need_reinit:
            self._init_camera()
    
    def _init_camera(self):
        """تهيئة الكاميرا الحقيقية"""
        try:
            if self.camera:
                self.camera.release()
            
            # محاولة الاتصال بالكاميرا
            # أولاً: RTSP URL إذا كان متوفراً
            if self.rtsp_url:
                self.camera = cv2.VideoCapture(self.rtsp_url)
                # إعدادات للكاميرات الشبكية
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                # استخدام فهرس الكاميرا (0 للكاميرا الافتراضية)
                # على Raspberry Pi، عادة ما تكون الكاميرا في /dev/video0
                self.camera = cv2.VideoCapture(self.camera_index)
            
            # تطبيق إعدادات الدقة وFPS
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera.set(cv2.CAP_PROP_FPS, self.frame_rate)
            
            if not self.camera.isOpened():
                raise Exception("فشل في فتح الكاميرا")
            
            print(f"تم تهيئة الكاميرا بنجاح (مؤشر: {self.camera_index}, RTSP: {self.rtsp_url}, دقة: {self.resolution[0]}x{self.resolution[1]}, FPS: {self.frame_rate})")
                
        except Exception as e:
            print(f"خطأ في تهيئة الكاميرا: {e}")
            raise Exception(f"فشل في الاتصال بالكاميرا: {str(e)}")
    
    def get_frame(self):
        """الحصول على إطار مع معالجة OCR"""
        try:
            return self._get_camera_frame()
        except Exception as e:
            print(f"خطأ في الحصول على الإطار: {e}")
            return self._get_error_frame()
    
    def _get_camera_frame(self):
        """الحصول على إطار من الكاميرا الحقيقية"""
        if not self.camera or not self.camera.isOpened():
            # محاولة إعادة الاتصال
            try:
                self._init_camera()
            except:
                return self._get_error_frame()
        
        ret, frame = self.camera.read()
        if not ret:
            return self._get_error_frame()
        
        return self._process_frame(frame)
    
    def _process_frame(self, frame):
        """معالجة الإطار وتطبيق OCR"""
        # تحويل الإطار إلى JPEG
        _, jpeg = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
        
        # معالجة OCR
        bounding_boxes = []
        
        # تطبيق OCR حقيقي: أولاً نكتشف منطقة اللوحة، ثم نستخرج النص منها
        try:
            # اكتشاف منطقة اللوحة في الإطار
            plate_region = self._detect_plate_region(frame)
            if plate_region:
                x, y, w, h = plate_region
                # استخراج منطقة اللوحة من الإطار
                plate_roi = frame[y:y+h, x:x+w]
                
                # استخراج النص من منطقة اللوحة فقط
                plate_text = self._extract_plate_text(plate_roi)
                if plate_text and len(plate_text) >= 4:
                    bounding_boxes.append({
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h,
                        'plate_text': plate_text,
                        'confidence': 0.75
                    })
        except Exception as e:
            print(f"خطأ في OCR: {e}")
        
        return {
            'image': frame_base64,
            'bounding_boxes': bounding_boxes,
            'timestamp': time.time()
        }
    
    def _detect_plate_region(self, frame):
        """كشف منطقة اللوحة في الإطار"""
        # تحويل إلى رمادي
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # تطبيق blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # كشف الحواف
        edges = cv2.Canny(blurred, 50, 150)
        
        # البحث عن المربعات
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # تقريب المربع
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # التحقق من أن المربع له 4 زوايا
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(contour)
                aspect_ratio = w / h
                
                # التحقق من نسبة العرض إلى الارتفاع (لوحة السيارة)
                if 2.0 < aspect_ratio < 5.0 and w > 80 and h > 20:
                    return (x, y, w, h)
        
        return None
    
    def _extract_plate_text(self, frame):
        """استخراج نص اللوحة باستخدام OCR"""
        try:
            # تحويل إلى رمادي
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # تحسين الصورة
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            gray = cv2.bilateralFilter(gray, 11, 17, 17)
            
            # تطبيق threshold
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # تحويل إلى PIL Image
            pil_image = Image.fromarray(thresh)
            
            # تطبيق OCR
            text = pytesseract.image_to_string(pil_image, config=Config.OCR_CONFIG)
            
            # تنظيف النص
            text = ''.join(filter(str.isalnum, text))
            
            return text if len(text) >= 4 else None
            
        except Exception as e:
            print(f"خطأ في OCR: {e}")
            return None
    
    def _get_error_frame(self):
        """إطار خطأ"""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 50
        cv2.putText(frame, "خطأ في الكاميرا", (200, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        _, jpeg = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
        
        return {
            'image': frame_base64,
            'bounding_boxes': [],
            'timestamp': time.time()
        }
    
    def __del__(self):
        """تنظيف الموارد"""
        if self.camera:
            self.camera.release()
