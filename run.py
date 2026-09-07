#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SilentTrack - ملف التشغيل الرئيسي
نظام ALPR للشرطة السرية
"""

import os
import sys
from app import app, init_database

def main():
    """الدالة الرئيسية لتشغيل النظام"""
    print("=" * 60)
    print("🚗 SilentTrack - نظام ALPR للشرطة السرية")
    print("=" * 60)
    print()
    
    # التحقق من وجود Tesseract
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        print("✅ Tesseract OCR: متوفر")
    except Exception as e:
        print("❌ Tesseract OCR: غير متوفر")
        print(f"   الخطأ: {e}")
        print("   يرجى تثبيت Tesseract من: https://github.com/UB-Mannheim/tesseract/wiki")
        print()
    
    # التحقق من وجود OpenCV
    try:
        import cv2
        print(f"✅ OpenCV: متوفر (الإصدار {cv2.__version__})")
    except ImportError:
        print("❌ OpenCV: غير متوفر")
        print("   يرجى تثبيته: pip install opencv-python")
        print()
    
    # تهيئة قاعدة البيانات
    try:
        init_database()
        print("✅ قاعدة البيانات: تم تهيئتها بنجاح")
    except Exception as e:
        print(f"❌ قاعدة البيانات: خطأ في التهيئة - {e}")
        print()
    
    print()
    print("🌐 بدء تشغيل الخادم...")
    print("📱 افتح المتصفح وانتقل إلى: http://127.0.0.1:5000")
    print("👤 اسم المستخدم: admin")
    print("🔑 كلمة المرور: admin123")
    print()
    print("⏹️  لإيقاف الخادم: اضغط Ctrl+C")
    print("=" * 60)
    print()
    
    # تشغيل التطبيق
    try:
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=False  # تجنب إعادة التحميل التلقائي
        )
    except KeyboardInterrupt:
        print("\n🛑 تم إيقاف الخادم بواسطة المستخدم")
    except Exception as e:
        print(f"\n❌ خطأ في تشغيل الخادم: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
