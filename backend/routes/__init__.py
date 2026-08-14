"""
KLinePlayground - Route Blueprints Module
"""
from flask import Blueprint

crypto_bp = Blueprint('crypto_routes', __name__)
stock_bp = Blueprint('stock_routes', __name__)
user_bp = Blueprint('user_routes', __name__)
training_bp = Blueprint('training_routes', __name__)
