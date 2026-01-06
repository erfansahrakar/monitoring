"""
🏥 سیستم Health Check پیشرفته
✅ وضعیت دیتابیس
✅ مصرف RAM و CPU
✅ آمار کاربران و سفارشات
✅ آخرین خطاها
✅ Dependency Checks
✅ Health Score Calculation
✅ تشخیص خودکار مشکلات

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import psutil
import os
import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class HealthStatus(Enum):
    """وضعیت سلامت"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentStatus(Enum):
    """وضعیت جزء"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


# ==================== Data Classes ====================

@dataclass
class ComponentHealth:
    """سلامت یک جزء"""
    name: str
    status: ComponentStatus
    message: str
    details: Dict = None
    checked_at: datetime = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.checked_at is None:
            self.checked_at = datetime.now()
    
    def to_dict(self):
        return {
            'name': self.name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'checked_at': self.checked_at.isoformat()
        }


@dataclass
class SystemHealth:
    """سلامت کلی سیستم"""
    overall_status: HealthStatus
    health_score: float  # 0-100
    timestamp: datetime
    uptime_seconds: float
    components: List[ComponentHealth]
    issues: List[str]
    recommendations: List[str]
    
    def to_dict(self):
        return {
            'overall_status': self.overall_status.value,
            'health_score': self.health_score,
            'timestamp': self.timestamp.isoformat(),
            'uptime_seconds': self.uptime_seconds,
            'uptime_formatted': self._format_uptime(),
            'components': [c.to_dict() for c in self.components],
            'issues': self.issues,
            'recommendations': self.recommendations
        }
    
    def _format_uptime(self) -> str:
        """فرمت uptime"""
        seconds = self.uptime_seconds
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"


# ==================== Enhanced Health Checker ====================

class EnhancedHealthChecker:
    """Health Checker پیشرفته"""
    
    def __init__(self, db, start_time: float, cache_manager=None, 
                 monitoring_system=None):
        self.db = db
        self.start_time = start_time
        self.cache_manager = cache_manager
        self.monitoring_system = monitoring_system
        
        # تاریخچه خطاها
        self.last_errors: deque = deque(maxlen=100)
        
        # تاریخچه Health Checks
        self.health_history: deque = deque(maxlen=288)  # 24 ساعت با فاصله 5 دقیقه
        
        # آمار
        self.check_count = 0
        self.last_check_time = None
        self.consecutive_failures = 0
        
        logger.info("✅ Enhanced Health Checker initialized")
    
    def add_error(self, error_type: str, error_message: str, 
                  user_id: Optional[int] = None):
        """اضافه کردن خطا به لیست"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': error_message,
            'user_id': user_id
        }
        
        self.last_errors.append(error_entry)
        logger.debug(f"🔴 Error recorded: {error_type}")
    
    # ==================== Component Checks ====================
    
    def check_database(self) -> ComponentHealth:
        """بررسی وضعیت دیتابیس"""
        try:
            # تست اتصال
            cursor = self.db.cursor
            cursor.execute("SELECT 1")
            
            # اندازه دیتابیس
            from config import DATABASE_NAME
            db_size = os.path.getsize(DATABASE_NAME) / (1024 * 1024)  # MB
            
            # تعداد جداول
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            )
            table_count = cursor.fetchone()[0]
            
            # تست نوشتن
            cursor.execute("PRAGMA quick_check")
            integrity_check = cursor.fetchone()[0]
            
            # بررسی سلامت
            status = ComponentStatus.OK
            message = "دیتابیس سالم است"
            
            if db_size > 500:  # بیشتر از 500MB
                status = ComponentStatus.WARNING
                message = "حجم دیتابیس زیاد است"
            
            if integrity_check != "ok":
                status = ComponentStatus.ERROR
                message = "مشکل در یکپارچگی دیتابیس"
            
            return ComponentHealth(
                name="database",
                status=status,
                message=message,
                details={
                    'size_mb': round(db_size, 2),
                    'tables': table_count,
                    'integrity': integrity_check,
                    'connected': True
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status=ComponentStatus.ERROR,
                message=f"خطا در اتصال: {str(e)}",
                details={'connected': False, 'error': str(e)}
            )
    
    def check_memory(self) -> ComponentHealth:
        """بررسی مصرف حافظه"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            # مصرف RAM پروسس
            ram_used_mb = memory_info.rss / (1024 * 1024)
            ram_percent = process.memory_percent()
            
            # مصرف کل سیستم
            system_memory = psutil.virtual_memory()
            
            # تشخیص وضعیت
            if ram_percent > 10 or ram_used_mb > 500:
                status = ComponentStatus.ERROR
                message = "مصرف حافظه بحرانی"
            elif ram_percent > 7 or ram_used_mb > 300:
                status = ComponentStatus.WARNING
                message = "مصرف حافظه بالا"
            else:
                status = ComponentStatus.OK
                message = "مصرف حافظه نرمال"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                details={
                    'process_mb': round(ram_used_mb, 2),
                    'process_percent': round(ram_percent, 2),
                    'system_total_mb': round(system_memory.total / (1024 * 1024), 2),
                    'system_available_mb': round(system_memory.available / (1024 * 1024), 2),
                    'system_percent': system_memory.percent
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Memory health check failed: {e}")
            return ComponentHealth(
                name="memory",
                status=ComponentStatus.UNKNOWN,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_cpu(self) -> ComponentHealth:
        """بررسی مصرف CPU"""
        try:
            process = psutil.Process(os.getpid())
            
            # CPU درصد (با اندازه‌گیری 100ms)
            cpu_percent = process.cpu_percent(interval=0.1)
            
            # تعداد threadها
            num_threads = process.num_threads()
            
            # CPU کل سیستم
            system_cpu = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # تشخیص وضعیت
            if cpu_percent > 80:
                status = ComponentStatus.ERROR
                message = "مصرف CPU بحرانی"
            elif cpu_percent > 50:
                status = ComponentStatus.WARNING
                message = "مصرف CPU بالا"
            else:
                status = ComponentStatus.OK
                message = "مصرف CPU نرمال"
            
            return ComponentHealth(
                name="cpu",
                status=status,
                message=message,
                details={
                    'process_percent': round(cpu_percent, 2),
                    'threads': num_threads,
                    'system_percent': system_cpu,
                    'cpu_count': cpu_count
                }
            )
            
        except Exception as e:
            logger.error(f"❌ CPU health check failed: {e}")
            return ComponentHealth(
                name="cpu",
                status=ComponentStatus.UNKNOWN,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_disk(self) -> ComponentHealth:
        """بررسی فضای دیسک"""
        try:
            disk = psutil.disk_usage('/')
            
            disk_percent = disk.percent
            disk_free_gb = disk.free / (1024 ** 3)
            
            # تشخیص وضعیت
            if disk_percent > 95 or disk_free_gb < 1:
                status = ComponentStatus.ERROR
                message = "فضای دیسک بحرانی"
            elif disk_percent > 85 or disk_free_gb < 5:
                status = ComponentStatus.WARNING
                message = "فضای دیسک کم است"
            else:
                status = ComponentStatus.OK
                message = "فضای دیسک کافی"
            
            return ComponentHealth(
                name="disk",
                status=status,
                message=message,
                details={
                    'total_gb': round(disk.total / (1024 ** 3), 2),
                    'used_gb': round(disk.used / (1024 ** 3), 2),
                    'free_gb': round(disk_free_gb, 2),
                    'percent': disk_percent
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Disk health check failed: {e}")
            return ComponentHealth(
                name="disk",
                status=ComponentStatus.UNKNOWN,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_cache(self) -> ComponentHealth:
        """بررسی وضعیت کش"""
        if not self.cache_manager:
            return ComponentHealth(
                name="cache",
                status=ComponentStatus.UNKNOWN,
                message="Cache Manager فعال نیست",
                details={'enabled': False}
            )
        
        try:
            stats = self.cache_manager.get_stats()
            
            hit_rate = stats.get('hit_rate', 0)
            cache_size = stats.get('cache_size', 0)
            
            # تشخیص وضعیت
            if hit_rate < 30:
                status = ComponentStatus.WARNING
                message = "نرخ موفقیت کش پایین"
            elif cache_size > 5000:
                status = ComponentStatus.WARNING
                message = "تعداد آیتم‌های کش زیاد"
            else:
                status = ComponentStatus.OK
                message = "کش سالم است"
            
            return ComponentHealth(
                name="cache",
                status=status,
                message=message,
                details={
                    'hit_rate': hit_rate,
                    'cache_size': cache_size,
                    'hits': stats.get('hits', 0),
                    'misses': stats.get('misses', 0),
                    'enabled': True
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Cache health check failed: {e}")
            return ComponentHealth(
                name="cache",
                status=ComponentStatus.ERROR,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_users(self) -> ComponentHealth:
        """بررسی آمار کاربران"""
        try:
            cursor = self.db.cursor
            
            # کل کاربران
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # کاربران امروز
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_users = cursor.fetchone()[0]
            
            # کاربران این هفته
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE created_at >= DATE('now', '-7 days')
            """)
            week_users = cursor.fetchone()[0]
            
            status = ComponentStatus.OK
            message = "آمار کاربران نرمال"
            
            return ComponentHealth(
                name="users",
                status=status,
                message=message,
                details={
                    'total': total_users,
                    'today': today_users,
                    'this_week': week_users
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Users health check failed: {e}")
            return ComponentHealth(
                name="users",
                status=ComponentStatus.ERROR,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_orders(self) -> ComponentHealth:
        """بررسی آمار سفارشات"""
        try:
            cursor = self.db.cursor
            
            # کل سفارشات
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            # سفارشات امروز
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_orders = cursor.fetchone()[0]
            
            # سفارشات pending
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending'
            """)
            pending_orders = cursor.fetchone()[0]
            
            # سفارشات موفق امروز
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            successful_today = cursor.fetchone()[0]
            
            # تشخیص وضعیت
            if pending_orders > 20:
                status = ComponentStatus.WARNING
                message = "تعداد سفارشات در انتظار زیاد است"
            else:
                status = ComponentStatus.OK
                message = "سفارشات نرمال"
            
            return ComponentHealth(
                name="orders",
                status=status,
                message=message,
                details={
                    'total': total_orders,
                    'today': today_orders,
                    'pending': pending_orders,
                    'successful_today': successful_today
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Orders health check failed: {e}")
            return ComponentHealth(
                name="orders",
                status=ComponentStatus.ERROR,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    def check_errors(self) -> ComponentHealth:
        """بررسی خطاها"""
        try:
            recent_errors = list(self.last_errors)[-20:]
            
            # خطاهای یک ساعت اخیر
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            recent_critical = [
                e for e in recent_errors 
                if e['timestamp'] > one_hour_ago
            ]
            
            # تشخیص وضعیت
            if len(recent_critical) > 10:
                status = ComponentStatus.ERROR
                message = f"خطاهای زیاد در یک ساعه اخیر ({len(recent_critical)})"
            elif len(recent_critical) > 5:
                status = ComponentStatus.WARNING
                message = f"خطاهای متوسط ({len(recent_critical)})"
            else:
                status = ComponentStatus.OK
                message = "خطاها در حد نرمال"
            
            return ComponentHealth(
                name="errors",
                status=status,
                message=message,
                details={
                    'total_errors': len(self.last_errors),
                    'recent_errors': len(recent_critical),
                    'last_5': recent_errors[-5:] if recent_errors else []
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Errors health check failed: {e}")
            return ComponentHealth(
                name="errors",
                status=ComponentStatus.UNKNOWN,
                message=f"خطا: {str(e)}",
                details={'error': str(e)}
            )
    
    # ==================== Overall Health Check ====================
    
    def perform_health_check(self) -> SystemHealth:
        """انجام بررسی کامل سلامت"""
        self.check_count += 1
        self.last_check_time = datetime.now()
        
        # بررسی تمام اجزا
        components = [
            self.check_database(),
            self.check_memory(),
            self.check_cpu(),
            self.check_disk(),
            self.check_cache(),
            self.check_users(),
            self.check_orders(),
            self.check_errors()
        ]
        
        # محاسبه Health Score
        health_score = self._calculate_health_score(components)
        
        # تعیین وضعیت کلی
        overall_status = self._determine_overall_status(components, health_score)
        
        # شناسایی مشکلات
        issues = self._identify_issues(components)
        
        # توصیه‌ها
        recommendations = self._generate_recommendations(components, issues)
        
        # Uptime
        uptime = time.time() - self.start_time
        
        # ساخت SystemHealth
        system_health = SystemHealth(
            overall_status=overall_status,
            health_score=health_score,
            timestamp=datetime.now(),
            uptime_seconds=uptime,
            components=components,
            issues=issues,
            recommendations=recommendations
        )
        
        # ذخیره در تاریخچه
        self.health_history.append(system_health)
        
        # بررسی شکست‌های متوالی
        if overall_status in [HealthStatus.CRITICAL, HealthStatus.WARNING]:
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
        
        logger.info(
            f"🏥 Health Check #{self.check_count}: "
            f"{overall_status.value.upper()} (Score: {health_score:.1f})"
        )
        
        return system_health
    
    def _calculate_health_score(self, components: List[ComponentHealth]) -> float:
        """محاسبه امتیاز سلامت (0-100)"""
        if not components:
            return 0.0
        
        # وزن‌های اجزا
        weights = {
            'database': 25,
            'memory': 15,
            'cpu': 15,
            'disk': 10,
            'cache': 5,
            'users': 10,
            'orders': 15,
            'errors': 5
        }
        
        # امتیاز هر وضعیت
        status_scores = {
            ComponentStatus.OK: 100,
            ComponentStatus.WARNING: 60,
            ComponentStatus.ERROR: 20,
            ComponentStatus.UNKNOWN: 50
        }
        
        total_score = 0
        total_weight = 0
        
        for component in components:
            weight = weights.get(component.name, 10)
            score = status_scores.get(component.status, 50)
            
            total_score += score * weight
            total_weight += weight
        
        return round(total_score / total_weight, 1) if total_weight > 0 else 0.0
    
    def _determine_overall_status(self, components: List[ComponentHealth], 
                                  health_score: float) -> HealthStatus:
        """تعیین وضعیت کلی"""
        # بررسی خطاهای بحرانی
        error_count = sum(1 for c in components if c.status == ComponentStatus.ERROR)
        warning_count = sum(1 for c in components if c.status == ComponentStatus.WARNING)
        
        if error_count >= 2:
            return HealthStatus.CRITICAL
        elif error_count >= 1:
            return HealthStatus.WARNING
        elif warning_count >= 3:
            return HealthStatus.DEGRADED
        elif health_score >= 90:
            return HealthStatus.HEALTHY
        elif health_score >= 70:
            return HealthStatus.DEGRADED
        elif health_score >= 50:
            return HealthStatus.WARNING
        else:
            return HealthStatus.CRITICAL
    
    def _identify_issues(self, components: List[ComponentHealth]) -> List[str]:
        """شناسایی مشکلات"""
        issues = []
        
        for component in components:
            if component.status in [ComponentStatus.ERROR, ComponentStatus.WARNING]:
                issues.append(f"{component.name}: {component.message}")
        
        return issues
    
    def _generate_recommendations(self, components: List[ComponentHealth], 
                                  issues: List[str]) -> List[str]:
        """تولید توصیه‌ها"""
        recommendations = []
        
        for component in components:
            if component.status == ComponentStatus.ERROR:
                if component.name == "database":
                    recommendations.append("بررسی اتصال دیتابیس و یکپارچگی آن")
                elif component.name == "memory":
                    recommendations.append("بررسی memory leak و رفع آن")
                elif component.name == "cpu":
                    recommendations.append("بررسی عملیات سنگین و بهینه‌سازی کد")
                elif component.name == "disk":
                    recommendations.append("پاکسازی فایل‌های قدیمی و لاگ‌ها")
            
            elif component.status == ComponentStatus.WARNING:
                if component.name == "cache":
                    hit_rate = component.details.get('hit_rate', 0)
                    if hit_rate < 50:
                        recommendations.append("بهبود استراتژی کش")
                elif component.name == "orders":
                    pending = component.details.get('pending', 0)
                    if pending > 10:
                        recommendations.append("بررسی سفارشات در انتظار")
        
        if not recommendations:
            recommendations.append("همه چیز خوب است! ادامه دهید")
        
        return recommendations
    
    # ==================== Report Generation ====================
    
    def get_health_status(self) -> SystemHealth:
        """دریافت آخرین وضعیت سلامت"""
        if self.health_history:
            return self.health_history[-1]
        else:
            return self.perform_health_check()
    
    def get_health_report(self) -> str:
        """گزارش متنی وضعیت سلامت"""
        health = self.get_health_status()
        
        # ایموجی وضعیت
        status_emoji = {
            HealthStatus.HEALTHY: '✅',
            HealthStatus.DEGRADED: '🟡',
            HealthStatus.WARNING: '⚠️',
            HealthStatus.CRITICAL: '🔴',
            HealthStatus.UNKNOWN: '❓'
        }
        
        emoji = status_emoji.get(health.overall_status, '❓')
        
        report = f"{emoji} **وضعیت سیستم: {health.overall_status.value.upper()}**\n\n"
        report += f"🎯 امتیاز سلامت: {health.health_score}/100\n"
        report += f"⏱ Uptime: {health._format_uptime()}\n"
        report += f"📅 {health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # اجزا
        report += "**🔍 وضعیت اجزا:**\n"
        for component in health.components:
            comp_emoji = {
                ComponentStatus.OK: '✅',
                ComponentStatus.WARNING: '⚠️',
                ComponentStatus.ERROR: '❌',
                ComponentStatus.UNKNOWN: '❓'
            }.get(component.status, '❓')
            
            report += f"{comp_emoji} {component.name}: {component.message}\n"
        
        # مشکلات
        if health.issues:
            report += "\n**⚠️ مشکلات:**\n"
            for issue in health.issues:
                report += f"• {issue}\n"
        
        # توصیه‌ها
        if health.recommendations:
            report += "\n**💡 توصیه‌ها:**\n"
            for rec in health.recommendations[:3]:
                report += f"• {rec}\n"
        
        return report
    
    def get_health_trend(self, hours: int = 24) -> Dict:
        """روند سلامت"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_checks = [
            h for h in self.health_history 
            if h.timestamp >= cutoff_time
        ]
        
        if not recent_checks:
            return {'trend': 'unknown', 'checks': 0}
        
        avg_score = sum(h.health_score for h in recent_checks) / len(recent_checks)
        
        # تعیین روند
        if len(recent_checks) < 2:
            trend = 'stable'
        else:
            first_half = recent_checks[:len(recent_checks)//2]
            second_half = recent_checks[len(recent_checks)//2:]
            
            avg_first = sum(h.health_score for h in first_half) / len(first_half)
            avg_second = sum(h.health_score for h in second_half) / len(second_half)
            
            if avg_second > avg_first + 5:
                trend = 'improving'
            elif avg_second < avg_first - 5:
                trend = 'degrading'
            else:
                trend = 'stable'
        
        return {
            'trend': trend,
            'checks': len(recent_checks),
            'avg_score': round(avg_score, 1),
            'current_score': recent_checks[-1].health_score
        }


# ==================== Helper Functions ====================

def format_bytes(bytes_value: float) -> str:
    """فرمت کردن byte به واحد خوانا"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def format_uptime(seconds: float) -> str:
    """فرمت کردن uptime"""
    if seconds < 60:
        return f"{seconds:.0f} ثانیه"
    elif seconds < 3600:
        return f"{seconds / 60:.1f} دقیقه"
    elif seconds < 86400:
        return f"{seconds / 3600:.1f} ساعت"
    else:
        return f"{seconds / 86400:.1f} روز"


logger.info("✅ Enhanced Health Check module loaded")