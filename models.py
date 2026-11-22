"""SQLite data layer for AVANGARD SHOP.

Connections are scoped to one Flask application context and closed by
``close_db`` registered in app.py. All user-provided SQL values are passed
as parameters rather than interpolated into query strings.
"""

import sqlite3
from datetime import datetime

from flask import current_app, g


ORDER_STATUSES = ("Нове", "В обробці", "Відправлено", "Доставлено", "Скасовано")
PRODUCT_CATEGORIES = ("Ноутбук", "Стаціонарний ПК", "Приставка")

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    phone      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id  INTEGER,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    category       TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    specifications TEXT NOT NULL DEFAULT '',
    price          REAL NOT NULL CHECK (price >= 0),
    image_url      TEXT NOT NULL DEFAULT '',
    is_available   INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER,
    customer_name TEXT NOT NULL,
    email       TEXT NOT NULL,
    address     TEXT NOT NULL,
    total_price REAL NOT NULL CHECK (total_price >= 0),
    promo_code  TEXT NOT NULL DEFAULT '',
    discount_amount REAL NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE SET NULL
);

-- Junction table for the many-to-many relationship between orders and products.
-- unit_price preserves the price that applied when the order was placed.
CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT NOT NULL UNIQUE,
    discount_percent REAL NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_orders_client ON orders (client_id);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (created_at);
"""


INITIAL_PRODUCTS = (
    (
        'Ноутбук', 'Asus ROG Strix G18 G814, 18″',
        '18-дюймовий ROG Strix для ігор і вимогливих робочих задач.',
        'AMD Ryzen 9 8940HX · 96 ГБ RAM · SSD 4 ТБ · RTX 5070',
        256299,
        'https://img.jabko.ua/image/cache/catalog/products/2025/08/071224/rtgf-1046x1046.png.webp',
    ),
    (
        'Ноутбук', 'ASUS ROG Zephyrus G16 GU605MY',
        'Ігровий ноутбук ROG Zephyrus G16 із процесором Core Ultra 9 та графікою RTX 4090.',
        'Intel Core Ultra 9 · 32 ГБ RAM · SSD 8 ТБ · RTX 4090',
        248999,
        'https://img.jabko.ua/image/cache/catalog/products/2024/08/131715/zephyrus_7-770x770.png.webp',
    ),
    (
        'Ноутбук', 'Asus ROG Strix G16 G615JMR, 16″',
        '16-дюймовий ROG Strix для ігор та інтенсивних робочих задач.',
        'Intel Core i7 · 32 ГБ RAM · SSD 1 ТБ · RTX 5060',
        118299,
        'https://img.jabko.ua/image/cache/catalog/products/2026/02/070923/b82b852cfb01fc811b18d39559479c45-770x770.jpg.webp',
    ),
    (
        'Ноутбук', 'Asus Vivobook 14 Flip TP3407SA, 14″',
        '14-дюймовий ноутбук-трансформер із сенсорним екраном.',
        'Intel Core Ultra 7 · 16 ГБ RAM · SSD 1 ТБ · Intel Arc',
        58199,
        'https://img.jabko.ua/image/cache/catalog/products/2025/08/061312/15-770x770.jpg.webp',
    ),
    (
        'Ноутбук', 'Asus Vivobook 14 M1407GA-LY005, 14″',
        '14-дюймовий Vivobook для повсякденних і робочих задач.',
        'AMD Ryzen AI 7 · 16 ГБ RAM · SSD 512 ГБ · AMD Radeon Graphics',
        62499,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/211507/2-770x770.jpg.webp',
    ),
    (
        'Ноутбук', 'Asus Zenbook 14 UX3405CA, 14″',
        'Компактний 14-дюймовий Zenbook для роботи й поїздок.',
        'Intel Core Ultra 5 · 16 ГБ RAM · SSD 512 ГБ · Intel Arc Graphics',
        53999,
        'https://img.jabko.ua/image/cache/catalog/products/2025/08/071224/asus-zenbook-14-ux3405ca-ultra-5-770x770.jpg.webp',
    ),
    (
        'Ноутбук', 'Acer Aspire Lite AL16-54P-54U7, 16″',
        '16-дюймовий Aspire Lite для навчання та офісних задач.',
        'Intel Core 5 · 16 ГБ RAM · SSD 512 ГБ · Intel Graphics',
        38999,
        'https://img.jabko.ua/image/cache/catalog/products/2025/11/071256/rfdser-770x770.png.webp',
    ),
    (
        'Ноутбук', 'HP OmniBook 3 16-bu0007dx, 16″',
        '16-дюймовий ноутбук HP OmniBook 3 для щоденної роботи.',
        'Intel Core Ultra 7 · 16 ГБ RAM · SSD 512 ГБ · Intel Graphics',
        43499,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/081440/qwsedrf-1046x1046.jpeg.webp',
    ),
    (
        'Ноутбук', 'HP EliteBook 6 G1a, 16″',
        '16-дюймовий бізнес-ноутбук HP EliteBook.',
        'AMD Ryzen 7 · 24 ГБ RAM · SSD 1 ТБ · AMD Radeon Graphics',
        90399,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/221653/d43b938dbe8f43a425156719c99395f2-1046x1046.jpg.webp',
    ),
    (
        'Ноутбук', 'Ноутбук Dell Alienware 16 Aurora AC16250 16" (Intel Core 9/16GB/1TB (SSD)/RTX 5070) (HGYMH)',
        '16-дюймовий ігровий ноутбук Dell Alienware серії Aurora.',
        'Intel Core 9 · 16 ГБ RAM · SSD 1 ТБ · RTX 5070 · HGYMH',
        117299,
        'https://img.jabko.ua/image/cache/catalog/products/2025/08/080927/efrt65-1046x1046.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Gaming X43',
        'Стаціонарний ігровий ПК ARTLINE Gaming X43.',
        'Модель: ARTLINE Gaming X43',
        62382,
        'https://img.jabko.ua/image/cache/catalog/products/2023/08/251221/Kompyuter%20ARTLINE%20Gaming%20X47v46_1%20(2)-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Overlord GT302',
        'Стаціонарний ПК серії ARTLINE Overlord GT302.',
        'Модель: ARTLINE Overlord GT302',
        185868,
        'https://img.jabko.ua/image/cache/catalog/products/2025/03/141303/6-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'COBRA Gaming',
        'Ігровий ПК із Ryzen 7 9700X та графікою RTX 5060.',
        'AMD Ryzen 7 9700X · 32 ГБ RAM · SSD 500 ГБ · RTX 5060',
        89869,
        'https://img.jabko.ua/image/cache/catalog/products/2026/05/121408/gasrteg-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', '2E Complex Gaming — варіант 1',
        'Ігровий ПК 2E Complex з Ryzen 5 7500F та RTX 5060 Ti.',
        'AMD Ryzen 5 7500F · 32 ГБ RAM · SSD 1 ТБ · RTX 5060 Ti 16 ГБ',
        119829,
        'https://img.jabko.ua/image/cache/catalog/products/2026/10/091034/product%20(2)-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', '2E Complex Gaming — варіант 2',
        'Ігровий ПК 2E Complex з Ryzen 5 7500F та RTX 5060 Ti.',
        'AMD Ryzen 5 7500F · 32 ГБ RAM · SSD 1 ТБ · RTX 5060 Ti 16 ГБ',
        104639,
        'https://img.jabko.ua/image/cache/catalog/products/2026/10/091015/product-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Business B57',
        'Робочий комп’ютер ARTLINE Business B57.',
        'Модель: ARTLINE Business B57',
        39879,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/091505/3094e61128fcadc82e11ab244e589698-770x770.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Business X22',
        'Робочий комп’ютер ARTLINE Business X22.',
        'Модель: ARTLINE Business X22',
        41379,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/071548/product-1046x1046.jpg.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Gaming A21',
        'Ігровий ПК ARTLINE Gaming A21.',
        'Модель: ARTLINE Gaming A21',
        117129,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/241140/89421410-770x770.png.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Gaming A21WHITE',
        'Біла версія ігрового ПК ARTLINE Gaming A21.',
        'Модель: ARTLINE Gaming A21WHITE · Білий корпус',
        91879,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/241728/87201311-770x770.png.webp',
    ),
    (
        'Стаціонарний ПК', 'ARTLINE Gaming DRGN',
        'Ігровий ПК серії ARTLINE Gaming DRGN.',
        'Модель: ARTLINE Gaming DRGN',
        94829,
        'https://img.jabko.ua/image/cache/catalog/products/2026/09/241408/product-770x770.jpg.webp',
    ),
    (
        'Приставка', 'Sony PlayStation 5 Slim Blu-ray, Fortnite Flowering Chaos Bundle, 1 ТБ',
        'PS5 Slim із Blu-ray приводом і комплектом Fortnite Flowering Chaos.',
        'Накопичувач: 1 ТБ · Дисковод Blu-ray · Fortnite Flowering Chaos Bundle',
        42399,
        'https://img.jabko.ua/image/cache/catalog/products/2025/11/211525/1000040591-1046x1046.png.webp',
    ),
    (
        'Приставка', 'Microsoft Xbox Series X, 1 ТБ',
        'Домашня ігрова консоль Xbox Series X з накопичувачем 1 ТБ.',
        'Накопичувач: 1 ТБ',
        48199,
        'https://img.jabko.ua/image/cache/catalog/products/2023/03/271257/2-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'Microsoft Xbox Series X Digital Edition, Robot White, 1 ТБ',
        'Цифрова Xbox Series X у білому кольорі Robot White.',
        'Накопичувач: 1 ТБ · Колір: Robot White · Digital Edition',
        49699,
        'https://img.jabko.ua/image/cache/catalog/products/2024/11/071440/692e7e8b-782c-4dbb-afe4-343c94aa8a4f-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'Sony PlayStation 4 Pro, 1 ТБ, Black',
        'Sony PlayStation 4 Pro з накопичувачем 1 ТБ у чорному корпусі.',
        'Накопичувач: 1 ТБ · Колір: Black',
        10477,
        'https://img.jabko.ua/image/cache/catalog/products/2026/01/261704/4-Pro-1046x1046.png.webp',
    ),
    (
        'Приставка', 'Microsoft Xbox Series S, 1 ТБ, White (Ultra)',
        'Цифрова Xbox Series S у білому кольорі з накопичувачем 1 ТБ.',
        'Накопичувач: 1 ТБ · Колір: White · Серія Ultra',
        32499,
        'https://img.jabko.ua/image/cache/catalog/products/2023/03/271253/2-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'Microsoft Xbox Series S, 1 ТБ, Carbon Black',
        'Цифрова Xbox Series S Carbon Black з накопичувачем 1 ТБ.',
        'Накопичувач: 1 ТБ · Колір: Carbon Black',
        20498,
        'https://img.jabko.ua/image/cache/catalog/products/2023/09/191214/2-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'Lenovo Legion Go S, 32 ГБ / 1 ТБ',
        'Портативна ігрова система з 32 ГБ пам’яті та SSD 1 ТБ.',
        'Пам’ять: 32 ГБ · Накопичувач: 1 ТБ',
        35999,
        'https://img.jabko.ua/image/cache/catalog/products/2025/11/121732/product-770x770.jpg.webp',
    ),
    (
        'Приставка', 'MSI Claw A1M Intel Ultra 7, 1 ТБ, Black',
        'Портативна MSI Claw з Intel Core Ultra 7 і накопичувачем 1 ТБ.',
        'Процесор: Intel Ultra 7 · Накопичувач: 1 ТБ · Колір: Black',
        29999,
        'https://img.jabko.ua/image/cache/catalog/products/2024/04/251620/gjkfgjjfkfbh-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'ASUS ROG Ally',
        'Портативна ігрова система ASUS ROG Ally для ПК-ігор.',
        'Модель: ASUS ROG Ally',
        24999,
        'https://img.jabko.ua/image/cache/catalog/products/2023/06/121728/22%20(1)-1046x1046.jpg.webp',
    ),
    (
        'Приставка', 'ASUS ROG Xbox Ally X, 1 ТБ',
        'Портативна ігрова система ROG Xbox Ally X з накопичувачем 1 ТБ.',
        'Накопичувач: 1 ТБ',
        53999,
        'https://img.jabko.ua/image/cache/catalog/products/2025/10/281504/65787654-770x770.jpg.webp',
    ),
)


LEGACY_PRODUCT_NAMES = (
    'Apple MacBook Pro 14″ M5 16/1TB (MDE54UA/A), Silver',
    'Acer Predator Helios Neo 16S AI (NH.U0KAA.001)',
    'Lenovo LOQ 17IRX10',
    'LG Gram Book 17 (17Z90TL-H.AUB7U1), Black',
    'Dream Machines RG5060-17 (RG5060-17UA32)',
    'ASUS ROG Zephyrus G14 (GA403UM-G14.R9HX4)',
    'ARTLINE Gaming PBG (PBGv01)',
    'Ігровий ПК Lumen',
    'ARTLINE Gaming PBGWHITE (PBGWHITEv07)',
    'Ігрова приставка Sony PlayStation 5 Slim (CFI-2116)',
    'Ігрова консоль Microsoft Xbox Series S 512GB White (889842651386) [50322]',
    'Ігрова приставка Microsoft Xbox Series X 1TB (889842640816)',
)

DEMO_CATALOG_COPY_MIGRATION = 'refresh-demo-catalog-copy-2026-11'
REPLACED_LAPTOP_NAME = 'HP ProBook 4 G1ah, 14″'


def now():
    """Return a readable local timestamp for records in the demo database."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_db():
    """Return one SQLite connection for the current Flask request/context."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(exception=None):
    """Close the request-scoped database connection, if one was opened."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """Create tables and add the current demo catalog and promotion data."""
    db = get_db()
    db.executescript(SCHEMA)
    with db:
        db.executemany(
            '''INSERT INTO products
               (category, name, description, specifications, price, image_url, created_at)
               SELECT ?, ?, ?, ?, ?, ?, ?
               WHERE NOT EXISTS (SELECT 1 FROM products WHERE name = ?)''',
            [(*product, now(), product[1]) for product in INITIAL_PRODUCTS],
        )
        db.execute(
            '''INSERT OR IGNORE INTO promo_codes (code, discount_percent, is_active, created_at)
               VALUES (?, ?, ?, ?)''',
            ('AVANGARD10', 10, 1, now()),
        )
        migration_version = 'replace-old-demo-catalog-2026-11'
        migration_applied = db.execute(
            'SELECT 1 FROM app_migrations WHERE version = ?',
            (migration_version,),
        ).fetchone()
        if migration_applied is None:
            db.executemany(
                'UPDATE products SET is_available = 0, image_url = ? WHERE name = ?',
                [('', name) for name in LEGACY_PRODUCT_NAMES],
            )
            db.execute(
                'INSERT INTO app_migrations (version, applied_at) VALUES (?, ?)',
                (migration_version, now()),
            )

        copy_migration_applied = db.execute(
            'SELECT 1 FROM app_migrations WHERE version = ?',
            (DEMO_CATALOG_COPY_MIGRATION,),
        ).fetchone()
        if copy_migration_applied is None:
            dell_product = next(
                product for product in INITIAL_PRODUCTS
                if product[1].startswith('Ноутбук Dell Alienware 16 Aurora AC16250')
            )
            old_laptop = db.execute(
                'SELECT id FROM products WHERE name = ? AND is_available = 1',
                (REPLACED_LAPTOP_NAME,),
            ).fetchone()
            dell_in_catalog = db.execute(
                'SELECT id FROM products WHERE name = ? AND is_available = 1',
                (dell_product[1],),
            ).fetchone()

            if old_laptop and dell_in_catalog:
                # Keep any historical order references while removing the duplicate from the shop.
                db.execute(
                    'UPDATE products SET is_available = 0, image_url = ? WHERE id = ?',
                    ('', old_laptop['id']),
                )
            elif old_laptop:
                db.execute(
                    '''UPDATE products
                       SET category = ?, name = ?, description = ?, specifications = ?,
                           price = ?, image_url = ?
                       WHERE id = ?''',
                    (*dell_product, old_laptop['id']),
                )

            db.executemany(
                'UPDATE products SET description = ? WHERE name = ?',
                [(product[2], product[1]) for product in INITIAL_PRODUCTS],
            )
            db.execute(
                'INSERT INTO app_migrations (version, applied_at) VALUES (?, ?)',
                (DEMO_CATALOG_COPY_MIGRATION, now()),
            )


# ------------------------------------------------------------------- clients

def get_clients():
    return get_db().execute('SELECT * FROM clients ORDER BY id DESC').fetchall()


def get_client(client_id):
    return get_db().execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()


def get_client_by_email(email):
    """Find a client by their normalized email address."""
    return get_db().execute(
        'SELECT * FROM clients WHERE email = ?',
        (email.strip().lower(),),
    ).fetchone()


def add_client(name, email, phone=''):
    db = get_db()
    with db:
        cursor = db.execute(
            'INSERT INTO clients (name, email, phone, created_at) VALUES (?, ?, ?, ?)',
            (name.strip(), email.strip().lower(), phone.strip(), now()),
        )
    return cursor.lastrowid


def update_client(client_id, name, email, phone=''):
    db = get_db()
    with db:
        db.execute(
            'UPDATE clients SET name = ?, email = ?, phone = ? WHERE id = ?',
            (name.strip(), email.strip().lower(), phone.strip(), client_id),
        )


def delete_client(client_id):
    db = get_db()
    with db:
        db.execute('DELETE FROM clients WHERE id = ?', (client_id,))


# ------------------------------------------------------------------ feedback

def add_feedback(name, email, message, client_id=None):
    db = get_db()
    if client_id is None:
        client = get_client_by_email(email)
        if client is not None:
            client_id = client['id']
    with db:
        cursor = db.execute(
            '''INSERT INTO feedback (client_id, name, email, message, created_at)
               VALUES (?, ?, ?, ?, ?)''',
            (client_id, name.strip(), email.strip().lower(), message.strip(), now()),
        )
    return cursor.lastrowid


def get_feedback():
    return get_db().execute('SELECT * FROM feedback ORDER BY id DESC').fetchall()


def get_feedback_item(feedback_id):
    return get_db().execute('SELECT * FROM feedback WHERE id = ?', (feedback_id,)).fetchone()


def update_feedback(feedback_id, name, email, message):
    db = get_db()
    with db:
        db.execute(
            'UPDATE feedback SET name = ?, email = ?, message = ? WHERE id = ?',
            (name.strip(), email.strip().lower(), message.strip(), feedback_id),
        )


def delete_feedback(feedback_id):
    db = get_db()
    with db:
        db.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))


# ------------------------------------------------------------------- products

def get_products(query='', category=''):
    """List products, optionally filtering by text and category."""
    sql = 'SELECT * FROM products WHERE is_available = 1'
    params = []
    if query.strip():
        pattern = f"%{query.strip()}%"
        sql += ' AND (name LIKE ? OR description LIKE ? OR specifications LIKE ?)'
        params.extend((pattern, pattern, pattern))
    if category.strip():
        sql += ' AND category = ?'
        params.append(category.strip())
    sql += ' ORDER BY id'
    return get_db().execute(sql, params).fetchall()


def get_product(product_id):
    return get_db().execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()


def get_products_by_ids(ids):
    ids = list(ids)
    if not ids:
        return []
    placeholders = ','.join('?' for _ in ids)
    return get_db().execute(
        f'SELECT * FROM products WHERE id IN ({placeholders})', ids
    ).fetchall()


def add_product(category, name, description, specifications, price, image_url):
    db = get_db()
    with db:
        cursor = db.execute(
            '''INSERT INTO products
               (category, name, description, specifications, price, image_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (category, name, description, specifications, price, image_url, now()),
        )
    return cursor.lastrowid


def update_product(product_id, category, name, description, specifications, price, image_url):
    db = get_db()
    with db:
        db.execute(
            '''UPDATE products
               SET category = ?, name = ?, description = ?, specifications = ?,
                   price = ?, image_url = ?
               WHERE id = ?''',
            (category, name, description, specifications, price, image_url, product_id),
        )


def delete_product(product_id):
    """Delete an unused product; referenced products are protected by SQLite."""
    db = get_db()
    with db:
        db.execute('DELETE FROM products WHERE id = ?', (product_id,))


# -------------------------------------------------------------- промокоди

def get_promo_codes():
    return get_db().execute('SELECT * FROM promo_codes ORDER BY id DESC').fetchall()


def get_promo_code(code):
    normalized_code = code.strip().upper()
    return get_db().execute(
        'SELECT * FROM promo_codes WHERE code = ?', (normalized_code,)
    ).fetchone()


def add_promo_code(code, discount_percent, is_active=True):
    normalized_code = code.strip().upper()
    discount_percent = float(discount_percent)
    if not normalized_code:
        raise ValueError('Вкажіть код промокоду.')
    if not 0 < discount_percent <= 100:
        raise ValueError('Знижка має бути більшою за 0 і не перевищувати 100%.')

    db = get_db()
    with db:
        cursor = db.execute(
            '''INSERT INTO promo_codes (code, discount_percent, is_active, created_at)
               VALUES (?, ?, ?, ?)''',
            (normalized_code, discount_percent, int(bool(is_active)), now()),
        )
    return cursor.lastrowid


def update_promo_code(promo_id, code, discount_percent, is_active):
    normalized_code = code.strip().upper()
    discount_percent = float(discount_percent)
    if not normalized_code:
        raise ValueError('Вкажіть код промокоду.')
    if not 0 < discount_percent <= 100:
        raise ValueError('Знижка має бути більшою за 0 і не перевищувати 100%.')

    db = get_db()
    with db:
        db.execute(
            '''UPDATE promo_codes
               SET code = ?, discount_percent = ?, is_active = ?
               WHERE id = ?''',
            (normalized_code, discount_percent, int(bool(is_active)), promo_id),
        )


def delete_promo_code(promo_id):
    db = get_db()
    with db:
        db.execute('DELETE FROM promo_codes WHERE id = ?', (promo_id,))


# -------------------------------------------------------------------- orders

def create_order(customer_name, email, address, cart, client_id=None, promo_code=''):
    """Create an order atomically, linking or creating its client by email."""
    normalized_cart = {}
    for raw_product_id, raw_quantity in cart.items():
        try:
            product_id = int(raw_product_id)
            quantity = int(raw_quantity)
        except (TypeError, ValueError) as error:
            raise ValueError('Некоректний товар або кількість у кошику') from error
        if product_id <= 0 or quantity <= 0:
            raise ValueError('Кількість товару має бути більшою за нуль')
        normalized_cart[product_id] = quantity

    products = get_products_by_ids(normalized_cart.keys())
    if not products:
        raise ValueError('Кошик порожній')
    if len(products) != len(normalized_cart):
        raise ValueError('Один або кілька товарів більше недоступні')

    subtotal = round(
        sum(product['price'] * normalized_cart[product['id']] for product in products), 2
    )
    normalized_promo = promo_code.strip().upper()
    discount_amount = 0
    if normalized_promo:
        promotion = get_promo_code(normalized_promo)
        if promotion is None or not promotion['is_active']:
            raise ValueError('Промокод не знайдено або він неактивний.')
        discount_amount = round(subtotal * promotion['discount_percent'] / 100, 2)
    total = round(subtotal - discount_amount, 2)

    db = get_db()
    normalized_email = email.strip().lower()
    with db:
        if client_id is None:
            client = db.execute(
                'SELECT id FROM clients WHERE email = ?',
                (normalized_email,),
            ).fetchone()
            if client is None:
                client_cursor = db.execute(
                    '''INSERT INTO clients (name, email, phone, created_at)
                       VALUES (?, ?, ?, ?)''',
                    (customer_name.strip(), normalized_email, '', now()),
                )
                client_id = client_cursor.lastrowid
            else:
                client_id = client['id']

        cursor = db.execute(
            '''INSERT INTO orders
               (client_id, customer_name, email, address, total_price, promo_code,
                discount_amount, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (client_id, customer_name.strip(), normalized_email, address.strip(),
             total, normalized_promo, discount_amount, ORDER_STATUSES[0], now()),
        )
        order_id = cursor.lastrowid
        db.executemany(
            '''INSERT INTO order_items (order_id, product_id, quantity, unit_price)
               VALUES (?, ?, ?, ?)''',
            [(order_id, product['id'], normalized_cart[product['id']], product['price'])
             for product in products],
        )
    return order_id


def get_orders():
    return get_db().execute('SELECT * FROM orders ORDER BY id DESC').fetchall()


def get_order(order_id):
    return get_db().execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()


def get_order_details(order_id):
    db = get_db()
    order = db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    items = db.execute(
        '''SELECT p.name, oi.quantity, oi.unit_price,
                  (oi.quantity * oi.unit_price) AS subtotal
           FROM order_items AS oi
           JOIN products AS p ON p.id = oi.product_id
           WHERE oi.order_id = ? ORDER BY oi.id''',
        (order_id,),
    ).fetchall()
    return order, items


def update_order_status(order_id, status):
    if status not in ORDER_STATUSES:
        raise ValueError(f'Невідомий статус замовлення: {status}')
    db = get_db()
    with db:
        db.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))


def delete_order(order_id):
    """The database removes related order_items through ON DELETE CASCADE."""
    db = get_db()
    with db:
        db.execute('DELETE FROM orders WHERE id = ?', (order_id,))
