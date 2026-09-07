#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SilentTrack - فحص المتطلبات
فحص جميع المتطلبات قبل تشغيل النظام
"""

import sys
import subprocess
import importlib
import os

def check_python_version():
    """فحص إصدار Python"""
    print("🐍 فحص إصدار Python...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 10:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro} - متوافق")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} - غير متوافق")
        print("   يرجى تثبيت Python 3.10 أو أحدث")
        return False

def check_package(package_name, import_name=None):
    """فحص وجود مكتبة"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = importlib.import_module(import_name)
        version = getattr(module, '__version__', 'غير معروف')
        print(f"   ✅ {package_name} - متوفر (الإصدار: {version})")
        return True
    except ImportError:
        print(f"   ❌ {package_name} - غير متوفر")
        return False

def check_tesseract():
    """فحص Tesseract OCR"""
    print("🔍 فحص Tesseract OCR...")
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"   ✅ Tesseract OCR - متوفر (الإصدار: {version})")
        return True
    except Exception as e:
        print(f"   ❌ Tesseract OCR - غير متوفر")
        print(f"   الخطأ: {e}")
        print("   يرجى تثبيت Tesseract من: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def check_opencv():
    """فحص OpenCV"""
    print("📷 فحص OpenCV...")
    try:
        import cv2
        version = cv2.__version__
        print(f"   ✅ OpenCV - متوفر (الإصدار: {version})")
        
        # فحص الكاميرا
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("   ✅ كاميرا - متاحة")
            cap.release()
        else:
            print("   ⚠️  كاميرا - غير متاحة (سيتم استخدام وضع المحاكاة)")
        
        return True
    except ImportError:
        print("   ❌ OpenCV - غير متوفر")
        return False

def check_flask():
    """فحص Flask"""
    print("🌐 فحص Flask...")
    return check_package("Flask", "flask")

def check_database():
    """فحص قاعدة البيانات"""
    print("🗄️  فحص قاعدة البيانات...")
    try:
        import sqlite3
        # محاولة إنشاء قاعدة بيانات تجريبية
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE test (id INTEGER)')
        conn.close()
        print("   ✅ SQLite - متوفر")
        return True
    except Exception as e:
        print(f"   ❌ SQLite - خطأ: {e}")
        return False

def check_file_structure():
    """فحص هيكلية الملفات"""
    print("📁 فحص هيكلية الملفات...")
    
    required_files = [
        'app.py',
        'config.py',
        'camera_engine.py',
        'requirements.txt',
        'README.md',
        'templates/layout.html',
        'templates/login.html',
        'templates/live_view.html',
        'templates/history.html',
        'templates/settings.html',
        'static/css/styles.css',
        'static/js/main.js',
        'assets/images/SilentTrack Logo.jpeg'
    ]
    
    missing_files = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - مفقود")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"   ⚠️  {len(missing_files)} ملف مفقود")
        return False
    else:
        print("   ✅ جميع الملفات المطلوبة متوفرة")
        return True

def install_requirements():
    """تثبيت المتطلبات"""
    print("📦 تثبيت المتطلبات...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("   ✅ تم تثبيت المتطلبات بنجاح")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ خطأ في تثبيت المتطلبات: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("=" * 60)
    print("🔧 SilentTrack - فحص المتطلبات")
    print("=" * 60)
    print()
    
    all_checks_passed = True
    
    # فحص Python
    if not check_python_version():
        all_checks_passed = False
    
    print()
    
    # فحص المكتبات الأساسية
    packages = [
        ("Flask", "flask"),
        ("Pillow", "PIL"),
        ("numpy", "numpy"),
        ("imutils", "imutils"),
        ("python-dotenv", "dotenv")
    ]
    
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_checks_passed = False
    
    print()
    
    # فحص Tesseract
    if not check_tesseract():
        all_checks_passed = False
    
    print()
    
    # فحص OpenCV
    if not check_opencv():
        all_checks_passed = False
    
    print()
    
    # فحص قاعدة البيانات
    if not check_database():
        all_checks_passed = False
    
    print()
    
    # فحص هيكلية الملفات
    if not check_file_structure():
        all_checks_passed = False
    
    print()
    print("=" * 60)
    
    if all_checks_passed:
        print("🎉 جميع المتطلبات متوفرة! يمكن تشغيل النظام.")
        print()
        print("لتشغيل النظام:")
        print("  python run.py")
        print("  أو")
        print("  python app.py")
        print()
        print("ثم افتح المتصفح على: http://127.0.0.1:5000")
    else:
        print("❌ بعض المتطلبات مفقودة. يرجى تثبيتها أولاً.")
        print()
        print("لتثبيت المكتبات المطلوبة:")
        print("  pip install -r requirements.txt")
        print()
        print("لتثبيت Tesseract:")
        print("  https://github.com/UB-Mannheim/tesseract/wiki")
    
    print("=" * 60)
    
    return all_checks_passed

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
