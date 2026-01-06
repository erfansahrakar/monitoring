"""
Wrapper file for handlers package
این فایل فقط از پوشه handlers import می‌کنه
"""

from handlers.user import (
    user_start as start_handler,
    contact_us as help_handler,
    handle_pack_selection,
    view_cart,
)

from handlers.order import (
    handle_receipt as receipt_handler,
    view_user_orders,
)

from handlers import setup_user_handlers

# Inline handlers (فعلا None)
search_inline_handler = None
chosen_inline_result_handler = None
order_callback_handler = None

__all__ = [
    'start_handler',
    'help_handler',
    'search_inline_handler',
    'chosen_inline_result_handler',
    'order_callback_handler',
    'receipt_handler',
    'setup_user_handlers',
]
