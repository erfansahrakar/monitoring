"""
⚙️ تنظیمات اصلی ربات - نسخه بهبود یافته
🔒 امن شده با Environment Variables
✅ تنظیمات مانیتورینگ
✅ تنظیمات Alert
✅ تنظیمات Performance
✅ Validation پیشرفته

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import os
import warnings
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# بارگذاری متغیرهای محیطی
load_dotenv()


# ==================== Helper Functions ====================

def get_env(key: str, default=None, required=True, value_type=str):
    """
    دریافت متغیر محیطی با type conversion
    
    Args:
        key: نام متغیر
        default: مقدار پیش‌فرض
        required: آیا الزامی است؟
        value_type: نوع داده (str, int, float, bool)
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"❌ متغیر محیطی {key} تنظیم نشده است!")
    
    if value is None:
        return default
    
    # تبدیل نوع
    try:
        if value_type == bool:
            if isinstance(value, bool):
                return value
            return str(value).lower() in ('true', '1', 'yes', 'on')
        elif value_type == int:
            return int(value)
        elif value_type == float:
            return float(value)
        else:
            return str(value)
    except (ValueError, AttributeError) as e:
        warnings.warn(f"⚠️ خطا در تبدیل {key}: {e}")
        return default


# ==================== Bot Configuration ====================

# توکن ربات - از BotFather دریافت کنید
BOT_TOKEN = get_env('BOT_TOKEN', required=True)

# آیدی عددی ادمین - از @userinfobot دریافت کنید
ADMIN_ID = get_env('ADMIN_ID', required=True, value_type=int)

# username کانال بدون @ - مثال: mychannel
CHANNEL_USERNAME = get_env('CHANNEL_USERNAME', required=True)


# ==================== Database Configuration ====================

# تنظیمات دیتابیس
DATABASE_NAME = get_env('DATABASE_NAME', default='shop_bot.db', required=False)

# مسیر ذخیره بکاپ‌ها
BACKUP_FOLDER = get_env('BACKUP_FOLDER', default='backups', required=False)

# ساعت بکاپ روزانه (فرمت 24 ساعته)
BACKUP_HOUR = get_env('BACKUP_HOUR', default=3, required=False, value_type=int)
BACKUP_MINUTE = get_env('BACKUP_MINUTE', default=0, required=False, value_type=int)


# ==================== Payment Configuration ====================

# شماره کارت برای پرداخت
CARD_NUMBER = get_env('CARD_NUMBER', required=True)
CARD_HOLDER = get_env('CARD_HOLDER', required=True)


# ==================== Logging Configuration ====================

# مسیر لاگ‌ها
LOG_FOLDER = get_env('LOG_FOLDER', default='logs', required=False)

# سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL = get_env('LOG_LEVEL', default='INFO', required=False)

# حداکثر سایز فایل لاگ (MB)
MAX_LOG_SIZE_MB = get_env('MAX_LOG_SIZE_MB', default=20, required=False, value_type=int)

# تعداد فایل‌های backup لاگ
LOG_BACKUP_COUNT = get_env('LOG_BACKUP_COUNT', default=10, required=False, value_type=int)


# ==================== Cache Configuration ====================

# زمان کش inline queries (ثانیه)
INLINE_CACHE_TIME = get_env('INLINE_CACHE_TIME', default=300, required=False, value_type=int)

# فعال/غیرفعال کردن کش
CACHE_ENABLED = get_env('CACHE_ENABLED', default=True, required=False, value_type=bool)

# زمان پیش‌فرض TTL کش (ثانیه)
CACHE_DEFAULT_TTL = get_env('CACHE_DEFAULT_TTL', default=300, required=False, value_type=int)

# فاصله پاکسازی خودکار کش (ثانیه)
CACHE_CLEANUP_INTERVAL = get_env('CACHE_CLEANUP_INTERVAL', default=300, required=False, value_type=int)


# ==================== Monitoring Configuration ====================

# فعال/غیرفعال کردن مانیتورینگ
MONITORING_ENABLED = get_env('MONITORING_ENABLED', default=True, required=False, value_type=bool)

# فاصله جمع‌آوری metrics (ثانیه)
MONITORING_INTERVAL = get_env('MONITORING_INTERVAL', default=300, required=False, value_type=int)

# حداکثر تعداد نقاط ذخیره شده برای هر متریک
MONITORING_MAX_POINTS = get_env('MONITORING_MAX_POINTS', default=1000, required=False, value_type=int)

# فعال/غیرفعال کردن Auto Health Check
AUTO_HEALTH_CHECK = get_env('AUTO_HEALTH_CHECK', default=True, required=False, value_type=bool)

# فاصله Health Check (ثانیه)
HEALTH_CHECK_INTERVAL = get_env('HEALTH_CHECK_INTERVAL', default=300, required=False, value_type=int)


# ==================== Alert Configuration ====================

# فعال/غیرفعال کردن Alert System
ALERTS_ENABLED = get_env('ALERTS_ENABLED', default=True, required=False, value_type=bool)

# ارسال اعلان‌های هشدار به تلگرام
ALERT_TELEGRAM_ENABLED = get_env('ALERT_TELEGRAM_ENABLED', default=True, required=False, value_type=bool)

# حداقل شدت برای ارسال به تلگرام (low, medium, high, critical)
ALERT_MIN_SEVERITY = get_env('ALERT_MIN_SEVERITY', default='high', required=False)

# Cooldown پیش‌فرض برای هشدارها (ثانیه)
ALERT_DEFAULT_COOLDOWN = get_env('ALERT_DEFAULT_COOLDOWN', default=300, required=False, value_type=int)

# Grace Period پیش‌فرض (ثانیه)
ALERT_GRACE_PERIOD = get_env('ALERT_GRACE_PERIOD', default=60, required=False, value_type=int)


# ==================== Notification Configuration ====================

# فعال/غیرفعال کردن Notification Service
NOTIFICATIONS_ENABLED = get_env('NOTIFICATIONS_ENABLED', default=True, required=False, value_type=bool)

# حداکثر اعلان در دقیقه (rate limiting)
NOTIFICATION_RATE_LIMIT = get_env('NOTIFICATION_RATE_LIMIT', default=10, required=False, value_type=int)

# تعداد دفعات retry برای اعلان‌های ناموفق
NOTIFICATION_MAX_RETRIES = get_env('NOTIFICATION_MAX_RETRIES', default=3, required=False, value_type=int)


# ==================== Performance Configuration ====================

# حداکثر تعداد thread های Connection Pool
DB_MAX_CONNECTIONS = get_env('DB_MAX_CONNECTIONS', default=10, required=False, value_type=int)

# Timeout برای عملیات دیتابیس (ثانیه)
DB_TIMEOUT = get_env('DB_TIMEOUT', default=30, required=False, value_type=float)

# فعال/غیرفعال کردن Performance Tracking
PERFORMANCE_TRACKING = get_env('PERFORMANCE_TRACKING', default=True, required=False, value_type=bool)


# ==================== Rate Limiting Configuration ====================

# حداکثر درخواست سراسری در دقیقه
GLOBAL_RATE_LIMIT = get_env('GLOBAL_RATE_LIMIT', default=20, required=False, value_type=int)

# حداکثر سفارش در ساعت
ORDER_RATE_LIMIT = get_env('ORDER_RATE_LIMIT', default=3, required=False, value_type=int)

# حداکثر امتحان کد تخفیف در دقیقه
DISCOUNT_RATE_LIMIT = get_env('DISCOUNT_RATE_LIMIT', default=5, required=False, value_type=int)


# ==================== Cleanup Configuration ====================

# فعال/غیرفعال کردن پاکسازی خودکار
AUTO_CLEANUP_ENABLED = get_env('AUTO_CLEANUP_ENABLED', default=True, required=False, value_type=bool)

# ساعت پاکسازی روزانه
CLEANUP_HOUR = get_env('CLEANUP_HOUR', default=3, required=False, value_type=int)
CLEANUP_MINUTE = get_env('CLEANUP_MINUTE', default=30, required=False, value_type=int)

# سن سفارشات برای پاکسازی (روز)
CLEANUP_ORDER_AGE_DAYS = get_env('CLEANUP_ORDER_AGE_DAYS', default=7, required=False, value_type=int)


# ==================== Alert Thresholds ====================

class AlertThresholds:
    """آستانه‌های هشدار"""
    
    # CPU
    CPU_HIGH = get_env('ALERT_CPU_HIGH', default=80.0, required=False, value_type=float)
    CPU_CRITICAL = get_env('ALERT_CPU_CRITICAL', default=90.0, required=False, value_type=float)
    
    # Memory
    MEMORY_HIGH = get_env('ALERT_MEMORY_HIGH', default=85.0, required=False, value_type=float)
    MEMORY_CRITICAL = get_env('ALERT_MEMORY_CRITICAL', default=95.0, required=False, value_type=float)
    
    # Response Time (ms)
    RESPONSE_TIME_SLOW = get_env('ALERT_RESPONSE_SLOW', default=2000.0, required=False, value_type=float)
    RESPONSE_TIME_CRITICAL = get_env('ALERT_RESPONSE_CRITICAL', default=5000.0, required=False, value_type=float)
    
    # Error Rate (%)
    ERROR_RATE_HIGH = get_env('ALERT_ERROR_RATE_HIGH', default=5.0, required=False, value_type=float)
    ERROR_RATE_CRITICAL = get_env('ALERT_ERROR_RATE_CRITICAL', default=10.0, required=False, value_type=float)
    
    # Cache Hit Rate (%)
    CACHE_HIT_LOW = get_env('ALERT_CACHE_HIT_LOW', default=50.0, required=False, value_type=float)
    
    # Pending Orders
    PENDING_ORDERS_HIGH = get_env('ALERT_PENDING_HIGH', default=10, required=False, value_type=int)


# ==================== Messages ====================

MESSAGES = {
    "start_user": "🛍 به فروشگاه مانتو ما خوش اومدید!\n\n✨ محصولات جدید رو در کانال ما ببینید:\n📢 @manto_omdeh_erfan\n\nو مستقیماً از همون‌جا سفارش بدید!\n\n📦 سبد خرید شما خالیه.",
    "start_admin": "👨‍💼 پنل مدیریت\n\nبرای شروع از منوی زیر استفاده کنید.",
    "product_added": "✅ محصول با موفقیت اضافه شد!",
    "pack_added": "✅ پک به محصول اضافه شد!",
    "order_received": "📦 سفارش شما ثبت شد!\n\nلطفاً منتظر تایید ادمین باشید.",
    "order_confirmed": "✅ سفارش شما تایید شد!\n\n💳 لطفاً مبلغ {amount} تومان را به شماره کارت زیر واریز کنید:\n\n{card}\n\nبه نام: {holder}\n\n📷 بعد از واریز، رسید را ارسال کنید.",
    "order_rejected": "❌ متأسفانه سفارش شما رد شد.",
    "receipt_received": "✅ رسید شما دریافت شد!\n\nلطفاً منتظر تایید نهایی باشید.",
    "payment_confirmed": "✅ پرداخت شما تایید شد!\n\n🎉 سفارش شما در حال آماده‌سازی است.",
    "payment_rejected": "❌ رسید شما رد شد. لطفاً دوباره تلاش کنید.",
}


# ==================== Feature Flags ====================

class FeatureFlags:
    """پرچم‌های ویژگی (برای فعال/غیرفعال کردن قابلیت‌ها)"""
    
    # Core Features
    CACHE = CACHE_ENABLED
    MONITORING = MONITORING_ENABLED
    ALERTS = ALERTS_ENABLED
    NOTIFICATIONS = NOTIFICATIONS_ENABLED
    PERFORMANCE_TRACKING = PERFORMANCE_TRACKING
    AUTO_CLEANUP = AUTO_CLEANUP_ENABLED
    
    # Advanced Features
    AUTO_HEALTH_CHECK = AUTO_HEALTH_CHECK
    ALERT_TELEGRAM = ALERT_TELEGRAM_ENABLED
    
    # Experimental Features
    METRICS_EXPORT = get_env('FEATURE_METRICS_EXPORT', default=True, required=False, value_type=bool)
    ALERT_ANALYTICS = get_env('FEATURE_ALERT_ANALYTICS', default=True, required=False, value_type=bool)


# ==================== Validation ====================

from typing import Tuple, List

def validate_config() -> Tuple[bool, List[str]]:
    """
    اعتبارسنجی تنظیمات
    
    Returns:
        (is_valid, errors)
    """
    errors = []
    
    # بررسی توکن
    if not BOT_TOKEN or len(BOT_TOKEN) < 20:
        errors.append("❌ توکن ربات نامعتبر است")
    
    # بررسی ADMIN_ID
    if ADMIN_ID <= 0:
        errors.append("❌ ADMIN_ID نامعتبر است")
    
    # بررسی شماره کارت
    if not CARD_NUMBER or len(CARD_NUMBER) != 16:
        errors.append("⚠️ شماره کارت ممکن است نامعتبر باشد")
    
    # بررسی کانال
    if not CHANNEL_USERNAME:
        errors.append("⚠️ username کانال تنظیم نشده است")
    
    # بررسی Alert Thresholds
    if AlertThresholds.CPU_HIGH >= AlertThresholds.CPU_CRITICAL:
        errors.append("⚠️ CPU_CRITICAL باید بیشتر از CPU_HIGH باشد")
    
    if AlertThresholds.MEMORY_HIGH >= AlertThresholds.MEMORY_CRITICAL:
        errors.append("⚠️ MEMORY_CRITICAL باید بیشتر از MEMORY_HIGH باشد")
    
    # بررسی Intervals
    if MONITORING_INTERVAL < 60:
        errors.append("⚠️ MONITORING_INTERVAL نباید کمتر از 60 ثانیه باشد")
    
    if HEALTH_CHECK_INTERVAL < 60:
        errors.append("⚠️ HEALTH_CHECK_INTERVAL نباید کمتر از 60 ثانیه باشد")
    
    # بررسی Rate Limits
    if GLOBAL_RATE_LIMIT < 5:
        errors.append("⚠️ GLOBAL_RATE_LIMIT خیلی کم است (حداقل 5)")
    
    return len(errors) == 0, errors


def print_config_summary():
    """نمایش خلاصه تنظیمات"""
    print("\n" + "=" * 60)
    print("⚙️ تنظیمات ربات")
    print("=" * 60)
    
    # Bot Info
    print("\n📱 اطلاعات ربات:")
    print(f"  ├─ BOT_TOKEN: {'*' * 20}...{BOT_TOKEN[-10:] if BOT_TOKEN else 'NOT SET'}")
    print(f"  ├─ ADMIN_ID: {ADMIN_ID}")
    print(f"  └─ CHANNEL: @{CHANNEL_USERNAME}")
    
    # Database
    print("\n💾 دیتابیس:")
    print(f"  ├─ DATABASE: {DATABASE_NAME}")
    print(f"  ├─ BACKUP_FOLDER: {BACKUP_FOLDER}")
    print(f"  └─ BACKUP_TIME: {BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d}")
    
    # Monitoring
    print("\n📊 مانیتورینگ:")
    print(f"  ├─ ENABLED: {MONITORING_ENABLED}")
    print(f"  ├─ INTERVAL: {MONITORING_INTERVAL}s")
    print(f"  └─ MAX_POINTS: {MONITORING_MAX_POINTS}")
    
    # Alerts
    print("\n🚨 هشدارها:")
    print(f"  ├─ ENABLED: {ALERTS_ENABLED}")
    print(f"  ├─ TELEGRAM: {ALERT_TELEGRAM_ENABLED}")
    print(f"  ├─ MIN_SEVERITY: {ALERT_MIN_SEVERITY}")
    print(f"  └─ COOLDOWN: {ALERT_DEFAULT_COOLDOWN}s")
    
    # Performance
    print("\n⚡ عملکرد:")
    print(f"  ├─ CACHE: {CACHE_ENABLED}")
    print(f"  ├─ TRACKING: {PERFORMANCE_TRACKING}")
    print(f"  └─ DB_TIMEOUT: {DB_TIMEOUT}s")
    
    # Thresholds
    print("\n⚠️ آستانه‌های هشدار:")
    print(f"  ├─ CPU_HIGH: {AlertThresholds.CPU_HIGH}%")
    print(f"  ├─ MEMORY_HIGH: {AlertThresholds.MEMORY_HIGH}%")
    print(f"  ├─ RESPONSE_SLOW: {AlertThresholds.RESPONSE_TIME_SLOW}ms")
    print(f"  └─ ERROR_RATE_HIGH: {AlertThresholds.ERROR_RATE_HIGH}%")
    
    print("\n" + "=" * 60 + "\n")


def get_config_dict() -> Dict[str, Any]:
    """دریافت تمام تنظیمات به صورت دیکشنری"""
    return {
        'bot': {
            'token': BOT_TOKEN[:20] + '...' if BOT_TOKEN else None,
            'admin_id': ADMIN_ID,
            'channel': CHANNEL_USERNAME
        },
        'database': {
            'name': DATABASE_NAME,
            'backup_folder': BACKUP_FOLDER,
            'backup_time': f"{BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d}"
        },
        'monitoring': {
            'enabled': MONITORING_ENABLED,
            'interval': MONITORING_INTERVAL,
            'max_points': MONITORING_MAX_POINTS,
            'auto_health_check': AUTO_HEALTH_CHECK,
            'health_check_interval': HEALTH_CHECK_INTERVAL
        },
        'alerts': {
            'enabled': ALERTS_ENABLED,
            'telegram': ALERT_TELEGRAM_ENABLED,
            'min_severity': ALERT_MIN_SEVERITY,
            'cooldown': ALERT_DEFAULT_COOLDOWN,
            'grace_period': ALERT_GRACE_PERIOD
        },
        'thresholds': {
            'cpu_high': AlertThresholds.CPU_HIGH,
            'cpu_critical': AlertThresholds.CPU_CRITICAL,
            'memory_high': AlertThresholds.MEMORY_HIGH,
            'memory_critical': AlertThresholds.MEMORY_CRITICAL,
            'response_slow': AlertThresholds.RESPONSE_TIME_SLOW,
            'error_rate_high': AlertThresholds.ERROR_RATE_HIGH
        },
        'cache': {
            'enabled': CACHE_ENABLED,
            'default_ttl': CACHE_DEFAULT_TTL,
            'cleanup_interval': CACHE_CLEANUP_INTERVAL
        },
        'performance': {
            'tracking': PERFORMANCE_TRACKING,
            'db_max_connections': DB_MAX_CONNECTIONS,
            'db_timeout': DB_TIMEOUT
        }
    }


# ==================== Auto Validation ====================

if __name__ != "__main__":
    try:
        is_valid, validation_errors = validate_config()
        
        if not is_valid:
            print("\n" + "=" * 60)
            print("⚠️ خطاهای تنظیمات:")
            print("=" * 60)
            for error in validation_errors:
                print(f"  {error}")
            print("=" * 60 + "\n")
            
            # فقط warning، crash نمی‌کنیم
            for error in validation_errors:
                if "❌" in error:
                    warnings.warn(f"⚠️ Configuration issue: {error}")
        else:
            print("✅ تمام تنظیمات معتبر هستند")
            
    except ValueError as e:
        warnings.warn(f"⚠️ Configuration issue: {e}")
        print(f"\n⚠️ هشدار تنظیمات: {e}\n")
        print("💡 راهنما:")
        print("  1. فایل .env را در روت پروژه ایجاد کنید")
        print("  2. از .env.example به عنوان الگو استفاده کنید")
        print("  3. تمام متغیرهای الزامی را تنظیم کنید\n")


# ==================== Debug Mode ====================

if __name__ == "__main__":
    print_config_summary()
    
    is_valid, validation_errors = validate_config()
    
    if is_valid:
        print("✅ همه چیز OK است!")
    else:
        print("\n❌ مشکلات موجود:")
        for error in validation_errors:
            print(f"  • {error}")
    
    print("\n📋 کانفیگ کامل:")
    import json
    print(json.dumps(get_config_dict(), indent=2, ensure_ascii=False))
