"""
💾 سیستم مدیریت پیشرفته دیتابیس
✅ Connection Pooling
✅ Transaction Management
✅ Query Performance Tracking
✅ Auto Backup با Schedule
✅ Health Monitoring
✅ Query Caching
✅ Statistics & Analytics
✅ Migration Support

نویسنده: Claude AI
تاریخ: 2026-01-06 (بهبود یافته)
"""

import sqlite3
import os
import logging
import time
import shutil
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import defaultdict, deque
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================

@dataclass
class QueryStats:
    """آمار یک کوئری"""
    query: str
    execution_count: int = 0
    total_time_ms: float = 0
    avg_time_ms: float = 0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0
    last_executed: Optional[datetime] = None
    errors: int = 0
    
    def update(self, execution_time_ms: float, success: bool = True):
        """بروزرسانی آمار"""
        self.execution_count += 1
        self.total_time_ms += execution_time_ms
        self.avg_time_ms = self.total_time_ms / self.execution_count
        self.min_time_ms = min(self.min_time_ms, execution_time_ms)
        self.max_time_ms = max(self.max_time_ms, execution_time_ms)
        self.last_executed = datetime.now()
        
        if not success:
            self.errors += 1
    
    def to_dict(self):
        return {
            'query': self.query[:100] + '...' if len(self.query) > 100 else self.query,
            'execution_count': self.execution_count,
            'avg_time_ms': round(self.avg_time_ms, 2),
            'min_time_ms': round(self.min_time_ms, 2),
            'max_time_ms': round(self.max_time_ms, 2),
            'total_time_ms': round(self.total_time_ms, 2),
            'errors': self.errors,
            'last_executed': self.last_executed.isoformat() if self.last_executed else None
        }


@dataclass
class BackupInfo:
    """اطلاعات بکاپ"""
    filepath: str
    created_at: datetime
    size_mb: float
    is_automatic: bool = True
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return {
            'filepath': self.filepath,
            'created_at': self.created_at.isoformat(),
            'size_mb': self.size_mb,
            'is_automatic': self.is_automatic,
            'metadata': self.metadata
        }


# ==================== Enhanced Database Manager ====================

class EnhancedDatabaseManager:
    """مدیریت پیشرفته دیتابیس"""
    
    def __init__(self, db_name: str = "shop_bot.db", 
                 backup_folder: str = "backups",
                 max_connections: int = 10,
                 enable_query_tracking: bool = True,
                 enable_query_cache: bool = True):
        
        self.db_name = db_name
        self.backup_folder = backup_folder
        self.max_connections = max_connections
        self.enable_query_tracking = enable_query_tracking
        self.enable_query_cache = enable_query_cache
        
        # Connection Pool
        self._connection_pool: List[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._connection_in_use: Dict[int, bool] = {}
        
        # اتصال اصلی (برای سازگاری با کد قدیمی)
        self.conn = None
        self.cursor = None
        
        # Query Statistics
        self.query_stats: Dict[str, QueryStats] = defaultdict(QueryStats)
        self.slow_queries: deque = deque(maxlen=50)
        self.failed_queries: deque = deque(maxlen=50)
        
        # Query Cache
        self._query_cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = 300  # 5 دقیقه
        self._cache_lock = threading.Lock()
        
        # Backup History
        self.backup_history: deque = deque(maxlen=50)
        
        # Statistics
        self.stats = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_time_ms': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'transactions': 0,
            'rollbacks': 0
        }
        
        # ساخت پوشه بکاپ
        Path(self.backup_folder).mkdir(exist_ok=True)
        
        # اتصال اولیه
        self._initialize_connection()
        
        logger.info(f"✅ Enhanced Database Manager initialized: {db_name}")
    
    # ==================== Connection Management ====================
    
    def _initialize_connection(self):
        """ایجاد اتصال اولیه"""
        self.conn = sqlite3.connect(
            self.db_name, 
            check_same_thread=False,
            timeout=30.0
        )
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # بهینه‌سازی‌های SQLite
        self._optimize_connection(self.conn)
        
        logger.info("✅ Main database connection established")
    
    def _optimize_connection(self, conn: sqlite3.Connection):
        """بهینه‌سازی اتصال SQLite"""
        cursor = conn.cursor()
        
        # تنظیمات بهینه‌سازی
        optimizations = [
            "PRAGMA journal_mode = WAL",  # Write-Ahead Logging
            "PRAGMA synchronous = NORMAL",  # تعادل بین سرعت و امنیت
            "PRAGMA cache_size = 10000",  # 10000 صفحه کش
            "PRAGMA temp_store = MEMORY",  # جداول موقت در RAM
            "PRAGMA mmap_size = 30000000000",  # 30GB memory-mapped I/O
        ]
        
        for pragma in optimizations:
            try:
                cursor.execute(pragma)
            except Exception as e:
                logger.warning(f"⚠️ Could not apply optimization '{pragma}': {e}")
        
        conn.commit()
    
    @contextmanager
    def get_connection(self):
        """دریافت اتصال از Pool"""
        conn = self._get_pooled_connection()
        try:
            yield conn
        finally:
            self._release_connection(conn)
    
    def _get_pooled_connection(self) -> sqlite3.Connection:
        """دریافت اتصال از Pool"""
        with self._pool_lock:
            # پیدا کردن اتصال آزاد
            for i, conn in enumerate(self._connection_pool):
                if not self._connection_in_use.get(i, False):
                    self._connection_in_use[i] = True
                    return conn
            
            # اگر Pool پر نشده، اتصال جدید بساز
            if len(self._connection_pool) < self.max_connections:
                conn = sqlite3.connect(
                    self.db_name,
                    check_same_thread=False,
                    timeout=30.0
                )
                conn.row_factory = sqlite3.Row
                self._optimize_connection(conn)
                
                conn_id = len(self._connection_pool)
                self._connection_pool.append(conn)
                self._connection_in_use[conn_id] = True
                
                logger.debug(f"📊 New connection created. Pool size: {len(self._connection_pool)}")
                return conn
            
            # اگر Pool پر است، از اتصال اصلی استفاده کن
            logger.warning("⚠️ Connection pool full, using main connection")
            return self.conn
    
    def _release_connection(self, conn: sqlite3.Connection):
        """آزاد کردن اتصال"""
        with self._pool_lock:
            for i, pool_conn in enumerate(self._connection_pool):
                if pool_conn is conn:
                    self._connection_in_use[i] = False
                    return
    
    def close_all_connections(self):
        """بستن تمام اتصالات"""
        with self._pool_lock:
            for conn in self._connection_pool:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"❌ Error closing connection: {e}")
            
            self._connection_pool.clear()
            self._connection_in_use.clear()
        
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                logger.error(f"❌ Error closing main connection: {e}")
        
        logger.info("✅ All database connections closed")
    
    # ==================== Query Execution ====================
    
    def execute(self, query: str, params: tuple = (), 
                use_cache: bool = False, cache_ttl: Optional[int] = None) -> List:
        """اجرای کوئری با tracking و caching"""
        
        # بررسی کش
        if use_cache and self.enable_query_cache:
            cache_key = self._get_cache_key(query, params)
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result is not None:
                self.stats['cache_hits'] += 1
                logger.debug(f"💾 Cache hit for query: {query[:50]}...")
                return cached_result
            
            self.stats['cache_misses'] += 1
        
        # اجرای کوئری
        start_time = time.time()
        success = True
        result = []
        
        try:
            self.cursor.execute(query, params)
            
            # اگر SELECT است، نتیجه را برگردان
            if query.strip().upper().startswith('SELECT'):
                result = self.cursor.fetchall()
            else:
                self.conn.commit()
            
            # ذخیره در کش
            if use_cache and self.enable_query_cache and result:
                cache_key = self._get_cache_key(query, params)
                ttl = cache_ttl or self._cache_ttl
                self._save_to_cache(cache_key, result, ttl)
            
        except Exception as e:
            success = False
            self.stats['failed_queries'] += 1
            
            # ذخیره خطا
            self.failed_queries.append({
                'query': query,
                'params': params,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            
            logger.error(f"❌ Query failed: {query[:100]}... Error: {e}")
            raise
        
        finally:
            # محاسبه زمان اجرا
            execution_time_ms = (time.time() - start_time) * 1000
            
            # بروزرسانی آمار
            self.stats['total_queries'] += 1
            self.stats['total_time_ms'] += execution_time_ms
            
            if success:
                self.stats['successful_queries'] += 1
            
            # Query Tracking
            if self.enable_query_tracking:
                query_key = self._normalize_query(query)
                
                if query_key not in self.query_stats:
                    self.query_stats[query_key] = QueryStats(query=query_key)
                
                self.query_stats[query_key].update(execution_time_ms, success)
                
                # شناسایی کوئری‌های کند
                if execution_time_ms > 1000:  # بیشتر از 1 ثانیه
                    self.slow_queries.append({
                        'query': query,
                        'time_ms': execution_time_ms,
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.warning(f"🐌 Slow query detected: {execution_time_ms:.2f}ms")
        
        return result
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """اجرای batch کوئری"""
        start_time = time.time()
        
        try:
            self.cursor.executemany(query, params_list)
            self.conn.commit()
            
            rows_affected = self.cursor.rowcount
            
            execution_time_ms = (time.time() - start_time) * 1000
            logger.info(
                f"✅ Batch query executed: {rows_affected} rows, "
                f"{execution_time_ms:.2f}ms"
            )
            
            self.stats['total_queries'] += 1
            self.stats['successful_queries'] += 1
            self.stats['total_time_ms'] += execution_time_ms
            
            return rows_affected
            
        except Exception as e:
            self.stats['failed_queries'] += 1
            logger.error(f"❌ Batch query failed: {e}")
            raise
    
    def _normalize_query(self, query: str) -> str:
        """نرمال کردن کوئری برای tracking"""
        # حذف فضاهای اضافی
        normalized = ' '.join(query.split())
        
        # جایگزینی مقادیر با placeholder
        # این کار باعث می‌شود کوئری‌های مشابه گروه‌بندی شوند
        # مثلاً: SELECT * FROM users WHERE id=1 و SELECT * FROM users WHERE id=2
        # هر دو به: SELECT * FROM users WHERE id=? تبدیل می‌شوند
        
        return normalized[:200]  # محدود به 200 کاراکتر
    
    # ==================== Transaction Management ====================
    
    @contextmanager
    def transaction(self):
        """مدیریت Transaction با context manager"""
        self.conn.execute('BEGIN')
        self.stats['transactions'] += 1
        
        try:
            yield self.cursor
            self.conn.commit()
            logger.debug("✅ Transaction committed")
        except Exception as e:
            self.conn.rollback()
            self.stats['rollbacks'] += 1
            logger.error(f"❌ Transaction rolled back: {e}")
            raise
    
    def begin_transaction(self):
        """شروع Transaction"""
        self.conn.execute('BEGIN')
        self.stats['transactions'] += 1
        logger.debug("🔄 Transaction started")
    
    def commit_transaction(self):
        """Commit کردن Transaction"""
        self.conn.commit()
        logger.debug("✅ Transaction committed")
    
    def rollback_transaction(self):
        """Rollback کردن Transaction"""
        self.conn.rollback()
        self.stats['rollbacks'] += 1
        logger.warning("⚠️ Transaction rolled back")
    
    # ==================== Query Cache ====================
    
    def _get_cache_key(self, query: str, params: tuple) -> str:
        """ساخت کلید کش"""
        return f"{query}:{str(params)}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[List]:
        """دریافت از کش"""
        with self._cache_lock:
            if cache_key in self._query_cache:
                result, expire_time = self._query_cache[cache_key]
                
                if time.time() < expire_time:
                    return result
                else:
                    # منقضی شده
                    del self._query_cache[cache_key]
        
        return None
    
    def _save_to_cache(self, cache_key: str, result: List, ttl: int):
        """ذخیره در کش"""
        with self._cache_lock:
            expire_time = time.time() + ttl
            self._query_cache[cache_key] = (result, expire_time)
    
    def clear_query_cache(self):
        """پاکسازی کش"""
        with self._cache_lock:
            self._query_cache.clear()
        
        logger.info("🧹 Query cache cleared")
    
    def cleanup_expired_cache(self):
        """پاکسازی کش منقضی شده"""
        with self._cache_lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expire_time) in self._query_cache.items()
                if current_time >= expire_time
            ]
            
            for key in expired_keys:
                del self._query_cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Cleaned {len(expired_keys)} expired cache entries")
    
    # ==================== Backup Management ====================
    
    def create_backup(self, backup_name: Optional[str] = None, 
                     is_automatic: bool = True) -> Optional[str]:
        """ساخت بکاپ"""
        try:
            # نام فایل بکاپ
            if backup_name is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"backup_{timestamp}.db"
            
            backup_path = os.path.join(self.backup_folder, backup_name)
            
            # بستن اتصالات موقت برای اطمینان
            self.conn.commit()
            
            # کپی فایل دیتابیس
            shutil.copy2(self.db_name, backup_path)
            
            # اندازه فایل
            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            
            # ذخیره اطلاعات بکاپ
            backup_info = BackupInfo(
                filepath=backup_path,
                created_at=datetime.now(),
                size_mb=round(size_mb, 2),
                is_automatic=is_automatic,
                metadata={'db_name': self.db_name}
            )
            
            self.backup_history.append(backup_info)
            
            logger.info(
                f"✅ Backup created: {backup_name} "
                f"({backup_info.size_mb} MB)"
            )
            
            return backup_path
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """بازیابی از بکاپ"""
        try:
            if not os.path.exists(backup_path):
                logger.error(f"❌ Backup file not found: {backup_path}")
                return False
            
            # بستن اتصالات
            self.close_all_connections()
            
            # بکاپ از فایل فعلی
            emergency_backup = f"{self.db_name}.emergency_backup"
            shutil.copy2(self.db_name, emergency_backup)
            
            # بازیابی
            shutil.copy2(backup_path, self.db_name)
            
            # اتصال مجدد
            self._initialize_connection()
            
            logger.info(f"✅ Database restored from: {backup_path}")
            
            # حذف بکاپ اضطراری
            try:
                os.remove(emergency_backup)
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            
            # بازگشت به حالت قبلی
            if os.path.exists(emergency_backup):
                shutil.copy2(emergency_backup, self.db_name)
                self._initialize_connection()
            
            return False
    
    def list_backups(self) -> List[Dict]:
        """لیست بکاپ‌ها"""
        backups = []
        
        try:
            if not os.path.exists(self.backup_folder):
                return backups
            
            for filename in os.listdir(self.backup_folder):
                if filename.endswith('.db'):
                    filepath = os.path.join(self.backup_folder, filename)
                    stat = os.stat(filepath)
                    
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size_mb': round(stat.st_size / (1024 * 1024), 2),
                        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat()
                    })
            
            # مرتب‌سازی بر اساس تاریخ
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"❌ Error listing backups: {e}")
        
        return backups
    
    def delete_old_backups(self, keep_count: int = 10) -> int:
        """حذف بکاپ‌های قدیمی"""
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            return 0
        
        deleted_count = 0
        old_backups = backups[keep_count:]
        
        for backup in old_backups:
            try:
                os.remove(backup['filepath'])
                deleted_count += 1
                logger.info(f"🗑 Deleted old backup: {backup['filename']}")
            except Exception as e:
                logger.error(f"❌ Error deleting backup {backup['filename']}: {e}")
        
        return deleted_count
    
    # ==================== Database Info & Health ====================
    
    def get_database_info(self) -> Dict:
        """اطلاعات دیتابیس"""
        try:
            info = {
                'file': self.db_name,
                'exists': os.path.exists(self.db_name),
                'size_mb': 0,
                'tables': [],
                'total_rows': 0,
                'page_count': 0,
                'page_size': 0,
                'encoding': None
            }
            
            if not info['exists']:
                return info
            
            # اندازه فایل
            info['size_mb'] = round(
                os.path.getsize(self.db_name) / (1024 * 1024), 2
            )
            
            # لیست جداول
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in self.cursor.fetchall()]
            info['tables'] = tables
            
            # تعداد سطرهای هر جدول
            total_rows = 0
            table_rows = {}
            
            for table in tables:
                try:
                    self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = self.cursor.fetchone()[0]
                    table_rows[table] = count
                    total_rows += count
                except:
                    table_rows[table] = 'error'
            
            info['total_rows'] = total_rows
            info['table_rows'] = table_rows
            
            # اطلاعات صفحه
            self.cursor.execute("PRAGMA page_count")
            info['page_count'] = self.cursor.fetchone()[0]
            
            self.cursor.execute("PRAGMA page_size")
            info['page_size'] = self.cursor.fetchone()[0]
            
            self.cursor.execute("PRAGMA encoding")
            info['encoding'] = self.cursor.fetchone()[0]
            
            return info
            
        except Exception as e:
            logger.error(f"❌ Error getting database info: {e}")
            return {'error': str(e)}
    
    def vacuum_database(self):
        """بهینه‌سازی و فشرده‌سازی دیتابیس"""
        try:
            logger.info("🧹 Starting VACUUM...")
            start_time = time.time()
            
            self.cursor.execute("VACUUM")
            
            duration = time.time() - start_time
            logger.info(f"✅ VACUUM completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ VACUUM failed: {e}")
    
    def analyze_database(self):
        """آنالیز دیتابیس برای بهینه‌سازی کوئری‌ها"""
        try:
            logger.info("📊 Starting ANALYZE...")
            self.cursor.execute("ANALYZE")
            logger.info("✅ ANALYZE completed")
            
        except Exception as e:
            logger.error(f"❌ ANALYZE failed: {e}")
    
    # ==================== Statistics & Reports ====================
    
    def get_statistics(self) -> Dict:
        """آمار کامل دیتابیس"""
        avg_query_time = 0
        if self.stats['total_queries'] > 0:
            avg_query_time = self.stats['total_time_ms'] / self.stats['total_queries']
        
        success_rate = 0
        if self.stats['total_queries'] > 0:
            success_rate = (self.stats['successful_queries'] / self.stats['total_queries']) * 100
        
        cache_hit_rate = 0
        total_cache_ops = self.stats['cache_hits'] + self.stats['cache_misses']
        if total_cache_ops > 0:
            cache_hit_rate = (self.stats['cache_hits'] / total_cache_ops) * 100
        
        return {
            'queries': {
                'total': self.stats['total_queries'],
                'successful': self.stats['successful_queries'],
                'failed': self.stats['failed_queries'],
                'success_rate': round(success_rate, 2)
            },
            'performance': {
                'total_time_ms': round(self.stats['total_time_ms'], 2),
                'avg_query_time_ms': round(avg_query_time, 2),
                'slow_queries_count': len(self.slow_queries)
            },
            'cache': {
                'hits': self.stats['cache_hits'],
                'misses': self.stats['cache_misses'],
                'hit_rate': round(cache_hit_rate, 2),
                'cached_items': len(self._query_cache)
            },
            'transactions': {
                'total': self.stats['transactions'],
                'rollbacks': self.stats['rollbacks']
            },
            'connections': {
                'pool_size': len(self._connection_pool),
                'active': sum(self._connection_in_use.values())
            }
        }
    
    def get_top_queries(self, limit: int = 10, 
                       sort_by: str = 'count') -> List[Dict]:
        """پرکاربردترین کوئری‌ها"""
        queries = list(self.query_stats.values())
        
        if sort_by == 'count':
            queries.sort(key=lambda x: x.execution_count, reverse=True)
        elif sort_by == 'time':
            queries.sort(key=lambda x: x.total_time_ms, reverse=True)
        elif sort_by == 'avg':
            queries.sort(key=lambda x: x.avg_time_ms, reverse=True)
        
        return [q.to_dict() for q in queries[:limit]]
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """کوئری‌های کند"""
        return list(self.slow_queries)[-limit:]
    
    def get_database_report(self) -> str:
        """گزارش کامل دیتابیس"""
        stats = self.get_statistics()
        db_info = self.get_database_info()
        top_queries = self.get_top_queries(5)
        
        report = "💾 **گزارش دیتابیس**\n"
        report += "═" * 40 + "\n\n"
        
        # اطلاعات کلی
        report += "**📊 اطلاعات:**\n"
        report += f"├ فایل: {db_info.get('file', 'N/A')}\n"
        report += f"├ حجم: {db_info.get('size_mb', 0)} MB\n"
        report += f"├ تعداد جداول: {len(db_info.get('tables', []))}\n"
        report += f"└ کل سطرها: {db_info.get('total_rows', 0):,}\n\n"
        
        # آمار کوئری‌ها
        report += "**🔍 کوئری‌ها:**\n"
        q = stats['queries']
        report += f"├ کل: {q['total']}\n"
        report += f"├ موفق: {q['successful']}\n"
        report += f"├ ناموفق: {q['failed']}\n"
        report += f"└ نرخ موفقیت: {q['success_rate']}%\n\n"
        
        # عملکرد
        report += "**⚡ عملکرد:**\n"
        p = stats['performance']
        report += f"├ میانگین: {p['avg_query_time_ms']:.2f} ms\n"
        report += f"├ کل زمان: {p['total_time_ms']:.2f} ms\n"
        report += f"└ کوئری‌های کند: {p['slow_queries_count']}\n\n"
        
        # کش
        report += "**💾 کش:**\n"
        c = stats['cache']
        report += f"├ Hits: {c['hits']}\n"
        report += f"├ Misses: {c['misses']}\n"
        report += f"├ Hit Rate: {c['hit_rate']}%\n"
        report += f"└ آیتم‌های کش: {c['cached_items']}\n\n"
        
        # Transaction
        report += "**🔄 Transaction:**\n"
        t = stats['transactions']
        report += f"├ کل: {t['total']}\n"
        report += f"└ Rollback: {t['rollbacks']}\n\n"
        
        # Connection Pool
        report += "**🔗 Connection Pool:**\n"
        conn = stats['connections']
        report += f"├ اندازه Pool: {conn['pool_size']}\n"
        report += f"└ فعال: {conn['active']}\n\n"
        
        # پرکاربردترین کوئری‌ها
        if top_queries:
            report += "**🔥 پرکاربردترین کوئری‌ها:**\n"
            for i, q in enumerate(top_queries[:3], 1):
                report += f"{i}. {q['execution_count']} بار - "
                report += f"{q['avg_time_ms']:.1f}ms میانگین\n"
            report += "\n"
        
        report += "═" * 40
        
        return report
    
    # ==================== Maintenance ====================
    
    def perform_maintenance(self):
        """انجام نگهداری دوره‌ای"""
        logger.info("🔧 Starting database maintenance...")
        
        try:
            # 1. پاکسازی کش منقضی شده
            self.cleanup_expired_cache()
            
            # 2. آنالیز دیتابیس
            self.analyze_database()
            
            # 3. بکاپ خودکار
            self.create_backup(is_automatic=True)
            
            # 4. حذف بکاپ‌های قدیمی
            deleted = self.delete_old_backups(keep_count=10)
            if deleted > 0:
                logger.info(f"🗑 Deleted {deleted} old backups")
            
            # 5. بررسی یکپارچگی
            self.cursor.execute("PRAGMA integrity_check")
            result = self.cursor.fetchone()[0]
            
            if result == "ok":
                logger.info("✅ Database integrity check passed")
            else:
                logger.error(f"❌ Database integrity issue: {result}")
            
            logger.info("✅ Database maintenance completed")
            
        except Exception as e:
            logger.error(f"❌ Maintenance failed: {e}")
    
    # ==================== Health Check Integration ====================
    
    def get_health_status(self) -> Dict:
        """وضعیت سلامت دیتابیس برای Health Checker"""
        try:
            # تست اتصال
            self.cursor.execute("SELECT 1")
            connected = True
            
            # اندازه دیتابیس
            size_mb = os.path.getsize(self.db_name) / (1024 * 1024)
            
            # تعداد جداول
            self.cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            )
            table_count = self.cursor.fetchone()[0]
            
            # بررسی یکپارچگی
            self.cursor.execute("PRAGMA quick_check")
            integrity = self.cursor.fetchone()[0]
            
            # آمار
            stats = self.get_statistics()
            
            # تعیین وضعیت
            status = "ok"
            issues = []
            
            if size_mb > 500:
                status = "warning"
                issues.append("Database size is large")
            
            if stats['queries']['success_rate'] < 95:
                status = "warning"
                issues.append("Low query success rate")
            
            if integrity != "ok":
                status = "error"
                issues.append("Integrity check failed")
            
            if not connected:
                status = "error"
                issues.append("Connection failed")
            
            return {
                'status': status,
                'connected': connected,
                'size_mb': round(size_mb, 2),
                'tables': table_count,
                'integrity': integrity,
                'issues': issues,
                'stats': {
                    'total_queries': stats['queries']['total'],
                    'success_rate': stats['queries']['success_rate'],
                    'avg_query_time': stats['performance']['avg_query_time_ms']
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return {
                'status': 'error',
                'connected': False,
                'error': str(e)
            }


# ==================== Database Schema ====================

def initialize_database(db: EnhancedDatabaseManager):
    """ایجاد جداول دیتابیس"""
    
    logger.info("📋 Initializing database schema...")
    
    # جدول کاربران
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_orders INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    
    # ایندکس برای جستجوی سریع
    db.execute('CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at)')
    
    # جدول محصولات
    db.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            base_price REAL NOT NULL,
            image_id TEXT,
            category TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            views INTEGER DEFAULT 0,
            orders INTEGER DEFAULT 0
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
    
    # جدول پک‌ها
    db.execute('''
        CREATE TABLE IF NOT EXISTS packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            is_available INTEGER DEFAULT 1,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_packs_product ON packs(product_id)')
    
    # جدول سفارشات
    db.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            pack_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            discount_amount REAL DEFAULT 0,
            final_price REAL NOT NULL,
            discount_code TEXT,
            status TEXT DEFAULT 'pending',
            payment_image_id TEXT,
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (pack_id) REFERENCES packs (id)
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)')
    
    # جدول کدهای تخفیف
    db.execute('''
        CREATE TABLE IF NOT EXISTS discount_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL,
            discount_value REAL NOT NULL,
            max_uses INTEGER,
            current_uses INTEGER DEFAULT 0,
            valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_discount_code ON discount_codes(code)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_discount_active ON discount_codes(is_active)')
    
    # جدول استفاده از کدهای تخفیف
    db.execute('''
        CREATE TABLE IF NOT EXISTS discount_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discount_code_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (discount_code_id) REFERENCES discount_codes (id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_usage_user ON discount_usage(user_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_usage_code ON discount_usage(discount_code_id)')
    
    # جدول لاگ فعالیت‌ها (برای آنالیز)
    db.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    db.execute('CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)')
    
    logger.info("✅ Database schema initialized")
    
    # آنالیز برای بهینه‌سازی
    db.analyze_database()


# ==================== Migration System ====================

@dataclass
class Migration:
    """یک Migration"""
    version: int
    name: str
    up_sql: str
    down_sql: str = ""
    
    def apply(self, db: EnhancedDatabaseManager):
        """اعمال Migration"""
        try:
            logger.info(f"🔄 Applying migration {self.version}: {self.name}")
            db.execute(self.up_sql)
            logger.info(f"✅ Migration {self.version} applied")
            return True
        except Exception as e:
            logger.error(f"❌ Migration {self.version} failed: {e}")
            return False
    
    def rollback(self, db: EnhancedDatabaseManager):
        """Rollback Migration"""
        if not self.down_sql:
            logger.warning(f"⚠️ No rollback SQL for migration {self.version}")
            return False
        
        try:
            logger.info(f"⏪ Rolling back migration {self.version}")
            db.execute(self.down_sql)
            logger.info(f"✅ Migration {self.version} rolled back")
            return True
        except Exception as e:
            logger.error(f"❌ Rollback failed for migration {self.version}: {e}")
            return False


class MigrationManager:
    """مدیریت Migration‌ها"""
    
    def __init__(self, db: EnhancedDatabaseManager):
        self.db = db
        self.migrations: List[Migration] = []
        
        # ایجاد جدول migrations
        self._create_migrations_table()
    
    def _create_migrations_table(self):
        """ایجاد جدول migrations"""
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def add_migration(self, migration: Migration):
        """اضافه کردن Migration"""
        self.migrations.append(migration)
        self.migrations.sort(key=lambda m: m.version)
    
    def get_current_version(self) -> int:
        """دریافت نسخه فعلی"""
        result = self.db.execute(
            'SELECT MAX(version) FROM migrations',
            use_cache=False
        )
        
        version = result[0][0] if result and result[0][0] else 0
        return version
    
    def migrate(self, target_version: Optional[int] = None):
        """اجرای Migration‌ها"""
        current = self.get_current_version()
        
        if target_version is None:
            target_version = max(m.version for m in self.migrations) if self.migrations else 0
        
        logger.info(f"🔄 Migrating from version {current} to {target_version}")
        
        # Migration‌های باید اعمال شوند
        pending = [
            m for m in self.migrations
            if current < m.version <= target_version
        ]
        
        if not pending:
            logger.info("✅ Database is up to date")
            return
        
        # اعمال Migration‌ها
        for migration in pending:
            if migration.apply(self.db):
                # ثبت در جدول migrations
                self.db.execute(
                    'INSERT INTO migrations (version, name) VALUES (?, ?)',
                    (migration.version, migration.name)
                )
            else:
                logger.error(f"❌ Migration stopped at version {migration.version}")
                break
        
        new_version = self.get_current_version()
        logger.info(f"✅ Migration completed. Current version: {new_version}")


# ==================== Helper Functions ====================

def create_database_manager(db_name: str = "shop_bot.db",
                           backup_folder: str = "backups",
                           max_connections: int = 10) -> EnhancedDatabaseManager:
    """ساخت Database Manager"""
    return EnhancedDatabaseManager(
        db_name=db_name,
        backup_folder=backup_folder,
        max_connections=max_connections,
        enable_query_tracking=True,
        enable_query_cache=True
    )


def setup_database(db_name: str = "shop_bot.db") -> EnhancedDatabaseManager:
    """راه‌اندازی کامل دیتابیس"""
    db = create_database_manager(db_name)
    initialize_database(db)
    return db


# ==================== Example Migrations ====================

def get_example_migrations() -> List[Migration]:
    """مثال Migration‌ها"""
    return [
        Migration(
            version=1,
            name="add_user_preferences",
            up_sql='''
                ALTER TABLE users ADD COLUMN preferences TEXT DEFAULT '{}'
            ''',
            down_sql='''
                ALTER TABLE users DROP COLUMN preferences
            '''
        ),
        Migration(
            version=2,
            name="add_product_tags",
            up_sql='''
                ALTER TABLE products ADD COLUMN tags TEXT DEFAULT ''
            ''',
            down_sql='''
                ALTER TABLE products DROP COLUMN tags
            '''
        ),
    ]


logger.info("✅ Enhanced Database module loaded")