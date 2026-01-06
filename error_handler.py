"""
❌ سیستم مدیریت پیشرفته خطاها - نسخه بهبود یافته
✅ لاگ دقیق با context
✅ Retry mechanism
✅ اطلاع‌رسانی به ادمین
✅ ذخیره خطاها
✅ Error Analytics
✅ Smart Recovery
✅ Integration با Monitoring

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import logging
import asyncio
import traceback
import functools
import time
from datetime import datetime, timedelta
from typing import Callable, Optional, Any, Dict, List
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
from telegram.ext import ContextTypes
from telegram.error import TelegramError, NetworkError, TimedOut, BadRequest
from config import ADMIN_ID

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class ErrorCategory(Enum):
    """دسته‌بندی خطاها"""
    DATABASE = "database"
    NETWORK = "network"
    TELEGRAM = "telegram"
    VALIDATION = "validation"
    BUSINESS = "business"
    PERMISSION = "permission"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """شدت خطا"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """اقدام بازیابی"""
    RETRY = "retry"
    SKIP = "skip"
    ALERT = "alert"
    RESTART = "restart"
    NONE = "none"


# ==================== Custom Exceptions ====================

class BotError(Exception):
    """کلاس پایه برای خطاهای سفارشی ربات"""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 context: Optional[Dict] = None,
                 recovery_action: RecoveryAction = RecoveryAction.NONE):
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.recovery_action = recovery_action
        self.timestamp = datetime.now()
        super().__init__(self.message)


class DatabaseError(BotError):
    """خطای دیتابیس"""
    def __init__(self, message: str, context: Optional[Dict] = None):
        super().__init__(
            message,
            ErrorCategory.DATABASE,
            ErrorSeverity.HIGH,
            context,
            RecoveryAction.RETRY
        )


class ValidationError(BotError):
    """خطای اعتبارسنجی"""
    def __init__(self, message: str, context: Optional[Dict] = None):
        super().__init__(
            message,
            ErrorCategory.VALIDATION,
            ErrorSeverity.LOW,
            context,
            RecoveryAction.SKIP
        )


class BusinessLogicError(BotError):
    """خطای منطق کسب‌وکار"""
    def __init__(self, message: str, context: Optional[Dict] = None):
        super().__init__(
            message,
            ErrorCategory.BUSINESS,
            ErrorSeverity.MEDIUM,
            context,
            RecoveryAction.ALERT
        )


# ==================== Data Classes ====================

@dataclass
class ErrorRecord:
    """رکورد خطا"""
    id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    error_type: str
    message: str
    traceback: str
    user_id: Optional[int] = None
    handler_name: Optional[str] = None
    recovery_action: RecoveryAction = RecoveryAction.NONE
    recovered: bool = False
    retry_count: int = 0
    context: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'category': self.category.value,
            'severity': self.severity.value,
            'error_type': self.error_type,
            'message': self.message,
            'traceback': self.traceback,
            'user_id': self.user_id,
            'handler_name': self.handler_name,
            'recovery_action': self.recovery_action.value,
            'recovered': self.recovered,
            'retry_count': self.retry_count,
            'context': self.context
        }


# ==================== Enhanced Error Handler ====================

class EnhancedErrorHandler:
    """مدیریت پیشرفته خطاها"""
    
    def __init__(self, health_checker=None, monitoring_system=None,
                 notification_service=None):
        self.health_checker = health_checker
        self.monitoring_system = monitoring_system
        self.notification_service = notification_service
        
        # ذخیره خطاها
        self.error_history: deque = deque(maxlen=500)
        self.error_counts = defaultdict(int)
        self.error_by_category = defaultdict(int)
        self.error_by_severity = defaultdict(int)
        
        # Rate limiting برای اعلان‌ها
        self.last_notification: Dict[str, float] = {}
        self.notification_cooldown = 300  # 5 دقیقه
        
        # Circuit Breaker
        self.circuit_breaker = {
            'database': {'failures': 0, 'threshold': 5, 'open': False},
            'telegram': {'failures': 0, 'threshold': 10, 'open': False}
        }
        
        logger.info("✅ Enhanced Error Handler initialized")
    
    # ==================== Error Handling ====================
    
    async def handle_error(self, error: Exception, context: ContextTypes.DEFAULT_TYPE,
                          user_id: Optional[int] = None,
                          handler_name: Optional[str] = None,
                          extra_info: Optional[Dict] = None) -> str:
        """مدیریت مرکزی خطاها"""
        
        # استخراج اطلاعات خطا
        error_info = self._extract_error_info(
            error, user_id, handler_name, extra_info
        )
        
        # ساخت رکورد خطا
        error_record = self._create_error_record(error_info)
        
        # ذخیره خطا
        self._store_error(error_record)
        
        # لاگ کردن
        self._log_error(error_record)
        
        # ثبت در Health Checker
        if self.health_checker:
            self.health_checker.add_error(
                error_type=error_record.category.value,
                error_message=error_record.message,
                user_id=user_id
            )
        
        # ثبت در Monitoring System
        if self.monitoring_system:
            self.monitoring_system.record_request(
                endpoint=handler_name or 'unknown',
                duration_ms=0,
                success=False
            )
        
        # Circuit Breaker
        self._update_circuit_breaker(error_record)
        
        # تلاش برای بازیابی
        recovery_success = await self._attempt_recovery(error_record, context)
        
        if recovery_success:
            error_record.recovered = True
            logger.info(f"✅ Error recovered: {error_record.id}")
        
        # ارسال اعلان
        await self._notify_if_needed(error_record, context)
        
        # پیام کاربر
        user_message = self._get_user_message(error_record)
        
        return user_message
    
    def _extract_error_info(self, error: Exception, user_id: Optional[int],
                           handler_name: Optional[str],
                           extra_info: Optional[Dict]) -> Dict:
        """استخراج اطلاعات کامل خطا"""
        
        # تشخیص دسته و شدت
        if isinstance(error, BotError):
            category = error.category
            severity = error.severity
            message = error.message
            recovery_action = error.recovery_action
            context = error.context
        elif isinstance(error, (NetworkError, TimedOut)):
            category = ErrorCategory.NETWORK
            severity = ErrorSeverity.MEDIUM
            message = str(error)
            recovery_action = RecoveryAction.RETRY
            context = {}
        elif isinstance(error, BadRequest):
            category = ErrorCategory.TELEGRAM
            severity = ErrorSeverity.LOW
            message = str(error)
            recovery_action = RecoveryAction.SKIP
            context = {}
        elif isinstance(error, TelegramError):
            category = ErrorCategory.TELEGRAM
            severity = ErrorSeverity.MEDIUM
            message = str(error)
            recovery_action = RecoveryAction.RETRY
            context = {}
        elif isinstance(error, (IOError, OSError)):
            category = ErrorCategory.DATABASE
            severity = ErrorSeverity.HIGH
            message = str(error)
            recovery_action = RecoveryAction.RETRY
            context = {}
        else:
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.MEDIUM
            message = str(error)
            recovery_action = RecoveryAction.ALERT
            context = {}
        
        return {
            'type': type(error).__name__,
            'category': category,
            'severity': severity,
            'message': message,
            'traceback': traceback.format_exc(),
            'user_id': user_id,
            'handler_name': handler_name,
            'recovery_action': recovery_action,
            'timestamp': datetime.now(),
            'context': {**context, **(extra_info or {})}
        }
    
    def _create_error_record(self, error_info: Dict) -> ErrorRecord:
        """ساخت رکورد خطا"""
        error_id = f"err_{int(time.time() * 1000)}"
        
        return ErrorRecord(
            id=error_id,
            timestamp=error_info['timestamp'],
            category=error_info['category'],
            severity=error_info['severity'],
            error_type=error_info['type'],
            message=error_info['message'],
            traceback=error_info['traceback'],
            user_id=error_info.get('user_id'),
            handler_name=error_info.get('handler_name'),
            recovery_action=error_info['recovery_action'],
            context=error_info.get('context', {})
        )
    
    def _store_error(self, error_record: ErrorRecord):
        """ذخیره خطا"""
        self.error_history.append(error_record)
        
        # آمار
        self.error_counts['total'] += 1
        self.error_by_category[error_record.category.value] += 1
        self.error_by_severity[error_record.severity.value] += 1
        
        if error_record.handler_name:
            self.error_counts[f"handler:{error_record.handler_name}"] += 1
    
    def _log_error(self, error_record: ErrorRecord):
        """لاگ کردن خطا با جزئیات"""
        severity_log = {
            ErrorSeverity.CRITICAL: logging.CRITICAL,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.LOW: logging.INFO
        }
        
        log_level = severity_log.get(error_record.severity, logging.ERROR)
        
        log_message = (
            f"\n{'='*60}\n"
            f"❌ خطا رخ داد!\n"
            f"ID: {error_record.id}\n"
            f"نوع: {error_record.error_type}\n"
            f"دسته: {error_record.category.value}\n"
            f"شدت: {error_record.severity.value}\n"
            f"پیام: {error_record.message}\n"
        )
        
        if error_record.user_id:
            log_message += f"کاربر: {error_record.user_id}\n"
        
        if error_record.handler_name:
            log_message += f"Handler: {error_record.handler_name}\n"
        
        if error_record.context:
            log_message += f"Context: {error_record.context}\n"
        
        log_message += f"{'='*60}\n"
        log_message += f"Traceback:\n{error_record.traceback}"
        
        logger.log(log_level, log_message)
    
    def _update_circuit_breaker(self, error_record: ErrorRecord):
        """بروزرسانی Circuit Breaker"""
        category = error_record.category.value
        
        if category in self.circuit_breaker:
            breaker = self.circuit_breaker[category]
            breaker['failures'] += 1
            
            if breaker['failures'] >= breaker['threshold']:
                breaker['open'] = True
                logger.error(
                    f"🔴 Circuit Breaker OPEN for {category} "
                    f"(failures: {breaker['failures']})"
                )
    
    def is_circuit_open(self, category: str) -> bool:
        """بررسی وضعیت Circuit Breaker"""
        return self.circuit_breaker.get(category, {}).get('open', False)
    
    def reset_circuit_breaker(self, category: str):
        """ریست Circuit Breaker"""
        if category in self.circuit_breaker:
            self.circuit_breaker[category]['failures'] = 0
            self.circuit_breaker[category]['open'] = False
            logger.info(f"✅ Circuit Breaker CLOSED for {category}")
    
    # ==================== Recovery ====================
    
    async def _attempt_recovery(self, error_record: ErrorRecord,
                               context: ContextTypes.DEFAULT_TYPE) -> bool:
        """تلاش برای بازیابی"""
        action = error_record.recovery_action
        
        if action == RecoveryAction.RETRY:
            return await self._retry_operation(error_record, context)
        elif action == RecoveryAction.ALERT:
            await self._send_alert(error_record, context)
            return False
        elif action == RecoveryAction.RESTART:
            # این باید در سطح بالاتر مدیریت شود
            logger.critical("🔴 Restart required!")
            return False
        
        return False
    
    async def _retry_operation(self, error_record: ErrorRecord,
                              context: ContextTypes.DEFAULT_TYPE) -> bool:
        """تلاش مجدد"""
        max_retries = 3
        
        if error_record.retry_count >= max_retries:
            logger.warning(f"⚠️ Max retries reached for {error_record.id}")
            return False
        
        error_record.retry_count += 1
        
        # منتظر بمان (Exponential Backoff)
        delay = 2 ** error_record.retry_count
        await asyncio.sleep(delay)
        
        logger.info(
            f"🔄 Retry attempt {error_record.retry_count}/{max_retries} "
            f"for {error_record.id}"
        )
        
        # اینجا باید عملیات اصلی دوباره اجرا شود
        # این باید در decorator مدیریت شود
        
        return False
    
    async def _send_alert(self, error_record: ErrorRecord,
                         context: ContextTypes.DEFAULT_TYPE):
        """ارسال هشدار"""
        if self.notification_service:
            await self.notification_service.send_error_notification(
                error_type=error_record.error_type,
                error_msg=error_record.message,
                user_id=error_record.user_id
            )
    
    # ==================== Notifications ====================
    
    async def _notify_if_needed(self, error_record: ErrorRecord,
                               context: ContextTypes.DEFAULT_TYPE):
        """ارسال اعلان در صورت نیاز"""
        # فقط برای خطاهای HIGH و CRITICAL
        if error_record.severity not in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            return
        
        # بررسی cooldown
        category = error_record.category.value
        last_time = self.last_notification.get(category, 0)
        
        if time.time() - last_time < self.notification_cooldown:
            return
        
        self.last_notification[category] = time.time()
        
        # ارسال به تلگرام
        try:
            severity_emoji = {
                ErrorSeverity.CRITICAL: '🔴',
                ErrorSeverity.HIGH: '🟠',
                ErrorSeverity.MEDIUM: '🟡',
                ErrorSeverity.LOW: '🟢'
            }
            
            emoji = severity_emoji.get(error_record.severity, '⚠️')
            
            message = f"{emoji} **خطای {error_record.severity.value.upper()}**\n\n"
            message += f"**دسته:** {error_record.category.value}\n"
            message += f"**نوع:** {error_record.error_type}\n"
            message += f"**پیام:** {error_record.message[:200]}\n"
            
            if error_record.user_id:
                message += f"**کاربر:** {error_record.user_id}\n"
            
            if error_record.handler_name:
                message += f"**Handler:** {error_record.handler_name}\n"
            
            message += f"\n**زمان:** {error_record.timestamp.strftime('%H:%M:%S')}\n"
            
            # تعداد خطاهای این دسته
            count = self.error_by_category[category]
            if count > 1:
                message += f"\n⚠️ این خطا {count} بار تکرار شده است!"
            
            await context.bot.send_message(
                ADMIN_ID,
                message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    
    def _get_user_message(self, error_record: ErrorRecord) -> str:
        """پیام مناسب برای کاربر"""
        category = error_record.category
        severity = error_record.severity
        
        messages = {
            ErrorCategory.DATABASE: (
                "❌ مشکلی در ذخیره‌سازی اطلاعات پیش آمد.\n"
                "لطفاً چند لحظه صبر کنید و دوباره تلاش کنید."
            ),
            ErrorCategory.NETWORK: (
                "❌ مشکل در ارتباط با سرور.\n"
                "لطفاً اتصال اینترنت خود را بررسی کنید."
            ),
            ErrorCategory.TELEGRAM: (
                "❌ مشکلی در ارسال پیام پیش آمد.\n"
                "لطفاً دوباره تلاش کنید."
            ),
            ErrorCategory.VALIDATION: (
                "❌ اطلاعات وارد شده نامعتبر است.\n"
                "لطفاً دوباره بررسی کنید."
            ),
            ErrorCategory.BUSINESS: (
                "❌ عملیات قابل انجام نیست.\n"
                f"دلیل: {error_record.message}"
            ),
            ErrorCategory.PERMISSION: (
                "⛔️ شما دسترسی لازم را ندارید."
            ),
            ErrorCategory.RATE_LIMIT: (
                "⚠️ شما خیلی سریع درخواست می‌فرستید.\n"
                "لطفاً کمی صبر کنید."
            ),
            ErrorCategory.TIMEOUT: (
                "⏱ عملیات طولانی شد.\n"
                "لطفاً دوباره تلاش کنید."
            ),
            ErrorCategory.UNKNOWN: (
                "❌ خطای غیرمنتظره‌ای رخ داد.\n"
                "لطفاً با پشتیبانی تماس بگیرید."
            )
        }
        
        return messages.get(category, messages[ErrorCategory.UNKNOWN])
    
    # ==================== Statistics ====================
    
    def get_error_stats(self) -> Dict:
        """آمار خطاها"""
        recent_errors = list(self.error_history)[-100:]
        
        # خطاهای یک ساعت اخیر
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_critical = [
            e for e in recent_errors
            if e.timestamp > one_hour_ago and e.severity == ErrorSeverity.CRITICAL
        ]
        
        return {
            'total_errors': self.error_counts['total'],
            'by_category': dict(self.error_by_category),
            'by_severity': dict(self.error_by_severity),
            'recent_critical': len(recent_critical),
            'circuit_breakers': {
                k: v for k, v in self.circuit_breaker.items()
            }
        }
    
    def get_top_errors(self, top_n: int = 5) -> List[Dict]:
        """پرتکرارترین خطاها"""
        error_types = defaultdict(int)
        
        for error in self.error_history:
            key = f"{error.category.value}:{error.error_type}"
            error_types[key] += 1
        
        sorted_errors = sorted(
            error_types.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {'type': k, 'count': v}
            for k, v in sorted_errors[:top_n]
        ]
    
    def get_error_report(self) -> str:
        """گزارش متنی خطاها"""
        stats = self.get_error_stats()
        top_errors = self.get_top_errors(3)
        
        report = "❌ **گزارش خطاها**\n"
        report += "═" * 40 + "\n\n"
        
        # آمار کلی
        report += "**📊 آمار کلی:**\n"
        report += f"├ کل خطاها: {stats['total_errors']}\n"
        report += f"├ Critical اخیر: {stats['recent_critical']}\n"
        
        # بر اساس دسته
        report += "\n**📁 بر اساس دسته:**\n"
        for category, count in stats['by_category'].items():
            report += f"├ {category}: {count}\n"
        
        # بر اساس شدت
        report += "\n**⚠️ بر اساس شدت:**\n"
        for severity, count in stats['by_severity'].items():
            report += f"├ {severity}: {count}\n"
        
        # پرتکرارترین
        if top_errors:
            report += "\n**🔥 پرتکرارترین:**\n"
            for i, err in enumerate(top_errors, 1):
                report += f"{i}. {err['type']}: {err['count']} بار\n"
        
        # Circuit Breakers
        open_breakers = [
            k for k, v in stats['circuit_breakers'].items()
            if v.get('open')
        ]
        if open_breakers:
            report += f"\n**🔴 Circuit Breakers باز:**\n"
            for breaker in open_breakers:
                report += f"• {breaker}\n"
        
        return report


# ==================== Decorators ====================

def retry_on_error(max_retries: int = 3, delay: float = 1.0,
                  exponential_backoff: bool = True,
                  catch_exceptions: tuple = (Exception,)):
    """Decorator برای retry خودکار"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except catch_exceptions as e:
                    last_exception = e
                    
                    # برخی خطاها نباید retry شوند
                    if isinstance(e, (BadRequest, ValidationError)):
                        raise
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{max_retries} failed "
                            f"for {func.__name__}: {e}"
                        )
                        await asyncio.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logger.error(
                            f"❌ All {max_retries} attempts failed "
                            f"for {func.__name__}"
                        )
            
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except catch_exceptions as e:
                    last_exception = e
                    
                    if isinstance(e, (BadRequest, ValidationError)):
                        raise
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{max_retries} failed "
                            f"for {func.__name__}: {e}"
                        )
                        import time
                        time.sleep(current_delay)
                        
                        if exponential_backoff:
                            current_delay *= 2
                    else:
                        logger.error(
                            f"❌ All {max_retries} attempts failed "
                            f"for {func.__name__}"
                        )
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def handle_errors(error_handler: EnhancedErrorHandler):
    """Decorator برای مدیریت خطاها"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                user_id = update.effective_user.id if update.effective_user else None
                
                error_message = await error_handler.handle_error(
                    error=e,
                    context=context,
                    user_id=user_id,
                    handler_name=func.__name__,
                    extra_info={'update_type': type(update).__name__}
                )
                
                # ارسال پیام به کاربر
                try:
                    if update.message:
                        await update.message.reply_text(error_message)
                    elif update.callback_query:
                        await update.callback_query.answer(
                            "❌ خطا رخ داد!",
                            show_alert=True
                        )
                except:
                    pass
                
                return None
        
        return wrapper
    return decorator


logger.info("✅ Enhanced Error Handler module loaded")