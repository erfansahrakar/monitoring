"""
🤖 ربات فروش مانتو - نسخه حرفه‌ای با مانیتورینگ کامل
✅ Monitoring System
✅ Health Checker
✅ Alert Manager
✅ Cache Manager
✅ Rate Limiter
✅ Error Handler
✅ Logger
✅ Database with Connection Pool
✅ Notification Service
✅ Admin Dashboard

نویسنده: Claude AI
تاریخ: 2026-01-06
ورژن: 2.0.0 (Professional Edition)
"""

import asyncio
import logging
import sys
import time
import signal
from datetime import datetime
from pathlib import Path
import functools
from typing import Callable, Optional, Any

# Telegram imports
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# Configuration
from config import (
    BOT_TOKEN,
    ADMIN_ID,
    DATABASE_NAME,
    BACKUP_FOLDER,
    LOG_FOLDER,
    MONITORING_ENABLED,
    MONITORING_INTERVAL,
    AUTO_HEALTH_CHECK,
    HEALTH_CHECK_INTERVAL,
    ALERTS_ENABLED,
    CACHE_ENABLED,
    BACKUP_HOUR,
    BACKUP_MINUTE
)

# Database
from database import EnhancedDatabaseManager, initialize_database

# Logging
from logger import setup_logging, get_logger

# Cache
from cache_manager import EnhancedCacheManager, CacheFactory

# Rate Limiter
from rate_limiter import EnhancedRateLimiter, RateLimitMonitor

# Error Handler
from error_handler import EnhancedErrorHandler

# Health Checker
from health_check import EnhancedHealthChecker

# Monitoring
from monitoring_system import MonitoringSystem, AutoMonitoringTask

# Alert Manager
from alert_manager import AdvancedAlertManager, create_default_alert_rules

# Notification Service
from notification_service import NotificationService, AsyncNotificationSender

# Handlers (فرض می‌کنیم handlers.py وجود دارد)
# اگر نداری، باید بسازیش
try:
    from handlers import (
        start_handler,
        help_handler,
        search_inline_handler,
        chosen_inline_result_handler,
        order_callback_handler,
        receipt_handler,
        setup_user_handlers
    )
    HANDLERS_AVAILABLE = True
except ImportError:
    HANDLERS_AVAILABLE = False
    logging.warning("⚠️ handlers.py not found - using minimal handlers")

# Admin Dashboard
from admin_dashboard import setup_admin_handlers

# Setup logger
logger_manager = setup_logging(
    app_name="ShopBot",
    log_folder=LOG_FOLDER,
    log_level="INFO"
)
logger = get_logger(__name__)


# ==================== Bot Application ====================

class ShopBot:
    """کلاس اصلی ربات"""
    
    def __init__(self):
        self.start_time = time.time()
        self.application = None
        
        # Components
        self.db = None
        self.cache_manager = None
        self.rate_limiter = None
        self.error_handler = None
        self.health_checker = None
        self.monitoring_system = None
        self.alert_manager = None
        self.notification_service = None
        
        # Tasks
        self.monitoring_task = None
        self.health_check_task = None
        self.notification_sender = None
        self.backup_task = None
        
        # State
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        logger.info("=" * 60)
        logger.info("🤖 Shop Bot - Professional Edition")
        logger.info("=" * 60)
    
    # ==================== Initialization ====================
    
    def initialize_components(self):
        """راه‌اندازی تمام اجزا"""
        logger.info("🔧 Initializing components...")
        
        # 1. Database
        logger.info("📦 1/8 - Setting up database...")
        self.db = EnhancedDatabaseManager(
            db_name=DATABASE_NAME,
            backup_folder=BACKUP_FOLDER,
            max_connections=10,
            enable_query_tracking=True,
            enable_query_cache=True
        )
        initialize_database(self.db)
        logger.info("✅ Database initialized")
        
        # 2. Cache Manager
        if CACHE_ENABLED:
            logger.info("💾 2/8 - Setting up cache manager...")
            self.cache_manager = CacheFactory.get_cache(
                'default',
                enabled=True,
                default_ttl=300,
                max_size=10000
            )
            logger.info("✅ Cache manager initialized")
        else:
            logger.info("⏭ 2/8 - Cache disabled")
        
        # 3. Rate Limiter
        logger.info("⏱ 3/8 - Setting up rate limiter...")
        self.rate_limiter = EnhancedRateLimiter(admin_id=ADMIN_ID)
        logger.info("✅ Rate limiter initialized")
        
        # 4. Health Checker
        logger.info("🏥 4/8 - Setting up health checker...")
        self.health_checker = EnhancedHealthChecker(
            db=self.db,
            start_time=self.start_time,
            cache_manager=self.cache_manager,
            monitoring_system=None  # خودش بعداً set می‌شه
        )
        logger.info("✅ Health checker initialized")
        
        # 5. Alert Manager
        if ALERTS_ENABLED:
            logger.info("🚨 5/8 - Setting up alert manager...")
            self.alert_manager = AdvancedAlertManager(admin_id=ADMIN_ID)
            
            # اضافه کردن قوانین پیش‌فرض
            for rule in create_default_alert_rules():
                self.alert_manager.add_rule(rule)
            
            logger.info("✅ Alert manager initialized")
        else:
            logger.info("⏭ 5/8 - Alerts disabled")
        
        # 6. Notification Service
        logger.info("📱 6/8 - Setting up notification service...")
        self.notification_service = NotificationService(admin_id=ADMIN_ID)
        logger.info("✅ Notification service initialized")
        
        # 7. Monitoring System
        if MONITORING_ENABLED:
            logger.info("📊 7/8 - Setting up monitoring system...")
            self.monitoring_system = MonitoringSystem(
                db=self.db,
                cache_manager=self.cache_manager,
                health_checker=self.health_checker
            )
            
            # اتصال monitoring به health checker
            self.health_checker.monitoring_system = self.monitoring_system
            
            logger.info("✅ Monitoring system initialized")
        else:
            logger.info("⏭ 7/8 - Monitoring disabled")
        
        # 8. Error Handler
        logger.info("❌ 8/8 - Setting up error handler...")
        self.error_handler = EnhancedErrorHandler(
            health_checker=self.health_checker,
            monitoring_system=self.monitoring_system,
            notification_service=self.notification_service
        )
        logger.info("✅ Error handler initialized")
        
        logger.info("✅ All components initialized successfully!")
    
    def create_application(self):
        """ساخت Application"""
        logger.info("🔨 Creating Telegram application...")
        
        # ساخت Application
        self.application = (
            Application.builder()
            .token(BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )
        
        # ذخیره اجزا در bot_data
        self.application.bot_data['db'] = self.db
        self.application.bot_data['cache_manager'] = self.cache_manager
        self.application.bot_data['rate_limiter'] = self.rate_limiter
        self.application.bot_data['error_handler'] = self.error_handler
        self.application.bot_data['health_checker'] = self.health_checker
        self.application.bot_data['monitoring_system'] = self.monitoring_system
        self.application.bot_data['alert_manager'] = self.alert_manager
        self.application.bot_data['notification_service'] = self.notification_service
        
        # اتصال bot به notification service
        self.notification_service.set_bot(self.application.bot)
        
        logger.info("✅ Application created")
    
    def register_handlers(self):
        """ثبت handler ها"""
        logger.info("📝 Registering handlers...")
        
        # Error Handler (باید اول باشد)
        self.application.add_error_handler(self._global_error_handler)
        
        # Admin Handlers
        admin_dashboard = setup_admin_handlers(
            application=self.application,
            db=self.db,
            cache_manager=self.cache_manager,
            monitoring_system=self.monitoring_system,
            health_checker=self.health_checker,
            alert_manager=self.alert_manager,
            rate_limiter=self.rate_limiter
        )
        
        # User Handlers
        if HANDLERS_AVAILABLE:
            setup_user_handlers(self.application, self.db)
            logger.info("✅ User handlers registered")
        else:
            # Minimal handlers
            self.application.add_handler(CommandHandler("start", self._minimal_start))
            self.application.add_handler(CommandHandler("help", self._minimal_help))
            logger.info("⚠️ Using minimal handlers")
        
        # System Commands
        self.application.add_handler(CommandHandler("health", self._health_command))
        self.application.add_handler(CommandHandler("stats", self._stats_command))
        self.application.add_handler(CommandHandler("monitoring", self._monitoring_command))
        
        logger.info("✅ All handlers registered")
    
    async def set_bot_commands(self):
        """تنظیم دستورات ربات"""
        commands = [
            BotCommand("start", "شروع استفاده از ربات"),
            BotCommand("help", "راهنما"),
            BotCommand("admin", "پنل مدیریت (فقط ادمین)"),
        ]
        
        await self.application.bot.set_my_commands(commands)
        logger.info("✅ Bot commands set")
    
    # ==================== Background Tasks ====================
    
    async def start_background_tasks(self):
        """شروع task های پس‌زمینه"""
        logger.info("🚀 Starting background tasks...")
        
        # 1. Monitoring Task
        if self.monitoring_system and MONITORING_ENABLED:
            self.monitoring_task = AutoMonitoringTask(
                self.monitoring_system,
                interval_seconds=MONITORING_INTERVAL
            )
            asyncio.create_task(self.monitoring_task.start())
            logger.info("✅ Monitoring task started")
        
        # 2. Health Check Task
        if self.health_checker and AUTO_HEALTH_CHECK:
            asyncio.create_task(self._health_check_loop())
            logger.info("✅ Health check task started")
        
        # 3. Notification Sender
        if self.notification_service:
            self.notification_sender = AsyncNotificationSender(
                self.notification_service
            )
            asyncio.create_task(self.notification_sender.start())
            logger.info("✅ Notification sender started")
        
        # 4. Auto Backup Task
        asyncio.create_task(self._auto_backup_loop())
        logger.info("✅ Auto backup task started")
        
        # 5. Cleanup Task
        asyncio.create_task(self._cleanup_loop())
        logger.info("✅ Cleanup task started")
        
        logger.info("✅ All background tasks started")
    
    async def _health_check_loop(self):
        """حلقه بررسی سلامت"""
        logger.info(f"🏥 Health check loop started (interval: {HEALTH_CHECK_INTERVAL}s)")
        
        while self.is_running:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
                # انجام Health Check
                health = self.health_checker.perform_health_check()
                
                # اگر مشکل جدی باشد، اعلان بده
                if health.overall_status.value in ['critical', 'warning']:
                    if self.notification_service and self.alert_manager:
                        # ارسال اعلان
                        logger.warning(f"⚠️ Health status: {health.overall_status.value}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in health check loop: {e}")
                await asyncio.sleep(60)
        
        logger.info("🛑 Health check loop stopped")
    
    async def _auto_backup_loop(self):
        """حلقه بکاپ خودکار"""
        logger.info(f"💾 Auto backup scheduled at {BACKUP_HOUR:02d}:{BACKUP_MINUTE:02d}")
        
        while self.is_running:
            try:
                now = datetime.now()
                
                # محاسبه زمان بکاپ بعدی
                next_backup = now.replace(
                    hour=BACKUP_HOUR,
                    minute=BACKUP_MINUTE,
                    second=0,
                    microsecond=0
                )
                
                if next_backup <= now:
                    # اگر امروز گذشته، فردا
                    from datetime import timedelta
                    next_backup += timedelta(days=1)
                
                # محاسبه زمان انتظار
                wait_seconds = (next_backup - now).total_seconds()
                
                logger.info(f"⏰ Next backup in {wait_seconds/3600:.1f} hours")
                
                # انتظار تا زمان بکاپ
                await asyncio.sleep(wait_seconds)
                
                # ساخت بکاپ
                logger.info("💾 Creating automatic backup...")
                backup_path = self.db.create_backup(is_automatic=True)
                
                if backup_path:
                    logger.info(f"✅ Backup created: {backup_path}")
                    
                    # پاکسازی بکاپ‌های قدیمی
                    deleted = self.db.delete_old_backups(keep_count=10)
                    if deleted > 0:
                        logger.info(f"🗑 Deleted {deleted} old backups")
                    
                    # ارسال اعلان به ادمین
                    if self.notification_service:
                        await self.notification_service.create_notification(
                            channel='telegram',
                            message=f"✅ بکاپ خودکار با موفقیت ساخته شد\n\n📁 {backup_path}",
                            priority='low'
                        )
                else:
                    logger.error("❌ Backup failed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in backup loop: {e}")
                await asyncio.sleep(3600)  # یک ساعت صبر کن
        
        logger.info("🛑 Auto backup loop stopped")
    
    async def _cleanup_loop(self):
        """حلقه پاکسازی"""
        logger.info("🧹 Cleanup loop started (runs every hour)")
        
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # هر ساعت
                
                logger.info("🧹 Running cleanup tasks...")
                
                # 1. پاکسازی کش
                if self.cache_manager:
                    self.cache_manager.cleanup_expired_cache()
                
                # 2. پاکسازی مانیتورینگ
                if self.monitoring_system:
                    self.monitoring_system.cleanup_old_data()
                
                # 3. پاکسازی Rate Limiter
                if self.rate_limiter:
                    # حذف penalty های منقضی شده
                    current_time = time.time()
                    expired_penalties = [
                        key for key, expire_time in self.rate_limiter.penalties.items()
                        if current_time >= expire_time
                    ]
                    for key in expired_penalties:
                        del self.rate_limiter.penalties[key]
                    
                    if expired_penalties:
                        logger.info(f"🧹 Cleaned {len(expired_penalties)} expired penalties")
                
                logger.info("✅ Cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in cleanup loop: {e}")
        
        logger.info("🛑 Cleanup loop stopped")
    
    # ==================== System Commands ====================
    
    async def _health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور بررسی سلامت"""
        if update.effective_user.id != ADMIN_ID:
            return
        
        if not self.health_checker:
            await update.message.reply_text("⚠️ Health Checker فعال نیست!")
            return
        
        await update.message.reply_text("🏥 در حال بررسی سلامت...")
        
        # انجام Health Check
        health = self.health_checker.perform_health_check()
        
        # نمایش گزارش
        report = self.health_checker.get_health_report()
        
        await update.message.reply_text(
            report,
            parse_mode='Markdown'
        )
    
    async def _stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور آمار سریع"""
        if update.effective_user.id != ADMIN_ID:
            return
        
        cursor = self.db.cursor
        
        # آمار سریع
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE('now')")
        orders_today = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        # Uptime
        uptime_seconds = time.time() - self.start_time
        uptime_hours = uptime_seconds / 3600
        
        message = "📊 **آمار سریع**\n\n"
        message += f"👥 کاربران: {users}\n"
        message += f"📦 سفارشات امروز: {orders_today}\n"
        message += f"⏳ در انتظار: {pending}\n"
        message += f"⏱ Uptime: {uptime_hours:.1f}h\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def _monitoring_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """دستور مانیتورینگ"""
        if update.effective_user.id != ADMIN_ID:
            return
        
        if not self.monitoring_system:
            await update.message.reply_text("⚠️ Monitoring System فعال نیست!")
            return
        
        # دریافت داشبورد
        dashboard = self.monitoring_system.get_dashboard_data()
        
        await update.message.reply_text(
            dashboard,
            parse_mode='Markdown'
        )
    
    # ==================== Minimal Handlers ====================
    
    async def _minimal_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """handler start ساده"""
        await update.message.reply_text(
            "🤖 ربات فروش مانتو\n\n"
            "سلام! برای استفاده از ربات، لطفاً handlers.py را پیاده‌سازی کنید.\n"
            "فعلاً فقط دستورات مدیریتی در دسترس هستند.\n\n"
            "/admin - پنل مدیریت"
        )
    
    async def _minimal_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """handler help ساده"""
        message = """
🤖 **راهنمای ربات**

**دستورات عمومی:**
/start - شروع
/help - راهنما

**دستورات مدیریتی (ادمین):**
/admin - پنل مدیریت
/health - بررسی سلامت
/stats - آمار سریع
/monitoring - مانیتورینگ
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    
    # ==================== Error Handling ====================
    
    async def _global_error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت خطاهای سراسری"""
        logger.error(f"❌ Global error: {context.error}", exc_info=context.error)
        
        try:
            # استفاده از error handler
            if self.error_handler and update:
                user_id = update.effective_user.id if update.effective_user else None
                handler_name = None
                
                if update.message and update.message.text:
                    handler_name = update.message.text.split()[0]
                elif update.callback_query:
                    handler_name = update.callback_query.data
                
                error_message = await self.error_handler.handle_error(
                    error=context.error,
                    context=context,
                    user_id=user_id,
                    handler_name=handler_name
                )
                
                # ارسال پیام به کاربر
                if update.message:
                    await update.message.reply_text(error_message)
                elif update.callback_query:
                    await update.callback_query.answer(
                        "❌ خطایی رخ داد!",
                        show_alert=True
                    )
        except Exception as e:
            logger.error(f"❌ Error in error handler: {e}")
    
    # ==================== Startup & Shutdown ====================
    
    async def post_init(self, application: Application):
        """اجرا بعد از init"""
        logger.info("🚀 Running post-init tasks...")
        
        # تنظیم دستورات
        await self.set_bot_commands()
        
        # شروع background tasks
        await self.start_background_tasks()
        
        # ارسال اعلان شروع به ادمین
        try:
            uptime_msg = (
                "✅ **ربات راه‌اندازی شد!**\n\n"
                f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"📊 Monitoring: {'✅' if MONITORING_ENABLED else '❌'}\n"
                f"🚨 Alerts: {'✅' if ALERTS_ENABLED else '❌'}\n"
                f"💾 Cache: {'✅' if CACHE_ENABLED else '❌'}"
            )
            
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=uptime_msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send startup message: {e}")
        
        self.is_running = True
        logger.info("✅ Post-init completed")
    
    async def post_shutdown(self, application: Application):
        """اجرا قبل از shutdown"""
        logger.info("🛑 Running shutdown tasks...")
        
        self.is_running = False
        
        # توقف background tasks
        if self.monitoring_task:
            self.monitoring_task.stop()
        
        if self.notification_sender:
            self.notification_sender.stop()
        
        # بستن اتصالات
        if self.db:
            self.db.close_all_connections()
        
        if self.cache_manager:
            self.cache_manager.stop()
        
        # ارسال اعلان خاموشی به ادمین
        try:
            uptime_seconds = time.time() - self.start_time
            uptime_hours = uptime_seconds / 3600
            
            shutdown_msg = (
                "🛑 **ربات خاموش شد**\n\n"
                f"🕐 {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"⏱ Uptime: {uptime_hours:.2f}h"
            )
            
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=shutdown_msg,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send shutdown message: {e}")
        
        logger.info("✅ Shutdown completed")
    
    # ==================== Run ====================
    
    def run(self):
        """اجرای ربات"""
        try:
            logger.info("🚀 Starting Shop Bot...")
            
            # 1. راه‌اندازی اجزا
            self.initialize_components()
            
            # 2. ساخت Application
            self.create_application()
            
            # 3. ثبت Handlers
            self.register_handlers()
            
            # 4. تنظیم post_init و post_shutdown
            self.application.post_init = self.post_init
            self.application.post_shutdown = self.post_shutdown
            
            # 5. اجرای ربات
            logger.info("=" * 60)
            logger.info("✅ Bot is ready!")
            logger.info("=" * 60)
            
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except KeyboardInterrupt:
            logger.info("\n⚠️ Received keyboard interrupt")
        except Exception as e:
            logger.critical(f"❌ Fatal error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            logger.info("👋 Bot stopped")


# ==================== Signal Handlers ====================

def setup_signal_handlers(bot: ShopBot):
    """تنظیم signal handlers"""
    def signal_handler(signum, frame):
        logger.info(f"⚠️ Received signal {signum}")
        bot.is_running = False
        if bot.application:
            bot.application.stop_running()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# ==================== Main ====================

def main():
    """تابع اصلی"""
    
    # چاپ banner
    print("""
╔═══════════════════════════════════════════════╗
║                                               ║
║        🤖  Shop Bot - Professional Edition    ║
║                                               ║
║        نویسنده: Claude AI                    ║
║        ورژن: 2.0.0                            ║
║        تاریخ: 2026-01-06                      ║
║                                               ║
╚═══════════════════════════════════════════════╝
    """)
    
    # بررسی Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 یا بالاتر مورد نیاز است!")
        sys.exit(1)
    
    # ساخت پوشه‌های مورد نیاز
    Path(LOG_FOLDER).mkdir(exist_ok=True)
    Path(BACKUP_FOLDER).mkdir(exist_ok=True)
    
    # ساخت و اجرای ربات
    bot = ShopBot()
    
    # تنظیم signal handlers
    setup_signal_handlers(bot)
    
    # اجرا
    bot.run()


if __name__ == "__main__":
    main()
    

# ==================== Decorators ====================

def async_timer(func: Callable):
    """Decorator برای اندازه‌گیری زمان اجرای توابع async"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        
        logger.debug(f"⏱ {func.__name__} took {duration:.2f}ms")
        
        # ثبت در monitoring
        if len(args) > 1 and hasattr(args[1], 'bot_data'):
            context = args[1]
            monitoring = context.bot_data.get('monitoring_system')
            if monitoring:
                monitoring.record_request(func.__name__, duration, True)
        
        return result
    
    return wrapper


def user_activity_tracker(func: Callable):
    """Decorator برای ثبت فعالیت کاربر"""
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user:
            user_id = update.effective_user.id
            
            # ثبت در monitoring
            monitoring = context.bot_data.get('monitoring_system')
            if monitoring:
                monitoring.record_user_activity(user_id)
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def admin_only(func: Callable):
    """Decorator برای محدود کردن دسترسی به ادمین"""
    @functools.wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        
        if user_id != ADMIN_ID:
            await update.message.reply_text("⛔️ شما دسترسی ندارید!")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


# ==================== Helper Functions ====================

def format_number(num: float) -> str:
    """فرمت کردن اعداد با جداکننده هزارگان"""
    return f"{num:,.0f}"


def format_price(price: float) -> str:
    """فرمت کردن قیمت"""
    return f"{price:,.0f} تومان"


def format_datetime(dt: datetime) -> str:
    """فرمت کردن تاریخ و زمان"""
    return dt.strftime('%Y/%m/%d %H:%M:%S')


def truncate_string(text: str, max_length: int = 50) -> str:
    """کوتاه کردن متن"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """تقسیم امن (بدون خطای تقسیم بر صفر)"""
    try:
        return a / b if b != 0 else default
    except:
        return default


def calculate_percentage(part: float, total: float) -> float:
    """محاسبه درصد"""
    return safe_divide(part * 100, total, 0.0)


# ==================== Validation Helpers ====================

def validate_phone(phone: str) -> bool:
    """اعتبارسنجی شماره تلفن"""
    import re
    pattern = r'^(\+98|0)?9\d{9}$'
    return bool(re.match(pattern, phone))


def validate_price(price: str) -> tuple[bool, float]:
    """اعتبارسنجی قیمت"""
    try:
        price_float = float(price.replace(',', ''))
        if price_float <= 0:
            return False, 0.0
        return True, price_float
    except:
        return False, 0.0


def validate_quantity(qty: str) -> tuple[bool, int]:
    """اعتبارسنجی تعداد"""
    try:
        qty_int = int(qty)
        if qty_int <= 0:
            return False, 0
        return True, qty_int
    except:
        return False, 0


# ==================== Database Helpers ====================

def get_user_info(db, user_id: int) -> Optional[dict]:
    """دریافت اطلاعات کاربر"""
    try:
        cursor = db.cursor
        cursor.execute("""
            SELECT user_id, username, full_name, phone, address, 
                   total_orders, total_spent, is_blocked
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'full_name': row[2],
                'phone': row[3],
                'address': row[4],
                'total_orders': row[5],
                'total_spent': row[6],
                'is_blocked': bool(row[7])
            }
        return None
    except Exception as e:
        logger.error(f"❌ Error getting user info: {e}")
        return None


def get_product_info(db, product_id: int) -> Optional[dict]:
    """دریافت اطلاعات محصول"""
    try:
        cursor = db.cursor
        cursor.execute("""
            SELECT id, name, description, base_price, image_id, 
                   category, is_active
            FROM products WHERE id = ?
        """, (product_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'base_price': row[3],
                'image_id': row[4],
                'category': row[5],
                'is_active': bool(row[6])
            }
        return None
    except Exception as e:
        logger.error(f"❌ Error getting product info: {e}")
        return None


def update_user_stats(db, user_id: int):
    """بروزرسانی آمار کاربر"""
    try:
        cursor = db.cursor
        
        # محاسبه آمار
        cursor.execute("""
            SELECT 
                COUNT(*) as order_count,
                COALESCE(SUM(final_price), 0) as total_spent
            FROM orders
            WHERE user_id = ?
                AND status IN ('confirmed', 'payment_confirmed')
        """, (user_id,))
        
        stats = cursor.fetchone()
        
        # بروزرسانی
        cursor.execute("""
            UPDATE users
            SET total_orders = ?,
                total_spent = ?
            WHERE user_id = ?
        """, (stats[0], stats[1], user_id))
        
        db.conn.commit()
        
    except Exception as e:
        logger.error(f"❌ Error updating user stats: {e}")


# ==================== Cache Helpers ====================

async def get_cached_or_fetch(cache_manager, key: str, 
                              fetch_func: Callable, ttl: int = 300) -> Any:
    """دریافت از کش یا fetch کردن"""
    if not cache_manager:
        return await fetch_func() if asyncio.iscoroutinefunction(fetch_func) else fetch_func()
    
    # سعی در دریافت از کش
    cached = cache_manager.get(key)
    if cached is not None:
        return cached
    
    # اگر نبود، fetch کن
    data = await fetch_func() if asyncio.iscoroutinefunction(fetch_func) else fetch_func()
    
    # ذخیره در کش
    if data is not None:
        cache_manager.set(key, data, ttl=ttl)
    
    return data


def invalidate_user_cache(cache_manager, user_id: int):
    """Invalidate کردن کش کاربر"""
    if not cache_manager:
        return
    
    patterns = [
        f"user:{user_id}",
        f"orders:user:{user_id}",
        f"stats:user:{user_id}"
    ]
    
    for pattern in patterns:
        cache_manager.delete(pattern)


# ==================== Notification Helpers ====================

async def send_admin_notification(context, message: str, priority: str = 'medium'):
    """ارسال اعلان به ادمین"""
    notification_service = context.bot_data.get('notification_service')
    
    if notification_service:
        notification_service.create_notification(
            channel='telegram',
            message=message,
            priority=priority,
            recipient=str(ADMIN_ID)
        )
    else:
        # ارسال مستقیم
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Failed to send admin notification: {e}")


async def notify_order_status(context, user_id: int, order_id: int, 
                              status: str, message: str):
    """اعلان تغییر وضعیت سفارش"""
    try:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'payment_confirmed': '💰',
            'rejected': '❌'
        }
        
        emoji = status_emoji.get(status, '📦')
        
        full_message = f"{emoji} **سفارش #{order_id}**\n\n{message}"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=full_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to notify user {user_id}: {e}")


# ==================== Performance Helpers ====================

class PerformanceProfiler:
    """Profiler برای اندازه‌گیری عملکرد"""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = (self.end_time - self.start_time) * 1000
        logger.debug(f"⏱ [{self.name}] took {duration:.2f}ms")
    
    def get_duration_ms(self) -> float:
        """دریافت مدت زمان"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


# ==================== Testing Helpers ====================

def create_test_user(db, user_id: int = 999999999):
    """ساخت کاربر تستی"""
    try:
        cursor = db.cursor
        cursor.execute("""
            INSERT OR REPLACE INTO users 
            (user_id, username, full_name, phone, address)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            'test_user',
            'Test User',
            '09123456789',
            'Test Address'
        ))
        db.conn.commit()
        logger.info(f"✅ Test user created: {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating test user: {e}")
        return False


def create_test_product(db, product_name: str = "تست مانتو"):
    """ساخت محصول تستی"""
    try:
        cursor = db.cursor
        cursor.execute("""
            INSERT INTO products 
            (name, description, base_price, is_active)
            VALUES (?, ?, ?, ?)
        """, (
            product_name,
            "این یک محصول تستی است",
            100000,
            1
        ))
        db.conn.commit()
        
        product_id = cursor.lastrowid
        
        # اضافه کردن پک تستی
        cursor.execute("""
            INSERT INTO packs 
            (product_id, name, quantity, price)
            VALUES (?, ?, ?, ?)
        """, (
            product_id,
            "تک",
            1,
            100000
        ))
        db.conn.commit()
        
        logger.info(f"✅ Test product created: {product_id}")
        return product_id
    except Exception as e:
        logger.error(f"❌ Error creating test product: {e}")
        return None


def cleanup_test_data(db):
    """پاکسازی داده‌های تستی"""
    try:
        cursor = db.cursor
        
        # حذف کاربران تستی
        cursor.execute("DELETE FROM users WHERE user_id >= 999999999")
        
        # حذف محصولات تستی
        cursor.execute("DELETE FROM products WHERE name LIKE 'تست%'")
        
        db.conn.commit()
        logger.info("✅ Test data cleaned up")
        return True
    except Exception as e:
        logger.error(f"❌ Error cleaning test data: {e}")
        return False


# ==================== Development Tools ====================

def print_system_info():
    """چاپ اطلاعات سیستم"""
    import platform
    import sys
    
    print("\n" + "=" * 60)
    print("🖥 System Information")
    print("=" * 60)
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Processor: {platform.processor()}")
    print("=" * 60 + "\n")


def print_config_status():
    """چاپ وضعیت تنظیمات"""
    from config import (
        MONITORING_ENABLED,
        ALERTS_ENABLED,
        CACHE_ENABLED,
        AUTO_HEALTH_CHECK,
        NOTIFICATIONS_ENABLED
    )
    
    print("\n" + "=" * 60)
    print("⚙️ Configuration Status")
    print("=" * 60)
    print(f"Monitoring: {'✅' if MONITORING_ENABLED else '❌'}")
    print(f"Alerts: {'✅' if ALERTS_ENABLED else '❌'}")
    print(f"Cache: {'✅' if CACHE_ENABLED else '❌'}")
    print(f"Auto Health Check: {'✅' if AUTO_HEALTH_CHECK else '❌'}")
    print(f"Notifications: {'✅' if NOTIFICATIONS_ENABLED else '❌'}")
    print("=" * 60 + "\n")


def check_dependencies():
    """بررسی وابستگی‌ها"""
    required_packages = [
        'telegram',
        'python-telegram-bot',
        'python-dotenv',
        'psutil',
        'asyncio'
    ]
    
    print("\n" + "=" * 60)
    print("📦 Checking Dependencies")
    print("=" * 60)
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT FOUND")
            missing.append(package)
    
    print("=" * 60)
    
    if missing:
        print(f"\n⚠️ Missing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
    else:
        print("\n✅ All dependencies are installed!")
    
    print()


# ==================== Utility Classes ====================

class Singleton:
    """Singleton pattern"""
    _instances = {}
    
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]


class RateLimitedExecutor:
    """اجراکننده با محدودیت نرخ"""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def execute(self, func: Callable, *args, **kwargs):
        """اجرای تابع با rate limiting"""
        now = time.time()
        
        # پاکسازی فراخوانی‌های قدیمی
        self.calls = [t for t in self.calls if now - t < self.time_window]
        
        # بررسی محدودیت
        if len(self.calls) >= self.max_calls:
            wait_time = self.time_window - (now - self.calls[0])
            await asyncio.sleep(wait_time)
            self.calls = []
        
        # ثبت فراخوانی
        self.calls.append(now)
        
        # اجرای تابع
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


# ==================== Export Functions ====================

def export_database_schema(db, filepath: str = "schema.sql"):
    """خروجی schema دیتابیس"""
    try:
        cursor = db.cursor
        
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND sql IS NOT NULL
        """)
        
        schemas = cursor.fetchall()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("-- Database Schema\n")
            f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")
            
            for schema in schemas:
                f.write(schema[0] + ";\n\n")
        
        logger.info(f"✅ Schema exported to: {filepath}")
        return True
    except Exception as e:
        logger.error(f"❌ Error exporting schema: {e}")
        return False


# ==================== CLI Tools ====================

def run_database_migration(db, migration_file: str):
    """اجرای migration"""
    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        cursor = db.cursor
        cursor.executescript(sql)
        db.conn.commit()
        
        logger.info(f"✅ Migration applied: {migration_file}")
        return True
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def interactive_shell(db):
    """Shell تعاملی برای کار با دیتابیس"""
    print("\n🐚 Interactive Database Shell")
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            query = input("SQL> ").strip()
            
            if query.lower() == 'exit':
                break
            
            if not query:
                continue
            
            cursor = db.cursor
            cursor.execute(query)
            
            if query.upper().startswith('SELECT'):
                results = cursor.fetchall()
                for row in results:
                    print(row)
            else:
                db.conn.commit()
                print(f"✅ {cursor.rowcount} rows affected")
        
        except KeyboardInterrupt:
            print("\n👋 Bye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# ==================== Main Guard ====================

if __name__ == "__main__":
    # اگر این فایل مستقیماً اجرا شد
    print("⚠️ This is not the main entry point!")
    print("Please run: python main.py")
