"""
پاکسازی خودکار دیتابیس

"""
import logging
from datetime import datetime, time
from telegram.ext import ContextTypes
from config import ADMIN_ID

logger = logging.getLogger(__name__)


async def scheduled_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """
    🆕 پاکسازی زمان‌بندی شده (خودکار)
    
    این تابع هر روز ساعت 3:30 صبح اجرا میشه و:
    - سفارشات رد شده قدیمی‌تر از 7 روز رو حذف می‌کنه
    - سفارشات منقضی شده قدیمی‌تر از 7 روز رو حذف می‌کنه
    - سفارشات تکمیل شده رو نگه می‌داره
    - گزارش به ادمین ارسال می‌کنه
    """
    try:
        logger.info("🧹 شروع پاکسازی خودکار روزانه...")
        
        db = context.bot_data.get('db')
        if not db:
            logger.error("❌ دیتابیس در دسترس نیست!")
            return
        
        # پاکسازی سفارشات قدیمی (بیشتر از 7 روز)
        report = db.cleanup_old_orders(days_old=7)
        
        if report.get('success'):
            deleted_count = report.get('deleted_count', 0)
            
            if deleted_count > 0:
                # ارسال گزارش به ادمین
                now = datetime.now()
                jalali_date = now.strftime('%Y-%m-%d')
                
                message = (
                    "🤖 **گزارش پاکسازی خودکار**\n\n"
                    f"🗑 تعداد حذف شده: **{deleted_count}** سفارش\n"
                    f"📅 سفارشات قدیمی‌تر از: **{report['days_old']}** روز\n"
                    f"⏰ زمان: {jalali_date} - {now.strftime('%H:%M:%S')}\n\n"
                    f"✅ پاکسازی با موفقیت انجام شد.\n\n"
                    f"📊 **جزئیات:**\n"
                    f"• سفارشات رد شده قدیمی حذف شدند\n"
                    f"• سفارشات منقضی شده قدیمی حذف شدند\n"
                    f"• سفارشات تکمیل شده حفظ شدند"
                )
                
                await context.bot.send_message(
                    ADMIN_ID,
                    message,
                    parse_mode='Markdown'
                )
                
                logger.info(f"✅ پاکسازی خودکار موفق: {deleted_count} سفارش حذف شد")
            else:
                logger.info("ℹ️ هیچ سفارش قدیمی برای حذف وجود نداشت")
        else:
            error_msg = report.get('error', 'خطای نامشخص')
            logger.error(f"❌ خطا در پاکسازی خودکار: {error_msg}")
            
            # اطلاع خطا به ادمین
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ **خطا در پاکسازی خودکار**\n\n"
                f"❌ {error_msg}\n\n"
                f"💡 لطفاً به صورت دستی پاکسازی را انجام دهید."
            )
            
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره در پاکسازی خودکار: {e}", exc_info=True)
        
        # اطلاع به ادمین در صورت خطا
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"⚠️ **خطای غیرمنتظره در پاکسازی خودکار**\n\n"
                f"❌ {str(e)}\n\n"
                f"📞 لطفاً لاگ‌ها را بررسی کنید."
            )
        except:
            pass


async def manual_cleanup(update, context: ContextTypes.DEFAULT_TYPE):
    """
    🆕 پاکسازی دستی توسط ادمین
    
    این تابع وقتی ادمین روی دکمه "🧹 پاکسازی دیتابیس" کلیک می‌کنه اجرا میشه
    """
    user_id = update.effective_user.id
    
    # چک کردن دسترسی ادمین
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔️ شما دسترسی به این بخش ندارید!")
        return
    
    # نمایش پیام در حال پردازش
    processing_msg = await update.message.reply_text(
        "🧹 **در حال پاکسازی دیتابیس...**\n\n"
        "⏳ لطفاً صبر کنید...",
        parse_mode='Markdown'
    )
    
    try:
        db = context.bot_data.get('db')
        if not db:
            await processing_msg.edit_text("❌ خطا: دیتابیس در دسترس نیست!")
            return
        
        # پاکسازی سفارشات قدیمی (بیشتر از 7 روز)
        report = db.cleanup_old_orders(days_old=7)
        
        if report.get('success'):
            deleted_count = report.get('deleted_count', 0)
            days_old = report.get('days_old', 7)
            
            if deleted_count > 0:
                message = (
                    "✅ **پاکسازی موفقیت‌آمیز بود!**\n\n"
                    f"🗑 تعداد حذف شده: **{deleted_count}** سفارش\n"
                    f"📅 سفارشات قدیمی‌تر از: **{days_old}** روز\n\n"
                    f"📊 **جزئیات:**\n"
                    f"✓ سفارشات رد شده قدیمی حذف شدند\n"
                    f"✓ سفارشات منقضی شده قدیمی حذف شدند\n"
                    f"✓ سفارشات تکمیل شده حفظ شدند\n\n"
                    f"💡 دیتابیس شما اکنون تمیزتر است!"
                )
            else:
                message = (
                    "ℹ️ **هیچ سفارش قدیمی وجود ندارد**\n\n"
                    f"✅ دیتابیس شما از قبل تمیز است!\n\n"
                    f"📊 سفارشات قدیمی‌تر از {days_old} روز وجود ندارد."
                )
            
            await processing_msg.edit_text(message, parse_mode='Markdown')
            
            logger.info(f"✅ پاکسازی دستی توسط ادمین: {deleted_count} سفارش حذف شد")
        else:
            error_msg = report.get('error', 'خطای نامشخص')
            message = (
                "❌ **خطا در پاکسازی**\n\n"
                f"⚠️ {error_msg}\n\n"
                f"💡 لطفاً دوباره تلاش کنید یا لاگ‌ها را بررسی کنید."
            )
            
            await processing_msg.edit_text(message, parse_mode='Markdown')
            
            logger.error(f"❌ خطا در پاکسازی دستی: {error_msg}")
            
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره در پاکسازی دستی: {e}", exc_info=True)
        
        try:
            await processing_msg.edit_text(
                f"❌ **خطای غیرمنتظره**\n\n"
                f"⚠️ {str(e)}\n\n"
                f"📞 لطفاً با پشتیبانی تماس بگیرید.",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text(f"❌ خطا رخ داد: {str(e)}")


def setup_cleanup_job(application):
    """
    🆕 راه‌اندازی Job پاکسازی خودکار
    
    این تابع پاکسازی روزانه را تنظیم می‌کنه:
    - زمان: هر روز ساعت 3:30 صبح
    - عملیات: حذف سفارشات قدیمی‌تر از 7 روز
    """
    try:
        if hasattr(application, 'job_queue') and application.job_queue is not None:
            # تنظیم پاکسازی روزانه
            application.job_queue.run_daily(
                scheduled_cleanup,
                time=time(hour=3, minute=30),  # ساعت 3:30 صبح
                name="daily_cleanup"
            )
            
            logger.info("✅ پاکسازی خودکار روزانه راه‌اندازی شد (ساعت 3:30 صبح)")
            return True
        else:
            logger.warning("⚠️ JobQueue در دسترس نیست - پاکسازی خودکار غیرفعال است")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا در راه‌اندازی پاکسازی خودکار: {e}", exc_info=True)
        return False


# ==================== توابع کمکی ====================

def get_cleanup_stats(db):
    """
    دریافت آمار سفارشات قابل پاکسازی
    """
    try:
        from datetime import timedelta
        
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=7)
        
        # شمارش سفارشات رد شده قدیمی
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE status = 'rejected' 
            AND datetime(created_at) < datetime(?)
        """, (cutoff_date,))
        rejected_count = cursor.fetchone()[0]
        
        # شمارش سفارشات منقضی شده قدیمی
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE datetime(expires_at) < datetime('now')
            AND status NOT IN ('payment_confirmed', 'confirmed', 'rejected')
            AND datetime(created_at) < datetime(?)
        """, (cutoff_date,))
        expired_count = cursor.fetchone()[0]
        
        # شمارش سفارشات تکمیل شده
        cursor.execute("""
            SELECT COUNT(*) FROM orders 
            WHERE status IN ('payment_confirmed', 'confirmed')
        """)
        completed_count = cursor.fetchone()[0]
        
        return {
            'rejected_old': rejected_count,
            'expired_old': expired_count,
            'completed': completed_count,
            'total_cleanable': rejected_count + expired_count
        }
        
    except Exception as e:
        logger.error(f"❌ خطا در دریافت آمار پاکسازی: {e}")
        return None


async def send_cleanup_report(context: ContextTypes.DEFAULT_TYPE):
    """
    ارسال گزارش وضعیت پاکسازی به ادمین
    """
    try:
        db = context.bot_data.get('db')
        if not db:
            return
        
        stats = get_cleanup_stats(db)
        if not stats:
            return
        
        message = (
            "📊 **گزارش وضعیت دیتابیس**\n\n"
            f"🗑 سفارشات رد شده قدیمی: {stats['rejected_old']}\n"
            f"⏰ سفارشات منقضی شده قدیمی: {stats['expired_old']}\n"
            f"✅ سفارشات تکمیل شده: {stats['completed']}\n\n"
            f"💡 تعداد قابل پاکسازی: **{stats['total_cleanable']}** سفارش\n\n"
            f"🧹 برای پاکسازی از دکمه '🧹 پاکسازی دیتابیس' استفاده کنید."
        )
        
        await context.bot.send_message(
            ADMIN_ID,
            message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ خطا در ارسال گزارش: {e}")
