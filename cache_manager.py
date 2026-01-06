"""
💾 سیستم مدیریت پیشرفته Cache
✅ TTL (Time To Live) Support
✅ LRU (Least Recently Used) Eviction
✅ Cache Statistics & Analytics
✅ Cache Warming (Pre-loading)
✅ Pattern-based Invalidation
✅ Hit/Miss Rate Tracking
✅ Auto Cleanup
✅ Memory Limit Management
✅ Cache Namespaces

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import time
import logging
import threading
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List, Tuple, Callable, Set
from dataclasses import dataclass, field, asdict
from collections import OrderedDict, defaultdict, deque
from pathlib import Path
import json

from config import (
    CACHE_ENABLED, 
    CACHE_DEFAULT_TTL, 
    CACHE_CLEANUP_INTERVAL
)

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class CacheEntry:
    """یک آیتم کش"""
    key: str
    value: Any
    created_at: float
    expires_at: Optional[float]
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    namespace: str = "default"
    tags: Set[str] = field(default_factory=set)
    
    def is_expired(self) -> bool:
        """بررسی انقضا"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self):
        """بروزرسانی زمان دسترسی"""
        self.hits += 1
        self.last_accessed = time.time()
    
    def get_age_seconds(self) -> float:
        """سن آیتم به ثانیه"""
        return time.time() - self.created_at
    
    def get_ttl_remaining(self) -> Optional[float]:
        """زمان باقی‌مانده تا انقضا"""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.time()
        return max(0, remaining)
    
    def to_dict(self):
        return {
            'key': self.key,
            'created_at': datetime.fromtimestamp(self.created_at).isoformat(),
            'expires_at': datetime.fromtimestamp(self.expires_at).isoformat() if self.expires_at else None,
            'hits': self.hits,
            'last_accessed': datetime.fromtimestamp(self.last_accessed).isoformat(),
            'size_bytes': self.size_bytes,
            'namespace': self.namespace,
            'tags': list(self.tags),
            'age_seconds': self.get_age_seconds(),
            'ttl_remaining': self.get_ttl_remaining()
        }


@dataclass
class CacheStatistics:
    """آمار کش"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    expirations: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    start_time: float = field(default_factory=time.time)
    
    def get_hit_rate(self) -> float:
        """نرخ موفقیت کش"""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100
    
    def get_miss_rate(self) -> float:
        """نرخ miss"""
        return 100 - self.get_hit_rate()
    
    def get_uptime_seconds(self) -> float:
        """مدت زمان فعالیت"""
        return time.time() - self.start_time
    
    def to_dict(self):
        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'deletes': self.deletes,
            'expirations': self.expirations,
            'evictions': self.evictions,
            'hit_rate': round(self.get_hit_rate(), 2),
            'miss_rate': round(self.get_miss_rate(), 2),
            'total_size_bytes': self.total_size_bytes,
            'total_size_mb': round(self.total_size_bytes / (1024 * 1024), 2),
            'uptime_seconds': self.get_uptime_seconds()
        }


# ==================== Enhanced Cache Manager ====================

class EnhancedCacheManager:
    """مدیریت پیشرفته Cache"""
    
    def __init__(self, 
                 enabled: bool = CACHE_ENABLED,
                 default_ttl: int = CACHE_DEFAULT_TTL,
                 max_size: int = 10000,
                 max_memory_mb: int = 500,
                 cleanup_interval: int = CACHE_CLEANUP_INTERVAL,
                 enable_persistence: bool = False,
                 persistence_path: str = "cache_data"):
        
        self.enabled = enabled
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        self.enable_persistence = enable_persistence
        self.persistence_path = Path(persistence_path)
        
        # ذخیره‌سازی اصلی (OrderedDict برای LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # نگاشت namespace به کلیدها
        self._namespaces: Dict[str, Set[str]] = defaultdict(set)
        
        # نگاشت tag به کلیدها
        self._tags: Dict[str, Set[str]] = defaultdict(set)
        
        # آمار
        self.stats = CacheStatistics()
        
        # تاریخچه عملیات اخیر
        self.recent_operations: deque = deque(maxlen=100)
        
        # Lock برای thread-safety
        self._lock = threading.RLock()
        
        # Cleanup task
        self._cleanup_task = None
        self._stop_cleanup = False
        
        # ساخت پوشه persistence
        if self.enable_persistence:
            self.persistence_path.mkdir(exist_ok=True)
        
        # شروع cleanup خودکار
        if self.enabled:
            self._start_cleanup_task()
        
        logger.info(
            f"✅ Enhanced Cache Manager initialized "
            f"(Enabled: {enabled}, Max: {max_size}, TTL: {default_ttl}s)"
        )
    
    # ==================== Core Operations ====================
    
    def get(self, key: str, default: Any = None, 
            namespace: str = "default") -> Any:
        """دریافت از کش"""
        if not self.enabled:
            return default
        
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            entry = self._cache.get(full_key)
            
            if entry is None:
                self.stats.misses += 1
                self._log_operation('miss', full_key)
                return default
            
            # بررسی انقضا
            if entry.is_expired():
                self._remove_entry(full_key, reason='expired')
                self.stats.misses += 1
                self.stats.expirations += 1
                self._log_operation('expired', full_key)
                return default
            
            # بروزرسانی و جابجایی به انتها (LRU)
            entry.touch()
            self._cache.move_to_end(full_key)
            
            self.stats.hits += 1
            self._log_operation('hit', full_key)
            
            return entry.value
    
    def set(self, key: str, value: Any, 
            ttl: Optional[int] = None,
            namespace: str = "default",
            tags: Optional[Set[str]] = None) -> bool:
        """ذخیره در کش"""
        if not self.enabled:
            return False
        
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            # محاسبه سایز تقریبی
            try:
                size_bytes = len(pickle.dumps(value))
            except:
                size_bytes = 0
            
            # بررسی محدودیت حافظه
            if size_bytes > self.max_memory_bytes:
                logger.warning(f"⚠️ Value too large for cache: {size_bytes} bytes")
                return False
            
            # اگر کش پر است، evict کن
            while len(self._cache) >= self.max_size:
                self._evict_lru()
            
            # بررسی فضای کافی
            while (self.stats.total_size_bytes + size_bytes) > self.max_memory_bytes:
                if not self._evict_lru():
                    break
            
            # محاسبه زمان انقضا
            current_time = time.time()
            expires_at = None
            
            if ttl is None:
                ttl = self.default_ttl
            
            if ttl > 0:
                expires_at = current_time + ttl
            
            # ساخت entry
            entry = CacheEntry(
                key=full_key,
                value=value,
                created_at=current_time,
                expires_at=expires_at,
                size_bytes=size_bytes,
                namespace=namespace,
                tags=tags or set()
            )
            
            # حذف entry قدیمی اگر وجود دارد
            if full_key in self._cache:
                self._remove_entry(full_key, reason='overwrite')
            
            # اضافه کردن
            self._cache[full_key] = entry
            self._namespaces[namespace].add(full_key)
            
            for tag in entry.tags:
                self._tags[tag].add(full_key)
            
            self.stats.total_size_bytes += size_bytes
            self.stats.sets += 1
            
            self._log_operation('set', full_key)
            
            # Persistence
            if self.enable_persistence:
                self._persist_entry(entry)
            
            return True
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """حذف از کش"""
        if not self.enabled:
            return False
        
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            if full_key in self._cache:
                self._remove_entry(full_key, reason='delete')
                self.stats.deletes += 1
                self._log_operation('delete', full_key)
                return True
        
        return False
    
    def exists(self, key: str, namespace: str = "default") -> bool:
        """بررسی وجود"""
        if not self.enabled:
            return False
        
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            if full_key not in self._cache:
                return False
            
            entry = self._cache[full_key]
            if entry.is_expired():
                self._remove_entry(full_key, reason='expired')
                return False
            
            return True
    
    def clear(self, namespace: Optional[str] = None) -> int:
        """پاک کردن کش"""
        if not self.enabled:
            return 0
        
        with self._lock:
            if namespace is None:
                # پاک کردن همه
                count = len(self._cache)
                self._cache.clear()
                self._namespaces.clear()
                self._tags.clear()
                self.stats.total_size_bytes = 0
                self._log_operation('clear_all', 'all')
                logger.info(f"🧹 Cache cleared: {count} items")
                return count
            else:
                # پاک کردن یک namespace
                keys_to_remove = list(self._namespaces.get(namespace, []))
                
                for key in keys_to_remove:
                    self._remove_entry(key, reason='clear_namespace')
                
                self._log_operation('clear_namespace', namespace)
                logger.info(f"🧹 Namespace '{namespace}' cleared: {len(keys_to_remove)} items")
                return len(keys_to_remove)
    
    # ==================== Advanced Operations ====================
    
    def get_multi(self, keys: List[str], namespace: str = "default") -> Dict[str, Any]:
        """دریافت چندتایی"""
        result = {}
        for key in keys:
            value = self.get(key, namespace=namespace)
            if value is not None:
                result[key] = value
        return result
    
    def set_multi(self, items: Dict[str, Any], 
                  ttl: Optional[int] = None,
                  namespace: str = "default") -> int:
        """ذخیره چندتایی"""
        success_count = 0
        for key, value in items.items():
            if self.set(key, value, ttl=ttl, namespace=namespace):
                success_count += 1
        return success_count
    
    def delete_multi(self, keys: List[str], namespace: str = "default") -> int:
        """حذف چندتایی"""
        deleted_count = 0
        for key in keys:
            if self.delete(key, namespace=namespace):
                deleted_count += 1
        return deleted_count
    
    def invalidate_by_tag(self, tag: str) -> int:
        """حذف بر اساس tag"""
        with self._lock:
            keys_to_remove = list(self._tags.get(tag, []))
            
            for key in keys_to_remove:
                self._remove_entry(key, reason='invalidate_tag')
            
            if tag in self._tags:
                del self._tags[tag]
            
            logger.info(f"🗑 Invalidated {len(keys_to_remove)} items with tag '{tag}'")
            return len(keys_to_remove)
    
    def invalidate_by_pattern(self, pattern: str, namespace: str = "default") -> int:
        """حذف بر اساس الگو (wildcard)"""
        import fnmatch
        
        with self._lock:
            keys_to_check = list(self._namespaces.get(namespace, []))
            keys_to_remove = [
                key for key in keys_to_check
                if fnmatch.fnmatch(key, f"*{pattern}*")
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key, reason='invalidate_pattern')
            
            logger.info(f"🗑 Invalidated {len(keys_to_remove)} items matching '{pattern}'")
            return len(keys_to_remove)
    
    def touch(self, key: str, namespace: str = "default") -> bool:
        """بروزرسانی last_accessed بدون دریافت مقدار"""
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            entry = self._cache.get(full_key)
            
            if entry and not entry.is_expired():
                entry.touch()
                self._cache.move_to_end(full_key)
                return True
        
        return False
    
    def extend_ttl(self, key: str, additional_seconds: int, 
                   namespace: str = "default") -> bool:
        """افزایش TTL"""
        full_key = self._make_key(key, namespace)
        
        with self._lock:
            entry = self._cache.get(full_key)
            
            if entry and not entry.is_expired():
                if entry.expires_at:
                    entry.expires_at += additional_seconds
                    return True
        
        return False
    
    # ==================== Cache Warming ====================
    
    def warm(self, loader: Callable[[str], Any], 
             keys: List[str],
             namespace: str = "default",
             ttl: Optional[int] = None) -> int:
        """پیش‌بارگذاری کش (Cache Warming)"""
        logger.info(f"🔥 Warming cache with {len(keys)} items...")
        
        success_count = 0
        
        for key in keys:
            try:
                value = loader(key)
                if self.set(key, value, ttl=ttl, namespace=namespace):
                    success_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to warm cache for key '{key}': {e}")
        
        logger.info(f"✅ Cache warmed: {success_count}/{len(keys)} items")
        return success_count
    
    # ==================== Internal Methods ====================
    
    def _make_key(self, key: str, namespace: str) -> str:
        """ساخت کلید کامل"""
        return f"{namespace}:{key}"
    
    def _remove_entry(self, key: str, reason: str = 'unknown'):
        """حذف یک entry"""
        entry = self._cache.get(key)
        
        if entry:
            # کاهش سایز
            self.stats.total_size_bytes -= entry.size_bytes
            
            # حذف از namespace
            if key in self._namespaces[entry.namespace]:
                self._namespaces[entry.namespace].remove(key)
            
            # حذف از tags
            for tag in entry.tags:
                if key in self._tags[tag]:
                    self._tags[tag].remove(key)
            
            # حذف از کش
            del self._cache[key]
            
            # Persistence
            if self.enable_persistence:
                self._delete_persisted_entry(key)
    
    def _evict_lru(self) -> bool:
        """حذف کم‌استفاده‌ترین آیتم (LRU)"""
        if not self._cache:
            return False
        
        # اولین آیتم OrderedDict = قدیمی‌ترین
        key, entry = self._cache.popitem(last=False)
        
        self.stats.total_size_bytes -= entry.size_bytes
        self.stats.evictions += 1
        
        # حذف از namespace و tags
        if key in self._namespaces[entry.namespace]:
            self._namespaces[entry.namespace].remove(key)
        
        for tag in entry.tags:
            if key in self._tags[tag]:
                self._tags[tag].remove(key)
        
        self._log_operation('evict', key)
        logger.debug(f"🗑 Evicted LRU item: {key}")
        
        return True
    
    def _log_operation(self, operation: str, key: str):
        """ثبت عملیات"""
        self.recent_operations.append({
            'timestamp': time.time(),
            'operation': operation,
            'key': key
        })
    
    # ==================== Cleanup ====================
    
    def _start_cleanup_task(self):
        """شروع task پاکسازی خودکار"""
        def cleanup_loop():
            while not self._stop_cleanup:
                time.sleep(self.cleanup_interval)
                self.cleanup_expired()
        
        self._cleanup_task = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_task.start()
        
        logger.info(f"✅ Auto cleanup started (interval: {self.cleanup_interval}s)")
    
    def cleanup_expired(self) -> int:
        """پاکسازی آیتم‌های منقضی شده"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._remove_entry(key, reason='expired')
                self.stats.expirations += 1
            
            if expired_keys:
                logger.info(f"🧹 Cleaned {len(expired_keys)} expired items")
            
            return len(expired_keys)
    
    def stop(self):
        """توقف کش منیجر"""
        self._stop_cleanup = True
        
        if self._cleanup_task:
            self._cleanup_task.join(timeout=5)
        
        # Persistence
        if self.enable_persistence:
            self._save_all()
        
        logger.info("🛑 Cache Manager stopped")
    
    # ==================== Persistence ====================
    
    def _persist_entry(self, entry: CacheEntry):
        """ذخیره یک entry در دیسک"""
        try:
            filepath = self.persistence_path / f"{self._hash_key(entry.key)}.pkl"
            
            with open(filepath, 'wb') as f:
                pickle.dump(entry, f)
        
        except Exception as e:
            logger.error(f"❌ Failed to persist entry {entry.key}: {e}")
    
    def _delete_persisted_entry(self, key: str):
        """حذف entry از دیسک"""
        try:
            filepath = self.persistence_path / f"{self._hash_key(key)}.pkl"
            
            if filepath.exists():
                filepath.unlink()
        
        except Exception as e:
            logger.error(f"❌ Failed to delete persisted entry {key}: {e}")
    
    def _save_all(self):
        """ذخیره تمام کش در دیسک"""
        logger.info("💾 Saving cache to disk...")
        
        with self._lock:
            for entry in self._cache.values():
                self._persist_entry(entry)
        
        logger.info("✅ Cache saved")
    
    def _load_all(self):
        """بارگذاری کش از دیسک"""
        if not self.persistence_path.exists():
            return
        
        logger.info("📂 Loading cache from disk...")
        
        loaded_count = 0
        
        for filepath in self.persistence_path.glob("*.pkl"):
            try:
                with open(filepath, 'rb') as f:
                    entry = pickle.load(f)
                
                # بررسی انقضا
                if not entry.is_expired():
                    self._cache[entry.key] = entry
                    self._namespaces[entry.namespace].add(entry.key)
                    
                    for tag in entry.tags:
                        self._tags[tag].add(entry.key)
                    
                    self.stats.total_size_bytes += entry.size_bytes
                    loaded_count += 1
                else:
                    filepath.unlink()
            
            except Exception as e:
                logger.error(f"❌ Failed to load {filepath}: {e}")
        
        logger.info(f"✅ Loaded {loaded_count} items from disk")
    
    def _hash_key(self, key: str) -> str:
        """ساخت hash برای نام فایل"""
        return hashlib.md5(key.encode()).hexdigest()
    
    # ==================== Statistics & Monitoring ====================
    
    def get_stats(self) -> Dict:
        """دریافت آمار کامل"""
        with self._lock:
            stats_dict = self.stats.to_dict()
            
            stats_dict.update({
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'utilization': round((len(self._cache) / self.max_size) * 100, 2) if self.max_size > 0 else 0,
                'namespaces_count': len(self._namespaces),
                'tags_count': len(self._tags),
                'enabled': self.enabled,
                'memory_utilization': round((self.stats.total_size_bytes / self.max_memory_bytes) * 100, 2) if self.max_memory_bytes > 0 else 0
            })
            
            return stats_dict
    
    def get_namespace_stats(self, namespace: str) -> Dict:
        """آمار یک namespace"""
        with self._lock:
            keys = self._namespaces.get(namespace, set())
            
            total_size = sum(
                self._cache[key].size_bytes
                for key in keys
                if key in self._cache
            )
            
            total_hits = sum(
                self._cache[key].hits
                for key in keys
                if key in self._cache
            )
            
            return {
                'namespace': namespace,
                'items_count': len(keys),
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'total_hits': total_hits
            }
    
    def get_top_items(self, limit: int = 10, 
                     sort_by: str = 'hits') -> List[Dict]:
        """آیتم‌های پربازدید یا بزرگ"""
        with self._lock:
            items = list(self._cache.values())
            
            if sort_by == 'hits':
                items.sort(key=lambda x: x.hits, reverse=True)
            elif sort_by == 'size':
                items.sort(key=lambda x: x.size_bytes, reverse=True)
            elif sort_by == 'age':
                items.sort(key=lambda x: x.get_age_seconds(), reverse=True)
            
            return [item.to_dict() for item in items[:limit]]
    
    def get_cache_report(self) -> str:
        """گزارش متنی کش"""
        stats = self.get_stats()
        top_items = self.get_top_items(5, sort_by='hits')
        
        report = "💾 **گزارش Cache**\n"
        report += "═" * 40 + "\n\n"
        
        # وضعیت
        status = "✅ فعال" if self.enabled else "❌ غیرفعال"
        report += f"**وضعیت:** {status}\n\n"
        
        # آمار کلی
        report += "**📊 آمار:**\n"
        report += f"├ اندازه: {stats['cache_size']}/{stats['max_size']}\n"
        report += f"├ استفاده: {stats['utilization']}%\n"
        report += f"├ حافظه: {stats['total_size_mb']} MB\n"
        report += f"└ Namespaces: {stats['namespaces_count']}\n\n"
        
        # Hit Rate
        report += "**🎯 عملکرد:**\n"
        report += f"├ Hit Rate: {stats['hit_rate']}%\n"
        report += f"├ Hits: {stats['hits']}\n"
        report += f"├ Misses: {stats['misses']}\n"
        report += f"├ Sets: {stats['sets']}\n"
        report += f"└ Evictions: {stats['evictions']}\n\n"
        
        # پربازدیدترین
        if top_items:
            report += "**🔥 پربازدیدترین:**\n"
            for i, item in enumerate(top_items[:3], 1):
                report += f"{i}. {item['hits']} hits - {item['key'][:30]}...\n"
        
        report += "\n" + "═" * 40
        
        return report
    
    def export_stats(self, filepath: str = "cache_stats.json") -> bool:
        """خروجی آمار به JSON"""
        try:
            stats = self.get_stats()
            top_items = self.get_top_items(20)
            
            data = {
                'exported_at': datetime.now().isoformat(),
                'statistics': stats,
                'top_items': top_items,
                'namespaces': [
                    self.get_namespace_stats(ns)
                    for ns in self._namespaces.keys()
                ]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Cache stats exported to: {filepath}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            return False


# ==================== Decorators ====================

def cached(ttl: Optional[int] = None, 
          namespace: str = "default",
          key_prefix: str = ""):
    """Decorator برای کش کردن نتیجه تابع"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # ساخت کلید کش
            cache_key = f"{key_prefix}{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # سعی در دریافت از کش
            from logger import get_logger
            logger_instance = get_logger(__name__)
            
            # فرض می‌کنیم cache_manager در context موجود است
            cache_manager = kwargs.pop('_cache_manager', None)
            
            if cache_manager:
                cached_value = cache_manager.get(cache_key, namespace=namespace)
                
                if cached_value is not None:
                    logger_instance.debug(
                        f"💾 Cache hit: {func.__name__}",
                        handler_name=func.__name__
                    )
                    return cached_value
            
            # اجرای تابع
            result = func(*args, **kwargs)
            
            # ذخیره در کش
            if cache_manager:
                cache_manager.set(
                    cache_key, 
                    result, 
                    ttl=ttl,
                    namespace=namespace
                )
                logger_instance.debug(
                    f"💾 Cache set: {func.__name__}",
                    handler_name=func.__name__
                )
            
            return result
        
        return wrapper
    return decorator


def cache_invalidate(namespace: str = "default", 
                    pattern: Optional[str] = None,
                    tag: Optional[str] = None):
    """Decorator برای invalidate کردن کش بعد از اجرا"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate کش
            cache_manager = kwargs.get('_cache_manager')
            
            if cache_manager:
                if tag:
                    cache_manager.invalidate_by_tag(tag)
                elif pattern:
                    cache_manager.invalidate_by_pattern(pattern, namespace)
                else:
                    cache_manager.clear(namespace)
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Invalidate کش
            cache_manager = kwargs.get('_cache_manager')
            
            if cache_manager:
                if tag:
                    cache_manager.invalidate_by_tag(tag)
                elif pattern:
                    cache_manager.invalidate_by_pattern(pattern, namespace)
                else:
                    cache_manager.clear(namespace)
            
            return result
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ==================== Specialized Cache Managers ====================

class QueryCacheManager(EnhancedCacheManager):
    """کش مخصوص کوئری‌های دیتابیس"""
    
    def __init__(self, **kwargs):
        # تنظیمات بهینه برای کوئری
        kwargs.setdefault('default_ttl', 300)  # 5 دقیقه
        kwargs.setdefault('max_size', 5000)
        kwargs.setdefault('namespace', 'queries')
        
        super().__init__(**kwargs)
        
        logger.info("✅ Query Cache Manager initialized")
    
    def cache_query(self, query: str, params: tuple, result: Any, 
                   ttl: Optional[int] = None):
        """کش کردن نتیجه کوئری"""
        import hashlib
        
        # ساخت کلید یکتا از کوئری و پارامترها
        query_hash = hashlib.md5(
            f"{query}:{str(params)}".encode()
        ).hexdigest()
        
        cache_key = f"query:{query_hash}"
        
        return self.set(
            cache_key, 
            result, 
            ttl=ttl,
            namespace='queries',
            tags={'database', 'query'}
        )
    
    def get_query(self, query: str, params: tuple) -> Optional[Any]:
        """دریافت نتیجه کوئری از کش"""
        import hashlib
        
        query_hash = hashlib.md5(
            f"{query}:{str(params)}".encode()
        ).hexdigest()
        
        cache_key = f"query:{query_hash}"
        
        return self.get(cache_key, namespace='queries')
    
    def invalidate_table(self, table_name: str):
        """Invalidate تمام کوئری‌های مربوط به یک جدول"""
        return self.invalidate_by_pattern(table_name, namespace='queries')


class UserSessionCache(EnhancedCacheManager):
    """کش مخصوص session های کاربر"""
    
    def __init__(self, **kwargs):
        # تنظیمات بهینه برای session
        kwargs.setdefault('default_ttl', 1800)  # 30 دقیقه
        kwargs.setdefault('max_size', 10000)
        
        super().__init__(**kwargs)
        
        logger.info("✅ User Session Cache initialized")
    
    def set_user_session(self, user_id: int, data: Dict, 
                        ttl: Optional[int] = None):
        """ذخیره session کاربر"""
        return self.set(
            f"user:{user_id}",
            data,
            ttl=ttl,
            namespace='sessions',
            tags={f'user:{user_id}', 'session'}
        )
    
    def get_user_session(self, user_id: int) -> Optional[Dict]:
        """دریافت session کاربر"""
        return self.get(f"user:{user_id}", namespace='sessions')
    
    def delete_user_session(self, user_id: int):
        """حذف session کاربر"""
        return self.delete(f"user:{user_id}", namespace='sessions')
    
    def extend_user_session(self, user_id: int, seconds: int = 1800):
        """افزایش زمان session"""
        return self.extend_ttl(
            f"user:{user_id}", 
            seconds, 
            namespace='sessions'
        )


class ProductCacheManager(EnhancedCacheManager):
    """کش مخصوص محصولات"""
    
    def __init__(self, **kwargs):
        # تنظیمات بهینه برای محصولات
        kwargs.setdefault('default_ttl', 600)  # 10 دقیقه
        kwargs.setdefault('max_size', 3000)
        
        super().__init__(**kwargs)
        
        logger.info("✅ Product Cache Manager initialized")
    
    def cache_product(self, product_id: int, product_data: Dict,
                     ttl: Optional[int] = None):
        """کش کردن محصول"""
        return self.set(
            f"product:{product_id}",
            product_data,
            ttl=ttl,
            namespace='products',
            tags={'product', f'product:{product_id}'}
        )
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        """دریافت محصول از کش"""
        return self.get(f"product:{product_id}", namespace='products')
    
    def cache_product_list(self, category: str, products: List[Dict],
                          ttl: Optional[int] = None):
        """کش کردن لیست محصولات"""
        return self.set(
            f"products:category:{category}",
            products,
            ttl=ttl,
            namespace='products',
            tags={'product_list', f'category:{category}'}
        )
    
    def get_product_list(self, category: str) -> Optional[List[Dict]]:
        """دریافت لیست محصولات"""
        return self.get(
            f"products:category:{category}",
            namespace='products'
        )
    
    def invalidate_product(self, product_id: int):
        """Invalidate یک محصول"""
        self.delete(f"product:{product_id}", namespace='products')
        self.invalidate_by_tag(f'product:{product_id}')
    
    def invalidate_category(self, category: str):
        """Invalidate محصولات یک دسته"""
        self.invalidate_by_tag(f'category:{category}')


# ==================== Cache Factory ====================

class CacheFactory:
    """کارخانه ساخت Cache Manager"""
    
    _instances: Dict[str, EnhancedCacheManager] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_cache(cls, cache_type: str = 'default', **kwargs) -> EnhancedCacheManager:
        """دریافت یا ساخت Cache Manager"""
        
        with cls._lock:
            if cache_type in cls._instances:
                return cls._instances[cache_type]
            
            # ساخت بر اساس نوع
            if cache_type == 'query':
                cache = QueryCacheManager(**kwargs)
            elif cache_type == 'session':
                cache = UserSessionCache(**kwargs)
            elif cache_type == 'product':
                cache = ProductCacheManager(**kwargs)
            else:
                cache = EnhancedCacheManager(**kwargs)
            
            cls._instances[cache_type] = cache
            return cache
    
    @classmethod
    def get_all_caches(cls) -> Dict[str, EnhancedCacheManager]:
        """دریافت تمام Cache Manager ها"""
        return cls._instances.copy()
    
    @classmethod
    def clear_all_caches(cls):
        """پاک کردن تمام کش‌ها"""
        for cache_type, cache in cls._instances.items():
            cache.clear()
            logger.info(f"🧹 Cleared cache: {cache_type}")
    
    @classmethod
    def stop_all_caches(cls):
        """توقف تمام Cache Manager ها"""
        for cache_type, cache in cls._instances.items():
            cache.stop()
            logger.info(f"🛑 Stopped cache: {cache_type}")


# ==================== Global Cache Manager ====================

# نمونه سراسری
_global_cache: Optional[EnhancedCacheManager] = None


def setup_cache(enabled: bool = CACHE_ENABLED,
               default_ttl: int = CACHE_DEFAULT_TTL,
               max_size: int = 10000) -> EnhancedCacheManager:
    """راه‌اندازی Cache Manager سراسری"""
    global _global_cache
    
    _global_cache = EnhancedCacheManager(
        enabled=enabled,
        default_ttl=default_ttl,
        max_size=max_size
    )
    
    return _global_cache


def get_cache() -> Optional[EnhancedCacheManager]:
    """دریافت Cache Manager سراسری"""
    if _global_cache is None:
        setup_cache()
    
    return _global_cache


# ==================== Cache Strategies ====================

class CacheStrategy:
    """استراتژی‌های کش"""
    
    @staticmethod
    def cache_aside(cache: EnhancedCacheManager, 
                   key: str,
                   loader: Callable[[], Any],
                   ttl: Optional[int] = None,
                   namespace: str = "default") -> Any:
        """الگوی Cache-Aside (Lazy Loading)"""
        
        # سعی در دریافت از کش
        value = cache.get(key, namespace=namespace)
        
        if value is not None:
            return value
        
        # اگر نبود، بارگذاری کن
        value = loader()
        
        # ذخیره در کش
        cache.set(key, value, ttl=ttl, namespace=namespace)
        
        return value
    
    @staticmethod
    def write_through(cache: EnhancedCacheManager,
                     key: str,
                     value: Any,
                     writer: Callable[[Any], None],
                     ttl: Optional[int] = None,
                     namespace: str = "default"):
        """الگوی Write-Through (نوشتن در کش و دیتابیس)"""
        
        # نوشتن در دیتابیس
        writer(value)
        
        # نوشتن در کش
        cache.set(key, value, ttl=ttl, namespace=namespace)
    
    @staticmethod
    def write_behind(cache: EnhancedCacheManager,
                    key: str,
                    value: Any,
                    writer: Callable[[Any], None],
                    ttl: Optional[int] = None,
                    namespace: str = "default"):
        """الگوی Write-Behind (فقط در کش، بعداً در دیتابیس)"""
        
        # نوشتن فوری در کش
        cache.set(key, value, ttl=ttl, namespace=namespace)
        
        # نوشتن async در دیتابیس (در background)
        threading.Thread(
            target=writer,
            args=(value,),
            daemon=True
        ).start()
    
    @staticmethod
    def refresh_ahead(cache: EnhancedCacheManager,
                     key: str,
                     loader: Callable[[], Any],
                     ttl: int,
                     refresh_threshold: float = 0.8,
                     namespace: str = "default") -> Any:
        """الگوی Refresh-Ahead (تازه‌سازی پیش از انقضا)"""
        
        value = cache.get(key, namespace=namespace)
        
        if value is not None:
            # بررسی نیاز به تازه‌سازی
            full_key = cache._make_key(key, namespace)
            entry = cache._cache.get(full_key)
            
            if entry:
                ttl_remaining = entry.get_ttl_remaining()
                
                if ttl_remaining and ttl_remaining < (ttl * (1 - refresh_threshold)):
                    # تازه‌سازی async
                    def refresh():
                        new_value = loader()
                        cache.set(key, new_value, ttl=ttl, namespace=namespace)
                    
                    threading.Thread(target=refresh, daemon=True).start()
            
            return value
        
        # اگر نبود، بارگذاری کن
        value = loader()
        cache.set(key, value, ttl=ttl, namespace=namespace)
        
        return value


# ==================== Helper Functions ====================

def create_cache_manager(cache_type: str = 'default', **kwargs) -> EnhancedCacheManager:
    """ساخت Cache Manager"""
    return CacheFactory.get_cache(cache_type, **kwargs)


def format_cache_size(size_bytes: int) -> str:
    """فرمت کردن سایز کش"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


# ==================== Cache Monitoring Integration ====================

class CacheMonitor:
    """مانیتورینگ کش"""
    
    def __init__(self, cache: EnhancedCacheManager):
        self.cache = cache
    
    def get_health_status(self) -> Dict:
        """وضعیت سلامت کش"""
        stats = self.cache.get_stats()
        
        status = "ok"
        issues = []
        
        # بررسی Hit Rate
        if stats['hit_rate'] < 50:
            status = "warning"
            issues.append("Low cache hit rate")
        
        # بررسی استفاده
        if stats['utilization'] > 90:
            status = "warning"
            issues.append("Cache nearly full")
        
        if stats['utilization'] >= 100:
            status = "error"
            issues.append("Cache is full")
        
        # بررسی eviction
        if stats['evictions'] > stats['sets'] * 0.3:
            status = "warning"
            issues.append("High eviction rate")
        
        return {
            'status': status,
            'enabled': self.cache.enabled,
            'hit_rate': stats['hit_rate'],
            'utilization': stats['utilization'],
            'cache_size': stats['cache_size'],
            'memory_mb': stats['total_size_mb'],
            'issues': issues
        }
    
    def get_metrics_for_monitoring(self) -> Dict:
        """متریک‌ها برای سیستم مانیتورینگ"""
        stats = self.cache.get_stats()
        health = self.get_health_status()
        
        return {
            'cache.hit_rate': stats['hit_rate'],
            'cache.miss_rate': stats['miss_rate'],
            'cache.size': stats['cache_size'],
            'cache.utilization': stats['utilization'],
            'cache.memory_mb': stats['total_size_mb'],
            'cache.evictions': stats['evictions'],
            'cache.health_status': health['status']
        }


# ==================== Example Usage ====================

def example_usage():
    """مثال استفاده"""
    
    # 1. ساخت Cache Manager
    cache = EnhancedCacheManager(
        enabled=True,
        default_ttl=300,
        max_size=1000
    )
    
    # 2. ذخیره در کش
    cache.set('user:123', {'name': 'Ali', 'age': 25}, ttl=600)
    
    # 3. دریافت از کش
    user = cache.get('user:123')
    print(f"User: {user}")
    
    # 4. استفاده از namespace
    cache.set('product:1', {'name': 'مانتو'}, namespace='products')
    
    # 5. استفاده از tags
    cache.set(
        'order:100',
        {'user_id': 123, 'total': 50000},
        tags={'user:123', 'orders'}
    )
    
    # 6. Invalidate با tag
    cache.invalidate_by_tag('user:123')
    
    # 7. آمار
    stats = cache.get_stats()
    print(f"Hit Rate: {stats['hit_rate']}%")
    
    # 8. گزارش
    print(cache.get_cache_report())
    
    # 9. توقف
    cache.stop()


if __name__ == "__main__":
    example_usage()


logger.info("✅ Enhanced Cache Manager module loaded")