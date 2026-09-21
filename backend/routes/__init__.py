"""
KLinePlayground - Route Blueprints Module
"""
from backend.routes.user_routes import user_bp, init_user_routes
from backend.routes.stock_routes import stock_bp, init_stock_routes
from backend.routes.crypto_routes import crypto_bp, init_crypto_routes
from backend.routes.training_routes import training_bp, init_training_routes
from backend.routes.ashare_live_routes import ashare_live_bp
from backend.routes.state_routes import state_bp

__all__ = [
    'user_bp',
    'init_user_routes',
    'stock_bp',
    'init_stock_routes',
    'crypto_bp',
    'init_crypto_routes',
    'training_bp',
    'init_training_routes',
    'ashare_live_bp',
    'state_bp'
]
