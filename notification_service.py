"""
📱 سیستم اعلان‌رسانی پیشرفته
✅ Multi-channel Notifications (Telegram, Log, File)
✅ Smart Formatting
✅ Rate Limiting for Notifications
✅ Notification Queue
✅ Retry Mechanism
✅ Template System

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import time
from threading import Lock

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class NotificationPriority(Enum):
    """اولویت اعلان"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class NotificationStatus(Enum):
    """وضعیت اعلان"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


# ==================== Data Classes ====================

@dataclass
class Notification:
    """اعلان"""
    id: str
    channel: str
    priority: NotificationPriority
    message: str
    recipient: Optional[str] = None
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'channel': self.channel,
            'priority': self.priority.value,
            'message': self.message,
            'recipient': self.recipient,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'retry_count': self.retry_count,
            'error': self.error,
            'metadata': self.metadata
        }


# ==================== Notification Templates ====================

class NotificationTemplates:
    """قالب‌های اعلان"""
    
    @staticmethod
    def format_alert(alert) -> str:
        """قالب هشدار"""
        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🟢'
        }
        
        emoji = severity_emoji.get(alert.severity.value, '⚪')
        
        text = f"{emoji} **هشدار {alert.severity.value.upper()}**\n\n"
        text += f"**{alert.rule_name}**\n"
        text += f"{alert.message}\n\n"
        text += f"📊 مقدار فعلی: {alert.current_value:.2f}\n"
        text += f"⚠️ حد آستانه: {alert.threshold}\n"
        text += f"⏰ زمان: {alert.triggered_at.strftime('%H:%M:%S')}\n"
        
        if alert.tags:
            text += f"\n🏷 Tags: {', '.join(f'{k}={v}' for k, v in alert.tags.items())}"
        
        return text
    
    @staticmethod
    def format_system_status(metrics: Dict) -> str:
        """قالب وضعیت سیستم"""
        system = metrics.get('system', {})
        bot = metrics.get('bot', {})
        
        text = "📊 **وضعیت سیستم**\n\n"
        
        # سیستم
        cpu = system.get('cpu_percent', 0)
        cpu_emoji = '🔴' if cpu > 80 else '🟡' if cpu > 60 else '🟢'
        text += f"{cpu_emoji} CPU: {cpu}%\n"
        
        mem = system.get('memory_percent', 0)
        mem_emoji = '🔴' if mem > 85 else '🟡' if mem > 70 else '🟢'
        text += f"{mem_emoji} RAM: {mem}%\n\n"
        
        # کاربران و سفارشات
        text += f"👥 کاربران فعال (1h): {bot.get('active_users_1h', 0)}\n"
        text += f"📦 سفارشات امروز: {bot.get('orders_today', 0)}\n"
        text += f"⏳ در انتظار: {bot.get('pending_orders', 0)}\n"
        text += f"💰 درآمد امروز: {bot.get('revenue_today', 0):,.0f} تومان\n"
        
        return text
    
    @staticmethod
    def format_performance_report(perf: Dict) -> str:
        """قالب گزارش عملکرد"""
        text = "⚡ **گزارش عملکرد**\n\n"
        
        avg_time = perf.get('avg_response_time', 0)
        time_emoji = '🔴' if avg_time > 2000 else '🟡' if avg_time > 1000 else '🟢'
        text += f"{time_emoji} Avg Response: {avg_time:.0f} ms\n"
        text += f"📈 P95: {perf.get('p95_response_time', 0):.0f} ms\n"
        text += f"📊 Total Requests: {perf.get('total_requests', 0)}\n"
        
        success_rate = 100 - perf.get('error_rate', 0)
        rate_emoji = '🔴' if success_rate < 95 else '🟡' if success_rate < 98 else '🟢'
        text += f"{rate_emoji} Success Rate: {success_rate:.1f}%\n"
        
        return text
    
    @staticmethod
    def format_error_notification(error_type: str, error_msg: str, 
                                  user_id: Optional[int] = None) -> str:
        """قالب اعلان خطا"""
        text = "❌ **خطای سیستم**\n\n"
        text += f"**نوع:** {error_type}\n"
        text += f"**پیام:** {error_msg[:200]}\n"
        
        if user_id:
            text += f"**کاربر:** {user_id}\n"
        
        text += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        return text
    
    @staticmethod
    def format_daily_summary(stats: Dict) -> str:
        """قالب خلاصه روزانه"""
        text = "📅 **خلاصه روزانه**\n"
        text += "═" * 30 + "\n\n"
        
        text += "**👥 کاربران:**\n"
        text += f"├ جدید: {stats.get('new_users', 0)}\n"
        text += f"└ فعال: {stats.get('active_users', 0)}\n\n"
        
        text += "**📦 سفارشات:**\n"
        text += f"├ کل: {stats.get('total_orders', 0)}\n"
        text += f"├ موفق: {stats.get('successful_orders', 0)}\n"
        text += f"└ در انتظار: {stats.get('pending_orders', 0)}\n\n"
        
        text += "**💰 درآمد:**\n"
        text += f"└ {stats.get('revenue', 0):,.0f} تومان\n\n"
        
        text += f"📊 نرخ تبدیل: {stats.get('conversion_rate', 0):.1f}%"
        
        return text


# ==================== Notification Service ====================

class NotificationService:
    """سرویس اعلان‌رسانی"""
    
    def __init__(self, admin_id: Optional[int] = None):
        self.admin_id = admin_id
        self.bot_instance = None
        
        # صف اعلان‌ها
        self.notification_queue: deque = deque()
        
        # تاریخچه اعلان‌ها
        self.notification_history: deque = deque(maxlen=200)
        
        # Rate limiting برای اعلان‌ها
        self.notification_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        
        # آمار
        self.stats = {
            'total_sent': 0,
            'total_failed': 0,
            'by_channel': defaultdict(int),
            'by_priority': defaultdict(int)
        }
        
        self._lock = Lock()
        self._running = False
        
        logger.info("✅ Notification Service initialized")
    
    def set_bot(self, bot):
        """تنظیم نمونه ربات"""
        self.bot_instance = bot
        logger.info("✅ Bot instance set for notifications")
    
    # ==================== Queue Management ====================
    
    def enqueue(self, notification: Notification):
        """اضافه کردن به صف"""
        with self._lock:
            self.notification_queue.append(notification)
            self.stats['by_priority'][notification.priority.value] += 1
            logger.debug(f"📬 Notification queued: {notification.id}")
    
    def create_notification(self, channel: str, message: str, 
                          priority: NotificationPriority = NotificationPriority.MEDIUM,
                          recipient: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> Notification:
        """ساخت و صف کردن اعلان"""
        notification = Notification(
            id=f"notif_{int(time.time() * 1000)}",
            channel=channel,
            priority=priority,
            message=message,
            recipient=recipient or str(self.admin_id),
            metadata=metadata or {}
        )
        
        self.enqueue(notification)
        return notification
    
    # ==================== Sending Notifications ====================
    
    async def send_telegram(self, notification: Notification) -> bool:
        """ارسال به تلگرام"""
        if not self.bot_instance or not self.admin_id:
            logger.warning("⚠️ Bot instance or admin_id not set")
            return False
        
        # بررسی rate limit
        if not self._check_rate_limit('telegram'):
            logger.warning("⚠️ Telegram rate limit exceeded")
            return False
        
        try:
            recipient_id = int(notification.recipient) if notification.recipient else self.admin_id
            
            await self.bot_instance.send_message(
                chat_id=recipient_id,
                text=notification.message,
                parse_mode='Markdown'
            )
            
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()
            
            self._record_notification_time('telegram')
            self.stats['total_sent'] += 1
            self.stats['by_channel']['telegram'] += 1
            
            logger.info(f"✅ Telegram notification sent: {notification.id}")
            return True
            
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error = str(e)
            self.stats['total_failed'] += 1
            
            logger.error(f"❌ Failed to send Telegram notification: {e}")
            return False
    
    async def send_log(self, notification: Notification) -> bool:
        """ارسال به لاگ"""
        try:
            log_level = {
                NotificationPriority.CRITICAL: logging.CRITICAL,
                NotificationPriority.HIGH: logging.ERROR,
                NotificationPriority.MEDIUM: logging.WARNING,
                NotificationPriority.LOW: logging.INFO
            }.get(notification.priority, logging.INFO)
            
            logger.log(log_level, f"📢 {notification.message}")
            
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()
            
            self.stats['total_sent'] += 1
            self.stats['by_channel']['log'] += 1
            
            return True
            
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error = str(e)
            self.stats['total_failed'] += 1
            
            logger.error(f"❌ Failed to log notification: {e}")
            return False
    
    async def send_file(self, notification: Notification) -> bool:
        """ارسال به فایل"""
        try:
            filepath = notification.metadata.get('filepath', 'notifications.log')
            
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().isoformat()}] ")
                f.write(f"[{notification.priority.name}] ")
                f.write(f"{notification.message}\n")
            
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now()
            
            self.stats['total_sent'] += 1
            self.stats['by_channel']['file'] += 1
            
            return True
            
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error = str(e)
            self.stats['total_failed'] += 1
            
            logger.error(f"❌ Failed to write notification to file: {e}")
            return False
    
    async def process_notification(self, notification: Notification) -> bool:
        """پردازش یک اعلان"""
        channel_handlers = {
            'telegram': self.send_telegram,
            'log': self.send_log,
            'file': self.send_file
        }
        
        handler = channel_handlers.get(notification.channel)
        if not handler:
            logger.error(f"❌ Unknown notification channel: {notification.channel}")
            return False
        
        success = await handler(notification)
        
        # Retry در صورت شکست
        if not success and notification.retry_count < notification.max_retries:
            notification.retry_count += 1
            notification.status = NotificationStatus.RETRYING
            
            # اضافه کردن مجدد به صف با تاخیر
            await asyncio.sleep(5 * notification.retry_count)  # Exponential backoff
            self.enqueue(notification)
            
            logger.info(
                f"🔄 Retrying notification {notification.id} "
                f"(attempt {notification.retry_count}/{notification.max_retries})"
            )
        
        # ذخیره در تاریخچه
        self.notification_history.append(notification)
        
        return success
    
    # ==================== Queue Processing ====================
    
    async def process_queue(self):
        """پردازش صف اعلان‌ها"""
        while self._running:
            try:
                if not self.notification_queue:
                    await asyncio.sleep(1)
                    continue
                
                # مرتب‌سازی بر اساس اولویت
                with self._lock:
                    notifications = sorted(
                        list(self.notification_queue),
                        key=lambda n: n.priority.value,
                        reverse=True
                    )
                    self.notification_queue.clear()
                
                # پردازش
                for notification in notifications:
                    await self.process_notification(notification)
                    await asyncio.sleep(0.5)  # فاصله بین اعلان‌ها
                
            except Exception as e:
                logger.error(f"❌ Error processing notification queue: {e}")
                await asyncio.sleep(5)
    
    async def start(self):
        """شروع پردازش صف"""
        if self._running:
            logger.warning("⚠️ Notification service already running")
            return
        
        self._running = True
        logger.info("✅ Notification service started")
        
        await self.process_queue()
    
    def stop(self):
        """توقف سرویس"""
        self._running = False
        logger.info("🛑 Notification service stopped")
    
    # ==================== Rate Limiting ====================
    
    def _check_rate_limit(self, channel: str, max_per_minute: int = 10) -> bool:
        """بررسی محدودیت نرخ"""
        current_time = time.time()
        cutoff_time = current_time - 60
        
        # پاکسازی زمان‌های قدیمی
        times = self.notification_times[channel]
        while times and times[0] < cutoff_time:
            times.popleft()
        
        # بررسی محدودیت
        if len(times) >= max_per_minute:
            return False
        
        return True
    
    def _record_notification_time(self, channel: str):
        """ثبت زمان ارسال"""
        self.notification_times[channel].append(time.time())
    
    # ==================== Helper Methods ====================
    
    async def send_alert(self, alert):
        """ارسال هشدار"""
        message = NotificationTemplates.format_alert(alert)
        
        priority_map = {
            'critical': NotificationPriority.CRITICAL,
            'high': NotificationPriority.HIGH,
            'medium': NotificationPriority.MEDIUM,
            'low': NotificationPriority.LOW
        }
        priority = priority_map.get(alert.severity.value, NotificationPriority.MEDIUM)
        
        self.create_notification(
            channel='telegram',
            message=message,
            priority=priority,
            metadata={'alert_id': alert.id}
        )
        
        # همچنین لاگ کن
        self.create_notification(
            channel='log',
            message=message,
            priority=priority
        )
    
    async def send_system_status(self, metrics: Dict):
        """ارسال وضعیت سیستم"""
        message = NotificationTemplates.format_system_status(metrics)
        
        self.create_notification(
            channel='telegram',
            message=message,
            priority=NotificationPriority.LOW
        )
    
    async def send_performance_report(self, perf: Dict):
        """ارسال گزارش عملکرد"""
        message = NotificationTemplates.format_performance_report(perf)
        
        self.create_notification(
            channel='telegram',
            message=message,
            priority=NotificationPriority.LOW
        )
    
    async def send_error_notification(self, error_type: str, error_msg: str,
                                     user_id: Optional[int] = None):
        """ارسال اعلان خطا"""
        message = NotificationTemplates.format_error_notification(
            error_type, error_msg, user_id
        )
        
        self.create_notification(
            channel='telegram',
            message=message,
            priority=NotificationPriority.HIGH
        )
    
    async def send_daily_summary(self, stats: Dict):
        """ارسال خلاصه روزانه"""
        message = NotificationTemplates.format_daily_summary(stats)
        
        self.create_notification(
            channel='telegram',
            message=message,
            priority=NotificationPriority.MEDIUM
        )
    
    # ==================== Statistics ====================
    
    def get_statistics(self) -> Dict:
        """دریافت آمار اعلان‌ها"""
        return {
            'total_sent': self.stats['total_sent'],
            'total_failed': self.stats['total_failed'],
            'success_rate': (
                (self.stats['total_sent'] / (self.stats['total_sent'] + self.stats['total_failed']) * 100)
                if (self.stats['total_sent'] + self.stats['total_failed']) > 0
                else 100
            ),
            'by_channel': dict(self.stats['by_channel']),
            'by_priority': dict(self.stats['by_priority']),
            'queue_size': len(self.notification_queue),
            'history_size': len(self.notification_history)
        }
    
    def get_recent_notifications(self, count: int = 10) -> List[Notification]:
        """دریافت آخرین اعلان‌ها"""
        return list(self.notification_history)[-count:]
    
    def get_failed_notifications(self) -> List[Notification]:
        """دریافت اعلان‌های ناموفق"""
        return [
            n for n in self.notification_history 
            if n.status == NotificationStatus.FAILED
        ]


# ==================== Async Notification Sender ====================

class AsyncNotificationSender:
    """ارسال‌کننده غیرهمزمان اعلان‌ها"""
    
    def __init__(self, service: NotificationService):
        self.service = service
        self._task = None
    
    async def start(self):
        """شروع ارسال‌کننده"""
        if self._task and not self._task.done():
            logger.warning("⚠️ Async notification sender already running")
            return
        
        self._task = asyncio.create_task(self.service.start())
        logger.info("✅ Async notification sender started")
    
    def stop(self):
        """توقف ارسال‌کننده"""
        self.service.stop()
        
        if self._task and not self._task.done():
            self._task.cancel()
        
        logger.info("🛑 Async notification sender stopped")


# ==================== Helper Functions ====================

async def send_quick_notification(bot, admin_id: int, message: str, 
                                  priority: str = "medium"):
    """ارسال سریع یک اعلان (بدون صف)"""
    try:
        await bot.send_message(
            chat_id=admin_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("✅ Quick notification sent")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send quick notification: {e}")
        return False


def format_uptime_notification(uptime_seconds: float) -> str:
    """فرمت اعلان uptime"""
    hours = uptime_seconds / 3600
    days = hours / 24
    
    if days >= 1:
        uptime_str = f"{days:.1f} روز"
    elif hours >= 1:
        uptime_str = f"{hours:.1f} ساعت"
    else:
        uptime_str = f"{uptime_seconds / 60:.1f} دقیقه"
    
    return f"🎉 **ربات آنلاین است!**\n\nUptime: {uptime_str}"


logger.info("✅ Notification Service module loaded")