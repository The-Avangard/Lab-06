const PRODUCTS_API_URL = '/api/v2/products';

const elements = {
    apiStatus: document.getElementById('apiStatus'),
    apiStatusText: document.getElementById('apiStatusText'),
    message: document.getElementById('message'),
    filterForm: document.getElementById('filterForm'),
    searchInput: document.getElementById('searchInput'),
    categoryFilter: document.getElementById('categoryFilter'),
    reloadButton: document.getElementById('reloadButton'),
    productCount: document.getElementById('productCount'),
    loading: document.getElementById('loading'),
    emptyState: document.getElementById('emptyState'),
    productList: document.getElementById('productList'),
    addProductForm: document.getElementById('addProductForm'),
    submitButton: document.getElementById('submitButton'),
};

let messageTimeout;
let busy = false;

function showMessage(text, type = 'info') {
    window.clearTimeout(messageTimeout);
    elements.message.textContent = text;
    elements.message.dataset.type = type;
    elements.message.hidden = false;

    messageTimeout = window.setTimeout(() => {
        elements.message.hidden = true;
    }, 6500);
}

function setApiStatus(state, text) {
    elements.apiStatus.dataset.state = state;
    elements.apiStatusText.textContent = text;
}

function setBusy(value) {
    busy = value;
    elements.reloadButton.disabled = value;
    elements.submitButton.disabled = value;
    elements.submitButton.textContent = value ? 'Зачекайте…' : 'Додати товар';
}

function getApiError(payload, status) {
    const apiError = payload?.error;
    const message = typeof apiError === 'string'
        ? apiError
        : apiError?.message || payload?.message;
    const details = apiError?.details || payload?.details;

    let detailText = '';
    if (details && typeof details === 'object') {
        detailText = Object.values(details)
            .map(value => Array.isArray(value) ? value.join(', ') : String(value))
            .filter(Boolean)
            .join(' ');
    }

    return [message || `Сервер повернув помилку HTTP ${status}.`, detailText]
        .filter(Boolean)
        .join(' ');
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload;

    try {
        payload = await response.json();
    } catch {
        payload = null;
    }

    if (!response.ok) {
        throw new Error(getApiError(payload, response.status));
    }

    if (
        !payload ||
        payload.version !== 'v2' ||
        !Object.prototype.hasOwnProperty.call(payload, 'data')
    ) {
        throw new Error('API повернуло відповідь у неочікуваному форматі.');
    }

    return payload.data;
}

function formatPrice(price) {
    const numericPrice = Number(price);
    if (!Number.isFinite(numericPrice)) return 'Ціну не вказано';

    return new Intl.NumberFormat('uk-UA', {
        style: 'currency',
        currency: 'UAH',
        maximumFractionDigits: 2,
    }).format(numericPrice);
}

function formatProductCount(count) {
    const lastTwo = count % 100;
    const last = count % 10;
    let noun = 'товарів';

    if (lastTwo < 11 || lastTwo > 14) {
        if (last === 1) noun = 'товар';
        else if (last >= 2 && last <= 4) noun = 'товари';
    }

    return `${count} ${noun}`;
}

function safeImageUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return '';

    try {
        const url = new URL(value, window.location.origin);
        return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch {
        return '';
    }
}

function createProductCard(product) {
    const card = document.createElement('article');
    card.className = 'api-product-card';

    const imageWrap = document.createElement('div');
    imageWrap.className = 'api-product-image-wrap';

    const imageUrl = safeImageUrl(product.image_url);
    if (imageUrl) {
        const image = document.createElement('img');
        image.className = 'api-product-image';
        image.src = imageUrl;
        image.alt = product.name ? `Зображення товару ${product.name}` : 'Зображення товару';
        image.loading = 'lazy';
        image.addEventListener('error', () => {
            const fallback = document.createElement('span');
            fallback.className = 'api-product-image-fallback';
            fallback.setAttribute('aria-label', 'Зображення недоступне');
            fallback.textContent = '▧';
            image.replaceWith(fallback);
        }, { once: true });
        imageWrap.appendChild(image);
    } else {
        const fallback = document.createElement('span');
        fallback.className = 'api-product-image-fallback';
        fallback.setAttribute('aria-hidden', 'true');
        fallback.textContent = '▧';
        imageWrap.appendChild(fallback);
    }

    const body = document.createElement('div');
    body.className = 'api-product-card-body';

    const topline = document.createElement('div');
    topline.className = 'api-product-card-topline';

    const category = document.createElement('span');
    category.className = 'api-product-category';
    category.textContent = product.category || 'Без категорії';

    const id = document.createElement('span');
    id.className = 'api-product-id';
    id.textContent = `ID ${product.id ?? '—'}`;
    topline.append(category, id);

    const title = document.createElement('h3');
    title.textContent = product.name || 'Без назви';

    const description = document.createElement('p');
    description.className = 'api-product-description';
    description.textContent = product.description || 'Опис товару не додано.';

    const specifications = document.createElement('p');
    specifications.className = 'api-product-specifications';
    specifications.textContent = product.specifications || 'Характеристики не вказані';

    const footer = document.createElement('div');
    footer.className = 'api-product-card-footer';

    const price = document.createElement('span');
    price.className = 'api-product-price';
    price.textContent = formatPrice(product.price);

    const availability = document.createElement('span');
    const isAvailable = Boolean(product.is_available);
    availability.className = isAvailable
        ? 'api-availability'
        : 'api-availability api-availability--unavailable';
    availability.textContent = isAvailable ? 'Є в наявності' : 'Немає в наявності';
    footer.append(price, availability);

    body.append(topline, title, description, specifications, footer);
    card.append(imageWrap, body);
    return card;
}

function displayProducts(products) {
    elements.productList.replaceChildren();
    elements.productCount.textContent = formatProductCount(products.length);
    elements.emptyState.hidden = products.length > 0;

    const fragment = document.createDocumentFragment();
    products.forEach(product => fragment.appendChild(createProductCard(product)));
    elements.productList.appendChild(fragment);
}

function friendlyNetworkError(error) {
    if (error instanceof TypeError) {
        return 'Не вдалося зв’язатися із сервером. Переконайтеся, що Flask-застосунок запущений.';
    }
    return error.message || 'Сталася невідома помилка.';
}

async function loadProducts({ silent = false } = {}) {
    const params = new URLSearchParams();
    const query = elements.searchInput.value.trim();
    const category = elements.categoryFilter.value;
    if (query) params.set('q', query);
    if (category) params.set('category', category);

    const queryString = params.toString();
    const url = queryString ? `${PRODUCTS_API_URL}?${queryString}` : PRODUCTS_API_URL;
    elements.loading.hidden = false;
    elements.emptyState.hidden = true;
    setBusy(true);

    try {
        const products = await requestJson(url);
        if (!Array.isArray(products)) {
            throw new Error('API повернуло список товарів у неочікуваному форматі.');
        }

        displayProducts(products);
        setApiStatus('online', `З’єднання з API активне · завантажено ${formatProductCount(products.length)}`);
        return true;
    } catch (error) {
        setApiStatus('offline', 'Не вдалося отримати відповідь від API');
        if (!silent) {
            showMessage(`Помилка завантаження: ${friendlyNetworkError(error)}`, 'error');
        }
        return false;
    } finally {
        elements.loading.hidden = true;
        setBusy(false);
    }
}

function validateProductForm() {
    const formData = new FormData(elements.addProductForm);
    const category = String(formData.get('category') || '').trim();
    const name = String(formData.get('name') || '').trim();
    const priceText = String(formData.get('price') || '').trim();
    const imageUrl = String(formData.get('image_url') || '').trim();
    const errors = [];

    if (!category) errors.push('оберіть категорію');
    if (name.length < 2) errors.push('назва має містити щонайменше 2 символи');
    if (name.length > 120) errors.push('назва має бути не довшою за 120 символів');

    const price = Number(priceText);
    if (!priceText || !Number.isFinite(price) || price < 0) {
        errors.push('вкажіть коректну ціну, не меншу за 0');
    }

    if (imageUrl) {
        try {
            const url = new URL(imageUrl);
            if (!['http:', 'https:'].includes(url.protocol)) {
                errors.push('посилання на зображення має починатися з http:// або https://');
            }
        } catch {
            errors.push('вкажіть коректне посилання на зображення');
        }
    }

    if (errors.length) {
        showMessage(`Перевірте форму: ${errors.join('; ')}.`, 'error');
        return null;
    }

    return {
        category,
        name,
        price,
        description: String(formData.get('description') || '').trim(),
        specifications: String(formData.get('specifications') || '').trim(),
        image_url: imageUrl,
    };
}

async function addProduct(event) {
    event.preventDefault();
    if (busy) return;

    const product = validateProductForm();
    if (!product) return;

    setBusy(true);
    try {
        await requestJson(PRODUCTS_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(product),
        });

        elements.addProductForm.reset();
        const listUpdated = await loadProducts({ silent: true });
        if (listUpdated) {
            showMessage('Товар успішно додано до каталогу.', 'success');
        } else {
            showMessage('Товар додано, але список не вдалося оновити. Натисніть «Оновити».', 'info');
        }
    } catch (error) {
        const networkError = error instanceof TypeError;
        setApiStatus(networkError ? 'offline' : 'online', networkError ? 'Сервер недоступний' : 'API відповідає');
        showMessage(`Не вдалося додати товар: ${friendlyNetworkError(error)}`, 'error');
    } finally {
        setBusy(false);
    }
}

elements.filterForm.addEventListener('submit', event => {
    event.preventDefault();
    if (!busy) loadProducts();
});

elements.reloadButton.addEventListener('click', () => {
    if (!busy) loadProducts();
});

elements.addProductForm.addEventListener('submit', addProduct);

loadProducts();
