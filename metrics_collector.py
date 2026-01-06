"""
📊 سیستم جمع‌آوری پیشرفته Metrics
✅ Real-time Data Collection
✅ Time-series Storage
✅ Aggregation & Statistics
✅ Custom Metrics
✅ Export to Different Formats

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from threading import Lock
import json
import csv

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class MetricPoint:
    """یک نقطه داده متریک"""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'value': self.value,
            'tags': self.tags
        }


@dataclass
class TimeSeriesMetric:
    """متریک سری زمانی"""
    name: str
    description: str
    unit: str
    metric_type: str  # gauge, counter, histogram
    points: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_point(self, value: float, tags: Optional[Dict[str, str]] = None):
        """اضافه کردن نقطه جدید"""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            tags=tags or {}
        )
        self.points.append(point)
    
    def get_latest(self) -> Optional[float]:
        """آخرین مقدار"""
        return self.points[-1].value if self.points else None
    
    def get_average(self, last_n: Optional[int] = None) -> float:
        """میانگین"""
        points = list(self.points)[-last_n:] if last_n else list(self.points)
        if not points:
            return 0.0
        return sum(p.value for p in points) / len(points)
    
    def get_min(self, last_n: Optional[int] = None) -> float:
        """کمترین مقدار"""
        points = list(self.points)[-last_n:] if last_n else list(self.points)
        if not points:
            return 0.0
        return min(p.value for p in points)
    
    def get_max(self, last_n: Optional[int] = None) -> float:
        """بیشترین مقدار"""
        points = list(self.points)[-last_n:] if last_n else list(self.points)
        if not points:
            return 0.0
        return max(p.value for p in points)
    
    def get_percentile(self, percentile: float, last_n: Optional[int] = None) -> float:
        """محاسبه صدک"""
        points = list(self.points)[-last_n:] if last_n else list(self.points)
        if not points:
            return 0.0
        
        values = sorted([p.value for p in points])
        index = int(len(values) * (percentile / 100))
        return values[min(index, len(values) - 1)]
    
    def get_rate(self, time_window: int = 60) -> float:
        """محاسبه نرخ تغییر (در ثانیه)"""
        if len(self.points) < 2:
            return 0.0
        
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        recent_points = [p for p in self.points if p.timestamp >= cutoff_time]
        
        if len(recent_points) < 2:
            return 0.0
        
        time_diff = recent_points[-1].timestamp - recent_points[0].timestamp
        if time_diff == 0:
            return 0.0
        
        value_diff = recent_points[-1].value - recent_points[0].value
        return value_diff / time_diff
    
    def to_dict(self):
        """تبدیل به دیکشنری"""
        return {
            'name': self.name,
            'description': self.description,
            'unit': self.unit,
            'type': self.metric_type,
            'latest': self.get_latest(),
            'average': round(self.get_average(), 2),
            'min': round(self.get_min(), 2),
            'max': round(self.get_max(), 2),
            'p50': round(self.get_percentile(50), 2),
            'p95': round(self.get_percentile(95), 2),
            'p99': round(self.get_percentile(99), 2),
            'points_count': len(self.points)
        }


# ==================== Metrics Collector ====================

class MetricsCollector:
    """جمع‌آوری‌کننده اصلی متریک‌ها"""
    
    def __init__(self):
        self.metrics: Dict[str, TimeSeriesMetric] = {}
        self._lock = Lock()
        
        # Counters (برای شمارش رویدادها)
        self.counters: Dict[str, float] = defaultdict(float)
        
        # Custom metrics storage
        self.custom_metrics: Dict[str, Any] = {}
        
        logger.info("✅ Metrics Collector initialized")
    
    def register_metric(self, name: str, description: str, unit: str, 
                       metric_type: str = "gauge", max_points: int = 1000):
        """ثبت یک متریک جدید"""
        with self._lock:
            if name not in self.metrics:
                self.metrics[name] = TimeSeriesMetric(
                    name=name,
                    description=description,
                    unit=unit,
                    metric_type=metric_type,
                    points=deque(maxlen=max_points)
                )
                logger.info(f"✅ Metric registered: {name}")
    
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """ثبت یک gauge metric (مقدار لحظه‌ای)"""
        with self._lock:
            if name not in self.metrics:
                logger.warning(f"⚠️ Metric not registered: {name}")
                return
            
            self.metrics[name].add_point(value, tags)
    
    def increment_counter(self, name: str, amount: float = 1.0):
        """افزایش یک counter"""
        with self._lock:
            self.counters[name] += amount
    
    def get_counter(self, name: str) -> float:
        """دریافت مقدار counter"""
        return self.counters.get(name, 0.0)
    
    def reset_counter(self, name: str):
        """ریست کردن counter"""
        with self._lock:
            self.counters[name] = 0.0
    
    def get_metric(self, name: str) -> Optional[TimeSeriesMetric]:
        """دریافت یک متریک"""
        return self.metrics.get(name)
    
    def get_metric_summary(self, name: str) -> Dict:
        """خلاصه یک متریک"""
        metric = self.get_metric(name)
        if not metric:
            return {}
        return metric.to_dict()
    
    def get_all_metrics_summary(self) -> Dict[str, Dict]:
        """خلاصه تمام متریک‌ها"""
        with self._lock:
            return {
                name: metric.to_dict() 
                for name, metric in self.metrics.items()
            }
    
    def set_custom_metric(self, key: str, value: Any):
        """تنظیم یک متریک سفارشی"""
        with self._lock:
            self.custom_metrics[key] = value
    
    def get_custom_metric(self, key: str) -> Optional[Any]:
        """دریافت متریک سفارشی"""
        return self.custom_metrics.get(key)
    
    def export_to_json(self, filepath: str = "metrics.json") -> bool:
        """خروجی به فرمت JSON"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'metrics': self.get_all_metrics_summary(),
                'counters': dict(self.counters),
                'custom_metrics': self.custom_metrics
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Metrics exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting metrics: {e}")
            return False
    
    def export_to_csv(self, metric_name: str, filepath: str) -> bool:
        """خروجی یک متریک به CSV"""
        try:
            metric = self.get_metric(metric_name)
            if not metric:
                logger.error(f"❌ Metric not found: {metric_name}")
                return False
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'DateTime', 'Value', 'Tags'])
                
                for point in metric.points:
                    writer.writerow([
                        point.timestamp,
                        datetime.fromtimestamp(point.timestamp).isoformat(),
                        point.value,
                        json.dumps(point.tags)
                    ])
            
            logger.info(f"✅ Metric {metric_name} exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting metric to CSV: {e}")
            return False


# ==================== Bot-Specific Metrics Collector ====================

class BotMetricsCollector(MetricsCollector):
    """جمع‌آوری متریک‌های مخصوص ربات"""
    
    def __init__(self, db, cache_manager=None):
        super().__init__()
        self.db = db
        self.cache_manager = cache_manager
        
        # ثبت متریک‌های استاندارد
        self._register_standard_metrics()
        
        logger.info("✅ Bot Metrics Collector initialized")
    
    def _register_standard_metrics(self):
        """ثبت متریک‌های استاندارد"""
        # کاربران
        self.register_metric("users.total", "کل کاربران", "count", "gauge")
        self.register_metric("users.active_1h", "کاربران فعال 1 ساعت", "count", "gauge")
        self.register_metric("users.active_24h", "کاربران فعال 24 ساعت", "count", "gauge")
        self.register_metric("users.new_today", "کاربران جدید امروز", "count", "gauge")
        
        # سفارشات
        self.register_metric("orders.total", "کل سفارشات", "count", "gauge")
        self.register_metric("orders.today", "سفارشات امروز", "count", "gauge")
        self.register_metric("orders.pending", "سفارشات در انتظار", "count", "gauge")
        self.register_metric("orders.success_rate", "نرخ موفقیت سفارشات", "percent", "gauge")
        
        # درآمد
        self.register_metric("revenue.total", "کل درآمد", "toman", "gauge")
        self.register_metric("revenue.today", "درآمد امروز", "toman", "gauge")
        self.register_metric("revenue.average_order", "میانگین ارزش سفارش", "toman", "gauge")
        
        # عملکرد
        self.register_metric("performance.response_time", "زمان پاسخگویی", "ms", "gauge")
        self.register_metric("performance.requests_per_minute", "درخواست در دقیقه", "count", "gauge")
        self.register_metric("performance.error_rate", "نرخ خطا", "percent", "gauge")
        
        # کش
        self.register_metric("cache.hit_rate", "نرخ موفقیت کش", "percent", "gauge")
        self.register_metric("cache.size", "تعداد آیتم‌های کش", "count", "gauge")
        
        # سیستم
        self.register_metric("system.cpu", "استفاده CPU", "percent", "gauge")
        self.register_metric("system.memory", "استفاده RAM", "MB", "gauge")
        self.register_metric("system.memory_percent", "استفاده RAM", "percent", "gauge")
    
    def collect_user_metrics(self):
        """جمع‌آوری متریک‌های کاربران"""
        try:
            cursor = self.db.cursor
            
            # کل کاربران
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]
            self.record_gauge("users.total", float(total))
            
            # کاربران جدید امروز
            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(created_at) = DATE('now')
            """)
            new_today = cursor.fetchone()[0]
            self.record_gauge("users.new_today", float(new_today))
            
            logger.debug(f"📊 User metrics collected: total={total}, new={new_today}")
            
        except Exception as e:
            logger.error(f"❌ Error collecting user metrics: {e}")
    
    def collect_order_metrics(self):
        """جمع‌آوری متریک‌های سفارشات"""
        try:
            cursor = self.db.cursor
            
            # کل سفارشات
            cursor.execute("SELECT COUNT(*) FROM orders")
            total = cursor.fetchone()[0]
            self.record_gauge("orders.total", float(total))
            
            # سفارشات امروز
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE DATE(created_at) = DATE('now')
            """)
            today = cursor.fetchone()[0]
            self.record_gauge("orders.today", float(today))
            
            # سفارشات در انتظار
            cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'pending'
            """)
            pending = cursor.fetchone()[0]
            self.record_gauge("orders.pending", float(pending))
            
            # نرخ موفقیت
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN status IN ('confirmed', 'payment_confirmed') THEN 1 END) * 100.0 / COUNT(*)
                FROM orders
                WHERE created_at >= DATE('now', '-7 days')
            """)
            result = cursor.fetchone()[0]
            success_rate = result if result else 0
            self.record_gauge("orders.success_rate", float(success_rate))
            
            logger.debug(f"📊 Order metrics collected: total={total}, today={today}, pending={pending}")
            
        except Exception as e:
            logger.error(f"❌ Error collecting order metrics: {e}")
    
    def collect_revenue_metrics(self):
        """جمع‌آوری متریک‌های درآمد"""
        try:
            cursor = self.db.cursor
            
            # کل درآمد
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
            """)
            total = cursor.fetchone()[0]
            self.record_gauge("revenue.total", float(total))
            
            # درآمد امروز
            cursor.execute("""
                SELECT COALESCE(SUM(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND DATE(created_at) = DATE('now')
            """)
            today = cursor.fetchone()[0]
            self.record_gauge("revenue.today", float(today))
            
            # میانگین ارزش سفارش
            cursor.execute("""
                SELECT COALESCE(AVG(final_price), 0) FROM orders 
                WHERE status IN ('confirmed', 'payment_confirmed')
                AND created_at >= DATE('now', '-30 days')
            """)
            avg_order = cursor.fetchone()[0]
            self.record_gauge("revenue.average_order", float(avg_order))
            
            logger.debug(f"📊 Revenue metrics collected: total={total:,.0f}, today={today:,.0f}")
            
        except Exception as e:
            logger.error(f"❌ Error collecting revenue metrics: {e}")
    
    def collect_cache_metrics(self):
        """جمع‌آوری متریک‌های کش"""
        if not self.cache_manager:
            return
        
        try:
            stats = self.cache_manager.get_stats()
            
            hit_rate = stats.get('hit_rate', 0)
            cache_size = stats.get('cache_size', 0)
            
            self.record_gauge("cache.hit_rate", float(hit_rate))
            self.record_gauge("cache.size", float(cache_size))
            
            logger.debug(f"📊 Cache metrics collected: hit_rate={hit_rate}%, size={cache_size}")
            
        except Exception as e:
            logger.error(f"❌ Error collecting cache metrics: {e}")
    
    def collect_all(self):
        """جمع‌آوری تمام متریک‌ها"""
        self.collect_user_metrics()
        self.collect_order_metrics()
        self.collect_revenue_metrics()
        self.collect_cache_metrics()
        
        logger.info("✅ All bot metrics collected")


# ==================== Metrics Aggregator ====================

class MetricsAggregator:
    """ادغام و تجمیع متریک‌ها"""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    def aggregate_by_time(self, metric_name: str, interval: str = "1h") -> List[Dict]:
        """تجمیع بر اساس بازه زمانی
        
        Args:
            metric_name: نام متریک
            interval: بازه زمانی (5m, 15m, 1h, 6h, 1d)
        """
        metric = self.collector.get_metric(metric_name)
        if not metric:
            return []
        
        # تبدیل interval به ثانیه
        interval_seconds = {
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "6h": 21600,
            "1d": 86400
        }.get(interval, 3600)
        
        # گروه‌بندی نقاط
        buckets = defaultdict(list)
        
        for point in metric.points:
            bucket_time = int(point.timestamp // interval_seconds) * interval_seconds
            buckets[bucket_time].append(point.value)
        
        # محاسبه آمار هر bucket
        result = []
        for bucket_time in sorted(buckets.keys()):
            values = buckets[bucket_time]
            result.append({
                'timestamp': bucket_time,
                'datetime': datetime.fromtimestamp(bucket_time).isoformat(),
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'sum': sum(values)
            })
        
        return result
    
    def get_metric_trend(self, metric_name: str, lookback_minutes: int = 60) -> str:
        """تشخیص روند متریک (increasing, decreasing, stable)"""
        metric = self.collector.get_metric(metric_name)
        if not metric or len(metric.points) < 2:
            return "unknown"
        
        cutoff_time = time.time() - (lookback_minutes * 60)
        recent_points = [p for p in metric.points if p.timestamp >= cutoff_time]
        
        if len(recent_points) < 2:
            return "stable"
        
        # محاسبه شیب خط رگرسیون ساده
        n = len(recent_points)
        x = list(range(n))
        y = [p.value for p in recent_points]
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # تعیین روند بر اساس شیب
        threshold = 0.01 * y_mean  # 1% از میانگین
        
        if slope > threshold:
            return "increasing"
        elif slope < -threshold:
            return "decreasing"
        else:
            return "stable"
    
    def compare_metrics(self, metric1: str, metric2: str) -> Dict:
        """مقایسه دو متریک"""
        m1 = self.collector.get_metric_summary(metric1)
        m2 = self.collector.get_metric_summary(metric2)
        
        if not m1 or not m2:
            return {}
        
        return {
            'metric1': metric1,
            'metric2': metric2,
            'correlation': self._calculate_correlation(metric1, metric2),
            'metric1_avg': m1.get('average', 0),
            'metric2_avg': m2.get('average', 0),
            'metric1_trend': self.get_metric_trend(metric1),
            'metric2_trend': self.get_metric_trend(metric2)
        }
    
    def _calculate_correlation(self, metric1: str, metric2: str) -> float:
        """محاسبه همبستگی بین دو متریک"""
        m1 = self.collector.get_metric(metric1)
        m2 = self.collector.get_metric(metric2)
        
        if not m1 or not m2:
            return 0.0
        
        # استفاده از آخرین 100 نقطه
        points1 = list(m1.points)[-100:]
        points2 = list(m2.points)[-100:]
        
        if len(points1) != len(points2):
            return 0.0
        
        n = len(points1)
        if n < 2:
            return 0.0
        
        x = [p.value for p in points1]
        y = [p.value for p in points2]
        
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        x_variance = sum((x[i] - x_mean) ** 2 for i in range(n))
        y_variance = sum((y[i] - y_mean) ** 2 for i in range(n))
        
        denominator = (x_variance * y_variance) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator


# ==================== Helper Functions ====================

def create_bot_metrics_collector(db, cache_manager=None) -> BotMetricsCollector:
    """ساخت یک BotMetricsCollector"""
    return BotMetricsCollector(db, cache_manager)


def export_metrics_report(collector: MetricsCollector, filepath: str = "metrics_report.txt") -> bool:
    """خروجی گزارش متریک‌ها به صورت متنی"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("📊 گزارش Metrics\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            metrics_summary = collector.get_all_metrics_summary()
            
            for name, data in metrics_summary.items():
                f.write(f"📈 {name}\n")
                f.write(f"   توضیحات: {data.get('description', 'N/A')}\n")
                f.write(f"   واحد: {data.get('unit', 'N/A')}\n")
                f.write(f"   آخرین مقدار: {data.get('latest', 0)}\n")
                f.write(f"   میانگین: {data.get('average', 0)}\n")
                f.write(f"   Min: {data.get('min', 0)}\n")
                f.write(f"   Max: {data.get('max', 0)}\n")
                f.write(f"   P95: {data.get('p95', 0)}\n")
                f.write("\n")
            
            f.write("=" * 60 + "\n")
        
        logger.info(f"✅ Metrics report exported to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error exporting metrics report: {e}")
        return False


logger.info("✅ Metrics Collector module loaded")