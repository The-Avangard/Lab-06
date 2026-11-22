import os
from datetime import datetime

from flasgger import Swagger
from flask import Flask, render_template, session

import models
from routes import admin_bp, feedback_bp, shop_bp
from routes.api_orders import api_orders_bp
from routes.api_products import api_products_bp


app = Flask(__name__)

app.config['DATABASE'] = os.environ.get(
    'DATABASE',
    os.path.join(app.root_path, 'db.sqlite')
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-me')

app.teardown_appcontext(models.close_db)

with app.app_context():
    models.init_db()

app.register_blueprint(feedback_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(shop_bp)
app.register_blueprint(api_orders_bp)
app.register_blueprint(api_products_bp)

swagger = Swagger(
    app,
    config={
        'headers': [],
        'auth': {},
        'static_url_path': '/flasgger_static',
        'specs': [
            {
                'endpoint': 'api_spec',
                'route': '/apispec_1.json',
                'rule_filter': lambda rule: rule.rule.startswith(('/api/v1/', '/api/v2/')),
                'model_filter': lambda tag: True,
            }
        ],
        'swagger_ui': True,
        'specs_route': '/apidocs/',
    },
    template={
        'swagger': '2.0',
        'info': {
            'title': 'AVANGARD SHOP API',
            'description': 'REST API магазину AVANGARD SHOP, версії v1 та v2.',
            'version': '1.0.0',
        },
        'basePath': '/',
        'schemes': ['http'],
        'consumes': ['application/json'],
        'produces': ['application/json'],
    },
)


@app.template_filter('money')
def money(value):
    return f'{value:.2f} грн'


@app.context_processor
def inject_globals():
    return {
        'current_year': datetime.now().year,
        'cart_count': sum(session.get('cart', {}).values()),
    }


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/categories')
def categories():
    return render_template('categories.html')


@app.route('/about')
def about():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
