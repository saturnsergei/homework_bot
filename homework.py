import os
from dotenv import load_dotenv
import logging
import telegram
import time
import requests
import sys

from exceptions import UnvalidTokenError, ApiRequestError


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s [%(levelname)s] %(message)s')

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN')
        raise UnvalidTokenError(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN')
    if TELEGRAM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN')
        raise UnvalidTokenError(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN')
    if TELEGRAM_CHAT_ID is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID')
        raise UnvalidTokenError(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID')


def send_message(bot, message):
    """Отправка сообщений в telegram-чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение "{message}"')
    except Exception:
        logger.error('Cбой при отправке сообщения в Telegram')


def get_api_answer(timestamp):
    """Запрос к эндпоинту."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params=payload)

        if response.status_code != 200:
            raise ApiRequestError(
                (f'Сбой запроса при обращении к эндпоинту. '
                 f'Код ответа API: {response.status_code}'))
        return response.json()
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        if response.status_code != 200:
            raise ApiRequestError(
                (f'Сбой запроса при обращении к эндпоинту. '
                 f'Код ответа API: {response.status_code}'))


def check_response(response):
    """Проверка ответа API."""
    if 'homeworks' not in response:
        logger.error('В ответе API отсутствует ключ homeworks')
        raise TypeError('В ответе API отсутствует ключ homeworks')
    if 'current_date' not in response:
        logger.error('В ответе API отсутствует ключ current_date')
        raise TypeError('В ответе API отсутствует ключ current_date')

    if not isinstance(response.get('homeworks'), list):
        logger.error(
            'В ответе API ключ homeworks имеет некорректный тип данных')
        raise TypeError(
            'В ответе API ключ homeworks имеет некорректный тип данных')

    if len(response.get('homeworks')) == 0:
        logger.debug('Статус работы не изменился')


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if homework.get('status') not in HOMEWORK_VERDICTS:
        logger.error('Неподдерживаемый статус работы')
        raise TypeError('Неподдерживаемый статус работы')
    if 'homework_name' not in homework:
        raise TypeError('В ответе API отсутствует ключ homework_name')

    homework_name = homework.get('homework_name')
    status = homework.get('status')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    last_error = ''
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    logger.debug('Бот запущен')
    check_tokens()
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if len(homeworks) > 0:
                telegram_message = parse_status(homeworks[0])
                send_message(bot, telegram_message)

            timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error != message:
                last_error = message
                send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
