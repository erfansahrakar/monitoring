"""
سیستم بکاپ خودکار دیتابیس
"""
import os
import shutil
import logging
from datetime import datetime
from telegram.ext import ContextTypes
from config import DATABASE_NAME, BACKUP_FOLDER, BACKUP_HOUR, BACKUP_MINUTE, ADMIN_ID

logger = logging.getLogger(__name__)


def setup_backup_folder():
    """ایجاد پوشه بکاپ اگر وجود نداشته باشد"""
    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)
        logger.info(f"✅ پوشه بکاپ ایجاد شد: {BACKUP_FOLDER}")


async def create_backup(context: ContextTypes.DEFAULT_TYPE):
    """ایجاد بکاپ از دیتابیس"""
    try:
        setup_backup_folder()
        
        # نام فایل با تاریخ و ساعت
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_FOLDER, backup_filename)
        
        # کپی دیتابیس
        shutil.copy2(DATABASE_NAME, backup_path)
        
        # حذف بکاپ‌های قدیمی (نگه‌داری فقط 7 بکاپ آخر)
        cleanup_old_backups(keep_count=7)
        
        logger.info(f"✅ بکاپ با موفقیت ایجاد شد: {backup_filename}")
        
        # ارسال پیام به ادمین
        file_size = os.path.getsize(backup_path) / 1024  # KB
        await context.bot.send_message(
            ADMIN_ID,
            f"✅ **بکاپ خودکار انجام شد**\n\n"
            f"📅 تاریخ: {datetime.now().strftime('%Y/%m/%d - %H:%M')}\n"
            f"📦 فایل: `{backup_filename}`\n"
            f"💾 حجم: {file_size:.2f} KB",
            parse_mode='Markdown'
        )
        
        # ارسال فایل بکاپ به ادمین
        with open(backup_path, 'rb') as f:
            await context.bot.send_document(
                ADMIN_ID,
                document=f,
                filename=backup_filename,
                caption="📦 فایل بکاپ دیتابیس"
            )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد بکاپ: {e}")
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"❌ **خطا در بکاپ خودکار**\n\n"
                f"⚠️ خطا: `{str(e)}`",
                parse_mode='Markdown'
            )
        except:
            pass
        
        return False


def cleanup_old_backups(keep_count=7):
    """حذف بکاپ‌های قدیمی"""
    try:
        if not os.path.exists(BACKUP_FOLDER):
            return
        
        # لیست فایل‌های بکاپ
        backups = []
        for filename in os.listdir(BACKUP_FOLDER):
            if filename.startswith("backup_") and filename.endswith(".db"):
                filepath = os.path.join(BACKUP_FOLDER, filename)
                backups.append((filepath, os.path.getctime(filepath)))
        
        # مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # حذف بکاپ‌های اضافی
        for filepath, _ in backups[keep_count:]:
            os.remove(filepath)
            logger.info(f"🗑 بکاپ قدیمی حذف شد: {os.path.basename(filepath)}")
            
    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی بکاپ‌های قدیمی: {e}")


async def manual_backup(update, context):
    """بکاپ دستی توسط ادمین"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    await update.message.reply_text("⏳ در حال ایجاد بکاپ...")
    
    success = await create_backup(context)
    
    if success:
        await update.message.reply_text("✅ بکاپ با موفقیت ایجاد و ارسال شد!")
    else:
        await update.message.reply_text("❌ خطا در ایجاد بکاپ!")


def setup_backup_job(application):
    """راه‌اندازی job بکاپ روزانه"""
    from datetime import time
    
    # تنظیم job برای اجرای روزانه
    application.job_queue.run_daily(
        create_backup,
        time=time(hour=BACKUP_HOUR, minute=BACKUP_MINUTE),
        name="daily_backup"
    )
    
    logger.info(f"✅ بکاپ خودکار روزانه فعال شد (ساعت {BACKUP_HOUR}:{BACKUP_MINUTE:02d})")