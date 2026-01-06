"""
Handlers Package - Simple Export
✅ FIX: تمام callback_data ها با keyboards.py هماهنگ شدند
"""

# User handlers
from .user import (
    user_start,
    contact_us,
    handle_pack_selection,
    view_cart,
    remove_from_cart,
    clear_cart,
    finalize_order_start,
    full_name_received,
    address_text_received,
    phone_number_received,
    confirm_user_info,
    edit_user_info_for_order,
    view_my_address,
    edit_address,
    handle_shipping_selection,
    final_confirm_order,
    final_edit_order
)

# Order handlers
from .order import (
    view_user_orders,
    handle_continue_payment,
    handle_delete_order,
    send_order_to_admin,
    view_pending_orders,
    confirm_order,
    reject_order,
    remove_item_from_order,
    reject_full_order,
    back_to_order_review,
    confirm_modified_order,
    handle_receipt,
    view_payment_receipts,
    confirm_payment,
    reject_payment
)

# Aliases
start_handler = user_start
help_handler = contact_us
receipt_handler = handle_receipt

# Setup function
def setup_user_handlers(application, db):
    """Setup all user-related handlers"""
    from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
    from states import FULL_NAME, ADDRESS_TEXT, PHONE_NUMBER
    
    # Start command
    application.add_handler(CommandHandler("start", user_start))
    
    # Help/Contact
    application.add_handler(CommandHandler("help", contact_us))
    application.add_handler(MessageHandler(filters.Regex("^📞 تماس با ما$"), contact_us))
    
    # Cart - 🆕 FIX: Pattern درست شد
    application.add_handler(CallbackQueryHandler(view_cart, pattern=r"^view_cart$"))
    application.add_handler(MessageHandler(filters.Regex("^🛒 سبد خرید$"), view_cart))
    application.add_handler(CallbackQueryHandler(remove_from_cart, pattern=r"^remove_cart:"))  # ✅ FIX
    application.add_handler(CallbackQueryHandler(clear_cart, pattern=r"^clear_cart$"))
    
    # Pack selection
    application.add_handler(CallbackQueryHandler(handle_pack_selection, pattern=r"^select_pack:"))
    
    # Orders
    application.add_handler(MessageHandler(filters.Regex("^📋 سفارشات من$"), view_user_orders))
    application.add_handler(CallbackQueryHandler(handle_continue_payment, pattern=r"^continue_payment:"))
    application.add_handler(CallbackQueryHandler(handle_delete_order, pattern=r"^delete_order:"))
    
    # Address
    application.add_handler(MessageHandler(filters.Regex("^📍 آدرس من$"), view_my_address))
    application.add_handler(CallbackQueryHandler(edit_address, pattern=r"^edit_address$"))
    
    # Finalize order conversation
    finalize_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(finalize_order_start, pattern=r"^finalize_order$")
        ],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name_received)],
            ADDRESS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_text_received)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_number_received)]
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ لغو$"), lambda u, c: ConversationHandler.END)]
    )
    application.add_handler(finalize_conv)
    
    # Confirm/Edit info - 🆕 FIX: Pattern درست شد
    application.add_handler(CallbackQueryHandler(confirm_user_info, pattern=r"^confirm_user_info$"))  # ✅ FIX
    application.add_handler(CallbackQueryHandler(edit_user_info_for_order, pattern=r"^edit_user_info$"))  # ✅ FIX
    
    # Shipping
    application.add_handler(CallbackQueryHandler(handle_shipping_selection, pattern=r"^ship_"))
    application.add_handler(CallbackQueryHandler(final_confirm_order, pattern=r"^final_confirm$"))
    application.add_handler(CallbackQueryHandler(final_edit_order, pattern=r"^final_edit$"))
    
    # Receipt (photo)
    application.add_handler(MessageHandler(filters.PHOTO, handle_receipt))
    
    # Order management (admin)
    application.add_handler(CallbackQueryHandler(confirm_order, pattern=r"^confirm_order:"))
    application.add_handler(CallbackQueryHandler(reject_order, pattern=r"^reject_order:"))
    application.add_handler(CallbackQueryHandler(remove_item_from_order, pattern=r"^remove_item:"))
    application.add_handler(CallbackQueryHandler(reject_full_order, pattern=r"^reject_full:"))
    application.add_handler(CallbackQueryHandler(back_to_order_review, pattern=r"^back_to_order:"))  # ✅ FIX
    application.add_handler(CallbackQueryHandler(confirm_modified_order, pattern=r"^confirm_modified:"))
    
    # Payment
    application.add_handler(CallbackQueryHandler(confirm_payment, pattern=r"^confirm_payment:"))
    application.add_handler(CallbackQueryHandler(reject_payment, pattern=r"^reject_payment:"))


__all__ = [
    'start_handler',
    'help_handler',
    'setup_user_handlers',
    'receipt_handler',
]
