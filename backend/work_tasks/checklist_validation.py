from decimal import Decimal, InvalidOperation
from .exceptions import TaskValidationError
from .models import ChecklistItemSchema

SCHEMA_FIELDS = ('text', 'position', 'required', 'section', 'help_text', 'answer_type', 'options', 'min_value', 'max_value')


def validate_schema(item):
    kind = item.get('answer_type', 'checkbox')
    if kind not in ChecklistItemSchema.AnswerType.values:
        raise TaskValidationError('Неизвестный тип ответа.')
    if not str(item.get('text', '')).strip():
        raise TaskValidationError('Заполните текст пункта.')
    options = item.get('options', [])
    if not isinstance(options, list) or len(options) > 100 or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in options):
        raise TaskValidationError('Варианты должны быть непустыми строками (до 100 вариантов).')
    if kind in ('single', 'multiple') and (len(options) < 2 or len(set(options)) != len(options)):
        raise TaskValidationError('Укажите минимум два различных варианта ответа.')
    if kind not in ('single', 'multiple') and options:
        raise TaskValidationError('Варианты доступны только для выбора ответа.')
    low, high = item.get('min_value'), item.get('max_value')
    if kind != 'number' and (low is not None or high is not None):
        raise TaskValidationError('Границы доступны только для числового ответа.')
    if low is not None and high is not None and low > high:
        raise TaskValidationError('Минимум не может быть больше максимума.')
    return item


def validate_items(items):
    if len(items) > 200:
        raise TaskValidationError('Максимум 200 пунктов в чек-листе.')
    positions = set()
    for index, item in enumerate(items, 1):
        validate_schema(item)
        position = item.get('position', index)
        if not isinstance(position, int) or isinstance(position, bool) or position < 0 or position in positions:
            raise TaskValidationError('Порядок пунктов должен быть уникальным неотрицательным числом.')
        positions.add(position)


def validate_answer(item, value):
    kind = item.answer_type
    if kind == 'checkbox':
        if value is not True:
            raise TaskValidationError('Подтвердите выполнение пункта.')
    elif kind == 'boolean':
        if not isinstance(value, bool):
            raise TaskValidationError('Выберите Да или Нет.')
    elif kind == 'text':
        if not isinstance(value, str) or not value.strip() or len(value) > 10000:
            raise TaskValidationError('Введите текст ответа (до 10000 символов).')
        value = value.strip()
    elif kind == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TaskValidationError('Введите число.')
        try:
            number = Decimal(str(value))
            if not number.is_finite() or (item.min_value is not None and number < item.min_value) or (item.max_value is not None and number > item.max_value):
                raise TaskValidationError('Число вне допустимого диапазона.')
        except InvalidOperation:
            raise TaskValidationError('Введите корректное число.')
    elif kind == 'single':
        if not isinstance(value, str) or value not in item.options:
            raise TaskValidationError('Выберите один из предложенных вариантов.')
    elif kind == 'multiple':
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or x not in item.options for x in value) or len(set(value)) != len(value):
            raise TaskValidationError('Выберите различные варианты из списка.')
    return value
