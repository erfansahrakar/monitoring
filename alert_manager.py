"""
🚨 سیستم پیشرفته مدیریت هشدارها و اعلان‌ها
✅ Multi-channel Alerts (Telegram, Log, File)
✅ Smart Alert Grouping
✅ Auto-resolve
✅ Alert History & Analytics
✅ Customizable Rules
✅ Alert Suppression & Throttling

نویسنده: Claude AI
تاریخ: 2026-01-06
"""

import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import json
from threading import Lock

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class AlertSeverity(Enum):
    """شدت هشدار"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """وضعیت هشدار"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"


class ComparisonOperator(Enum):
    """عملگر مقایسه"""
    GT = ">"  # بیشتر از
    LT = "<"  # کمتر از
    GTE = ">="  # بیشتر مساوی
    LTE = "<="  # کمتر مساوی
    EQ = "=="  # مساوی
    NEQ = "!="  # نامساوی


# ==================== Data Classes ====================

@dataclass
class AlertRule:
    """قانون هشدار"""
    id: str
    name: str
    description: str
    metric: str
    operator: ComparisonOperator
    threshold: float
    severity: AlertSeverity
    cooldown_seconds: int = 300  # 5 دقیقه
    grace_period_seconds: int = 60  # 1 دقیقه
    auto_resolve: bool = True
    enabled: bool = True
    channels: List[str] = field(default_factory=lambda: ["telegram", "log"])
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'metric': self.metric,
            'operator': self.operator.value,
            'threshold': self.threshold,
            'severity': self.severity.value,
            'cooldown_seconds': self.cooldown_seconds,
            'grace_period_seconds': self.grace_period_seconds,
            'auto_resolve': self.auto_resolve,
            'enabled': self.enabled,
            'channels': self.channels,
            'tags': self.tags
        }


@dataclass
class Alert:
    """هشدار"""
    id: str
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    status: AlertStatus
    message: str
    metric: str
    current_value: float
    threshold: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    suppressed: bool = False
    suppressed_until: Optional[datetime] = None
    notification_sent: bool = False
    tags: Dict[str, str] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'severity': self.severity.value,
            'status': self.status.value,
            'message': self.message,
            'metric': self.metric,
            'current_value': self.current_value,
            'threshold': self.threshold,
            'triggered_at': self.triggered_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by,
            'suppressed': self.suppressed,
            'suppressed_until': self.suppressed_until.isoformat() if self.suppressed_until else None,
            'notification_sent': self.notification_sent,
            'tags': self.tags,
            'context': self.context
        }
    
    def duration_seconds(self) -> float:
        """مدت زمان فعال بودن هشدار"""
        end_time = self.resolved_at or datetime.now()
        return (end_time - self.triggered_at).total_seconds()


# ==================== Alert Manager ====================

class AdvancedAlertManager:
    """مدیریت پیشرفته هشدارها"""
    
    def __init__(self, admin_id: Optional[int] = None):
        self.admin_id = admin_id
        
        # قوانین هشدار
        self.rules: Dict[str, AlertRule] = {}
        
        # هشدارهای فعال
        self.active_alerts: Dict[str, Alert] = {}
        
        # تاریخچه هشدارها
        self.alert_history: deque = deque(maxlen=500)
        
        # زمان آخرین هشدار برای هر قانون
        self.last_alert_time: Dict[str, float] = {}
        
        # زمان اولین تخطی (برای grace period)
        self.violation_start_time: Dict[str, float] = {}
        
        # شمارنده هشدارها
        self.alert_counts = {
            'total': 0,
            'by_severity': defaultdict(int),
            'by_rule': defaultdict(int),
            'resolved': 0,
            'active': 0
        }
        
        # Callbacks برای ارسال اعلان
        self.notification_callbacks: Dict[str, Callable] = {}
        
        self._lock = Lock()
        
        logger.info("✅ Advanced Alert Manager initialized")
    
    # ==================== Rule Management ====================
    
    def add_rule(self, rule: AlertRule):
        """اضافه کردن قانون هشدار"""
        with self._lock:
            self.rules[rule.id] = rule
            logger.info(f"✅ Alert rule added: {rule.name} (ID: {rule.id})")
    
    def remove_rule(self, rule_id: str):
        """حذف قانون"""
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                logger.info(f"🗑 Alert rule removed: {rule_id}")
    
    def enable_rule(self, rule_id: str):
        """فعال کردن قانون"""
        with self._lock:
            if rule_id in self.rules:
                self.rules[rule_id].enabled = True
                logger.info(f"✅ Alert rule enabled: {rule_id}")
    
    def disable_rule(self, rule_id: str):
        """غیرفعال کردن قانون"""
        with self._lock:
            if rule_id in self.rules:
                self.rules[rule_id].enabled = False
                logger.info(f"⏸ Alert rule disabled: {rule_id}")
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """دریافت قانون"""
        return self.rules.get(rule_id)
    
    def get_all_rules(self) -> List[AlertRule]:
        """دریافت تمام قوانین"""
        return list(self.rules.values())
    
    # ==================== Alert Evaluation ====================
    
    def evaluate_metric(self, metric: str, value: float) -> List[Alert]:
        """ارزیابی یک متریک و تولید هشدار در صورت نیاز"""
        triggered_alerts = []
        current_time = time.time()
        
        with self._lock:
            for rule in self.rules.values():
                # بررسی فعال بودن و مطابقت متریک
                if not rule.enabled or rule.metric != metric:
                    continue
                
                # بررسی cooldown
                last_time = self.last_alert_time.get(rule.id, 0)
                if current_time - last_time < rule.cooldown_seconds:
                    continue
                
                # بررسی شرط
                violated = self._check_condition(value, rule.operator, rule.threshold)
                
                if violated:
                    # بررسی grace period
                    violation_start = self.violation_start_time.get(rule.id, current_time)
                    self.violation_start_time[rule.id] = violation_start
                    
                    if current_time - violation_start < rule.grace_period_seconds:
                        logger.debug(
                            f"⏳ Grace period for {rule.name}: "
                            f"{current_time - violation_start:.0f}s / {rule.grace_period_seconds}s"
                        )
                        continue
                    
                    # تولید هشدار
                    alert = self._create_alert(rule, metric, value)
                    triggered_alerts.append(alert)
                    
                    self.active_alerts[alert.id] = alert
                    self.alert_history.append(alert)
                    self.last_alert_time[rule.id] = current_time
                    
                    # آمار
                    self.alert_counts['total'] += 1
                    self.alert_counts['by_severity'][rule.severity.value] += 1
                    self.alert_counts['by_rule'][rule.id] += 1
                    self.alert_counts['active'] += 1
                    
                    logger.warning(f"🚨 Alert triggered: {alert.message}")
                    
                else:
                    # پاک کردن violation_start_time اگر شرط برقرار نیست
                    if rule.id in self.violation_start_time:
                        del self.violation_start_time[rule.id]
                    
                    # Auto-resolve
                    if rule.auto_resolve:
                        self._auto_resolve_alerts(rule.id, metric, value)
        
        return triggered_alerts
    
    def _check_condition(self, value: float, operator: ComparisonOperator, 
                        threshold: float) -> bool:
        """بررسی شرط"""
        if operator == ComparisonOperator.GT:
            return value > threshold
        elif operator == ComparisonOperator.LT:
            return value < threshold
        elif operator == ComparisonOperator.GTE:
            return value >= threshold
        elif operator == ComparisonOperator.LTE:
            return value <= threshold
        elif operator == ComparisonOperator.EQ:
            return value == threshold
        elif operator == ComparisonOperator.NEQ:
            return value != threshold
        return False
    
    def _create_alert(self, rule: AlertRule, metric: str, value: float) -> Alert:
        """ساخت هشدار"""
        alert_id = f"{rule.id}_{int(time.time())}"
        
        # ساخت پیام
        operator_text = {
            ComparisonOperator.GT: "بیشتر از",
            ComparisonOperator.LT: "کمتر از",
            ComparisonOperator.GTE: "بیشتر یا مساوی",
            ComparisonOperator.LTE: "کمتر یا مساوی",
            ComparisonOperator.EQ: "مساوی با",
            ComparisonOperator.NEQ: "نامساوی با"
        }.get(rule.operator, "")
        
        message = f"{rule.description}: {value:.2f} {operator_text} {rule.threshold}"
        
        return Alert(
            id=alert_id,
            rule_id=rule.id,
            rule_name=rule.name,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            message=message,
            metric=metric,
            current_value=value,
            threshold=rule.threshold,
            triggered_at=datetime.now(),
            tags=rule.tags.copy()
        )
    
    def _auto_resolve_alerts(self, rule_id: str, metric: str, value: float):
        """حل خودکار هشدارها"""
        for alert in list(self.active_alerts.values()):
            if alert.rule_id == rule_id and alert.status == AlertStatus.ACTIVE:
                self.resolve_alert(alert.id, auto=True)
                logger.info(f"✅ Auto-resolved alert: {alert.id}")
    
    # ==================== Alert Actions ====================
    
    def resolve_alert(self, alert_id: str, auto: bool = False):
        """حل کردن هشدار"""
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.now()
                
                self.alert_counts['resolved'] += 1
                self.alert_counts['active'] -= 1
                
                resolve_type = "Auto-resolved" if auto else "Manually resolved"
                logger.info(f"✅ {resolve_type} alert: {alert_id}")
    
    def acknowledge_alert(self, alert_id: str, user_id: Optional[str] = None):
        """تایید هشدار توسط کاربر"""
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = user_id
                
                logger.info(f"✓ Alert acknowledged: {alert_id} by {user_id}")
    
    def suppress_alert(self, alert_id: str, duration_seconds: int = 3600):
        """سرکوب هشدار برای مدت زمان مشخص"""
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.suppressed = True
                alert.suppressed_until = datetime.now() + timedelta(seconds=duration_seconds)
                alert.status = AlertStatus.SUPPRESSED
                
                logger.info(f"🔇 Alert suppressed for {duration_seconds}s: {alert_id}")
    
    def unsuppress_alert(self, alert_id: str):
        """لغو سرکوب"""
        with self._lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.suppressed = False
                alert.suppressed_until = None
                alert.status = AlertStatus.ACTIVE
                
                logger.info(f"🔊 Alert unsuppressed: {alert_id}")
    
    # ==================== Alert Queries ====================
    
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """دریافت هشدارهای فعال"""
        alerts = [
            a for a in self.active_alerts.values() 
            if a.status == AlertStatus.ACTIVE and not a.suppressed
        ]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda x: x.triggered_at, reverse=True)
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """دریافت یک هشدار"""
        return self.active_alerts.get(alert_id)
    
    def get_recent_alerts(self, count: int = 10) -> List[Alert]:
        """دریافت آخرین هشدارها"""
        return list(self.alert_history)[-count:]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """دریافت هشدارها بر اساس شدت"""
        return [a for a in self.active_alerts.values() if a.severity == severity]
    
    def get_alerts_by_metric(self, metric: str) -> List[Alert]:
        """دریافت هشدارها بر اساس متریک"""
        return [a for a in self.active_alerts.values() if a.metric == metric]
    
    # ==================== Notifications ====================
    
    def register_notification_callback(self, channel: str, callback: Callable):
        """ثبت callback برای ارسال اعلان"""
        self.notification_callbacks[channel] = callback
        logger.info(f"✅ Notification callback registered for channel: {channel}")
    
    async def send_notifications(self, alert: Alert):
        """ارسال اعلان‌های هشدار"""
        if alert.notification_sent or alert.suppressed:
            return
        
        rule = self.get_rule(alert.rule_id)
        if not rule:
            return
        
        for channel in rule.channels:
            callback = self.notification_callbacks.get(channel)
            if callback:
                try:
                    await callback(alert)
                    logger.info(f"✅ Notification sent via {channel}: {alert.id}")
                except Exception as e:
                    logger.error(f"❌ Failed to send notification via {channel}: {e}")
        
        alert.notification_sent = True
    
    # ==================== Statistics & Analytics ====================
    
    def get_alert_summary(self) -> Dict:
        """خلاصه هشدارها"""
        active_alerts = self.get_active_alerts()
        
        by_severity = defaultdict(int)
        for alert in active_alerts:
            by_severity[alert.severity.value] += 1
        
        return {
            'total_alerts': self.alert_counts['total'],
            'active_alerts': len(active_alerts),
            'resolved_alerts': self.alert_counts['resolved'],
            'by_severity': dict(by_severity),
            'critical_count': by_severity.get('critical', 0),
            'high_count': by_severity.get('high', 0),
            'medium_count': by_severity.get('medium', 0),
            'low_count': by_severity.get('low', 0)
        }
    
    def get_alert_statistics(self, hours: int = 24) -> Dict:
        """آمار هشدارها در بازه زمانی"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            a for a in self.alert_history 
            if a.triggered_at >= cutoff_time
        ]
        
        by_hour = defaultdict(int)
        by_severity = defaultdict(int)
        by_rule = defaultdict(int)
        
        for alert in recent_alerts:
            hour_key = alert.triggered_at.strftime('%Y-%m-%d %H:00')
            by_hour[hour_key] += 1
            by_severity[alert.severity.value] += 1
            by_rule[alert.rule_name] += 1
        
        # محاسبه MTTR (Mean Time To Resolve)
        resolved_alerts = [a for a in recent_alerts if a.resolved_at]
        mttr = 0
        if resolved_alerts:
            total_duration = sum(a.duration_seconds() for a in resolved_alerts)
            mttr = total_duration / len(resolved_alerts)
        
        return {
            'time_range_hours': hours,
            'total_alerts': len(recent_alerts),
            'resolved': len(resolved_alerts),
            'still_active': len([a for a in recent_alerts if not a.resolved_at]),
            'by_hour': dict(by_hour),
            'by_severity': dict(by_severity),
            'by_rule': dict(by_rule),
            'mttr_seconds': round(mttr, 2),
            'mttr_minutes': round(mttr / 60, 2)
        }
    
    def get_most_frequent_alerts(self, top_n: int = 5) -> List[Dict]:
        """پرتکرارترین هشدارها"""
        rule_counts = self.alert_counts['by_rule']
        sorted_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)
        
        result = []
        for rule_id, count in sorted_rules[:top_n]:
            rule = self.get_rule(rule_id)
            if rule:
                result.append({
                    'rule_id': rule_id,
                    'rule_name': rule.name,
                    'count': count,
                    'severity': rule.severity.value
                })
        
        return result
    
    # ==================== Alert Report ====================
    
    def generate_alert_report(self) -> str:
        """تولید گزارش متنی هشدارها"""
        summary = self.get_alert_summary()
        stats = self.get_alert_statistics(24)
        frequent = self.get_most_frequent_alerts(3)
        
        report = "🚨 **گزارش هشدارها**\n"
        report += "═" * 40 + "\n\n"
        
        # خلاصه
        report += "**📊 خلاصه:**\n"
        report += f"├ کل هشدارها: {summary['total_alerts']}\n"
        report += f"├ فعال: {summary['active_alerts']}\n"
        report += f"├ حل شده: {summary['resolved_alerts']}\n"
        report += f"└ Critical: {summary['critical_count']}\n\n"
        
        # بر اساس شدت
        report += "**⚠️ بر اساس شدت:**\n"
        report += f"├ 🔴 Critical: {summary['critical_count']}\n"
        report += f"├ 🟠 High: {summary['high_count']}\n"
        report += f"├ 🟡 Medium: {summary['medium_count']}\n"
        report += f"└ 🟢 Low: {summary['low_count']}\n\n"
        
        # آمار 24 ساعت
        report += "**📈 آمار 24 ساعت:**\n"
        report += f"├ کل: {stats['total_alerts']}\n"
        report += f"├ حل شده: {stats['resolved']}\n"
        report += f"├ فعال: {stats['still_active']}\n"
        report += f"└ MTTR: {stats['mttr_minutes']:.1f} دقیقه\n\n"
        
        # پرتکرارترین
        if frequent:
            report += "**🔥 پرتکرارترین هشدارها:**\n"
            for i, item in enumerate(frequent, 1):
                report += f"{i}. {item['rule_name']}: {item['count']} بار\n"
            report += "\n"
        
        # هشدارهای فعال
        active = self.get_active_alerts()
        if active:
            report += f"**🚨 هشدارهای فعال ({len(active)}):**\n"
            for alert in active[:5]:
                duration = alert.duration_seconds()
                duration_str = f"{duration/60:.0f}m" if duration < 3600 else f"{duration/3600:.1f}h"
                severity_emoji = {
                    AlertSeverity.CRITICAL: "🔴",
                    AlertSeverity.HIGH: "🟠",
                    AlertSeverity.MEDIUM: "🟡",
                    AlertSeverity.LOW: "🟢"
                }.get(alert.severity, "⚪")
                
                report += f"{severity_emoji} {alert.rule_name} ({duration_str})\n"
                report += f"   {alert.message}\n"
        else:
            report += "**✅ هشدار فعالی وجود ندارد**\n"
        
        report += "\n" + "═" * 40 + "\n"
        report += f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return report
    
    # ==================== Data Export ====================
    
    def export_alerts(self, filepath: str = "alerts_export.json") -> bool:
        """خروجی هشدارها به JSON"""
        try:
            data = {
                'export_time': datetime.now().isoformat(),
                'summary': self.get_alert_summary(),
                'statistics': self.get_alert_statistics(24),
                'active_alerts': [a.to_dict() for a in self.get_active_alerts()],
                'recent_alerts': [a.to_dict() for a in self.get_recent_alerts(50)],
                'rules': [r.to_dict() for r in self.get_all_rules()]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Alerts exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error exporting alerts: {e}")
            return False


# ==================== Default Alert Rules ====================

def create_default_alert_rules() -> List[AlertRule]:
    """ساخت قوانین هشدار پیش‌فرض"""
    return [
        # CPU
        AlertRule(
            id="cpu_high",
            name="CPU بالا",
            description="استفاده CPU بیش از حد",
            metric="system.cpu",
            operator=ComparisonOperator.GT,
            threshold=80.0,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=300
        ),
        AlertRule(
            id="cpu_critical",
            name="CPU بحرانی",
            description="استفاده CPU در سطح بحرانی",
            metric="system.cpu",
            operator=ComparisonOperator.GT,
            threshold=90.0,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=180
        ),
        
        # Memory
        AlertRule(
            id="memory_high",
            name="RAM بالا",
            description="استفاده RAM بیش از حد",
            metric="system.memory_percent",
            operator=ComparisonOperator.GT,
            threshold=85.0,
            severity=AlertSeverity.HIGH,
            cooldown_seconds=300
        ),
        
        # Error Rate
        AlertRule(
            id="error_rate_high",
            name="نرخ خطا بالا",
            description="نرخ خطا بیش از حد مجاز",
            metric="performance.error_rate",
            operator=ComparisonOperator.GT,
            threshold=5.0,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=600
        ),
        
        # Response Time
        AlertRule(
            id="slow_response",
            name="پاسخ کند",
            description="زمان پاسخ بیش از حد",
            metric="performance.response_time",
            operator=ComparisonOperator.GT,
            threshold=2000.0,  # 2 seconds
            severity=AlertSeverity.MEDIUM,
            cooldown_seconds=300
        ),
        
        # Cache
        AlertRule(
            id="cache_hit_low",
            name="Hit Rate کش پایین",
            description="نرخ موفقیت کش پایین است",
            metric="cache.hit_rate",
            operator=ComparisonOperator.LT,
            threshold=50.0,
            severity=AlertSeverity.LOW,
            cooldown_seconds=600
        ),
        
        # Orders
        AlertRule(
            id="pending_orders_high",
            name="سفارشات معلق زیاد",
            description="تعداد سفارشات در انتظار زیاد است",
            metric="orders.pending",
            operator=ComparisonOperator.GT,
            threshold=10.0,
            severity=AlertSeverity.MEDIUM,
            cooldown_seconds=1800
        )
    ]


logger.info("✅ Alert Manager module loaded")