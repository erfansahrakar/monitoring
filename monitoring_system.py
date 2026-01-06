"""
🔥 سیستم مانیتورینگ حرفه‌ای و پیشرفته
✅ Real-time Monitoring
✅ Performance Tracking
✅ Auto Health Checks
✅ Alert System
✅ Metrics Collection
✅ Live Dashboard

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import time
import asyncio
import logging
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import deque
from threading import Lock
import json

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class SystemMetrics:
    """متریک‌های سیستم"""
    timestamp: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_usage_percent: float
    active_threads: int
    process_age_seconds: float
    
    def to_dict(self):
        return asdict(self)


@dataclass
class BotMetrics:
    """متریک‌های ربات"""
    timestamp: str
    total_users: int
    active_users_1h: int
    active_users_24h: int
    total_orders: int
    orders_today: int
    pending_orders: int
    successful_orders_today: int
    total_revenue: float
    revenue_today: float
    avg_response_time_ms: float
    requests_per_minute: float
    error_rate_percent: float
    cache_hit_rate: float
    
    def to_dict(self):
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """متریک‌های عملکرد"""
    avg_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    slowest_endpoint: str
    fastest_endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    def to_dict(self):
        return asdict(self)


@dataclass
class AlertConfig:
    """تنظیمات هشدار"""
    name: str
    metric: str
    threshold: float
    comparison: str  # >, <, >=, <=, ==
    severity: str  # low, medium, high, critical
    cooldown_seconds: int = 300
    enabled: bool = True


@dataclass
class Alert:
    """هشدار"""
    id: str
    config_name: str
    severity: str
    message: str
    value: float
    threshold: float
    timestamp: str
    resolved: bool = False
    resolved_at: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


# ==================== Performance Tracker ====================

class PerformanceTracker:
    """ردیابی عملکرد"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self._response_times: deque = deque(maxlen=max_history)
        self._endpoint_times: Dict[str, deque] = {}
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._lock = Lock()
    
    def record_request(self, endpoint: str, duration_ms: float, success: bool = True):
        """ثبت یک درخواست"""
        with self._lock:
            self._response_times.append(duration_ms)
            self._request_count += 1
            
            if success:
                self._success_count += 1
            else:
                self._error_count += 1
            
            if endpoint not in self._endpoint_times:
                self._endpoint_times[endpoint] = deque(maxlen=100)
            
            self._endpoint_times[endpoint].append(duration_ms)
    
    def get_metrics(self) -> PerformanceMetrics:
        """دریافت متریک‌های عملکرد"""
        with self._lock:
            if not self._response_times:
                return PerformanceMetrics(
                    avg_response_time=0,
                    p50_response_time=0,
                    p95_response_time=0,
                    p99_response_time=0,
                    slowest_endpoint="N/A",
                    fastest_endpoint="N/A",
                    total_requests=0,
                    successful_requests=0,
                    failed_requests=0
                )
            
            sorted_times = sorted(self._response_times)
            n = len(sorted_times)
            
            avg = sum(sorted_times) / n
            p50 = sorted_times[int(n * 0.50)]
            p95 = sorted_times[int(n * 0.95)] if n > 20 else sorted_times[-1]
            p99 = sorted_times[int(n * 0.99)] if n > 100 else sorted_times[-1]
            
            # پیدا کردن کندترین و سریع‌ترین endpoint
            slowest = "N/A"
            fastest = "N/A"
            slowest_time = 0
            fastest_time = float('inf')
            
            for endpoint, times in self._endpoint_times.items():
                if times:
                    avg_time = sum(times) / len(times)
                    if avg_time > slowest_time:
                        slowest_time = avg_time
                        slowest = endpoint
                    if avg_time < fastest_time:
                        fastest_time = avg_time
                        fastest = endpoint
            
            return PerformanceMetrics(
                avg_response_time=round(avg, 2),
                p50_response_time=round(p50, 2),
                p95_response_time=round(p95, 2),
                p99_response_time=round(p99, 2),
                slowest_endpoint=slowest,
                fastest_endpoint=fastest,
                total_requests=self._request_count,
                successful_requests=self._success_count,
                failed_requests=self._error_count
            )
    
    def reset(self):
        """ریست کردن متریک‌ها"""
        with self._lock:
            self._response_times.clear()
            self._endpoint_times.clear()
            self._request_count = 0
            self._success_count = 0
            self._error_count = 0


# ==================== Alert Manager ====================

class AlertManager:
    """مدیریت هشدارها"""
    
    def __init__(self):
        self.configs: Dict[str, AlertConfig] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=100)
        self.last_alert_time: Dict[str, float] = {}
        self._lock = Lock()
    
    def add_config(self, config: AlertConfig):
        """اضافه کردن تنظیمات هشدار"""
        self.configs[config.name] = config
        logger.info(f"✅ Alert config added: {config.name}")
    
    def check_metric(self, metric_name: str, value: float) -> Optional[Alert]:
        """بررسی یک متریک"""
        with self._lock:
            for config in self.configs.values():
                if not config.enabled or config.metric != metric_name:
                    continue
                
                # بررسی cooldown
                last_time = self.last_alert_time.get(config.name, 0)
                if time.time() - last_time < config.cooldown_seconds:
                    continue
                
                # بررسی شرط
                triggered = False
                if config.comparison == '>':
                    triggered = value > config.threshold
                elif config.comparison == '<':
                    triggered = value < config.threshold
                elif config.comparison == '>=':
                    triggered = value >= config.threshold
                elif config.comparison == '<=':
                    triggered = value <= config.threshold
                elif config.comparison == '==':
                    triggered = value == config.threshold
                
                if triggered:
                    alert = Alert(
                        id=f"{config.name}_{int(time.time())}",
                        config_name=config.name,
                        severity=config.severity,
                        message=f"{config.metric} is {value:.2f} (threshold: {config.threshold})",
                        value=value,
                        threshold=config.threshold,
                        timestamp=datetime.now().isoformat()
                    )
                    
                    self.active_alerts[alert.id] = alert
                    self.alert_history.append(alert)
                    self.last_alert_time[config.name] = time.time()
                    
                    logger.warning(f"🚨 Alert triggered: {alert.message}")
                    return alert
        
        return None
    
    def resolve_alert(self, alert_id: str):
        """حل کردن یک هشدار"""
        with self._lock:
            if alert_id in self.active_alerts:
                self.active_alerts[alert_id].resolved = True
                self.active_alerts[alert_id].resolved_at = datetime.now().isoformat()
                logger.info(f"✅ Alert resolved: {alert_id}")
    
    def get_active_alerts(self) -> List[Alert]:
        """دریافت هشدارهای فعال"""
        return [a for a in self.active_alerts.values() if not a.resolved]
    
    def get_alert_summary(self) -> Dict:
        """خلاصه هشدارها"""
        active = self.get_active_alerts()
        
        by_severity = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for alert in active:
            by_severity[alert.severity] += 1
        
        return {
            'total_active': len(active),
            'by_severity': by_severity,
            'recent_alerts': [a.to_dict() for a in list(self.alert_history)[-5:]]
        }


# ==================== Monitoring System ====================

class MonitoringSystem:
    """سیستم اصلی مانیتورینگ"""
    
    def __init__(self, db, cache_manager=None, health_checker=None):
        self.db = db
        self.cache_manager = cache_manager
        self.health_checker = health_checker
        self.start_time = time.time()
        
        # Components
        self.performance_tracker = PerformanceTracker()
        self.alert_manager = AlertManager()
        
        # Metrics History
        self.system_metrics_history: deque = deque(maxlen=288)  # 24 ساعت با فاصله 5 دقیقه
        self.bot_metrics_history: deque = deque(maxlen=288)
        
        # Request Counter
        self._request_times: deque = deque(maxlen=1000)
        self._active_users_1h: set = set()
        self._active_users_24h: set = set()
        self._user_activity_lock = Lock()
        
        # تنظیم هشدارهای پیش‌فرض
        self._setup_default_alerts()
        
        logger.info("✅ Monitoring System initialized")
    
    def _setup_default_alerts(self):
        """تنظیم هشدارهای پیش‌فرض"""
        default_alerts = [
            AlertConfig(
                name="high_cpu",
                metric="cpu_percent",
                threshold=80.0,
                comparison=">",
                severity="high",
                cooldown_seconds=300
            ),
            AlertConfig(
                name="high_memory",
                metric="memory_percent",
                threshold=85.0,
                comparison=">",
                severity="high",
                cooldown_seconds=300
            ),
            AlertConfig(
                name="high_error_rate",
                metric="error_rate",
                threshold=5.0,
                comparison=">",
                severity="critical",
                cooldown_seconds=600
            ),
            AlertConfig(
                name="slow_response",
                metric="avg_response_time",
                threshold=2000.0,  # 2 second
                comparison=">",
                severity="medium",
                cooldown_seconds=300
            ),
            AlertConfig(
                name="low_cache_hit",
                metric="cache_hit_rate",
                threshold=50.0,
                comparison="<",
                severity="low",
                cooldown_seconds=600
            )
        ]
        
        for alert_config in default_alerts:
            self.alert_manager.add_config(alert_config)
    
    def record_user_activity(self, user_id: int):
        """ثبت فعالیت کاربر"""
        with self._user_activity_lock:
            self._active_users_1h.add(user_id)
            self._active_users_24h.add(user_id)
    
    def record_request(self, endpoint: str, duration_ms: float, success: bool = True):
        """ثبت یک درخواست"""
        self._request_times.append(time.time())
        self.performance_tracker.record_request(endpoint, duration_ms, success)
    
    def collect_system_metrics(self) -> SystemMetrics:
        """جمع‌آوری متریک‌های سیستم"""
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            metrics = SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=round(process.cpu_percent(interval=0.1), 2),
                memory_mb=round(memory_info.rss / (1024 * 1024), 2),
                memory_percent=round(process.memory_percent(), 2),
                disk_usage_percent=round(psutil.disk_usage('/').percent, 2),
                active_threads=process.num_threads(),
                process_age_seconds=round(time.time() - self.start_time, 2)
            )
            
            # بررسی هشدارها
            self.alert_manager.check_metric("cpu_percent", metrics.cpu_percent)
            self.alert_manager.check_metric("memory_percent", metrics.memory_percent)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error collecting system metrics: {e}")
            return None
    
    def collect_bot_metrics(self) -> BotMetrics:
        """جمع‌آوری متریک‌های ربات"""
        try:
            cursor = self.db.cursor
            
            # کاربران
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            with self._user_activity_lock:
                active_1h = len(self._active_users_1h)
                active_24h = len(self._active_users_24h)
            
            # سفارشات
            cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE DATE(created_at) = DATE('now')
            """)
            orders_today = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending'
            """)
            pending_orders = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            successful_today = cursor.fetchone()[0]
            
            # درآمد
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
            """)
            total_revenue = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            revenue_today = cursor.fetchone()[0]
            
            # Performance
            perf_metrics = self.performance_tracker.get_metrics()
            
            # Requests per minute
            current_time = time.time()
            recent_requests = sum(1 for t in self._request_times if current_time - t < 60)
            
            # Error rate
            error_rate = 0
            if perf_metrics.total_requests > 0:
                error_rate = (perf_metrics.failed_requests / perf_metrics.total_requests) * 100
            
            # Cache hit rate
            cache_hit_rate = 0
            if self.cache_manager:
                cache_stats = self.cache_manager.get_stats()
                cache_hit_rate = cache_stats.get('hit_rate', 0)
            
            metrics = BotMetrics(
                timestamp=datetime.now().isoformat(),
                total_users=total_users,
                active_users_1h=active_1h,
                active_users_24h=active_24h,
                total_orders=total_orders,
                orders_today=orders_today,
                pending_orders=pending_orders,
                successful_orders_today=successful_today,
                total_revenue=float(total_revenue),
                revenue_today=float(revenue_today),
                avg_response_time_ms=perf_metrics.avg_response_time,
                requests_per_minute=float(recent_requests),
                error_rate_percent=round(error_rate, 2),
                cache_hit_rate=cache_hit_rate
            )
            
            # بررسی هشدارها
            self.alert_manager.check_metric("error_rate", metrics.error_rate_percent)
            self.alert_manager.check_metric("avg_response_time", metrics.avg_response_time_ms)
            self.alert_manager.check_metric("cache_hit_rate", metrics.cache_hit_rate)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error collecting bot metrics: {e}")
            return None
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """جمع‌آوری تمام متریک‌ها"""
        system_metrics = self.collect_system_metrics()
        bot_metrics = self.collect_bot_metrics()
        perf_metrics = self.performance_tracker.get_metrics()
        
        # ذخیره در تاریخچه
        if system_metrics:
            self.system_metrics_history.append(system_metrics)
        if bot_metrics:
            self.bot_metrics_history.append(bot_metrics)
        
        return {
            'system': system_metrics.to_dict() if system_metrics else {},
            'bot': bot_metrics.to_dict() if bot_metrics else {},
            'performance': perf_metrics.to_dict(),
            'alerts': self.alert_manager.get_alert_summary(),
            'uptime_seconds': round(time.time() - self.start_time, 2)
        }
    
    def cleanup_old_data(self):
        """پاکسازی داده‌های قدیمی"""
        current_time = time.time()
        
        # پاکسازی فعالیت کاربران
        with self._user_activity_lock:
            self._active_users_1h.clear()
            # 24h رو نگه می‌داریم
        
        logger.info("🧹 Old monitoring data cleaned up")
    
    def get_dashboard_data(self) -> str:
        """داده‌های داشبورد به صورت متنی"""
        metrics = self.collect_all_metrics()
        
        system = metrics.get('system', {})
        bot = metrics.get('bot', {})
        perf = metrics.get('performance', {})
        alerts_summary = metrics.get('alerts', {})
        
        # محاسبه uptime
        uptime_seconds = metrics.get('uptime_seconds', 0)
        uptime_hours = uptime_seconds / 3600
        if uptime_hours < 1:
            uptime_str = f"{uptime_seconds / 60:.1f} دقیقه"
        elif uptime_hours < 24:
            uptime_str = f"{uptime_hours:.1f} ساعت"
        else:
            uptime_str = f"{uptime_hours / 24:.1f} روز"
        
        # ساخت متن
        text = "📊 **داشبورد مانیتورینگ**\n"
        text += "═" * 40 + "\n\n"
        
        # وضعیت کلی
        active_alerts = alerts_summary.get('total_active', 0)
        if active_alerts > 0:
            text += f"🚨 **هشدار:** {active_alerts} هشدار فعال!\n\n"
        else:
            text += "✅ **وضعیت:** سالم\n\n"
        
        # سیستم
        text += "**⚙️ سیستم:**\n"
        text += f"├ CPU: {system.get('cpu_percent', 0)}%\n"
        text += f"├ RAM: {system.get('memory_mb', 0)} MB ({system.get('memory_percent', 0)}%)\n"
        text += f"├ Disk: {system.get('disk_usage_percent', 0)}%\n"
        text += f"└ Uptime: {uptime_str}\n\n"
        
        # عملکرد
        text += "**⚡ عملکرد:**\n"
        text += f"├ Avg Response: {perf.get('avg_response_time', 0):.0f} ms\n"
        text += f"├ P95: {perf.get('p95_response_time', 0):.0f} ms\n"
        text += f"├ Requests: {perf.get('total_requests', 0)}\n"
        text += f"├ Success Rate: {100 - bot.get('error_rate_percent', 0):.1f}%\n"
        text += f"└ Cache Hit: {bot.get('cache_hit_rate', 0):.1f}%\n\n"
        
        # کاربران و سفارشات
        text += "**👥 کاربران:**\n"
        text += f"├ کل: {bot.get('total_users', 0)}\n"
        text += f"├ فعال (1h): {bot.get('active_users_1h', 0)}\n"
        text += f"└ فعال (24h): {bot.get('active_users_24h', 0)}\n\n"
        
        text += "**📦 سفارشات:**\n"
        text += f"├ کل: {bot.get('total_orders', 0)}\n"
        text += f"├ امروز: {bot.get('orders_today', 0)}\n"
        text += f"├ در انتظار: {bot.get('pending_orders', 0)}\n"
        text += f"└ موفق امروز: {bot.get('successful_orders_today', 0)}\n\n"
        
        text += "**💰 درآمد:**\n"
        text += f"├ کل: {bot.get('total_revenue', 0):,.0f} تومان\n"
        text += f"└ امروز: {bot.get('revenue_today', 0):,.0f} تومان\n\n"
        
        text += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return text
    
    def export_metrics(self, filepath: str = "metrics_export.json"):
        """خروجی متریک‌ها به فایل JSON"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'current_metrics': self.collect_all_metrics(),
                'system_history': [m.to_dict() for m in self.system_metrics_history],
                'bot_history': [m.to_dict() for m in self.bot_metrics_history],
                'active_alerts': [a.to_dict() for a in self.alert_manager.get_active_alerts()]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Metrics exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting metrics: {e}")
            return False


# ==================== Auto Monitoring Task ====================

class AutoMonitoringTask:
    """تسک خودکار مانیتورینگ"""
    
    def __init__(self, monitoring_system: MonitoringSystem, interval_seconds: int = 300):
        self.monitoring_system = monitoring_system
        self.interval_seconds = interval_seconds
        self.running = False
        self._task = None
    
    async def start(self):
        """شروع مانیتورینگ خودکار"""
        if self.running:
            logger.warning("⚠️ Auto monitoring already running")
            return
        
        self.running = True
        logger.info(f"✅ Auto monitoring started (interval: {self.interval_seconds}s)")
        
        while self.running:
            try:
                # جمع‌آوری متریک‌ها
                metrics = self.monitoring_system.collect_all_metrics()
                
                # لاگ کردن
                logger.info(
                    f"📊 Monitoring: "
                    f"CPU={metrics['system'].get('cpu_percent', 0)}% "
                    f"RAM={metrics['system'].get('memory_mb', 0)}MB "
                    f"Users(1h)={metrics['bot'].get('active_users_1h', 0)} "
                    f"Orders(today)={metrics['bot'].get('orders_today', 0)}"
                )
                
                # بررسی هشدارها
                active_alerts = self.monitoring_system.alert_manager.get_active_alerts()
                if active_alerts:
                    logger.warning(f"🚨 {len(active_alerts)} active alerts detected")
                
                # پاکسازی دوره‌ای
                if int(time.time()) % 3600 == 0:  # هر ساعت
                    self.monitoring_system.cleanup_old_data()
                
            except Exception as e:
                logger.error(f"❌ Error in auto monitoring: {e}")
            
            await asyncio.sleep(self.interval_seconds)
    
    def stop(self):
        """توقف مانیتورینگ خودکار"""
        self.running = False
        logger.info("🛑 Auto monitoring stopped")


# ==================== Monitoring Decorator ====================

def monitor_performance(endpoint_name: str):
    """Decorator برای مانیتور کردن عملکرد توابع"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # پیدا کردن monitoring_system از context
                if len(args) > 1 and hasattr(args[1], 'bot_data'):
                    context = args[1]
                    monitoring_system = context.bot_data.get('monitoring_system')
                    if monitoring_system:
                        monitoring_system.record_request(endpoint_name, duration_ms, success)
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"⏱ {endpoint_name}: {duration_ms:.2f}ms")
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ==================== Helper Functions ====================

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


def format_bytes(bytes_value: float) -> str:
    """فرمت کردن bytes"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


logger.info("✅ Monitoring System module loaded")