"""
⏱️ سیستم Rate Limiting پیشرفته
✅ Token Bucket Algorithm
✅ Sliding Window Counter
✅ Fixed Window Counter
✅ Per-User & Global Limits
✅ Multiple Rate Limiters
✅ Whitelist/Blacklist
✅ Rate Limit Statistics
✅ Auto-reset
✅ Integration با Monitoring

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Callable, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import json

from config import (
    GLOBAL_RATE_LIMIT,
    ORDER_RATE_LIMIT,
    DISCOUNT_RATE_LIMIT
)

logger = logging.getLogger(__name__)


# ==================== Enums ====================

class RateLimitAlgorithm(Enum):
    """الگوریتم Rate Limiting"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitAction(Enum):
    """عملیات هنگام تخطی"""
    REJECT = "reject"
    THROTTLE = "throttle"
    WARN = "warn"


# ==================== Data Classes ====================

@dataclass
class RateLimitRule:
    """قانون Rate Limit"""
    name: str
    limit: int  # تعداد مجاز
    window_seconds: int  # بازه زمانی
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    action: RateLimitAction = RateLimitAction.REJECT
    burst_limit: Optional[int] = None  # حداکثر burst
    penalty_seconds: int = 0  # مجازات (تاخیر)
    enabled: bool = True
    
    def to_dict(self):
        return {
            'name': self.name,
            'limit': self.limit,
            'window_seconds': self.window_seconds,
            'algorithm': self.algorithm.value,
            'action': self.action.value,
            'burst_limit': self.burst_limit,
            'penalty_seconds': self.penalty_seconds,
            'enabled': self.enabled
        }


@dataclass
class RateLimitViolation:
    """تخطی از Rate Limit"""
    user_id: int
    rule_name: str
    timestamp: datetime
    current_count: int
    limit: int
    retry_after_seconds: int
    action_taken: str
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'rule_name': self.rule_name,
            'timestamp': self.timestamp.isoformat(),
            'current_count': self.current_count,
            'limit': self.limit,
            'retry_after_seconds': self.retry_after_seconds,
            'action_taken': self.action_taken
        }


@dataclass
class RateLimitStats:
    """آمار Rate Limit"""
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    throttled_requests: int = 0
    violations: int = 0
    unique_users: int = 0
    
    def get_rejection_rate(self) -> float:
        """نرخ رد"""
        if self.total_requests == 0:
            return 0.0
        return (self.rejected_requests / self.total_requests) * 100
    
    def get_allow_rate(self) -> float:
        """نرخ قبول"""
        return 100 - self.get_rejection_rate()
    
    def to_dict(self):
        return {
            'total_requests': self.total_requests,
            'allowed_requests': self.allowed_requests,
            'rejected_requests': self.rejected_requests,
            'throttled_requests': self.throttled_requests,
            'violations': self.violations,
            'unique_users': self.unique_users,
            'rejection_rate': round(self.get_rejection_rate(), 2),
            'allow_rate': round(self.get_allow_rate(), 2)
        }


# ==================== Token Bucket ====================

class TokenBucket:
    """الگوریتم Token Bucket"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: ظرفیت bucket (حداکثر توکن)
            refill_rate: نرخ پر شدن (توکن در ثانیه)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """مصرف توکن"""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def _refill(self):
        """پر کردن bucket"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # محاسبه توکن‌های جدید
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        
        self.last_refill = now
    
    def get_available_tokens(self) -> float:
        """دریافت توکن‌های موجود"""
        with self._lock:
            self._refill()
            return self.tokens
    
    def get_retry_after(self, tokens: int = 1) -> float:
        """زمان تا پر شدن کافی توکن"""
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            needed_tokens = tokens - self.tokens
            return needed_tokens / self.refill_rate


# ==================== Sliding Window Counter ====================

class SlidingWindowCounter:
    """الگوریتم Sliding Window Counter"""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self._lock = threading.Lock()
    
    def is_allowed(self) -> Tuple[bool, int]:
        """
        بررسی مجاز بودن درخواست
        
        Returns:
            (allowed, current_count)
        """
        with self._lock:
            now = time.time()
            cutoff_time = now - self.window_seconds
            
            # حذف درخواست‌های قدیمی
            while self.requests and self.requests[0] < cutoff_time:
                self.requests.popleft()
            
            current_count = len(self.requests)
            
            if current_count < self.limit:
                self.requests.append(now)
                return True, current_count + 1
            
            return False, current_count
    
    def get_retry_after(self) -> int:
        """زمان تا آزاد شدن یک slot"""
        with self._lock:
            if not self.requests or len(self.requests) < self.limit:
                return 0
            
            oldest_request = self.requests[0]
            now = time.time()
            retry_after = oldest_request + self.window_seconds - now
            
            return max(0, int(retry_after) + 1)
    
    def get_current_count(self) -> int:
        """تعداد درخواست‌های فعلی"""
        with self._lock:
            now = time.time()
            cutoff_time = now - self.window_seconds
            
            # حذف قدیمی‌ها
            while self.requests and self.requests[0] < cutoff_time:
                self.requests.popleft()
            
            return len(self.requests)
    
    def reset(self):
        """ریست کردن"""
        with self._lock:
            self.requests.clear()


# ==================== Fixed Window Counter ====================

class FixedWindowCounter:
    """الگوریتم Fixed Window Counter"""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.count = 0
        self.window_start = time.time()
        self._lock = threading.Lock()
    
    def is_allowed(self) -> Tuple[bool, int]:
        """بررسی مجاز بودن"""
        with self._lock:
            now = time.time()
            
            # بررسی ریست window
            if now - self.window_start >= self.window_seconds:
                self.count = 0
                self.window_start = now
            
            if self.count < self.limit:
                self.count += 1
                return True, self.count
            
            return False, self.count
    
    def get_retry_after(self) -> int:
        """زمان تا window بعدی"""
        with self._lock:
            now = time.time()
            window_end = self.window_start + self.window_seconds
            retry_after = window_end - now
            
            return max(0, int(retry_after) + 1)
    
    def get_current_count(self) -> int:
        """تعداد درخواست‌های فعلی"""
        with self._lock:
            now = time.time()
            
            if now - self.window_start >= self.window_seconds:
                return 0
            
            return self.count
    
    def reset(self):
        """ریست کردن"""
        with self._lock:
            self.count = 0
            self.window_start = time.time()


# ==================== Enhanced Rate Limiter ====================

class EnhancedRateLimiter:
    """Rate Limiter پیشرفته"""
    
    def __init__(self, admin_id: Optional[int] = None):
        self.admin_id = admin_id
        
        # قوانین Rate Limit
        self.rules: Dict[str, RateLimitRule] = {}
        
        # Limiter ها برای هر کاربر و قانون
        self.limiters: Dict[Tuple[int, str], Any] = {}
        
        # Whitelist & Blacklist
        self.whitelist: set = set()
        self.blacklist: set = set()
        
        # آمار
        self.stats = RateLimitStats()
        self.stats_by_rule: Dict[str, RateLimitStats] = defaultdict(RateLimitStats)
        
        # تاریخچه تخطی‌ها
        self.violations: deque = deque(maxlen=200)
        
        # تاریخچه درخواست‌ها
        self.recent_requests: deque = deque(maxlen=1000)
        
        # کاربران یکتا
        self.unique_users: set = set()
        
        # Penalty timers
        self.penalties: Dict[Tuple[int, str], float] = {}
        
        self._lock = threading.RLock()
        
        # تنظیم قوانین پیش‌فرض
        self._setup_default_rules()
        
        logger.info("✅ Enhanced Rate Limiter initialized")
    
    def _setup_default_rules(self):
        """تنظیم قوانین پیش‌فرض"""
        default_rules = [
            RateLimitRule(
                name="global",
                limit=GLOBAL_RATE_LIMIT,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                action=RateLimitAction.REJECT
            ),
            RateLimitRule(
                name="orders",
                limit=ORDER_RATE_LIMIT,
                window_seconds=3600,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                action=RateLimitAction.REJECT,
                penalty_seconds=300
            ),
            RateLimitRule(
                name="discount_code",
                limit=DISCOUNT_RATE_LIMIT,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                action=RateLimitAction.THROTTLE
            ),
            RateLimitRule(
                name="messages",
                limit=10,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                burst_limit=15,
                action=RateLimitAction.REJECT
            ),
            RateLimitRule(
                name="search",
                limit=30,
                window_seconds=60,
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                action=RateLimitAction.WARN
            ),
            # ✅ اضافه شدن قانون order (برای action_limit)
            RateLimitRule(
                name="order",
                limit=3,
                window_seconds=3600,
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                action=RateLimitAction.REJECT,
                penalty_seconds=300
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    # ==================== Rule Management ====================
    
    def add_rule(self, rule: RateLimitRule):
        """اضافه کردن قانون"""
        with self._lock:
            self.rules[rule.name] = rule
            logger.info(f"✅ Rate limit rule added: {rule.name} ({rule.limit}/{rule.window_seconds}s)")
    
    def remove_rule(self, rule_name: str):
        """حذف قانون"""
        with self._lock:
            if rule_name in self.rules:
                del self.rules[rule_name]
                logger.info(f"🗑 Rate limit rule removed: {rule_name}")
    
    def enable_rule(self, rule_name: str):
        """فعال کردن قانون"""
        with self._lock:
            if rule_name in self.rules:
                self.rules[rule_name].enabled = True
                logger.info(f"✅ Rate limit rule enabled: {rule_name}")
    
    def disable_rule(self, rule_name: str):
        """غیرفعال کردن قانون"""
        with self._lock:
            if rule_name in self.rules:
                self.rules[rule_name].enabled = False
                logger.info(f"⏸ Rate limit rule disabled: {rule_name}")
    
    def get_rule(self, rule_name: str) -> Optional[RateLimitRule]:
        """دریافت قانون"""
        return self.rules.get(rule_name)
    
    def get_all_rules(self) -> List[RateLimitRule]:
        """دریافت تمام قوانین"""
        return list(self.rules.values())
    
    # ==================== Whitelist/Blacklist ====================
    
    def add_to_whitelist(self, user_id: int):
        """اضافه به whitelist"""
        with self._lock:
            self.whitelist.add(user_id)
            logger.info(f"✅ User {user_id} added to whitelist")
    
    def remove_from_whitelist(self, user_id: int):
        """حذف از whitelist"""
        with self._lock:
            self.whitelist.discard(user_id)
            logger.info(f"🗑 User {user_id} removed from whitelist")
    
    def add_to_blacklist(self, user_id: int):
        """اضافه به blacklist"""
        with self._lock:
            self.blacklist.add(user_id)
            logger.info(f"🚫 User {user_id} added to blacklist")
    
    def remove_from_blacklist(self, user_id: int):
        """حذف از blacklist"""
        with self._lock:
            self.blacklist.discard(user_id)
            logger.info(f"✅ User {user_id} removed from blacklist")
    
    def is_whitelisted(self, user_id: int) -> bool:
        """بررسی whitelist"""
        return user_id in self.whitelist or user_id == self.admin_id
    
    def is_blacklisted(self, user_id: int) -> bool:
        """بررسی blacklist"""
        return user_id in self.blacklist
    
    # ==================== Rate Limiting ====================
    
    def check_rate_limit(self, user_id: int, rule_name: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        بررسی Rate Limit
        
        Returns:
            (allowed, retry_after_seconds, message)
        """
        
        # بررسی blacklist
        if self.is_blacklisted(user_id):
            return False, None, "شما مسدود شده‌اید"
        
        # بررسی whitelist (bypass)
        if self.is_whitelisted(user_id):
            return True, None, None
        
        # دریافت قانون
        rule = self.get_rule(rule_name)
        if not rule or not rule.enabled:
            return True, None, None
        
        with self._lock:
            # بررسی penalty
            penalty_key = (user_id, rule_name)
            if penalty_key in self.penalties:
                penalty_end = self.penalties[penalty_key]
                now = time.time()
                
                if now < penalty_end:
                    retry_after = int(penalty_end - now) + 1
                    return False, retry_after, f"شما برای {retry_after} ثانیه محدود شده‌اید"
                else:
                    del self.penalties[penalty_key]
            
            # دریافت یا ساخت limiter
            limiter_key = (user_id, rule_name)
            
            if limiter_key not in self.limiters:
                limiter = self._create_limiter(rule)
                self.limiters[limiter_key] = limiter
            else:
                limiter = self.limiters[limiter_key]
            
            # بررسی limit
            allowed, current_count = self._check_limiter(limiter, rule)
            
            # ثبت آمار
            self.stats.total_requests += 1
            self.stats_by_rule[rule_name].total_requests += 1
            self.unique_users.add(user_id)
            self.stats.unique_users = len(self.unique_users)
            
            # ثبت درخواست
            self.recent_requests.append({
                'timestamp': time.time(),
                'user_id': user_id,
                'rule_name': rule_name,
                'allowed': allowed,
                'current_count': current_count
            })
            
            if allowed:
                self.stats.allowed_requests += 1
                self.stats_by_rule[rule_name].allowed_requests += 1
                return True, None, None
            
            else:
                # محاسبه retry_after
                retry_after = self._get_retry_after(limiter, rule)
                
                # اعمال action
                if rule.action == RateLimitAction.REJECT:
                    self.stats.rejected_requests += 1
                    self.stats_by_rule[rule_name].rejected_requests += 1
                    
                    message = (
                        f"⚠️ شما خیلی سریع درخواست می‌فرستید!\n"
                        f"لطفاً {retry_after} ثانیه صبر کنید."
                    )
                
                elif rule.action == RateLimitAction.THROTTLE:
                    self.stats.throttled_requests += 1
                    self.stats_by_rule[rule_name].throttled_requests += 1
                    
                    # اعمال تاخیر
                    time.sleep(min(5, retry_after))
                    
                    message = "⏱ درخواست شما کند شده است"
                
                elif rule.action == RateLimitAction.WARN:
                    # فقط هشدار، اجازه بده
                    message = "⚠️ توجه: شما در حال رسیدن به محدودیت هستید"
                    return True, retry_after, message
                
                else:
                    message = "Rate limit exceeded"
                
                # ثبت تخطی
                violation = RateLimitViolation(
                    user_id=user_id,
                    rule_name=rule_name,
                    timestamp=datetime.now(),
                    current_count=current_count,
                    limit=rule.limit,
                    retry_after_seconds=retry_after,
                    action_taken=rule.action.value
                )
                
                self.violations.append(violation)
                self.stats.violations += 1
                self.stats_by_rule[rule_name].violations += 1
                
                # اعمال penalty اگر تعریف شده
                if rule.penalty_seconds > 0:
                    penalty_end = time.time() + rule.penalty_seconds
                    self.penalties[penalty_key] = penalty_end
                    
                    logger.warning(
                        f"⚠️ User {user_id} penalized for {rule.penalty_seconds}s "
                        f"(rule: {rule_name})"
                    )
                
                logger.warning(
                    f"⚠️ Rate limit exceeded: User {user_id}, Rule {rule_name}, "
                    f"Count {current_count}/{rule.limit}"
                )
                
                return False, retry_after, message
    
    def _create_limiter(self, rule: RateLimitRule):
        """ساخت limiter بر اساس الگوریتم"""
        if rule.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            capacity = rule.burst_limit or rule.limit
            refill_rate = rule.limit / rule.window_seconds
            return TokenBucket(capacity, refill_rate)
        
        elif rule.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return SlidingWindowCounter(rule.limit, rule.window_seconds)
        
        elif rule.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            return FixedWindowCounter(rule.limit, rule.window_seconds)
        
        else:
            # پیش‌فرض: Sliding Window
            return SlidingWindowCounter(rule.limit, rule.window_seconds)
    
    def _check_limiter(self, limiter, rule: RateLimitRule) -> Tuple[bool, int]:
        """بررسی limiter"""
        if isinstance(limiter, TokenBucket):
            allowed = limiter.consume(1)
            current = int(rule.limit - limiter.get_available_tokens())
            return allowed, current
        
        else:  # SlidingWindow or FixedWindow
            return limiter.is_allowed()
    
    def _get_retry_after(self, limiter, rule: RateLimitRule) -> int:
        """محاسبه retry_after"""
        if isinstance(limiter, TokenBucket):
            return int(limiter.get_retry_after(1)) + 1
        else:
            return limiter.get_retry_after()
    
    # ==================== Reset & Clear ====================
    
    def reset_user(self, user_id: int, rule_name: Optional[str] = None):
        """ریست Rate Limit یک کاربر"""
        with self._lock:
            if rule_name:
                # ریست یک قانون خاص
                limiter_key = (user_id, rule_name)
                if limiter_key in self.limiters:
                    del self.limiters[limiter_key]
                
                penalty_key = (user_id, rule_name)
                if penalty_key in self.penalties:
                    del self.penalties[penalty_key]
                
                logger.info(f"🔄 Reset rate limit for user {user_id}, rule {rule_name}")
            
            else:
                # ریست تمام قوانین
                keys_to_remove = [
                    key for key in self.limiters.keys()
                    if key[0] == user_id
                ]
                
                for key in keys_to_remove:
                    del self.limiters[key]
                
                penalty_keys = [
                    key for key in self.penalties.keys()
                    if key[0] == user_id
                ]
                
                for key in penalty_keys:
                    del self.penalties[key]
                
                logger.info(f"🔄 Reset all rate limits for user {user_id}")
    
    def clear_all(self):
        """پاک کردن تمام limiterها"""
        with self._lock:
            self.limiters.clear()
            self.penalties.clear()
            logger.info("🧹 All rate limiters cleared")
    
    # ==================== Statistics ====================
    
    def get_statistics(self) -> Dict:
        """آمار کامل"""
        with self._lock:
            stats_dict = self.stats.to_dict()
            
            stats_dict.update({
                'active_limiters': len(self.limiters),
                'active_penalties': len(self.penalties),
                'whitelist_size': len(self.whitelist),
                'blacklist_size': len(self.blacklist),
                'by_rule': {
                    name: rule_stats.to_dict()
                    for name, rule_stats in self.stats_by_rule.items()
                }
            })
            
            return stats_dict
    
    def get_user_status(self, user_id: int, rule_name: Optional[str] = None) -> Dict:
        """وضعیت Rate Limit یک کاربر"""
        with self._lock:
            status = {
                'user_id': user_id,
                'is_whitelisted': self.is_whitelisted(user_id),
                'is_blacklisted': self.is_blacklisted(user_id),
                'limits': {}
            }
            
            rules_to_check = [rule_name] if rule_name else self.rules.keys()
            
            for rname in rules_to_check:
                rule = self.rules.get(rname)
                if not rule:
                    continue
                
                limiter_key = (user_id, rname)
                penalty_key = (user_id, rname)
                
                limit_info = {
                    'rule': rule.to_dict(),
                    'current_count': 0,
                    'remaining': rule.limit,
                    'has_penalty': penalty_key in self.penalties,
                    'penalty_ends_at': None
                }
                
                # دریافت current count
                if limiter_key in self.limiters:
                    limiter = self.limiters[limiter_key]
                    
                    if isinstance(limiter, TokenBucket):
                        available = limiter.get_available_tokens()
                        limit_info['current_count'] = int(rule.limit - available)
                        limit_info['remaining'] = int(available)
                    else:
                        current_count = limiter.get_current_count()
                        limit_info['current_count'] = current_count
                        limit_info['remaining'] = max(0, rule.limit - current_count)
                
                # penalty info
                if penalty_key in self.penalties:
                    penalty_end = self.penalties[penalty_key]
                    limit_info['penalty_ends_at'] = datetime.fromtimestamp(penalty_end).isoformat()
                
                status['limits'][rname] = limit_info
            
            return status
    
    def get_recent_violations(self, count: int = 20) -> List[Dict]:
        """تخطی‌های اخیر"""
        violations = list(self.violations)[-count:]
        return [v.to_dict() for v in violations]
    
    def get_top_violators(self, limit: int = 10) -> List[Dict]:
        """پرتخطی‌ترین کاربران"""
        with self._lock:
            user_violations = defaultdict(int)
            
            for violation in self.violations:
                user_violations[violation.user_id] += 1
            
            sorted_users = sorted(
                user_violations.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            return [
                {'user_id': user_id, 'violations': count}
                for user_id, count in sorted_users[:limit]
            ]
    
    def get_rate_limit_report(self) -> str:
        """گزارش متنی Rate Limit"""
        stats = self.get_statistics()
        top_violators = self.get_top_violators(5)
        
        report = "⏱️ **گزارش Rate Limiting**\n"
        report += "═" * 40 + "\n\n"
        
        # آمار کلی
        report += "**📊 آمار:**\n"
        report += f"├ کل درخواست‌ها: {stats['total_requests']}\n"
        report += f"├ مجاز: {stats['allowed_requests']}\n"
        report += f"├ رد شده: {stats['rejected_requests']}\n"
        report += f"├ Throttled: {stats['throttled_requests']}\n"
        report += f"└ تخطی‌ها: {stats['violations']}\n\n"
        
        # نرخ‌ ها
        report += "**📈 نرخ‌ها:**\n"
        report += f"├ Allow Rate: {stats['allow_rate']}%\n"
        report += f"└ Rejection Rate: {stats['rejection_rate']}%\n\n"
        
        # وضعیت
        report += "**🔧 وضعیت:**\n"
        report += f"├ Limiters فعال: {stats['active_limiters']}\n"
        report += f"├ Penalties فعال: {stats['active_penalties']}\n"
        report += f"├ Whitelist: {stats['whitelist_size']}\n"
        report += f"└ Blacklist: {stats['blacklist_size']}\n\n"
        
        # پرتخطی‌ترین کاربران
        if top_violators:
            report += "**🚨 پرتخطی‌ترین کاربران:**\n"
            for i, violator in enumerate(top_violators[:3], 1):
                report += f"{i}. User {violator['user_id']}: {violator['violations']} تخطی\n"
            report += "\n"
        
        # آمار بر اساس قانون
        if stats.get('by_rule'):
            report += "**📋 بر اساس قانون:**\n"
            for rule_name, rule_stats in stats['by_rule'].items():
                report += f"• {rule_name}: "
                report += f"{rule_stats['rejected_requests']}/{rule_stats['total_requests']} رد\n"
        
        report += "\n" + "═" * 40
        
        return report
    
    def export_statistics(self, filepath: str = "rate_limit_stats.json") -> bool:
        """خروجی آمار به JSON"""
        try:
            stats = self.get_statistics()
            violations = self.get_recent_violations(100)
            top_violators = self.get_top_violators(20)
            
            data = {
                'exported_at': datetime.now().isoformat(),
                'statistics': stats,
                'recent_violations': violations,
                'top_violators': top_violators,
                'rules': [rule.to_dict() for rule in self.get_all_rules()]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Rate limit stats exported to: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return False


# ==================== Decorators ====================

def rate_limit(rule_name: str = None, 
              max_requests: int = None,
              window_seconds: int = None,
              error_message: Optional[str] = None):
    """
    Decorator برای اعمال Rate Limit
    
    استفاده:
        @rate_limit(rule_name="global")
        یا
        @rate_limit(max_requests=10, window_seconds=60)
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            # دریافت rate_limiter از context
            rate_limiter = context.bot_data.get('rate_limiter')
            
            if rate_limiter:
                # اگر rule_name داده شده، از قانون موجود استفاده کن
                if rule_name:
                    allowed, retry_after, message = rate_limiter.check_rate_limit(
                        user_id,
                        rule_name
                    )
                # اگر max_requests داده شده، یک قانون موقت بساز
                elif max_requests and window_seconds:
                    temp_rule_name = f"{func.__name__}_rate_limit"
                    
                    # بررسی اگر قانون وجود نداره، بسازش
                    if not rate_limiter.get_rule(temp_rule_name):
                        temp_rule = RateLimitRule(
                            name=temp_rule_name,
                            limit=max_requests,
                            window_seconds=window_seconds,
                            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                            action=RateLimitAction.REJECT
                        )
                        rate_limiter.add_rule(temp_rule)
                    
                    allowed, retry_after, message = rate_limiter.check_rate_limit(
                        user_id,
                        temp_rule_name
                    )
                else:
                    # هیچ محدودیتی تعریف نشده، اجازه بده
                    allowed = True
                    message = None
                
                if not allowed:
                    error_msg = error_message or message
                    
                    if update.message:
                        await update.message.reply_text(error_msg)
                    elif update.callback_query:
                        await update.callback_query.answer(
                            error_msg,
                            show_alert=True
                        )
                    
                    return None
            
            return await func(update, context, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            # دریافت rate_limiter از context
            rate_limiter = context.bot_data.get('rate_limiter')
            
            if rate_limiter:
                if rule_name:
                    allowed, retry_after, message = rate_limiter.check_rate_limit(
                        user_id,
                        rule_name
                    )
                elif max_requests and window_seconds:
                    temp_rule_name = f"{func.__name__}_rate_limit"
                    
                    if not rate_limiter.get_rule(temp_rule_name):
                        temp_rule = RateLimitRule(
                            name=temp_rule_name,
                            limit=max_requests,
                            window_seconds=window_seconds,
                            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                            action=RateLimitAction.REJECT
                        )
                        rate_limiter.add_rule(temp_rule)
                    
                    allowed, retry_after, message = rate_limiter.check_rate_limit(
                        user_id,
                        temp_rule_name
                    )
                else:
                    allowed = True
                    message = None
                
                if not allowed:
                    error_msg = error_message or message
                    return None
            
            return func(update, context, *args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ✅ اضافه کردن action_limit decorator
def action_limit(action_name: str,
                max_requests: int = None,
                window_seconds: int = None,
                error_message: Optional[str] = None):
    """
    Decorator برای محدود کردن یک عملیات خاص
    
    استفاده:
        @action_limit('order', max_requests=3, window_seconds=3600)
        async def finalize_order_start(update, context):
            ...
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            # دریافت rate_limiter از context
            rate_limiter = context.bot_data.get('rate_limiter')
            
            if rate_limiter:
                # استفاده از action_name به عنوان rule_name
                rule_name = action_name
                
                # بررسی اگر قانون وجود نداره، بسازش
                if not rate_limiter.get_rule(rule_name):
                    if max_requests and window_seconds:
                        action_rule = RateLimitRule(
                            name=rule_name,
                            limit=max_requests,
                            window_seconds=window_seconds,
                            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                            action=RateLimitAction.REJECT,
                            penalty_seconds=300  # 5 دقیقه penalty
                        )
                        rate_limiter.add_rule(action_rule)
                
                allowed, retry_after, message = rate_limiter.check_rate_limit(
                    user_id,
                    rule_name
                )
                
                if not allowed:
                    error_msg = error_message or message or f"⚠️ شما برای {retry_after} ثانیه محدود شده‌اید"
                    
                    if update.message:
                        await update.message.reply_text(error_msg)
                    elif update.callback_query:
                        await update.callback_query.answer(
                            error_msg,
                            show_alert=True
                        )
                    
                    return None
            
            return await func(update, context, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            rate_limiter = context.bot_data.get('rate_limiter')
            
            if rate_limiter:
                rule_name = action_name
                
                if not rate_limiter.get_rule(rule_name):
                    if max_requests and window_seconds:
                        action_rule = RateLimitRule(
                            name=rule_name,
                            limit=max_requests,
                            window_seconds=window_seconds,
                            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                            action=RateLimitAction.REJECT,
                            penalty_seconds=300
                        )
                        rate_limiter.add_rule(action_rule)
                
                allowed, retry_after, message = rate_limiter.check_rate_limit(
                    user_id,
                    rule_name
                )
                
                if not allowed:
                    error_msg = error_message or message or f"⚠️ شما برای {retry_after} ثانیه محدود شده‌اید"
                    return None
            
            return func(update, context, *args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ==================== Rate Limit Monitor ====================

class RateLimitMonitor:
    """مانیتورینگ Rate Limit"""
    
    def __init__(self, rate_limiter: EnhancedRateLimiter):
        self.rate_limiter = rate_limiter
    
    def get_health_status(self) -> Dict:
        """وضعیت سلامت Rate Limiter"""
        stats = self.rate_limiter.get_statistics()
        
        status = "ok"
        issues = []
        
        # بررسی نرخ رد
        if stats['rejection_rate'] > 50:
            status = "warning"
            issues.append("High rejection rate")
        
        if stats['rejection_rate'] > 80:
            status = "error"
            issues.append("Very high rejection rate")
        
        # بررسی تخطی‌ها
        if stats['violations'] > 100:
            status = "warning"
            issues.append("Many violations detected")
        
        # بررسی blacklist
        if stats['blacklist_size'] > 50:
            status = "warning"
            issues.append("Large blacklist")
        
        return {
            'status': status,
            'rejection_rate': stats['rejection_rate'],
            'violations': stats['violations'],
            'active_limiters': stats['active_limiters'],
            'blacklist_size': stats['blacklist_size'],
            'issues': issues
        }
    
    def get_metrics_for_monitoring(self) -> Dict:
        """متریک‌ها برای سیستم مانیتورینگ"""
        stats = self.rate_limiter.get_statistics()
        health = self.get_health_status()
        
        return {
            'rate_limit.total_requests': stats['total_requests'],
            'rate_limit.allowed_requests': stats['allowed_requests'],
            'rate_limit.rejected_requests': stats['rejected_requests'],
            'rate_limit.rejection_rate': stats['rejection_rate'],
            'rate_limit.violations': stats['violations'],
            'rate_limit.active_limiters': stats['active_limiters'],
            'rate_limit.health_status': health['status']
        }
    
    def check_anomalies(self) -> List[str]:
        """تشخیص ناهنجاری‌ها"""
        anomalies = []
        
        # بررسی افزایش ناگهانی درخواست‌ها
        recent_requests = list(self.rate_limiter.recent_requests)[-100:]
        
        if recent_requests:
            # بررسی spike در درخواست‌ها
            user_counts = defaultdict(int)
            for req in recent_requests:
                user_counts[req['user_id']] += 1
            
            for user_id, count in user_counts.items():
                if count > 50:  # بیش از 50 درخواست در 100 درخواست اخیر
                    anomalies.append(
                        f"Possible attack from user {user_id}: {count} requests"
                    )
        
        # بررسی تخطی‌های مکرر
        recent_violations = list(self.rate_limiter.violations)[-50:]
        
        if len(recent_violations) > 30:
            anomalies.append("High number of recent violations")
        
        # بررسی الگوی مشکوک
        violation_users = [v.user_id for v in recent_violations]
        unique_violators = len(set(violation_users))
        
        if len(recent_violations) > 20 and unique_violators < 5:
            anomalies.append(
                f"Concentrated violations from {unique_violators} users"
            )
        
        return anomalies


# ==================== Adaptive Rate Limiter ====================

class AdaptiveRateLimiter(EnhancedRateLimiter):
    """Rate Limiter با تنظیم خودکار"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیمات adaptive
        self.adaptive_enabled = True
        self.adjustment_interval = 300  # 5 دقیقه
        self.last_adjustment = time.time()
        
        logger.info("✅ Adaptive Rate Limiter initialized")
    
    def auto_adjust_limits(self):
        """تنظیم خودکار limitها بر اساس بار"""
        if not self.adaptive_enabled:
            return
        
        now = time.time()
        if now - self.last_adjustment < self.adjustment_interval:
            return
        
        self.last_adjustment = now
        
        with self._lock:
            stats = self.get_statistics()
            
            # اگر rejection rate خیلی بالاست، limitها را افزایش بده
            if stats['rejection_rate'] > 70:
                for rule in self.rules.values():
                    if rule.name != 'global':
                        old_limit = rule.limit
                        rule.limit = int(rule.limit * 1.2)  # 20% افزایش
                        
                        logger.info(
                            f"🔧 Auto-adjusted {rule.name}: "
                            f"{old_limit} -> {rule.limit}"
                        )
            
            # اگر rejection rate خیلی پایین است، limitها را کاهش بده
            elif stats['rejection_rate'] < 10 and stats['total_requests'] > 100:
                for rule in self.rules.values():
                    if rule.name != 'global' and rule.limit > 5:
                        old_limit = rule.limit
                        rule.limit = max(5, int(rule.limit * 0.9))  # 10% کاهش
                        
                        logger.info(
                            f"🔧 Auto-adjusted {rule.name}: "
                            f"{old_limit} -> {rule.limit}"
                        )
    
    def check_rate_limit(self, user_id: int, rule_name: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Override با auto-adjustment"""
        
        # تنظیم خودکار
        self.auto_adjust_limits()
        
        # استفاده از متد اصلی
        return super().check_rate_limit(user_id, rule_name)


# ==================== Distributed Rate Limiter (Redis-ready) ====================

class DistributedRateLimiter(EnhancedRateLimiter):
    """Rate Limiter برای محیط توزیع‌شده (آماده Redis)"""
    
    def __init__(self, redis_client=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = redis_client
        
        if self.redis:
            logger.info("✅ Distributed Rate Limiter with Redis initialized")
        else:
            logger.warning("⚠️ Distributed Rate Limiter initialized without Redis")
    
    def check_rate_limit(self, user_id: int, rule_name: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """Override برای استفاده از Redis"""
        
        # اگر Redis موجود نیست، از متد local استفاده کن
        if not self.redis:
            return super().check_rate_limit(user_id, rule_name)
        
        # پیاده‌سازی Redis (برای آینده)
        # این قسمت فعلاً placeholder است
        # در صورت نیاز می‌توان کامل کرد
        
        return super().check_rate_limit(user_id, rule_name)


# ==================== Helper Functions ====================

def create_rate_limiter(admin_id: Optional[int] = None,
                       adaptive: bool = False) -> EnhancedRateLimiter:
    """ساخت Rate Limiter"""
    if adaptive:
        return AdaptiveRateLimiter(admin_id=admin_id)
    else:
        return EnhancedRateLimiter(admin_id=admin_id)


def format_time_remaining(seconds: int) -> str:
    """فرمت کردن زمان باقیمانده"""
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} دقیقه"
    else:
        hours = seconds // 3600
        return f"{hours} ساعت"


# ==================== Context Manager for Rate Limiting ====================

class RateLimitContext:
    """Context Manager برای Rate Limiting"""
    
    def __init__(self, rate_limiter: EnhancedRateLimiter, 
                 user_id: int, rule_name: str):
        self.rate_limiter = rate_limiter
        self.user_id = user_id
        self.rule_name = rule_name
        self.allowed = False
        self.retry_after = None
        self.message = None
    
    def __enter__(self):
        """ورود به context"""
        self.allowed, self.retry_after, self.message = \
            self.rate_limiter.check_rate_limit(self.user_id, self.rule_name)
        
        if not self.allowed:
            raise RateLimitExceeded(
                self.user_id,
                self.rule_name,
                self.retry_after,
                self.message
            )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """خروج از context"""
        pass


class RateLimitExceeded(Exception):
    """Exception برای تخطی از Rate Limit"""
    
    def __init__(self, user_id: int, rule_name: str, 
                 retry_after: Optional[int], message: str):
        self.user_id = user_id
        self.rule_name = rule_name
        self.retry_after = retry_after
        self.message = message
        super().__init__(message)


# ==================== Global Rate Limiter ====================

# نمونه سراسری
_global_rate_limiter: Optional[EnhancedRateLimiter] = None


def setup_rate_limiter(admin_id: Optional[int] = None,
                      adaptive: bool = False) -> EnhancedRateLimiter:
    """راه‌اندازی Rate Limiter سراسری"""
    global _global_rate_limiter
    
    _global_rate_limiter = create_rate_limiter(
        admin_id=admin_id,
        adaptive=adaptive
    )
    
    return _global_rate_limiter


def get_rate_limiter() -> Optional[EnhancedRateLimiter]:
    """دریافت Rate Limiter سراسری"""
    if _global_rate_limiter is None:
        setup_rate_limiter()
    
    return _global_rate_limiter


# ==================== Integration Helper ====================

def integrate_with_monitoring(rate_limiter: EnhancedRateLimiter,
                             monitoring_system) -> RateLimitMonitor:
    """ادغام با سیستم مانیتورینگ"""
    monitor = RateLimitMonitor(rate_limiter)
    
    # ثبت متریک‌ها
    if hasattr(monitoring_system, 'register_metric_collector'):
        monitoring_system.register_metric_collector(
            'rate_limit',
            monitor.get_metrics_for_monitoring
        )
    
    logger.info("✅ Rate Limiter integrated with monitoring system")
    
    return monitor


# ==================== Example Usage ====================

def example_usage():
    """مثال استفاده"""
    
    # 1. ساخت Rate Limiter
    rate_limiter = EnhancedRateLimiter(admin_id=123456789)
    
    # 2. اضافه کردن قانون سفارشی
    custom_rule = RateLimitRule(
        name="api_calls",
        limit=100,
        window_seconds=3600,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_limit=120,
        action=RateLimitAction.REJECT
    )
    rate_limiter.add_rule(custom_rule)
    
    # 3. بررسی Rate Limit
    user_id = 123
    allowed, retry_after, message = rate_limiter.check_rate_limit(
        user_id, 
        "global"
    )
    
    if allowed:
        print("✅ Request allowed")
    else:
        print(f"❌ Rate limit exceeded: {message}")
        print(f"Retry after: {retry_after} seconds")
    
    # 4. استفاده از Context Manager
    try:
        with RateLimitContext(rate_limiter, user_id, "orders"):
            print("✅ Processing order...")
            # عملیات سفارش
    except RateLimitExceeded as e:
        print(f"❌ {e.message}")
    
    # 5. اضافه به whitelist
    rate_limiter.add_to_whitelist(999)
    
    # 6. دریافت آمار
    stats = rate_limiter.get_statistics()
    print(f"Total requests: {stats['total_requests']}")
    print(f"Rejection rate: {stats['rejection_rate']}%")
    
    # 7. وضعیت یک کاربر
    user_status = rate_limiter.get_user_status(user_id)
    print(f"User {user_id} status: {user_status}")
    
    # 8. گزارش
    print(rate_limiter.get_rate_limit_report())
    
    # 9. Export
    rate_limiter.export_statistics("rate_limit_stats.json")


if __name__ == "__main__":
    example_usage()


logger.info("✅ Enhanced Rate Limiter module loaded")
