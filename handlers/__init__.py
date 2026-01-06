"""
Handlers Package
"""

from .user import (
    start_handler,
    help_handler,
    setup_user_handlers
)

from .order import (
    order_callback_handler,
    receipt_handler
)

# اگه inline handler داری
try:
    from .inline import (
        search_inline_handler,
        chosen_inline_result_handler
    )
except ImportError:
    search_inline_handler = None
    chosen_inline_result_handler = None

__all__ = [
    'start_handler',
    'help_handler',
    'setup_user_handlers',
    'order_callback_handler',
    'receipt_handler',
    'search_inline_handler',
    'chosen_inline_result_handler',
]
