"""
📝 سیستم Logging پیشرفته
✅ Multi-level Logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
✅ Rotating File Handler (با محدودیت حجم)
✅ Colored Console Output
✅ Structured Logging (JSON format)
✅ Context Logging (با اطلاعات کاربر)
✅ Log Analytics
✅ Performance Logging
✅ Error Tracking Integration

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import logging
import os
import sys
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
import threading

from config import LOG_FOLDER, LOG_LEVEL, MAX_LOG_SIZE_MB, LOG_BACKUP_COUNT


# ==================== ANSI Color Codes ====================

class Colors:
    """رنگ‌های ANSI برای ترمینال"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # رنگ‌های اصلی
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # رنگ‌های روشن
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'


# ==================== Data Classes ====================

@dataclass
class LogEntry:
    """یک رکورد لاگ"""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    context: Dict = field(default_factory=dict)
    exception: Optional[str] = None
    user_id: Optional[int] = None
    handler_name: Optional[str] = None
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'logger': self.logger_name,
            'message': self.message,
            'context': self.context,
            'exception': self.exception,
            'user_id': self.user_id,
            'handler_name': self.handler_name
        }
    
    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class LogStatistics:
    """آمار لاگ‌ها"""
    total_logs: int = 0
    by_level: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    by_logger: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_count: int = 0
    warnings_count: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self):
        return {
            'total_logs': self.total_logs,
            'by_level': dict(self.by_level),
            'by_logger': dict(self.by_logger),
            'errors_count': self.errors_count,
            'warnings_count': self.warnings_count,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds()
        }


# ==================== Custom Formatters ====================

class ColoredFormatter(logging.Formatter):
    """Formatter با رنگ برای Console"""
    
    LEVEL_COLORS = {
        'DEBUG': Colors.BRIGHT_BLACK,
        'INFO': Colors.BRIGHT_BLUE,
        'WARNING': Colors.BRIGHT_YELLOW,
        'ERROR': Colors.BRIGHT_RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
    }
    
    LEVEL_EMOJIS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️ ',
        'WARNING': '⚠️ ',
        'ERROR': '❌',
        'CRITICAL': '🔴',
    }
    
    def format(self, record):
        # رنگ بر اساس سطح
        level_color = self.LEVEL_COLORS.get(record.levelname, Colors.WHITE)
        emoji = self.LEVEL_EMOJIS.get(record.levelname, '  ')
        
        # فرمت زمان
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # رنگ‌آمیزی نام logger
        logger_name = f"{Colors.CYAN}{record.name}{Colors.RESET}"
        
        # پیام اصلی
        message = record.getMessage()
        
        # اگر exception است، اضافه کن
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            message = f"{message}\n{Colors.BRIGHT_RED}{exc_text}{Colors.RESET}"
        
        # ساخت خط نهایی
        log_line = (
            f"{Colors.BRIGHT_BLACK}[{timestamp}]{Colors.RESET} "
            f"{emoji} {level_color}{record.levelname:8}{Colors.RESET} "
            f"{logger_name:20} | {message}"
        )
        
        return log_line


class JSONFormatter(logging.Formatter):
    """Formatter برای خروجی JSON"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # اضافه کردن context اگر موجود است
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        # اضافه کردن exception اگر موجود است
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredFormatter(logging.Formatter):
    """Formatter ساختاریافته برای فایل"""
    
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # پیام پایه
        base_msg = (
            f"[{timestamp}] "
            f"[{record.levelname:8}] "
            f"[{record.name:20}] "
            f"{record.getMessage()}"
        )
        
        # اضافه کردن context
        if hasattr(record, 'context') and record.context:
            context_str = json.dumps(record.context, ensure_ascii=False)
            base_msg += f" | Context: {context_str}"
        
        if hasattr(record, 'user_id') and record.user_id:
            base_msg += f" | User: {record.user_id}"
        
        # اضافه کردن exception
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            base_msg += f"\n{exc_text}"
        
        return base_msg


# ==================== Custom Handlers ====================

class LogAnalyticsHandler(logging.Handler):
    """Handler برای جمع‌آوری آمار لاگ‌ها"""
    
    def __init__(self):
        super().__init__()
        self.stats = LogStatistics()
        self.recent_logs: deque = deque(maxlen=1000)
        self.error_logs: deque = deque(maxlen=200)
        self._lock = threading.Lock()
    
    def emit(self, record):
        with self._lock:
            # ساخت LogEntry
            log_entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                context=getattr(record, 'context', {}),
                exception=self.formatException(record.exc_info) if record.exc_info else None,
                user_id=getattr(record, 'user_id', None),
                handler_name=getattr(record, 'handler_name', None)
            )
            
            # بروزرسانی آمار
            self.stats.total_logs += 1
            self.stats.by_level[record.levelname] += 1
            self.stats.by_logger[record.name] += 1
            
            if record.levelname == 'ERROR':
                self.stats.errors_count += 1
                self.error_logs.append(log_entry)
            elif record.levelname == 'WARNING':
                self.stats.warnings_count += 1
            
            # ذخیره در تاریخچه
            self.recent_logs.append(log_entry)
    
    def get_statistics(self) -> Dict:
        """دریافت آمار"""
        with self._lock:
            return self.stats.to_dict()
    
    def get_recent_logs(self, count: int = 50) -> List[LogEntry]:
        """دریافت آخرین لاگ‌ها"""
        with self._lock:
            return list(self.recent_logs)[-count:]
    
    def get_recent_errors(self, count: int = 20) -> List[LogEntry]:
        """دریافت آخرین خطاها"""
        with self._lock:
            return list(self.error_logs)[-count:]
    
    def get_logs_by_level(self, level: str, count: int = 50) -> List[LogEntry]:
        """دریافت لاگ‌ها بر اساس سطح"""
        with self._lock:
            filtered = [log for log in self.recent_logs if log.level == level]
            return filtered[-count:]


# ==================== Context Logger ====================

class ContextLogger:
    """Logger با قابلیت Context"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._context = {}
    
    def set_context(self, **kwargs):
        """تنظیم context"""
        self._context.update(kwargs)
    
    def clear_context(self):
        """پاک کردن context"""
        self._context.clear()
    
    def _log_with_context(self, level, message, exc_info=None, **extra_context):
        """لاگ با context"""
        context = {**self._context, **extra_context}
        
        # ساخت LogRecord با context
        extra = {'context': context}
        
        if 'user_id' in context:
            extra['user_id'] = context['user_id']
        
        if 'handler_name' in context:
            extra['handler_name'] = context['handler_name']
        
        self.logger.log(level, message, exc_info=exc_info, extra=extra)
    
    def debug(self, message, **context):
        self._log_with_context(logging.DEBUG, message, **context)
    
    def info(self, message, **context):
        self._log_with_context(logging.INFO, message, **context)
    
    def warning(self, message, **context):
        self._log_with_context(logging.WARNING, message, **context)
    
    def error(self, message, exc_info=None, **context):
        self._log_with_context(logging.ERROR, message, exc_info=exc_info, **context)
    
    def critical(self, message, exc_info=None, **context):
        self._log_with_context(logging.CRITICAL, message, exc_info=exc_info, **context)
    
    def exception(self, message, **context):
        """لاگ exception با traceback"""
        self._log_with_context(logging.ERROR, message, exc_info=True, **context)


# ==================== Enhanced Logger Setup ====================

class EnhancedLoggerManager:
    """مدیریت پیشرفته Logger"""
    
    def __init__(self, app_name: str = "ShopBot",
                 log_folder: str = LOG_FOLDER,
                 log_level: str = LOG_LEVEL,
                 max_bytes: int = MAX_LOG_SIZE_MB * 1024 * 1024,
                 backup_count: int = LOG_BACKUP_COUNT):
        
        self.app_name = app_name
        self.log_folder = log_folder
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        
        # ساخت پوشه لاگ
        Path(log_folder).mkdir(exist_ok=True)
        
        # Handler برای آنالیز
        self.analytics_handler = LogAnalyticsHandler()
        
        # Logger‌های ساخته شده
        self.loggers: Dict[str, ContextLogger] = {}
        
        # تنظیم root logger
        self._setup_root_logger()
        
        print(f"✅ Enhanced Logger Manager initialized (Level: {log_level})")
    
    def _setup_root_logger(self):
        """تنظیم root logger"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # پاک کردن handler‌های قبلی
        root_logger.handlers.clear()
        
        # 1. Console Handler (با رنگ)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)
        
        # 2. Main File Handler (RotatingFileHandler)
        main_file = os.path.join(self.log_folder, f"{self.app_name}.log")
        file_handler = RotatingFileHandler(
            main_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)
        
        # 3. Error File Handler (فقط ERROR و بالاتر)
        error_file = os.path.join(self.log_folder, f"{self.app_name}_errors.log")
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=self.max_bytes // 2,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        
        # 4. JSON File Handler (برای پردازش خودکار)
        json_file = os.path.join(self.log_folder, f"{self.app_name}_json.log")
        json_handler = RotatingFileHandler(
            json_file,
            maxBytes=self.max_bytes,
            backupCount=3,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
        
        # 5. Analytics Handler
        self.analytics_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(self.analytics_handler)
        
        # 6. Daily Rotating Handler (برای آرشیو روزانه)
        daily_file = os.path.join(self.log_folder, f"{self.app_name}_daily.log")
        daily_handler = TimedRotatingFileHandler(
            daily_file,
            when='midnight',
            interval=1,
            backupCount=30,  # نگه‌داری 30 روز
            encoding='utf-8'
        )
        daily_handler.setLevel(logging.INFO)
        daily_handler.setFormatter(StructuredFormatter())
        daily_handler.suffix = "%Y%m%d"
        root_logger.addHandler(daily_handler)
    
    def get_logger(self, name: str) -> ContextLogger:
        """دریافت یک logger با context"""
        if name not in self.loggers:
            base_logger = logging.getLogger(name)
            self.loggers[name] = ContextLogger(base_logger)
        
        return self.loggers[name]
    
    def get_statistics(self) -> Dict:
        """دریافت آمار لاگ‌ها"""
        return self.analytics_handler.get_statistics()
    
    def get_recent_logs(self, count: int = 50) -> List[Dict]:
        """دریافت آخرین لاگ‌ها"""
        logs = self.analytics_handler.get_recent_logs(count)
        return [log.to_dict() for log in logs]
    
    def get_recent_errors(self, count: int = 20) -> List[Dict]:
        """دریافت آخرین خطاها"""
        errors = self.analytics_handler.get_recent_errors(count)
        return [error.to_dict() for error in errors]
    
    def get_logs_report(self) -> str:
        """گزارش متنی لاگ‌ها"""
        stats = self.get_statistics()
        recent_errors = self.get_recent_errors(5)
        
        report = "📝 **گزارش لاگ‌ها**\n"
        report += "═" * 40 + "\n\n"
        
        # آمار کلی
        report += "**📊 آمار:**\n"
        report += f"├ کل لاگ‌ها: {stats['total_logs']}\n"
        report += f"├ خطاها: {stats['errors_count']}\n"
        report += f"├ هشدارها: {stats['warnings_count']}\n"
        report += f"└ Uptime: {stats['uptime_seconds'] / 3600:.1f}h\n\n"
        
        # بر اساس سطح
        report += "**🎚 بر اساس سطح:**\n"
        for level, count in stats['by_level'].items():
            emoji = {
                'DEBUG': '🔍',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🔴'
            }.get(level, '  ')
            report += f"{emoji} {level}: {count}\n"
        report += "\n"
        
        # آخرین خطاها
        if recent_errors:
            report += "**❌ آخرین خطاها:**\n"
            for i, error in enumerate(recent_errors[:3], 1):
                timestamp = datetime.fromisoformat(error['timestamp'])
                report += f"{i}. [{timestamp.strftime('%H:%M:%S')}] "
                report += f"{error['message'][:50]}...\n"
        else:
            report += "**✅ خطایی ثبت نشده**\n"
        
        report += "\n" + "═" * 40
        
        return report
    
    def export_logs(self, filepath: str = None, 
                   level: Optional[str] = None,
                   count: int = 1000) -> bool:
        """خروجی لاگ‌ها به JSON"""
        try:
            if filepath is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filepath = os.path.join(
                    self.log_folder,
                    f"logs_export_{timestamp}.json"
                )
            
            # دریافت لاگ‌ها
            if level:
                logs = self.analytics_handler.get_logs_by_level(level, count)
            else:
                logs = self.analytics_handler.get_recent_logs(count)
            
            # تبدیل به dict
            logs_data = [log.to_dict() for log in logs]
            
            # ذخیره
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'exported_at': datetime.now().isoformat(),
                    'total_logs': len(logs_data),
                    'level_filter': level,
                    'statistics': self.get_statistics(),
                    'logs': logs_data
                }, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Logs exported to: {filepath}")
            return True
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False
    
    def set_level(self, level: str):
        """تغییر سطح logging"""
        new_level = getattr(logging, level.upper(), logging.INFO)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(new_level)
        
        for handler in root_logger.handlers:
            if not isinstance(handler, logging.StreamHandler) or \
               not isinstance(handler, LogAnalyticsHandler):
                handler.setLevel(new_level)
        
        self.log_level = new_level
        print(f"✅ Log level changed to: {level.upper()}")


# ==================== Global Logger Manager ====================

# نمونه سراسری
_logger_manager: Optional[EnhancedLoggerManager] = None


def setup_logging(app_name: str = "ShopBot",
                 log_folder: str = LOG_FOLDER,
                 log_level: str = LOG_LEVEL) -> EnhancedLoggerManager:
    """راه‌اندازی سیستم logging"""
    global _logger_manager
    
    _logger_manager = EnhancedLoggerManager(
        app_name=app_name,
        log_folder=log_folder,
        log_level=log_level
    )
    
    return _logger_manager


def get_logger(name: str) -> ContextLogger:
    """دریافت logger"""
    if _logger_manager is None:
        setup_logging()
    
    return _logger_manager.get_logger(name)


def get_logger_manager() -> Optional[EnhancedLoggerManager]:
    """دریافت logger manager"""
    return _logger_manager


# ==================== Decorators ====================

def log_function_call(logger: Optional[ContextLogger] = None):
    """Decorator برای لاگ کردن فراخوانی تابع"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            
            func_name = func.__name__
            logger.debug(f"→ Calling {func_name}", handler_name=func_name)
            
            try:
                result = await func(*args, **kwargs)
                logger.debug(f"← {func_name} completed", handler_name=func_name)
                return result
            except Exception as e:
                logger.error(
                    f"✗ {func_name} failed: {e}",
                    exc_info=True,
                    handler_name=func_name
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)
            
            func_name = func.__name__
            logger.debug(f"→ Calling {func_name}", handler_name=func_name)
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"← {func_name} completed", handler_name=func_name)
                return result
            except Exception as e:
                logger.error(
                    f"✗ {func_name} failed: {e}",
                    exc_info=True,
                    handler_name=func_name
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


print("✅ Enhanced Logger module loaded")
