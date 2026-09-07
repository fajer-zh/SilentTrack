# SilentTrack - نظام ALPR للشرطة السرية
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import sqlite3
import cv2
import base64
import numpy as np
from PIL import Image
import pytesseract
import os
import datetime
import hashlib
import json
from config import Config
from camera_engine import CameraEngine

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# تهيئة Tesseract
pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_CMD

# تهيئة محرك الكاميرا
camera_engine = CameraEngine()

def init_database():
    """تهيئة قاعدة البيانات"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المركبات المبلغ عنها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reported_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT UNIQUE NOT NULL,
            vehicle_type TEXT,
            vehicle_color TEXT,
            owner_first_name TEXT,
            owner_second_name TEXT,
            owner_third_name TEXT,
            owner_fourth_name TEXT,
            report_type TEXT,
            registration_number TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ترحيل قاعدة البيانات - إضافة الأعمدة الجديدة إذا لم تكن موجودة
    migrate_database(cursor)
    
    # جدول الاكتشافات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT,
            status TEXT DEFAULT 'pending',
            confidence REAL,
            location TEXT,
            vehicle_type TEXT,
            vehicle_color TEXT,
            report_type TEXT
        )
    ''')
    
    # جدول طلبات الدعم
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detection_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            location TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (detection_id) REFERENCES detections (id)
        )
    ''')
    
    # إضافة مستخدم افتراضي
    default_password = hashlib.sha256('admin123'.encode()).hexdigest()
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password_hash) 
        VALUES ('admin', ?)
    ''', (default_password,))
    
    # إضافة لوحات تجريبية (يمكن حذفها في الإنتاج)
    # sample_plates = ['ABC123', 'XYZ789', 'DEF456', 'GHI012']
    # for plate in sample_plates:
    #     cursor.execute('''
    #         INSERT OR IGNORE INTO reported_vehicles (plate, notes) 
    #         VALUES (?, 'لوحة تجريبية للاختبار')
    #     ''', (plate,))
    
    conn.commit()
    conn.close()

def migrate_database(cursor):
    """ترحيل قاعدة البيانات - إضافة الأعمدة الجديدة"""
    try:
        # التحقق من وجود الأعمدة في جدول reported_vehicles
        cursor.execute("PRAGMA table_info(reported_vehicles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = {
            'vehicle_type': 'TEXT',
            'vehicle_color': 'TEXT',
            'owner_first_name': 'TEXT',
            'owner_second_name': 'TEXT',
            'owner_third_name': 'TEXT',
            'owner_fourth_name': 'TEXT',
            'report_type': 'TEXT',
            'registration_number': 'TEXT'
        }
        
        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                cursor.execute(f'ALTER TABLE reported_vehicles ADD COLUMN {column_name} {column_type}')
        
        # التحقق من وجود الأعمدة في جدول detections
        cursor.execute("PRAGMA table_info(detections)")
        columns = [column[1] for column in cursor.fetchall()]
        
        detection_new_columns = {
            'vehicle_type': 'TEXT',
            'vehicle_color': 'TEXT',
            'report_type': 'TEXT'
        }
        
        for column_name, column_type in detection_new_columns.items():
            if column_name not in columns:
                cursor.execute(f'ALTER TABLE detections ADD COLUMN {column_name} {column_type}')
        
    except Exception as e:
        print(f"خطأ في ترحيل قاعدة البيانات: {e}")
        # إذا فشل الترحيل، نعيد إنشاء الجداول
        pass

def get_db_connection():
    """الحصول على اتصال قاعدة البيانات"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    if 'user_id' in session:
        return redirect(url_for('live_view'))
    return redirect(url_for('login'))

@app.route('/assets/<path:filename>')
def assets(filename):
    """خدمة الملفات من مجلد assets"""
    return send_from_directory('assets', filename)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """صفحة تسجيل الدخول"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password_hash = ?',
            (username, password_hash)
        ).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('live_view'))
        else:
            return render_template('login.html', error='اسم المستخدم أو كلمة المرور غير صحيحة')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """تسجيل الخروج"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/live')
def live_view():
    """صفحة البث المباشر"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('live_view.html')

@app.route('/history')
def history():
    """صفحة السجل"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('history.html')

@app.route('/settings')
def settings():
    """صفحة الإعدادات"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('settings.html')

@app.route('/api/start_stream', methods=['POST'])
def start_stream():
    """بدء البث"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    data = request.get_json()
    mode = data.get('mode', 'simulator')
    
    camera_engine.set_mode(mode)
    return jsonify({'status': 'success', 'mode': mode})

@app.route('/api/frame')
def get_frame():
    """الحصول على إطار من الكاميرا"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    try:
        frame_data = camera_engine.get_frame()
        return jsonify(frame_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def normalize_plate(plate):
    """تطبيع رقم اللوحة: إزالة المسافات والأحرف الخاصة وتحويل إلى أحرف كبيرة"""
    if not plate:
        return ''
    import re
    return re.sub(r'[^A-Z0-9]', '', str(plate).upper())

@app.route('/api/detections', methods=['POST'])
def save_detection():
    """حفظ اكتشاف جديد"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    data = request.get_json()
    plate = data.get('plate')
    confidence = data.get('confidence', 0.75)
    status = data.get('status', 'pending')
    
    if not plate:
        return jsonify({'error': 'رقم اللوحة مطلوب'}), 400
    
    conn = get_db_connection()
    
    try:
        # تطبيع اللوحة المكتشفة
        normalized_plate = normalize_plate(plate)
        
        # البحث عن لوحة مبلغ عنها (تطابق مرن)
        vehicles = conn.execute(
            'SELECT * FROM reported_vehicles WHERE status = ?',
            ('active',)
        ).fetchall()
        
        vehicle = None
        for v in vehicles:
            vehicle_plate = normalize_plate(v['plate'])
            if vehicle_plate == normalized_plate:
                vehicle = v
                break
            # تطابق مرن: 80% تطابق
            if len(normalized_plate) >= 4 and len(vehicle_plate) >= 4:
                min_len = min(len(normalized_plate), len(vehicle_plate))
                matches = sum(1 for i in range(min_len) if normalized_plate[i] == vehicle_plate[i])
                if matches / min_len >= 0.8:
                    vehicle = v
                    break
        
        # حفظ الاكتشاف (جميع الاكتشافات يتم حفظها)
        cursor = conn.execute('''
            INSERT INTO detections (plate, confidence, status, vehicle_type, vehicle_color, report_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            plate,
            confidence,
            status,
            vehicle['vehicle_type'] if vehicle else None,
            vehicle['vehicle_color'] if vehicle else None,
            vehicle['report_type'] if vehicle else None
        ))
        
        detection_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"تم حفظ الاكتشاف بنجاح: {plate} (ID: {detection_id})")
        return jsonify({'status': 'success', 'detection_id': detection_id})
    except Exception as e:
        conn.close()
        print(f"خطأ في حفظ الاكتشاف: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/match', methods=['POST'])
def match_plate():
    """معالجة تطابق اللوحة"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    data = request.get_json()
    plate = data.get('plate')
    action = data.get('action', 'complete')
    
    conn = get_db_connection()
    
    if action == 'complete':
        # تحديث حالة الاكتشاف
        conn.execute(
            'UPDATE detections SET status = ? WHERE plate = ? AND status = ?',
            ('completed', plate, 'pending')
        )
    elif action == 'call_support':
        # إنشاء طلب دعم
        detection = conn.execute(
            'SELECT id FROM detections WHERE plate = ? AND status = ? ORDER BY timestamp DESC LIMIT 1',
            (plate, 'pending')
        ).fetchone()
        
        if detection:
            conn.execute(
                'INSERT INTO support_requests (detection_id, notes) VALUES (?, ?)',
                (detection['id'], f'طلب دعم للوحة {plate}')
            )
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

@app.route('/api/call_support', methods=['POST'])
def call_support():
    """طلب دعم"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    data = request.get_json()
    plate = data.get('plate')
    notes = data.get('notes', '')
    
    conn = get_db_connection()
    
    # البحث عن آخر اكتشاف للوحة
    detection = conn.execute(
        'SELECT id FROM detections WHERE plate = ? ORDER BY timestamp DESC LIMIT 1',
        (plate,)
    ).fetchone()
    
    if detection:
        conn.execute(
            'INSERT INTO support_requests (detection_id, notes) VALUES (?, ?)',
            (detection['id'], notes)
        )
    
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success'})

def safe_get(row, key, default=None):
    """الحصول على قيمة من sqlite3.Row بشكل آمن"""
    try:
        value = row[key]
        return value if value is not None and value != '' else default
    except (KeyError, IndexError):
        return default

@app.route('/api/history')
def get_history():
    """الحصول على السجل"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    try:
        conn = get_db_connection()
        detections = conn.execute('''
            SELECT d.*, rv.notes as vehicle_notes 
            FROM detections d 
            LEFT JOIN reported_vehicles rv ON d.plate = rv.plate 
            ORDER BY d.timestamp DESC 
            LIMIT 100
        ''').fetchall()
        
        history_data = []
        for detection in detections:
            try:
                # جلب معلومات المركبة من جدول reported_vehicles
                plate_number = safe_get(detection, 'plate', '')
                if not plate_number:
                    continue
                    
                vehicle = conn.execute(
                    'SELECT * FROM reported_vehicles WHERE plate = ?',
                    (plate_number,)
                ).fetchone()
                
                detection_vehicle_type = safe_get(detection, 'vehicle_type')
                detection_vehicle_color = safe_get(detection, 'vehicle_color')
                detection_report_type = safe_get(detection, 'report_type')
                
                # بناء اسم المالك الكامل
                owner_full_name = ''
                if vehicle:
                    owner_parts = []
                    first_name = safe_get(vehicle, 'owner_first_name')
                    if first_name:
                        owner_parts.append(first_name)
                    second_name = safe_get(vehicle, 'owner_second_name')
                    if second_name:
                        owner_parts.append(second_name)
                    third_name = safe_get(vehicle, 'owner_third_name')
                    if third_name:
                        owner_parts.append(third_name)
                    fourth_name = safe_get(vehicle, 'owner_fourth_name')
                    if fourth_name:
                        owner_parts.append(fourth_name)
                    owner_full_name = ' '.join(owner_parts).strip()
                
                confidence_value = safe_get(detection, 'confidence')
                try:
                    confidence_float = float(confidence_value) if confidence_value is not None else None
                except (ValueError, TypeError):
                    confidence_float = None
                
                history_data.append({
                    'id': safe_get(detection, 'id'),
                    'plate': safe_get(detection, 'plate', ''),
                    'timestamp': safe_get(detection, 'timestamp', ''),
                    'status': safe_get(detection, 'status', 'pending'),
                    'confidence': confidence_float,
                    'vehicle_type': safe_get(vehicle, 'vehicle_type') if vehicle else detection_vehicle_type,
                    'vehicle_color': safe_get(vehicle, 'vehicle_color') if vehicle else detection_vehicle_color,
                    'report_type': safe_get(vehicle, 'report_type') if vehicle else detection_report_type,
                    'owner_full_name': owner_full_name,
                    'registration_number': safe_get(vehicle, 'registration_number', '') if vehicle else '',
                    'vehicle_notes': safe_get(detection, 'vehicle_notes', '')
                })
            except Exception as e:
                detection_id = safe_get(detection, 'id', 'unknown')
                print(f"خطأ في معالجة الاكتشاف {detection_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        conn.close()
        return jsonify(history_data)
    except Exception as e:
        import traceback
        print(f"خطأ في الحصول على السجل: {e}")
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'خطأ في تحميل السجل: {str(e)}'}), 500

@app.route('/api/vehicles', methods=['GET', 'POST'])
def manage_vehicles():
    """إدارة المركبات المبلغ عنها"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    conn = get_db_connection()
    
    if request.method == 'GET':
        vehicles = conn.execute(
            'SELECT * FROM reported_vehicles ORDER BY created_at DESC'
        ).fetchall()
        
        vehicles_data = []
        for vehicle in vehicles:
            vehicles_data.append({
                'id': vehicle['id'],
                'plate': vehicle['plate'],
                'vehicle_type': vehicle['vehicle_type'],
                'vehicle_color': vehicle['vehicle_color'],
                'owner_first_name': vehicle['owner_first_name'],
                'owner_second_name': vehicle['owner_second_name'],
                'owner_third_name': vehicle['owner_third_name'],
                'owner_fourth_name': vehicle['owner_fourth_name'],
                'owner_full_name': f"{vehicle['owner_first_name'] or ''} {vehicle['owner_second_name'] or ''} {vehicle['owner_third_name'] or ''} {vehicle['owner_fourth_name'] or ''}".strip(),
                'report_type': vehicle['report_type'],
                'registration_number': vehicle['registration_number'],
                'status': vehicle['status'],
                'notes': vehicle['notes'],
                'created_at': vehicle['created_at']
            })
        
        conn.close()
        return jsonify(vehicles_data)
    
    elif request.method == 'POST':
        data = request.get_json()
        plate = data.get('plate')
        vehicle_type = data.get('vehicle_type', '')
        vehicle_color = data.get('vehicle_color', '')
        owner_first_name = data.get('owner_first_name', '')
        owner_second_name = data.get('owner_second_name', '')
        owner_third_name = data.get('owner_third_name', '')
        owner_fourth_name = data.get('owner_fourth_name', '')
        report_type = data.get('report_type', '')
        registration_number = data.get('registration_number', '')
        notes = data.get('notes', '')
        
        try:
            conn.execute('''
                INSERT INTO reported_vehicles 
                (plate, vehicle_type, vehicle_color, owner_first_name, owner_second_name, 
                 owner_third_name, owner_fourth_name, report_type, registration_number, notes) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (plate, vehicle_type, vehicle_color, owner_first_name, owner_second_name,
                  owner_third_name, owner_fourth_name, report_type, registration_number, notes))
            conn.commit()
            conn.close()
            return jsonify({'status': 'success'})
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'اللوحة موجودة بالفعل'}), 400

@app.route('/api/vehicles/<int:vehicle_id>', methods=['DELETE'])
def delete_vehicle(vehicle_id):
    """حذف مركبة"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    conn = get_db_connection()
    
    try:
        cursor = conn.execute('DELETE FROM reported_vehicles WHERE id = ?', (vehicle_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            conn.close()
            return jsonify({'status': 'success'})
        else:
            conn.close()
            return jsonify({'error': 'المركبة غير موجودة'}), 404
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    """إدارة إعدادات النظام"""
    if 'user_id' not in session:
        return jsonify({'error': 'غير مصرح'}), 401
    
    if request.method == 'GET':
        # تحميل الإعدادات
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                return jsonify({'settings': settings})
            except Exception as e:
                print(f"خطأ في قراءة الإعدادات: {e}")
        
        # إعدادات افتراضية
        default_settings = {
            'camera': {
                'mode': 'camera',
                'index': Config.CAMERA_INDEX,
                'rtspUrl': Config.RTSP_URL or '',
                'frameRate': 15,
                'resolution': '1280x720'
            },
            'ocr': {
                'tesseractPath': Config.TESSERACT_CMD,
                'language': 'eng',
                'confidence': 70
            },
            'system': {
                'language': 'ar',
                'theme': 'dark',
                'autoStart': False,
                'soundAlerts': True,
                'logLevel': 'info'
            }
        }
        return jsonify({'settings': default_settings})
    
    elif request.method == 'POST':
        # حفظ الإعدادات
        data = request.get_json()
        settings_file = os.path.join(os.path.dirname(__file__), 'settings.json')
        
        try:
            # قراءة الإعدادات الحالية (إن وجدت)
            current_settings = {}
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    current_settings = json.load(f)
            
            # دمج الإعدادات الجديدة مع الحالية
            current_settings.update(data)
            
            # حفظ الإعدادات
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(current_settings, f, indent=2, ensure_ascii=False)
            
            # تطبيق إعدادات الكاميرا
            if 'camera' in data:
                camera_settings = data['camera']
                if 'index' in camera_settings:
                    Config.CAMERA_INDEX = int(camera_settings['index'])
                if 'rtspUrl' in camera_settings:
                    Config.RTSP_URL = camera_settings['rtspUrl'] if camera_settings['rtspUrl'] else None
                if 'frameRate' in camera_settings:
                    Config.MAX_FPS = int(camera_settings['frameRate'])
                if 'resolution' in camera_settings:
                    resolution = camera_settings['resolution']
                    if 'x' in resolution:
                        width, height = map(int, resolution.split('x'))
                        Config.CAMERA_WIDTH = width
                        Config.CAMERA_HEIGHT = height
                
                # إعادة تهيئة الكاميرا بالإعدادات الجديدة
                camera_engine.apply_settings(camera_settings)
            
            return jsonify({'status': 'success'})
        except Exception as e:
            print(f"خطأ في حفظ الإعدادات: {e}")
            return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def system_status():
    """حالة النظام"""
    return jsonify({
        'status': 'online',
        'timestamp': datetime.datetime.now().isoformat(),
        'database': 'connected',
        'camera_mode': 'camera'
    })

if __name__ == '__main__':
    init_database()
    # الاستماع على 0.0.0.0 للسماح بالوصول من الشبكة (مفيد لـ Raspberry Pi)
    app.run(host='0.0.0.0', port=5000, debug=True)
