"""
👨‍💼 پنل مدیریت پیشرفته ادمین - بخش اول
✅ Dashboard با Monitoring
✅ User Management
✅ Order Management
✅ Product Management
✅ Statistics & Reports
✅ System Health
✅ Alert Management
✅ Export Functions

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from telegram.constants import ParseMode
from config import ADMIN_ID, MESSAGES

logger = logging.getLogger(__name__)


# ==================== Conversation States ====================

class AdminStates:
    """حالت‌های مکالمه ادمین"""
    # محصولات
    ADD_PRODUCT_NAME = 1
    ADD_PRODUCT_DESC = 2
    ADD_PRODUCT_PRICE = 3
    ADD_PRODUCT_IMAGE = 4
    ADD_PACK_NAME = 5
    ADD_PACK_QTY = 6
    ADD_PACK_PRICE = 7
    
    # کاربران
    USER_ACTION = 10
    SEND_MESSAGE = 11
    
    # گزارشات
    REPORT_SELECTION = 20
    EXPORT_SELECTION = 21
    
    # تنظیمات
    SETTINGS_SELECTION = 30
    ALERT_CONFIG = 31


# ==================== Admin Dashboard Handler ====================

class AdminDashboardHandler:
    """مدیریت داشبورد ادمین"""
    
    def __init__(self, db, cache_manager=None, monitoring_system=None,
                 health_checker=None, alert_manager=None, rate_limiter=None):
        self.db = db
        self.cache_manager = cache_manager
        self.monitoring_system = monitoring_system
        self.health_checker = health_checker
        self.alert_manager = alert_manager
        self.rate_limiter = rate_limiter
        
        logger.info("✅ Admin Dashboard Handler initialized")
    
    # ==================== Main Dashboard ====================
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل اصلی ادمین"""
        user_id = update.effective_user.id
        
        if user_id != ADMIN_ID:
            await update.message.reply_text("⛔️ شما دسترسی ندارید!")
            return
        
        # جمع‌آوری آمار سریع
        stats = await self._get_quick_stats()
        
        # ساخت پیام
        message = "👨‍💼 **پنل مدیریت**\n"
        message += "═" * 30 + "\n\n"
        
        # آمار سریع
        message += "**📊 خلاصه:**\n"
        message += f"├ کاربران: {stats['total_users']}\n"
        message += f"├ سفارشات امروز: {stats['orders_today']}\n"
        message += f"├ در انتظار: {stats['pending_orders']}\n"
        message += f"└ درآمد امروز: {stats['revenue_today']:,.0f} ت\n\n"
        
        # هشدارها
        if stats.get('active_alerts', 0) > 0:
            message += f"🚨 **{stats['active_alerts']} هشدار فعال!**\n\n"
        
        # وضعیت سیستم
        system_status = "✅ سالم" if stats.get('system_healthy', True) else "⚠️ مشکل"
        message += f"**سیستم:** {system_status}\n"
        
        # کیبورد
        keyboard = [
            [
                InlineKeyboardButton("📊 مانیتورینگ", callback_data="admin_monitoring"),
                InlineKeyboardButton("👥 کاربران", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton("📦 سفارشات", callback_data="admin_orders"),
                InlineKeyboardButton("🛍 محصولات", callback_data="admin_products")
            ],
            [
                InlineKeyboardButton("📈 گزارشات", callback_data="admin_reports"),
                InlineKeyboardButton("💾 بکاپ", callback_data="admin_backup")
            ],
            [
                InlineKeyboardButton("🚨 هشدارها", callback_data="admin_alerts"),
                InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")
            ],
            [
                InlineKeyboardButton("🔄 رفرش", callback_data="admin_refresh")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def _get_quick_stats(self) -> Dict:
        """دریافت آمار سریع"""
        try:
            cursor = self.db.cursor
            
            # کاربران
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # سفارشات امروز
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE DATE(created_at) = DATE('now')
            """)
            orders_today = cursor.fetchone()[0]
            
            # سفارشات در انتظار
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending'
            """)
            pending_orders = cursor.fetchone()[0]
            
            # درآمد امروز
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            revenue_today = cursor.fetchone()[0]
            
            # هشدارهای فعال
            active_alerts = 0
            if self.alert_manager:
                active_alerts = len(self.alert_manager.get_active_alerts())
            
            # وضعیت سیستم
            system_healthy = True
            if self.health_checker:
                health = self.health_checker.get_health_status()
                system_healthy = health.overall_status.value in ['healthy', 'degraded']
            
            return {
                'total_users': total_users,
                'orders_today': orders_today,
                'pending_orders': pending_orders,
                'revenue_today': float(revenue_today),
                'active_alerts': active_alerts,
                'system_healthy': system_healthy
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting quick stats: {e}")
            return {
                'total_users': 0,
                'orders_today': 0,
                'pending_orders': 0,
                'revenue_today': 0,
                'active_alerts': 0,
                'system_healthy': False
            }
    
    # ==================== Monitoring Dashboard ====================
    
    async def show_monitoring_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش داشبورد مانیتورینگ"""
        query = update.callback_query
        await query.answer()
        
        if not self.monitoring_system:
            await query.edit_message_text(
                "⚠️ سیستم مانیتورینگ فعال نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
                ]])
            )
            return
        
        # دریافت داده‌های مانیتورینگ
        dashboard_text = self.monitoring_system.get_dashboard_data()
        
        # کیبورد
        keyboard = [
            [
                InlineKeyboardButton("📊 متریک‌ها", callback_data="monitoring_metrics"),
                InlineKeyboardButton("⚡ عملکرد", callback_data="monitoring_performance")
            ],
            [
                InlineKeyboardButton("🏥 Health Check", callback_data="monitoring_health"),
                InlineKeyboardButton("💾 کش", callback_data="monitoring_cache")
            ],
            [
                InlineKeyboardButton("📈 روند", callback_data="monitoring_trends"),
                InlineKeyboardButton("📊 آمار", callback_data="monitoring_stats")
            ],
            [
                InlineKeyboardButton("💾 Export", callback_data="monitoring_export"),
                InlineKeyboardButton("🔄 رفرش", callback_data="admin_monitoring")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            dashboard_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_metrics_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش جزئیات متریک‌ها"""
        query = update.callback_query
        await query.answer()
        
        if not self.monitoring_system:
            return
        
        metrics = self.monitoring_system.collect_all_metrics()
        
        # ساخت پیام جزئیات
        message = "📊 **جزئیات متریک‌ها**\n"
        message += "═" * 30 + "\n\n"
        
        # سیستم
        system = metrics.get('system', {})
        message += "**⚙️ سیستم:**\n"
        message += f"```\n"
        message += f"CPU:    {system.get('cpu_percent', 0):.1f}%\n"
        message += f"RAM:    {system.get('memory_mb', 0):.1f} MB\n"
        message += f"RAM%:   {system.get('memory_percent', 0):.1f}%\n"
        message += f"Disk:   {system.get('disk_usage_percent', 0):.1f}%\n"
        message += f"Threads: {system.get('active_threads', 0)}\n"
        message += f"```\n\n"
        
        # ربات
        bot = metrics.get('bot', {})
        message += "**🤖 ربات:**\n"
        message += f"```\n"
        message += f"Users (1h):  {bot.get('active_users_1h', 0)}\n"
        message += f"Orders:      {bot.get('orders_today', 0)}\n"
        message += f"Pending:     {bot.get('pending_orders', 0)}\n"
        message += f"Revenue:     {bot.get('revenue_today', 0):,.0f} ت\n"
        message += f"Req/min:     {bot.get('requests_per_minute', 0):.1f}\n"
        message += f"Error Rate:  {bot.get('error_rate_percent', 0):.2f}%\n"
        message += f"Cache Hit:   {bot.get('cache_hit_rate', 0):.1f}%\n"
        message += f"```\n\n"
        
        # عملکرد
        perf = metrics.get('performance', {})
        message += "**⚡ عملکرد:**\n"
        message += f"```\n"
        message += f"Avg:  {perf.get('avg_response_time', 0):.0f} ms\n"
        message += f"P50:  {perf.get('p50_response_time', 0):.0f} ms\n"
        message += f"P95:  {perf.get('p95_response_time', 0):.0f} ms\n"
        message += f"P99:  {perf.get('p99_response_time', 0):.0f} ms\n"
        message += f"Total: {perf.get('total_requests', 0)}\n"
        message += f"Success: {perf.get('successful_requests', 0)}\n"
        message += f"Failed:  {perf.get('failed_requests', 0)}\n"
        message += f"```"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_performance_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش جزئیات عملکرد"""
        query = update.callback_query
        await query.answer()
        
        if not self.monitoring_system:
            return
        
        perf_metrics = self.monitoring_system.performance_tracker.get_metrics()
        
        message = "⚡ **جزئیات عملکرد**\n"
        message += "═" * 30 + "\n\n"
        
        message += "**⏱ زمان پاسخ:**\n"
        message += f"├ میانگین: {perf_metrics.avg_response_time:.2f} ms\n"
        message += f"├ P50: {perf_metrics.p50_response_time:.2f} ms\n"
        message += f"├ P95: {perf_metrics.p95_response_time:.2f} ms\n"
        message += f"└ P99: {perf_metrics.p99_response_time:.2f} ms\n\n"
        
        message += "**📊 درخواست‌ها:**\n"
        message += f"├ کل: {perf_metrics.total_requests}\n"
        message += f"├ موفق: {perf_metrics.successful_requests}\n"
        message += f"└ ناموفق: {perf_metrics.failed_requests}\n\n"
        
        success_rate = 0
        if perf_metrics.total_requests > 0:
            success_rate = (perf_metrics.successful_requests / perf_metrics.total_requests) * 100
        
        message += f"**✅ نرخ موفقیت:** {success_rate:.2f}%\n\n"
        
        message += "**🔥 Endpoints:**\n"
        message += f"├ کندترین: {perf_metrics.slowest_endpoint}\n"
        message += f"└ سریع‌ترین: {perf_metrics.fastest_endpoint}\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش Health Check"""
        query = update.callback_query
        await query.answer()
        
        if not self.health_checker:
            await query.edit_message_text(
                "⚠️ Health Checker فعال نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
                ]])
            )
            return
        
        # اجرای Health Check
        health = self.health_checker.perform_health_check()
        
        # نمایش گزارش
        report = self.health_checker.get_health_report()
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 بررسی مجدد", callback_data="monitoring_health"),
                InlineKeyboardButton("📊 جزئیات", callback_data="health_details")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_cache_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار کش"""
        query = update.callback_query
        await query.answer()
        
        if not self.cache_manager:
            await query.edit_message_text(
                "⚠️ Cache Manager فعال نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
                ]])
            )
            return
        
        # دریافت گزارش کش
        report = self.cache_manager.get_cache_report()
        
        keyboard = [
            [
                InlineKeyboardButton("🧹 پاکسازی", callback_data="cache_clear"),
                InlineKeyboardButton("🔄 رفرش", callback_data="monitoring_cache")
            ],
            [
                InlineKeyboardButton("📊 Top Items", callback_data="cache_top_items"),
                InlineKeyboardButton("💾 Export", callback_data="cache_export")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def clear_cache(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پاکسازی کش"""
        query = update.callback_query
        await query.answer("🧹 در حال پاکسازی...")
        
        if not self.cache_manager:
            return
        
        # پاکسازی
        self.cache_manager.clear()
        
        await query.answer("✅ کش پاک شد!", show_alert=True)
        
        # بازگشت به صفحه کش
        await self.show_cache_stats(update, context)
    
    async def show_monitoring_trends(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش روندها"""
        query = update.callback_query
        await query.answer()
        
        if not self.health_checker:
            return
        
        # دریافت روند
        trend_data = self.health_checker.get_health_trend(hours=24)
        
        message = "📈 **روند سلامت سیستم**\n"
        message += "═" * 30 + "\n\n"
        
        trend_emoji = {
            'improving': '📈 بهبود',
            'stable': '➡️ پایدار',
            'degrading': '📉 افت',
            'unknown': '❓ نامشخص'
        }
        
        message += f"**روند:** {trend_emoji.get(trend_data['trend'], '❓')}\n"
        message += f"**بررسی‌ها:** {trend_data['checks']}\n"
        message += f"**میانگین امتیاز:** {trend_data['avg_score']}/100\n"
        message += f"**امتیاز فعلی:** {trend_data['current_score']}/100\n\n"
        
        # توضیح روند
        if trend_data['trend'] == 'improving':
            message += "✅ سیستم در حال بهبود است"
        elif trend_data['trend'] == 'degrading':
            message += "⚠️ سیستم در حال افت است"
        else:
            message += "ℹ️ وضعیت سیستم پایدار است"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_monitoring")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def export_monitoring_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """خروجی داده‌های مانیتورینگ"""
        query = update.callback_query
        await query.answer("💾 در حال تهیه فایل...")
        
        if not self.monitoring_system:
            return
        
        try:
            # ساخت نام فایل با timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"monitoring_export_{timestamp}.json"
            
            # Export
            success = self.monitoring_system.export_metrics(filepath)
            
            if success:
                # ارسال فایل
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=open(filepath, 'rb'),
                    caption="📊 داده‌های مانیتورینگ"
                )
                
                await query.answer("✅ فایل ارسال شد!", show_alert=True)
            else:
                await query.answer("❌ خطا در ساخت فایل!", show_alert=True)
                
        except Exception as e:
            logger.error(f"❌ Error exporting monitoring data: {e}")
            await query.answer("❌ خطا در export!", show_alert=True)
    
    # ==================== User Management ====================
    
    async def show_users_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل کاربران"""
        query = update.callback_query
        await query.answer()
        
        # آمار کاربران
        cursor = self.db.cursor
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(created_at) = DATE('now')
        """)
        today_users = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(created_at) >= DATE('now', '-7 days')
        """)
        week_users = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE is_blocked = 1
        """)
        blocked_users = cursor.fetchone()[0]
        
        message = "👥 **مدیریت کاربران**\n"
        message += "═" * 30 + "\n\n"
        message += f"**کل کاربران:** {total_users}\n"
        message += f"**امروز:** {today_users}\n"
        message += f"**این هفته:** {week_users}\n"
        message += f"**مسدود شده:** {blocked_users}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 جستجو", callback_data="users_search"),
                InlineKeyboardButton("📊 آمار", callback_data="users_stats")
            ],
            [
                InlineKeyboardButton("👑 برترین‌ها", callback_data="users_top"),
                InlineKeyboardButton("🆕 جدیدها", callback_data="users_recent")
            ],
            [
                InlineKeyboardButton("🚫 مسدودها", callback_data="users_blocked"),
                InlineKeyboardButton("📨 ارسال پیام", callback_data="users_broadcast")
            ],
            [
                InlineKeyboardButton("💾 Export", callback_data="users_export"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_user_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار تفصیلی کاربران"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        # آمار تفصیلی
        message = "📊 **آمار کاربران**\n"
        message += "═" * 30 + "\n\n"
        
        # تعداد سفارشات کاربران
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT CASE WHEN total_orders = 0 THEN user_id END) as no_orders,
                COUNT(DISTINCT CASE WHEN total_orders BETWEEN 1 AND 3 THEN user_id END) as few_orders,
                COUNT(DISTINCT CASE WHEN total_orders > 3 THEN user_id END) as many_orders
            FROM users
        """)
        order_stats = cursor.fetchone()
        
        message += "**📦 بر اساس سفارشات:**\n"
        message += f"├ بدون سفارش: {order_stats[0]}\n"
        message += f"├ 1-3 سفارش: {order_stats[1]}\n"
        message += f"└ بیش از 3: {order_stats[2]}\n\n"
        
        # بر اساس هزینه
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN total_spent = 0 THEN 1 END) as no_spend,
                COUNT(CASE WHEN total_spent BETWEEN 1 AND 100000 THEN 1 END) as low_spend,
                COUNT(CASE WHEN total_spent BETWEEN 100001 AND 500000 THEN 1 END) as mid_spend,
                COUNT(CASE WHEN total_spent > 500000 THEN 1 END) as high_spend
            FROM users
        """)
        spend_stats = cursor.fetchone()
        
        message += "**💰 بر اساس هزینه:**\n"
        message += f"├ 0 تومان: {spend_stats[0]}\n"
        message += f"├ تا 100K: {spend_stats[1]}\n"
        message += f"├ 100K-500K: {spend_stats[2]}\n"
        message += f"└ بیش از 500K: {spend_stats[3]}\n\n"
        
        # بر اساس زمان عضویت
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN created_at >= DATE('now') THEN 1 END) as today,
                COUNT(CASE WHEN created_at >= DATE('now', '-7 days') 
                    AND created_at < DATE('now') THEN 1 END) as this_week,
                COUNT(CASE WHEN created_at >= DATE('now', '-30 days') 
                    AND created_at < DATE('now', '-7 days') THEN 1 END) as this_month,
                COUNT(CASE WHEN created_at < DATE('now', '-30 days') THEN 1 END) as older
            FROM users
        """)
        time_stats = cursor.fetchone()
        
        message += "**📅 بر اساس زمان:**\n"
        message += f"├ امروز: {time_stats[0]}\n"
        message += f"├ این هفته: {time_stats[1]}\n"
        message += f"├ این ماه: {time_stats[2]}\n"
        message += f"└ قدیمی‌تر: {time_stats[3]}\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_top_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش برترین کاربران"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        # برترین خریداران
        cursor.execute("""
            SELECT user_id, full_name, total_orders, total_spent
            FROM users
            WHERE total_orders > 0
            ORDER BY total_spent DESC
            LIMIT 10
        """)
        top_buyers = cursor.fetchall()
        
        message = "👑 **برترین کاربران**\n"
        message += "═" * 30 + "\n\n"
        
        message += "**💎 برترین خریداران:**\n"
        
        for i, user in enumerate(top_buyers, 1):
            name = user[1] or f"User {user[0]}"
            message += f"{i}. {name}\n"
            message += f"   📦 {user[2]} سفارش | 💰 {user[3]:,.0f} تومان\n"
        
        if not top_buyers:
            message += "هنوز کاربری خرید نکرده است.\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_recent_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش کاربران جدید"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        cursor.execute("""
            SELECT user_id, full_name, username, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 15
        """)
        recent_users = cursor.fetchall()
        
        message = "🆕 **کاربران جدید**\n"
        message += "═" * 30 + "\n\n"
        
        for user in recent_users:
            name = user[1] or f"User {user[0]}"
            username = f"@{user[2]}" if user[2] else "بدون username"
            created = datetime.fromisoformat(user[3])
            time_ago = self._time_ago(created)
            
            message += f"• {name} ({username})\n"
            message += f"  🕐 {time_ago}\n\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_users")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Order Management ====================
    
    async def show_orders_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل سفارشات"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        # آمار سفارشات
        cursor.execute("SELECT COUNT(*) FROM orders")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'")
        confirmed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'payment_confirmed'")
        completed = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'rejected'")
        rejected = cursor.fetchone()[0]
        
        message = "📦 **مدیریت سفارشات**\n"
        message += "═" * 30 + "\n\n"
        message += f"**کل سفارشات:** {total}\n"
        message += f"**در انتظار:** {pending} 🟡\n"
        message += f"**تایید شده:** {confirmed} 🟢\n"
        message += f"**تکمیل شده:** {completed} ✅\n"
        message += f"**رد شده:** {rejected} ❌\n"
        
        keyboard = [
            [
                InlineKeyboardButton(f"⏳ در انتظار ({pending})", callback_data="orders_pending")
            ],
            [
                InlineKeyboardButton("🟢 تایید شده", callback_data="orders_confirmed"),
                InlineKeyboardButton("✅ تکمیل", callback_data="orders_completed")
            ],
            [
                InlineKeyboardButton("🆕 جدیدترین", callback_data="orders_recent"),
                InlineKeyboardButton("📊 آمار", callback_data="orders_stats")
            ],
            [
                InlineKeyboardButton("💾 Export", callback_data="orders_export"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_pending_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش سفارشات در انتظار"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        cursor.execute("""
            SELECT o.id, o.user_id, u.full_name, p.name, pk.name, 
                   o.quantity, o.final_price, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            JOIN packs pk ON o.pack_id = pk.id
            WHERE o.status = 'pending'
            ORDER BY o.created_at DESC
            LIMIT 10
        """)
        orders = cursor.fetchall()
        
        message = "⏳ **سفارشات در انتظار**\n"
        message += "═" * 30 + "\n\n"
        
        if not orders:
            message += "✅ سفارش در انتظاری وجود ندارد"
        else:
            for order in orders:
                name = order[2] or f"User {order[1]}"
                time_ago = self._time_ago(datetime.fromisoformat(order[7]))
                
                message += f"**#{order[0]}** - {name}\n"
                message += f"📦 {order[3]} - {order[4]}\n"
                message += f"🔢 تعداد: {order[5]}\n"
                message += f"💰 {order[6]:,.0f} تومان\n"
                message += f"🕐 {time_ago}\n"
                message += f"▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 رفرش", callback_data="orders_pending"),
                InlineKeyboardButton("✅ تایید همه", callback_data="orders_approve_all")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_order_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش آمار سفارشات"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        message = "📊 **آمار سفارشات**\n"
        message += "═" * 30 + "\n\n"
        
        # سفارشات امروز
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE DATE(created_at) = DATE('now')
        """)
        today = cursor.fetchone()
        
        message += "**📅 امروز:**\n"
        message += f"├ تعداد: {today[0]}\n"
        message += f"└ مبلغ: {today[1]:,.0f} تومان\n\n"
        
        # این هفته
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE created_at >= DATE('now', '-7 days')
        """)
        week = cursor.fetchone()
        
        message += "**📅 این هفته:**\n"
        message += f"├ تعداد: {week[0]}\n"
        message += f"└ مبلغ: {week[1]:,.0f} تومان\n\n"
        
        # این ماه
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE created_at >= DATE('now', '-30 days')
        """)
        month = cursor.fetchone()
        
        message += "**📅 این ماه:**\n"
        message += f"├ تعداد: {month[0]}\n"
        message += f"└ مبلغ: {month[1]:,.0f} تومان\n\n"
        
        # میانگین سفارش
        cursor.execute("""
            SELECT AVG(final_price)
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        avg = cursor.fetchone()[0] or 0
        
        message += f"**💰 میانگین سفارش:** {avg:,.0f} تومان\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Product Management ====================
    
    async def show_products_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل محصولات"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
        active = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 0")
        inactive = cursor.fetchone()[0]
        
        message = "🛍 **مدیریت محصولات**\n"
        message += "═" * 30 + "\n\n"
        message += f"**فعال:** {active}\n"
        message += f"**غیرفعال:** {inactive}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ افزودن محصول", callback_data="product_add")
            ],
            [
                InlineKeyboardButton("📋 لیست محصولات", callback_data="product_list"),
                InlineKeyboardButton("📊 آمار", callback_data="product_stats")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_product_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لیست محصولات"""
        query = update.callback_query
        await query.answer()
        
        cursor = self.db.cursor
        
        cursor.execute("""
            SELECT id, name, base_price, is_active,
                   (SELECT COUNT(*) FROM packs WHERE product_id = products.id) as pack_count,
                   (SELECT COUNT(*) FROM orders WHERE product_id = products.id) as order_count
            FROM products
            ORDER BY created_at DESC
        """)
        products = cursor.fetchall()
        
        message = "📋 **لیست محصولات**\n"
        message += "═" * 30 + "\n\n"
        
        if not products:
            message += "هنوز محصولی ثبت نشده است"
        else:
            for product in products:
                status = "✅" if product[3] else "❌"
                message += f"{status} **{product[1]}**\n"
                message += f"💰 قیمت پایه: {product[2]:,.0f} ت\n"
                message += f"📦 پک‌ها: {product[4]} | سفارشات: {product[5]}\n"
                message += f"🔧 /edit_product_{product[0]}\n"
                message += f"▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ افزودن", callback_data="product_add"),
                InlineKeyboardButton("🔄 رفرش", callback_data="product_list")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_products")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Reports ====================
    
    async def show_reports_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل گزارشات"""
        query = update.callback_query
        await query.answer()
        
        message = "📈 **گزارشات و تحلیل**\n"
        message += "═" * 30 + "\n\n"
        message += "گزارش مورد نظر را انتخاب کنید:"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 گزارش روزانه", callback_data="report_daily"),
                InlineKeyboardButton("📅 گزارش هفتگی", callback_data="report_weekly")
            ],
            [
                InlineKeyboardButton("📆 گزارش ماهانه", callback_data="report_monthly"),
                InlineKeyboardButton("📈 گزارش فروش", callback_data="report_sales")
            ],
            [
                InlineKeyboardButton("👥 گزارش کاربران", callback_data="report_users"),
                InlineKeyboardButton("📦 گزارش محصولات", callback_data="report_products")
            ],
            [
                InlineKeyboardButton("💰 گزارش مالی", callback_data="report_financial"),
                InlineKeyboardButton("📊 گزارش کامل", callback_data="report_full")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def generate_daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تولید گزارش روزانه"""
        query = update.callback_query
        await query.answer("📊 در حال تهیه گزارش...")
        
        cursor = self.db.cursor
        
        message = "📊 **گزارش روزانه**\n"
        message += f"📅 {datetime.now().strftime('%Y/%m/%d')}\n"
        message += "═" * 30 + "\n\n"
        
        # کاربران جدید
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE DATE(created_at) = DATE('now')
        """)
        new_users = cursor.fetchone()[0]
        
        # سفارشات
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status IN ('confirmed', 'payment_confirmed') THEN 1 END) as success,
                COALESCE(SUM(CASE WHEN status IN ('confirmed', 'payment_confirmed') 
                    THEN final_price END), 0) as revenue
            FROM orders
            WHERE DATE(created_at) = DATE('now')
        """)
        order_stats = cursor.fetchone()
        
        message += "**👥 کاربران:**\n"
        message += f"└ جدید: {new_users}\n\n"
        
        message += "**📦 سفارشات:**\n"
        message += f"├ کل: {order_stats[0]}\n"
        message += f"├ در انتظار: {order_stats[1]}\n"
        message += f"└ موفق: {order_stats[2]}\n\n"
        
        message += "**💰 درآمد:**\n"
        message += f"└ {order_stats[3]:,.0f} تومان\n\n"
        
        # محصولات پرفروش امروز
        cursor.execute("""
            SELECT p.name, COUNT(*) as count, SUM(o.final_price) as revenue
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE DATE(o.created_at) = DATE('now')
                AND o.status IN ('confirmed', 'payment_confirmed')
            GROUP BY p.id
            ORDER BY count DESC
            LIMIT 3
        """)
        top_products = cursor.fetchall()
        
        if top_products:
            message += "**🔥 پرفروش‌ترین:**\n"
            for i, product in enumerate(top_products, 1):
                message += f"{i}. {product[0]}: {product[1]} عدد\n"
        
        keyboard = [
            [
                InlineKeyboardButton("💾 ذخیره", callback_data="report_daily_save"),
                InlineKeyboardButton("📤 ارسال", callback_data="report_daily_send")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_reports")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def generate_financial_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تولید گزارش مالی"""
        query = update.callback_query
        await query.answer("💰 در حال تهیه گزارش مالی...")
        
        cursor = self.db.cursor
        
        message = "💰 **گزارش مالی**\n"
        message += "═" * 30 + "\n\n"
        
        # درآمد کل
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        total_revenue = cursor.fetchone()[0]
        
        # درآمد امروز
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
        """)
        today_revenue = cursor.fetchone()[0]
        
        # درآمد این ماه
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0)
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
                AND created_at >= DATE('now', 'start of month')
        """)
        month_revenue = cursor.fetchone()[0]
        
        # میانگین سفارش
        cursor.execute("""
            SELECT AVG(final_price)
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
        """)
        avg_order = cursor.fetchone()[0] or 0
        
        message += "**💵 درآمد کل:**\n"
        message += f"└ {total_revenue:,.0f} تومان\n\n"
        
        message += "**📅 درآمد امروز:**\n"
        message += f"└ {today_revenue:,.0f} تومان\n\n"
        
        message += "**📆 درآمد این ماه:**\n"
        message += f"└ {month_revenue:,.0f} تومان\n\n"
        
        message += "**📊 میانگین سفارش:**\n"
        message += f"└ {avg_order:,.0f} تومان\n\n"
        
        # درآمد روزانه 7 روز اخیر
        cursor.execute("""
            SELECT DATE(created_at) as day, 
                   COALESCE(SUM(final_price), 0) as revenue
            FROM orders
            WHERE status IN ('confirmed', 'payment_confirmed')
                AND created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day DESC
        """)
        daily_revenue = cursor.fetchall()
        
        if daily_revenue:
            message += "**📈 7 روز اخیر:**\n"
            for day in daily_revenue:
                date = datetime.fromisoformat(day[0]).strftime('%m/%d')
                message += f"• {date}: {day[1]:,.0f} ت\n"
        
        keyboard = [[
            InlineKeyboardButton("🔙 بازگشت", callback_data="admin_reports")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Alerts Management ====================
    
    async def show_alerts_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل هشدارها"""
        query = update.callback_query
        await query.answer()
        
        if not self.alert_manager:
            await query.edit_message_text(
                "⚠️ سیستم هشدار فعال نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
                ]])
            )
            return
        
        # دریافت هشدارها
        alert_summary = self.alert_manager.get_alert_summary()
        
        message = "🚨 **مدیریت هشدارها**\n"
        message += "═" * 30 + "\n\n"
        
        message += f"**فعال:** {alert_summary['total_active']}\n\n"
        
        message += "**بر اساس شدت:**\n"
        severity = alert_summary['by_severity']
        message += f"├ 🔴 Critical: {severity.get('critical', 0)}\n"
        message += f"├ 🟠 High: {severity.get('high', 0)}\n"
        message += f"├ 🟡 Medium: {severity.get('medium', 0)}\n"
        message += f"└ 🟢 Low: {severity.get('low', 0)}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🚨 فعال", callback_data="alerts_active"),
                InlineKeyboardButton("📜 تاریخچه", callback_data="alerts_history")
            ],
            [
                InlineKeyboardButton("⚙️ قوانین", callback_data="alerts_rules"),
                InlineKeyboardButton("📊 آمار", callback_data="alerts_stats")
            ],
            [
                InlineKeyboardButton("🔄 رفرش", callback_data="admin_alerts"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_active_alerts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش هشدارهای فعال"""
        query = update.callback_query
        await query.answer()
        
        if not self.alert_manager:
            return
        
        active_alerts = self.alert_manager.get_active_alerts()
        
        message = "🚨 **هشدارهای فعال**\n"
        message += "═" * 30 + "\n\n"
        
        if not active_alerts:
            message += "✅ هشدار فعالی وجود ندارد"
        else:
            for alert in active_alerts[:10]:
                severity_emoji = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(alert.severity.value, '⚪')
                
                message += f"{severity_emoji} **{alert.rule_name}**\n"
                message += f"{alert.message}\n"
                message += f"🕐 {alert.triggered_at.strftime('%H:%M:%S')}\n"
                message += f"▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ حل همه", callback_data="alerts_resolve_all"),
                InlineKeyboardButton("🔄 رفرش", callback_data="alerts_active")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_alerts")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Backup Management ====================
    
    async def show_backup_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل بکاپ"""
        query = update.callback_query
        await query.answer()
        
        # لیست بکاپ‌ها
        backups = self.db.list_backups()
        
        message = "💾 **مدیریت بکاپ**\n"
        message += "═" * 30 + "\n\n"
        message += f"**تعداد بکاپ‌ها:** {len(backups)}\n"
        
        if backups:
            latest = backups[0]
            message += f"\n**آخرین بکاپ:**\n"
            message += f"├ فایل: {latest['filename']}\n"
            message += f"├ حجم: {latest['size_mb']} MB\n"
            message += f"└ زمان: {latest['created_at'][:16]}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ ساخت بکاپ", callback_data="backup_create"),
                InlineKeyboardButton("📋 لیست بکاپ‌ها", callback_data="backup_list")
            ],
            [
                InlineKeyboardButton("🗑 پاکسازی", callback_data="backup_cleanup"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def create_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ساخت بکاپ"""
        query = update.callback_query
        await query.answer("💾 در حال ساخت بکاپ...")
        
        try:
            backup_path = self.db.create_backup(is_automatic=False)
            
            if backup_path:
                await query.answer("✅ بکاپ ساخته شد!", show_alert=True)
                
                # ارسال فایل بکاپ
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=open(backup_path, 'rb'),
                    caption="💾 فایل بکاپ دیتابیس"
                )
            else:
                await query.answer("❌ خطا در ساخت بکاپ!", show_alert=True)
        
        except Exception as e:
            logger.error(f"❌ Error creating backup: {e}")
            await query.answer("❌ خطا در ساخت بکاپ!", show_alert=True)
        
        # بازگشت به پنل بکاپ
        await self.show_backup_panel(update, context)
    
    async def list_backups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """لیست بکاپ‌ها"""
        query = update.callback_query
        await query.answer()
        
        backups = self.db.list_backups()
        
        message = "📋 **لیست بکاپ‌ها**\n"
        message += "═" * 30 + "\n\n"
        
        if not backups:
            message += "هنوز بکاپی ساخته نشده است"
        else:
            for i, backup in enumerate(backups[:10], 1):
                created = datetime.fromisoformat(backup['created_at'])
                message += f"{i}. **{backup['filename']}**\n"
                message += f"   💾 {backup['size_mb']} MB\n"
                message += f"   📅 {created.strftime('%Y/%m/%d %H:%M')}\n\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 رفرش", callback_data="backup_list"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_backup")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== Settings ====================
    
    async def show_settings_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش پنل تنظیمات"""
        query = update.callback_query
        await query.answer()
        
        message = "⚙️ **تنظیمات سیستم**\n"
        message += "═" * 30 + "\n\n"
        
        # وضعیت ماژول‌ها
        message += "**📦 ماژول‌ها:**\n"
        message += f"├ Cache: {'✅' if self.cache_manager else '❌'}\n"
        message += f"├ Monitoring: {'✅' if self.monitoring_system else '❌'}\n"
        message += f"├ Health Check: {'✅' if self.health_checker else '❌'}\n"
        message += f"├ Alert Manager: {'✅' if self.alert_manager else '❌'}\n"
        message += f"└ Rate Limiter: {'✅' if self.rate_limiter else '❌'}\n"
        
        keyboard = [
            [
                InlineKeyboardButton("💾 کش", callback_data="settings_cache"),
                InlineKeyboardButton("📊 مانیتورینگ", callback_data="settings_monitoring")
            ],
            [
                InlineKeyboardButton("🚨 هشدارها", callback_data="settings_alerts"),
                InlineKeyboardButton("⏱️ Rate Limit", callback_data="settings_ratelimit")
            ],
            [
                InlineKeyboardButton("🧹 نگهداری", callback_data="settings_maintenance"),
                InlineKeyboardButton("📤 Export", callback_data="settings_export")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_cache_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تنظیمات کش"""
        query = update.callback_query
        await query.answer()
        
        if not self.cache_manager:
            await query.edit_message_text(
                "⚠️ Cache Manager فعال نیست!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 بازگشت", callback_data="admin_settings")
                ]])
            )
            return
        
        stats = self.cache_manager.get_stats()
        
        message = "💾 **تنظیمات کش**\n"
        message += "═" * 30 + "\n\n"
        
        message += f"**وضعیت:** {'✅ فعال' if stats['enabled'] else '❌ غیرفعال'}\n"
        message += f"**اندازه:** {stats['cache_size']}/{stats['max_size']}\n"
        message += f"**Hit Rate:** {stats['hit_rate']}%\n"
        message += f"**حافظه:** {stats['total_size_mb']} MB\n"
        
        keyboard = [
            [
                InlineKeyboardButton("🧹 پاکسازی", callback_data="cache_clear"),
                InlineKeyboardButton("📊 آمار", callback_data="monitoring_cache")
            ],
            [
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_maintenance_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """پنل نگهداری"""
        query = update.callback_query
        await query.answer()
        
        message = "🧹 **نگهداری سیستم**\n"
        message += "═" * 30 + "\n\n"
        message += "عملیات نگهداری را انتخاب کنید:"
        
        keyboard = [
            [
                InlineKeyboardButton("🧹 پاکسازی کش", callback_data="maintenance_cache"),
                InlineKeyboardButton("📊 VACUUM DB", callback_data="maintenance_vacuum")
            ],
            [
                InlineKeyboardButton("🗑 پاک کردن لاگ‌ها", callback_data="maintenance_logs"),
                InlineKeyboardButton("🔄 بازنشانی آمار", callback_data="maintenance_reset_stats")
            ],
            [
                InlineKeyboardButton("⚠️ پاکسازی کامل", callback_data="maintenance_full"),
                InlineKeyboardButton("🔙 بازگشت", callback_data="admin_settings")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def perform_vacuum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """اجرای VACUUM"""
        query = update.callback_query
        await query.answer("🔧 در حال بهینه‌سازی دیتابیس...")
        
        try:
            self.db.vacuum_database()
            await query.answer("✅ دیتابیس بهینه شد!", show_alert=True)
        except Exception as e:
            logger.error(f"❌ Error during vacuum: {e}")
            await query.answer("❌ خطا در بهینه‌سازی!", show_alert=True)
        
        await self.show_maintenance_panel(update, context)
    
    async def perform_full_maintenance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نگهداری کامل"""
        query = update.callback_query
        await query.answer("🔧 در حال انجام نگهداری کامل...")
        
        try:
            # 1. پاکسازی کش
            if self.cache_manager:
                self.cache_manager.cleanup_expired_cache()
            
            # 2. VACUUM
            self.db.vacuum_database()
            
            # 3. Analyze
            self.db.analyze_database()
            
            # 4. بکاپ
            self.db.create_backup(is_automatic=False)
            
            # 5. پاکسازی بکاپ‌های قدیمی
            self.db.delete_old_backups(keep_count=10)
            
            await query.answer("✅ نگهداری کامل انجام شد!", show_alert=True)
            
        except Exception as e:
            logger.error(f"❌ Error during full maintenance: {e}")
            await query.answer("❌ خطا در نگهداری!", show_alert=True)
        
        await self.show_maintenance_panel(update, context)
    
    # ==================== Export Functions ====================
    
    async def export_all_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """خروجی تمام داده‌ها"""
        query = update.callback_query
        await query.answer("💾 در حال تهیه فایل...")
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Export database
            db_file = f"database_export_{timestamp}.db"
            self.db.create_backup(backup_name=db_file, is_automatic=False)
            
            # Export monitoring
            if self.monitoring_system:
                monitoring_file = f"monitoring_export_{timestamp}.json"
                self.monitoring_system.export_metrics(monitoring_file)
            
            # Export cache stats
            if self.cache_manager:
                cache_file = f"cache_stats_{timestamp}.json"
                self.cache_manager.export_stats(cache_file)
            
            # Export alerts
            if self.alert_manager:
                alerts_file = f"alerts_export_{timestamp}.json"
                from alert_manager import AdvancedAlertManager
                if isinstance(self.alert_manager, AdvancedAlertManager):
                    self.alert_manager.export_alerts(alerts_file)
            
            await query.answer("✅ فایل‌ها آماده شد!", show_alert=True)
            
            # ارسال پیام موفقیت
            await query.message.reply_text(
                "✅ تمام داده‌ها با موفقیت Export شد!\n\n"
                "فایل‌ها در پوشه پروژه ذخیره شده‌اند."
            )
            
        except Exception as e:
            logger.error(f"❌ Error exporting data: {e}")
            await query.answer("❌ خطا در export!", show_alert=True)
    
    # ==================== Helper Methods ====================
    
    def _time_ago(self, dt: datetime) -> str:
        """محاسبه زمان گذشته"""
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "چند لحظه پیش"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} دقیقه پیش"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} ساعت پیش"
        else:
            days = int(seconds / 86400)
            return f"{days} روز پیش"
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """مدیریت callback queryها"""
        query = update.callback_query
        data = query.data
        
        # Routing callbacks
        handlers = {
            # Main
            'admin_panel': self.show_admin_panel,
            'admin_refresh': self.show_admin_panel,
            
            # Monitoring
            'admin_monitoring': self.show_monitoring_dashboard,
            'monitoring_metrics': self.show_metrics_detail,
            'monitoring_performance': self.show_performance_detail,
            'monitoring_health': self.show_health_check,
            'monitoring_cache': self.show_cache_stats,
            'monitoring_trends': self.show_monitoring_trends,
            'monitoring_export': self.export_monitoring_data,
            
            # Users
            'admin_users': self.show_users_panel,
            'users_stats': self.show_user_stats,
            'users_top': self.show_top_users,
            'users_recent': self.show_recent_users,
            
            # Orders
            'admin_orders': self.show_orders_panel,
            'orders_pending': self.show_pending_orders,
            'orders_stats': self.show_order_stats,
            
            # Products
            'admin_products': self.show_products_panel,
            'product_list': self.show_product_list,
            
            # Reports
            'admin_reports': self.show_reports_panel,
            'report_daily': self.generate_daily_report,
            'report_financial': self.generate_financial_report,
            
            # Alerts
            'admin_alerts': self.show_alerts_panel,
            'alerts_active': self.show_active_alerts,
            
            # Backup
            'admin_backup': self.show_backup_panel,
            'backup_create': self.create_backup,
            'backup_list': self.list_backups,
            
            # Settings
            'admin_settings': self.show_settings_panel,
            'settings_cache': self.show_cache_settings,
            'settings_maintenance': self.show_maintenance_panel,
            
            # Maintenance
            'maintenance_vacuum': self.perform_vacuum,
            'maintenance_full': self.perform_full_maintenance,
            
            # Cache
            'cache_clear': self.clear_cache,
            
            # Export
            'settings_export': self.export_all_data,
        }
        
        handler = handlers.get(data)
        if handler:
            await handler(update, context)
        else:
            await query.answer("⚠️ این قسمت هنوز آماده نیست!", show_alert=True)


# ==================== Conversation Handlers ====================

def create_admin_conversation_handler(dashboard_handler: AdminDashboardHandler) -> ConversationHandler:
    """ساخت Conversation Handler برای ادمین"""
    
    # این قسمت برای افزودن محصول و... است که در صورت نیاز تکمیل می‌شود
    # فعلاً placeholder است
    
    return ConversationHandler(
        entry_points=[],
        states={},
        fallbacks=[]
    )


# ==================== Setup Function ====================

def setup_admin_handlers(application, db, cache_manager=None, 
                        monitoring_system=None, health_checker=None,
                        alert_manager=None, rate_limiter=None):
    """راه‌اندازی handler های ادمین"""
    
    # ساخت Dashboard Handler
    dashboard = AdminDashboardHandler(
        db=db,
        cache_manager=cache_manager,
        monitoring_system=monitoring_system,
        health_checker=health_checker,
        alert_manager=alert_manager,
        rate_limiter=rate_limiter
    )
    
    # دستور اصلی پنل ادمین
    application.add_handler(
        CommandHandler('admin', dashboard.show_admin_panel)
    )
    
    # Callback Query Handler برای تمام دکمه‌های ادمین
    application.add_handler(
        CallbackQueryHandler(
            dashboard.handle_callback_query,
            pattern=r'^(admin_|monitoring_|users_|orders_|product_|report_|'
                   r'alerts_|backup_|settings_|maintenance_|cache_)'
        )
    )
    
    logger.info("✅ Admin handlers registered")
    
    return dashboard


# ==================== Statistics Dashboard ====================

class StatisticsDashboard:
    """داشبورد آماری پیشرفته"""
    
    def __init__(self, db):
        self.db = db
    
    def get_comprehensive_stats(self) -> Dict:
        """آمار جامع"""
        cursor = self.db.cursor
        
        stats = {
            'users': {},
            'orders': {},
            'revenue': {},
            'products': {},
            'performance': {}
        }
        
        try:
            # کاربران
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['users']['total'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(created_at) >= DATE('now', '-30 days')
            """)
            stats['users']['last_30_days'] = cursor.fetchone()[0]
            
            # سفارشات
            cursor.execute("SELECT COUNT(*) FROM orders")
            stats['orders']['total'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
            """)
            stats['orders']['successful'] = cursor.fetchone()[0]
            
            # درآمد
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
            """)
            stats['revenue']['total'] = float(cursor.fetchone()[0])
            
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND created_at >= DATE('now', 'start of month')
            """)
            stats['revenue']['this_month'] = float(cursor.fetchone()[0])
            
            # محصولات
            cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
            stats['products']['active'] = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT p.name, COUNT(o.id) as order_count
                FROM products p
                LEFT JOIN orders o ON p.id = o.product_id
                WHERE o.status IN ('confirmed', 'payment_confirmed')
                GROUP BY p.id
                ORDER BY order_count DESC
                LIMIT 5
            """)
            stats['products']['top_selling'] = [
                {'name': row[0], 'orders': row[1]} 
                for row in cursor.fetchall()
            ]
            
        except Exception as e:
            logger.error(f"❌ Error getting comprehensive stats: {e}")
        
        return stats
    
    def generate_chart_data(self, metric: str, days: int = 30) -> Dict:
        """تولید داده برای نمودار"""
        cursor = self.db.cursor
        
        if metric == 'orders':
            cursor.execute(f"""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM orders
                WHERE created_at >= DATE('now', '-{days} days')
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        elif metric == 'revenue':
            cursor.execute(f"""
                SELECT DATE(created_at) as day, 
                       COALESCE(SUM(final_price), 0) as total
                FROM orders
                WHERE status IN ('confirmed', 'payment_confirmed')
                    AND created_at >= DATE('now', '-{days} days')
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        elif metric == 'users':
            cursor.execute(f"""
                SELECT DATE(created_at) as day, COUNT(*) as count
                FROM users
                WHERE created_at >= DATE('now', '-{days} days')
                GROUP BY DATE(created_at)
                ORDER BY day
            """)
        else:
            return {'labels': [], 'data': []}
        
        results = cursor.fetchall()
        
        return {
            'labels': [row[0] for row in results],
            'data': [row[1] for row in results]
        }


# ==================== Quick Actions ====================

async def quick_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                         db, message_text: str):
    """ارسال سریع پیام به همه"""
    cursor = db.cursor
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    
    success_count = 0
    fail_count = 0
    
    await update.message.reply_text(
        f"📤 شروع ارسال به {len(users)} کاربر..."
    )
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=message_text,
                parse_mode=ParseMode.MARKDOWN
            )
            success_count += 1
            await asyncio.sleep(0.05)  # جلوگیری از rate limit
        except Exception as e:
            fail_count += 1
            logger.error(f"Failed to send to {user[0]}: {e}")
    
    await update.message.reply_text(
        f"✅ ارسال کامل شد!\n\n"
        f"✅ موفق: {success_count}\n"
        f"❌ ناموفق: {fail_count}"
    )


async def quick_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """آمار سریع"""
    stats_dashboard = StatisticsDashboard(db)
    stats = stats_dashboard.get_comprehensive_stats()
    
    message = "📊 **آمار سریع**\n"
    message += "═" * 30 + "\n\n"
    
    message += f"👥 کاربران: {stats['users']['total']}\n"
    message += f"📦 سفارشات: {stats['orders']['total']}\n"
    message += f"✅ موفق: {stats['orders']['successful']}\n"
    message += f"💰 درآمد کل: {stats['revenue']['total']:,.0f} ت\n"
    message += f"💵 درآمد ماه: {stats['revenue']['this_month']:,.0f} ت\n"
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


# ==================== Admin Commands ====================

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای دستورات ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    message = """
👨‍💼 **راهنمای دستورات ادمین**

**📊 مانیتورینگ:**
/admin - پنل اصلی مدیریت
/monitoring - داشبورد مانیتورینگ
/health - بررسی سلامت سیستم
/stats - آمار سریع

**👥 کاربران:**
/users - مدیریت کاربران
/broadcast - ارسال پیام همگانی

**📦 سفارشات:**
/orders - مدیریت سفارشات
/pending - سفارشات در انتظار

**💾 سیستم:**
/backup - ساخت بکاپ
/maintenance - نگهداری سیستم
/export - خروجی داده‌ها

**🚨 هشدارها:**
/alerts - مدیریت هشدارها

**📈 گزارشات:**
/report - گزارشات و تحلیل
"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


# ==================== Logging & Monitoring Integration ====================

def log_admin_action(user_id: int, action: str, details: Optional[str] = None):
    """ثبت لاگ عملیات ادمین"""
    logger.info(
        f"👨‍💼 Admin action: {action}",
        extra={
            'user_id': user_id,
            'action': action,
            'details': details,
            'handler_name': 'admin_dashboard'
        }
    )


async def admin_activity_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware برای ثبت فعالیت ادمین"""
    if update.effective_user and update.effective_user.id == ADMIN_ID:
        action = "unknown"
        
        if update.message:
            action = f"command: {update.message.text}"
        elif update.callback_query:
            action = f"callback: {update.callback_query.data}"
        
        log_admin_action(update.effective_user.id, action)


# ==================== Error Handlers for Admin ====================

async def admin_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت خطاهای پنل ادمین"""
    logger.error(f"❌ Admin panel error: {context.error}")
    
    try:
        if update.effective_user and update.effective_user.id == ADMIN_ID:
            error_message = (
                "❌ خطایی رخ داد!\n\n"
                f"نوع خطا: {type(context.error).__name__}\n"
                f"پیام: {str(context.error)[:200]}"
            )
            
            if update.message:
                await update.message.reply_text(error_message)
            elif update.callback_query:
                await update.callback_query.message.reply_text(error_message)
    except:
        pass


logger.info("✅ Admin Dashboard module loaded (Complete)")