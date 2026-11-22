import re

from flasgger import swag_from
from flask import Blueprint, request

import models
from .api_common import MAX_SQLITE_ID, api_error, api_response
from .shop import MAX_QUANTITY


api_orders_bp = Blueprint('api_orders', __name__, url_prefix='/api')

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
MAX_ORDER_ITEMS = 50

ORDER_ITEM_SCHEMA = {
    'type': 'object',
    'required': ['name', 'quantity', 'unit_price', 'subtotal'],
    'properties': {
        'name': {'type': 'string', 'example': 'Ігровий ноутбук'},
        'quantity': {'type': 'integer', 'example': 1},
        'unit_price': {'type': 'number', 'example': 54999.0},
        'subtotal': {'type': 'number', 'example': 54999.0},
    },
}

ORDER_SUMMARY_SCHEMA = {
    'type': 'object',
    'required': ['id', 'customer_name', 'email', 'address', 'total_price', 'status', 'created_at'],
    'properties': {
        'id': {'type': 'integer', 'example': 1},
        'client_id': {'type': 'integer', 'example': 1},
        'customer_name': {'type': 'string', 'example': 'Тестовий Покупець'},
        'email': {'type': 'string', 'format': 'email', 'example': 'buyer@example.com'},
        'address': {'type': 'string', 'example': 'Київ, вул. Хрещатик, 1'},
        'total_price': {'type': 'number', 'example': 54999.0},
        'promo_code': {'type': 'string', 'example': ''},
        'discount_amount': {'type': 'number', 'example': 0},
        'status': {'type': 'string', 'enum': list(models.ORDER_STATUSES), 'example': 'Нове'},
        'created_at': {'type': 'string', 'example': '2026-11-16 12:00:00'},
    },
}

ORDER_DETAIL_SCHEMA = {
    **ORDER_SUMMARY_SCHEMA,
    'properties': {
        **ORDER_SUMMARY_SCHEMA['properties'],
        'items': {'type': 'array', 'items': ORDER_ITEM_SCHEMA},
    },
}

ORDER_INPUT_SCHEMA = {
    'type': 'object',
    'required': ['customer_name', 'email', 'address', 'items'],
    'properties': {
        'customer_name': {'type': 'string', 'example': 'Тестовий Покупець'},
        'email': {'type': 'string', 'format': 'email', 'example': 'buyer@example.com'},
        'address': {'type': 'string', 'example': 'Київ, вул. Хрещатик, 1'},
        'items': {
            'type': 'array',
            'minItems': 1,
            'maxItems': MAX_ORDER_ITEMS,
            'items': {
                'type': 'object',
                'required': ['product_id', 'quantity'],
                'properties': {
                    'product_id': {
                        'type': 'integer', 'minimum': 1, 'maximum': MAX_SQLITE_ID, 'example': 1,
                    },
                    'quantity': {
                        'type': 'integer', 'minimum': 1, 'maximum': MAX_QUANTITY, 'example': 1,
                    },
                },
            },
        },
        'promo_code': {'type': 'string', 'example': 'WELCOME10'},
    },
}

ORDER_EXAMPLE = {
    'id': 1,
    'client_id': 1,
    'customer_name': 'Тестовий Покупець',
    'email': 'buyer@example.com',
    'address': 'Київ, вул. Хрещатик, 1',
    'total_price': 54999.0,
    'promo_code': '',
    'discount_amount': 0,
    'status': 'Нове',
    'created_at': '2026-11-16 12:00:00',
}

ORDER_DETAIL_EXAMPLE = {
    **ORDER_EXAMPLE,
    'items': [
        {'name': 'Ігровий ноутбук', 'quantity': 1, 'unit_price': 54999.0, 'subtotal': 54999.0}
    ],
}


def _versioned_schema(version, data_schema):
    if version == 'v1':
        return data_schema
    return {
        'type': 'object',
        'required': ['version', 'data'],
        'properties': {
            'version': {'type': 'string', 'enum': ['v2']},
            'data': data_schema,
        },
    }


def _success_spec(version, description, data_schema, example):
    response_example = example
    if version == 'v2':
        response_example = {'version': 'v2', 'data': example}
    return {
        'description': description,
        'schema': _versioned_schema(version, data_schema),
        'examples': {'application/json': response_example},
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
        'tags': ['Замовлення'],
        'summary': summary,
        'description': f'Версія {version} API. Успішна відповідь і помилки мають формат цієї версії.',
        'parameters': parameters,
        'responses': responses,
        'produces': ['application/json'],
    }


def _list_orders_spec(version):
    order_list_schema = {'type': 'array', 'items': ORDER_SUMMARY_SCHEMA}
    order_list_example = [ORDER_EXAMPLE]
    return _operation_spec(
        version,
        'Отримати список замовлень',
        [{
            'name': 'status',
            'in': 'query',
            'type': 'string',
            'required': False,
            'enum': list(models.ORDER_STATUSES),
            'description': 'Необов’язковий фільтр за статусом замовлення.',
        }],
        {
            200: _success_spec(version, 'Список замовлень від нових до старих.', order_list_schema, order_list_example),
            400: _error_spec(
                version, 'Невідомий статус фільтра.', 'Невідомий статус замовлення.',
                {'allowed_statuses': list(models.ORDER_STATUSES)},
            ),
        },
    )


def _get_order_spec(version):
    return _operation_spec(
        version,
        'Отримати замовлення з товарами',
        [{'name': 'order_id', 'in': 'path', 'type': 'integer', 'required': True}],
        {
            200: _success_spec(version, 'Замовлення та його позиції.', ORDER_DETAIL_SCHEMA, ORDER_DETAIL_EXAMPLE),
            404: _error_spec(version, 'Замовлення не знайдено.', 'Замовлення не знайдено.'),
        },
    )


def _create_order_spec(version):
    return _operation_spec(
        version,
        'Створити замовлення',
        [{'name': 'body', 'in': 'body', 'required': True, 'schema': ORDER_INPUT_SCHEMA}],
        {
            201: _success_spec(version, 'Замовлення створено.', ORDER_DETAIL_SCHEMA, ORDER_DETAIL_EXAMPLE),
            400: _error_spec(
                version, 'Некоректні дані або товар не знайдено.',
                'Некоректні дані замовлення.', {'items': 'Перевірте наявність товарів та їхню кількість.'},
            ),
            409: _error_spec(
                version, 'Один або кілька товарів недоступні.',
                'Одного або кількох товарів немає в наявності.', {'product_ids': [1]},
            ),
        },
    )


def _update_order_status_spec(version):
    status_input_schema = {
        'type': 'object',
        'required': ['status'],
        'properties': {'status': {'type': 'string', 'enum': list(models.ORDER_STATUSES)}},
    }
    return _operation_spec(
        version,
        'Змінити статус замовлення',
        [
            {'name': 'order_id', 'in': 'path', 'type': 'integer', 'required': True},
            {'name': 'body', 'in': 'body', 'required': True, 'schema': status_input_schema},
        ],
        {
            200: _success_spec(version, 'Статус замовлення змінено.', ORDER_DETAIL_SCHEMA, ORDER_DETAIL_EXAMPLE),
            400: _error_spec(
                version, 'Невідомий статус.', 'Невідомий статус замовлення.',
                {'allowed_statuses': list(models.ORDER_STATUSES)},
            ),
            404: _error_spec(version, 'Замовлення не знайдено.', 'Замовлення не знайдено.'),
        },
    )


def _order_to_dict(order, items=None):
    result = dict(order)
    if items is not None:
        result['items'] = [dict(item) for item in items]
    return result


def _read_order_data(data):
    """Validate a JSON order and convert its item list to the model cart map."""
    if not isinstance(data, dict):
        return None, {'body': 'Тіло запиту має бути JSON-об’єктом.'}

    errors = {}
    customer_name = data.get('customer_name')
    if not isinstance(customer_name, str) or not customer_name.strip():
        errors['customer_name'] = 'Вкажіть ім’я покупця.'
    elif len(customer_name.strip()) > 100:
        errors['customer_name'] = 'Ім’я не має перевищувати 100 символів.'

    email = data.get('email')
    if not isinstance(email, str) or not EMAIL_RE.fullmatch(email.strip()):
        errors['email'] = 'Вкажіть коректну електронну адресу.'
    elif len(email.strip()) > 254:
        errors['email'] = 'Email не має перевищувати 254 символи.'

    address = data.get('address')
    if not isinstance(address, str) or not address.strip():
        errors['address'] = 'Вкажіть адресу доставки.'
    elif len(address.strip()) > 500:
        errors['address'] = 'Адреса не має перевищувати 500 символів.'

    items = data.get('items')
    cart = {}
    if not isinstance(items, list) or not items:
        errors['items'] = 'Додайте принаймні один товар до замовлення.'
    elif len(items) > MAX_ORDER_ITEMS:
        errors['items'] = f'Замовлення може містити не більше {MAX_ORDER_ITEMS} позицій.'
    else:
        for index, item in enumerate(items):
            item_key = f'items[{index}]'
            if not isinstance(item, dict):
                errors[item_key] = 'Позиція має бути JSON-об’єктом.'
                continue

            product_id = item.get('product_id')
            quantity = item.get('quantity')
            if (
                isinstance(product_id, bool)
                or not isinstance(product_id, int)
                or not 1 <= product_id <= MAX_SQLITE_ID
            ):
                errors[f'{item_key}.product_id'] = (
                    'ID товару має бути додатним цілим числом у допустимому діапазоні.'
                )
                continue
            if isinstance(quantity, bool) or not isinstance(quantity, int):
                errors[f'{item_key}.quantity'] = 'Кількість має бути цілим числом.'
                continue
            if not 1 <= quantity <= MAX_QUANTITY:
                errors[f'{item_key}.quantity'] = f'Кількість має бути від 1 до {MAX_QUANTITY}.'
                continue

            combined_quantity = cart.get(product_id, 0) + quantity
            if combined_quantity > MAX_QUANTITY:
                errors[f'{item_key}.quantity'] = (
                    f'Загальна кількість одного товару не може перевищувати {MAX_QUANTITY}.'
                )
            else:
                cart[product_id] = combined_quantity

    promo_code = data.get('promo_code', '')
    if not isinstance(promo_code, str):
        errors['promo_code'] = 'Код промокоду має бути текстом.'
    elif len(promo_code.strip()) > 50:
        errors['promo_code'] = 'Код промокоду не має перевищувати 50 символів.'

    if errors:
        return None, errors

    return {
        'customer_name': customer_name.strip(),
        'email': email.strip(),
        'address': address.strip(),
        'cart': cart,
        'promo_code': promo_code.strip(),
    }, None


def _list_orders():
    status = request.args.get('status', '').strip()
    if status and status not in models.ORDER_STATUSES:
        return api_error(
            'Невідомий статус замовлення.',
            400,
            {'allowed_statuses': list(models.ORDER_STATUSES)},
        )

    orders = models.get_orders()
    if status:
        orders = [order for order in orders if order['status'] == status]
    return api_response([_order_to_dict(order) for order in orders])


@api_orders_bp.get('/v1/orders', endpoint='list_orders_v1')
@swag_from(_list_orders_spec('v1'))
def list_orders_v1():
    return _list_orders()


@api_orders_bp.get('/v2/orders', endpoint='list_orders_v2')
@swag_from(_list_orders_spec('v2'))
def list_orders_v2():
    return _list_orders()


def _get_order(order_id):
    if order_id > MAX_SQLITE_ID:
        return api_error('Замовлення не знайдено.', 404)

    order, items = models.get_order_details(order_id)
    if order is None:
        return api_error('Замовлення не знайдено.', 404)
    return api_response(_order_to_dict(order, items))


@api_orders_bp.get('/v1/orders/<int:order_id>', endpoint='get_order_v1')
@swag_from(_get_order_spec('v1'))
def get_order_v1(order_id):
    return _get_order(order_id)


@api_orders_bp.get('/v2/orders/<int:order_id>', endpoint='get_order_v2')
@swag_from(_get_order_spec('v2'))
def get_order_v2(order_id):
    return _get_order(order_id)


def _create_order():
    data, errors = _read_order_data(request.get_json(silent=True))
    if errors:
        return api_error('Некоректні дані замовлення.', 400, errors)

    products = models.get_products_by_ids(data['cart'].keys())
    products_by_id = {product['id']: product for product in products}
    missing_ids = sorted(set(data['cart']) - set(products_by_id))
    if missing_ids:
        return api_error(
            'Одного або кількох товарів не знайдено.',
            400,
            {'product_ids': missing_ids},
        )

    unavailable_ids = sorted(
        product_id
        for product_id, product in products_by_id.items()
        if not product['is_available']
    )
    if unavailable_ids:
        return api_error(
            'Одного або кількох товарів немає в наявності.',
            409,
            {'product_ids': unavailable_ids},
        )

    try:
        order_id = models.create_order(
            data['customer_name'],
            data['email'],
            data['address'],
            data['cart'],
            promo_code=data['promo_code'],
        )
    except ValueError as error:
        return api_error(str(error), 400)

    order, items = models.get_order_details(order_id)
    response, status = api_response(_order_to_dict(order, items), 201)
    version_prefix = '/api/v2' if request.path.startswith('/api/v2/') else '/api/v1'
    response.headers['Location'] = f'{version_prefix}/orders/{order_id}'
    return response, status


@api_orders_bp.post('/v1/orders', endpoint='create_order_v1')
@swag_from(_create_order_spec('v1'))
def create_order_v1():
    return _create_order()


@api_orders_bp.post('/v2/orders', endpoint='create_order_v2')
@swag_from(_create_order_spec('v2'))
def create_order_v2():
    return _create_order()


def _update_order_status(order_id):
    if order_id > MAX_SQLITE_ID:
        return api_error('Замовлення не знайдено.', 404)

    order = models.get_order(order_id)
    if order is None:
        return api_error('Замовлення не знайдено.', 404)

    data = request.get_json(silent=True)
    status = data.get('status') if isinstance(data, dict) else None
    if status not in models.ORDER_STATUSES:
        return api_error(
            'Невідомий статус замовлення.',
            400,
            {'allowed_statuses': list(models.ORDER_STATUSES)},
        )

    models.update_order_status(order_id, status)
    updated_order, items = models.get_order_details(order_id)
    return api_response(_order_to_dict(updated_order, items))


@api_orders_bp.patch('/v1/orders/<int:order_id>', endpoint='update_order_status_v1')
@swag_from(_update_order_status_spec('v1'))
def update_order_status_v1(order_id):
    return _update_order_status(order_id)


@api_orders_bp.patch('/v2/orders/<int:order_id>', endpoint='update_order_status_v2')
@swag_from(_update_order_status_spec('v2'))
def update_order_status_v2(order_id):
    return _update_order_status(order_id)
