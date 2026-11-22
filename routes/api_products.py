"""Versioned JSON API routes and OpenAPI specifications for products."""

import math
import sqlite3

from flasgger import swag_from
from flask import Blueprint, request

import models
from .api_common import MAX_SQLITE_ID, api_error, api_response


api_products_bp = Blueprint('api_products', __name__, url_prefix='/api')

PRODUCT_SCHEMA = {
    'type': 'object',
    'required': ['id', 'category', 'name', 'price'],
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'category': {'type': 'string', 'enum': list(models.PRODUCT_CATEGORIES)},
        'name': {'type': 'string', 'example': 'Ігровий ноутбук'},
        'description': {'type': 'string', 'example': 'Ноутбук для ігор і роботи.'},
        'specifications': {'type': 'string', 'example': '32 ГБ RAM, SSD 1 ТБ'},
        'price': {'type': 'number', 'format': 'float', 'example': 54999.0},
        'image_url': {'type': 'string', 'example': 'https://example.com/laptop.jpg'},
        'is_available': {'type': 'boolean', 'example': True},
        'created_at': {'type': 'string', 'example': '2026-11-16 12:00:00'},
    },
}

PRODUCT_INPUT_SCHEMA = {
    'type': 'object',
    'required': ['category', 'name', 'price'],
    'properties': {
        'category': {'type': 'string', 'enum': list(models.PRODUCT_CATEGORIES)},
        'name': {'type': 'string', 'example': 'Ігровий ноутбук'},
        'description': {'type': 'string', 'example': 'Ноутбук для ігор і роботи.'},
        'specifications': {'type': 'string', 'example': '32 ГБ RAM, SSD 1 ТБ'},
        'price': {'type': 'number', 'format': 'float', 'minimum': 0, 'example': 54999.0},
        'image_url': {'type': 'string', 'example': 'https://example.com/laptop.jpg'},
    },
}

PRODUCT_EXAMPLE = {
    'id': 1,
    'category': 'Ноутбук',
    'name': 'Ігровий ноутбук',
    'description': 'Ноутбук для ігор і роботи.',
    'specifications': '32 ГБ RAM, SSD 1 ТБ',
    'price': 54999.0,
    'image_url': 'https://example.com/laptop.jpg',
    'is_available': True,
    'created_at': '2026-11-16 12:00:00',
}


def _versioned_schema(version, data_schema, include_message=False):
    if version == 'v1':
        return data_schema

    properties = {
        'version': {'type': 'string', 'enum': ['v2']},
        'data': data_schema,
    }
    required = ['version', 'data']
    if include_message:
        properties['message'] = {'type': 'string'}
        required.append('message')
    return {'type': 'object', 'required': required, 'properties': properties}


def _success_spec(version, description, data_schema, example, message=None):
    if version == 'v1' and message:
        schema = {
            'type': 'object',
            'required': ['message'],
            'properties': {'message': {'type': 'string'}},
        }
        example_body = {'message': message}
    else:
        schema = _versioned_schema(version, data_schema, include_message=bool(message))
        if version == 'v2':
            example_body = {'version': 'v2', 'data': example}
            if message:
                example_body['message'] = message
        else:
            example_body = example

    return {
        'description': description,
        'schema': schema,
        'examples': {'application/json': example_body},
    }


def _error_spec(version, description, message, details=None):
    if version == 'v2':
        schema = {
            'type': 'object',
            'required': ['version', 'error'],
            'properties': {
                'version': {'type': 'string', 'enum': ['v2']},
                'error': {
                    'type': 'object',
                    'required': ['message'],
                    'properties': {
                        'message': {'type': 'string'},
                        'details': {'type': 'object'},
                    },
                },
            },
        }
        example = {'version': 'v2', 'error': {'message': message}}
        if details is not None:
            example['error']['details'] = details
    else:
        schema = {
            'type': 'object',
            'required': ['error'],
            'properties': {
                'error': {'type': 'string'},
                'details': {'type': 'object'},
            },
        }
        example = {'error': message}
        if details is not None:
            example['details'] = details

    return {
        'description': description,
        'schema': schema,
        'examples': {'application/json': example},
    }


def _operation_spec(version, summary, parameters, responses):
    return {
        'tags': ['Товари'],
        'summary': summary,
        'description': f'Версія {version} API. Успішна відповідь і помилки мають формат цієї версії.',
        'parameters': parameters,
        'responses': responses,
        'produces': ['application/json'],
    }


def _list_products_spec(version):
    product_list_schema = {'type': 'array', 'items': PRODUCT_SCHEMA}
    product_list_example = [PRODUCT_EXAMPLE]
    return _operation_spec(
        version,
        'Отримати список доступних товарів',
        [
            {
                'name': 'q', 'in': 'query', 'type': 'string', 'required': False,
                'description': 'Пошук у назві, описі та характеристиках.',
            },
            {
                'name': 'category', 'in': 'query', 'type': 'string', 'required': False,
                'enum': list(models.PRODUCT_CATEGORIES),
                'description': 'Фільтр за категорією товару.',
            },
        ],
        {
            200: _success_spec(version, 'Список товарів.', product_list_schema, product_list_example),
            400: _error_spec(
                version, 'Невідома категорія.', 'Невідома категорія товару.',
                {'allowed_categories': list(models.PRODUCT_CATEGORIES)},
            ),
        },
    )


def _get_product_spec(version):
    return _operation_spec(
        version,
        'Отримати товар за ID',
        [{'name': 'product_id', 'in': 'path', 'type': 'integer', 'required': True}],
        {
            200: _success_spec(version, 'Дані товару.', PRODUCT_SCHEMA, PRODUCT_EXAMPLE),
            404: _error_spec(version, 'Товар не знайдено.', 'Товар не знайдено.'),
        },
    )


def _create_product_spec(version):
    return _operation_spec(
        version,
        'Створити товар',
        [{'name': 'body', 'in': 'body', 'required': True, 'schema': PRODUCT_INPUT_SCHEMA}],
        {
            201: _success_spec(version, 'Товар створено.', PRODUCT_SCHEMA, PRODUCT_EXAMPLE),
            400: _error_spec(
                version, 'Некоректні дані товару.', 'Некоректні дані товару.',
                {'price': 'Ціна має бути числом не меншим за 0.'},
            ),
        },
    )


def _replace_product_spec(version):
    return _operation_spec(
        version,
        'Повністю оновити товар',
        [
            {'name': 'product_id', 'in': 'path', 'type': 'integer', 'required': True},
            {'name': 'body', 'in': 'body', 'required': True, 'schema': PRODUCT_INPUT_SCHEMA},
        ],
        {
            200: _success_spec(version, 'Товар оновлено.', PRODUCT_SCHEMA, PRODUCT_EXAMPLE),
            400: _error_spec(version, 'Некоректні дані товару.', 'Некоректні дані товару.'),
            404: _error_spec(version, 'Товар не знайдено.', 'Товар не знайдено.'),
        },
    )


def _remove_product_spec(version):
    deleted_schema = {
        'type': 'object',
        'required': ['deleted'],
        'properties': {'deleted': {'type': 'boolean', 'example': True}},
    }
    return _operation_spec(
        version,
        'Видалити товар',
        [{'name': 'product_id', 'in': 'path', 'type': 'integer', 'required': True}],
        {
            200: _success_spec(
                version, 'Товар видалено.', deleted_schema, {'deleted': True},
                message='Товар видалено.',
            ),
            404: _error_spec(version, 'Товар не знайдено.', 'Товар не знайдено.'),
            409: _error_spec(
                version, 'Товар використовується в замовленні.',
                'Не можна видалити товар, який уже входить до замовлення.',
            ),
        },
    )


def _product_to_dict(product):
    return {
        'id': product['id'],
        'category': product['category'],
        'name': product['name'],
        'description': product['description'],
        'specifications': product['specifications'],
        'price': product['price'],
        'image_url': product['image_url'],
        'is_available': bool(product['is_available']),
        'created_at': product['created_at'],
    }


def _validate_product_data(data):
    """Validate fields accepted when creating or replacing a product."""
    if not isinstance(data, dict):
        return None, {'body': 'Надішліть JSON-об’єкт.'}

    errors = {}
    result = {}

    for field in ('category', 'name'):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors[field] = 'Поле обов’язкове і має бути текстом.'
        else:
            result[field] = value.strip()

    if result.get('category') not in models.PRODUCT_CATEGORIES:
        errors['category'] = (
            'Оберіть одну з категорій: ' + ', '.join(models.PRODUCT_CATEGORIES)
        )

    for field in ('description', 'specifications', 'image_url'):
        value = data.get(field, '')
        if not isinstance(value, str):
            errors[field] = 'Поле має бути текстом.'
        else:
            result[field] = value.strip()

    price = data.get('price')
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        errors['price'] = 'Ціна має бути числом.'
    else:
        try:
            normalized_price = float(price)
        except OverflowError:
            errors['price'] = 'Ціна має бути скінченним числом не меншим за 0.'
        else:
            if not math.isfinite(normalized_price) or normalized_price < 0:
                errors['price'] = 'Ціна має бути скінченним числом не меншим за 0.'
            else:
                result['price'] = normalized_price

    if errors:
        return None, errors
    return result, None


def _list_products():
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    if category and category not in models.PRODUCT_CATEGORIES:
        return api_error(
            'Невідома категорія товару.',
            400,
            {'allowed_categories': list(models.PRODUCT_CATEGORIES)},
        )

    products = models.get_products(query=query, category=category)
    return api_response([_product_to_dict(product) for product in products])


@api_products_bp.get('/v1/products', endpoint='list_products_v1')
@swag_from(_list_products_spec('v1'))
def list_products_v1():
    return _list_products()


@api_products_bp.get('/v2/products', endpoint='list_products_v2')
@swag_from(_list_products_spec('v2'))
def list_products_v2():
    return _list_products()


def _get_product(product_id):
    if product_id > MAX_SQLITE_ID:
        return api_error('Товар не знайдено.', 404)

    product = models.get_product(product_id)
    if product is None:
        return api_error('Товар не знайдено.', 404)
    return api_response(_product_to_dict(product))


@api_products_bp.get('/v1/products/<int:product_id>', endpoint='get_product_v1')
@swag_from(_get_product_spec('v1'))
def get_product_v1(product_id):
    return _get_product(product_id)


@api_products_bp.get('/v2/products/<int:product_id>', endpoint='get_product_v2')
@swag_from(_get_product_spec('v2'))
def get_product_v2(product_id):
    return _get_product(product_id)


def _create_product():
    data, errors = _validate_product_data(request.get_json(silent=True))
    if errors:
        return api_error('Некоректні дані товару.', 400, errors)

    product_id = models.add_product(
        data['category'],
        data['name'],
        data['description'],
        data['specifications'],
        data['price'],
        data['image_url'],
    )
    product = models.get_product(product_id)
    return api_response(_product_to_dict(product), 201)


@api_products_bp.post('/v1/products', endpoint='create_product_v1')
@swag_from(_create_product_spec('v1'))
def create_product_v1():
    return _create_product()


@api_products_bp.post('/v2/products', endpoint='create_product_v2')
@swag_from(_create_product_spec('v2'))
def create_product_v2():
    return _create_product()


def _replace_product(product_id):
    if product_id > MAX_SQLITE_ID:
        return api_error('Товар не знайдено.', 404)

    if models.get_product(product_id) is None:
        return api_error('Товар не знайдено.', 404)

    data, errors = _validate_product_data(request.get_json(silent=True))
    if errors:
        return api_error('Некоректні дані товару.', 400, errors)

    models.update_product(
        product_id,
        data['category'],
        data['name'],
        data['description'],
        data['specifications'],
        data['price'],
        data['image_url'],
    )
    return api_response(_product_to_dict(models.get_product(product_id)))


@api_products_bp.put('/v1/products/<int:product_id>', endpoint='replace_product_v1')
@swag_from(_replace_product_spec('v1'))
def replace_product_v1(product_id):
    return _replace_product(product_id)


@api_products_bp.put('/v2/products/<int:product_id>', endpoint='replace_product_v2')
@swag_from(_replace_product_spec('v2'))
def replace_product_v2(product_id):
    return _replace_product(product_id)


def _remove_product(product_id):
    if product_id > MAX_SQLITE_ID:
        return api_error('Товар не знайдено.', 404)

    if models.get_product(product_id) is None:
        return api_error('Товар не знайдено.', 404)

    try:
        models.delete_product(product_id)
    except sqlite3.IntegrityError:
        return api_error(
            'Не можна видалити товар, який уже входить до замовлення.', 409
        )

    return api_response({'deleted': True}, message='Товар видалено.')


@api_products_bp.delete('/v1/products/<int:product_id>', endpoint='remove_product_v1')
@swag_from(_remove_product_spec('v1'))
def remove_product_v1(product_id):
    return _remove_product(product_id)


@api_products_bp.delete('/v2/products/<int:product_id>', endpoint='remove_product_v2')
@swag_from(_remove_product_spec('v2'))
def remove_product_v2(product_id):
    return _remove_product(product_id)
