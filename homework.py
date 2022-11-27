import json
import sys
import time

import logging
import os

import requests
import telegram
from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import HTTPRequestError, ParseStatusError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTIC_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELE_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELE_CHAT')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    list_env = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    return all(list_env)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Отправка сообщения в Telegram прошла удачно.')
    except Exception as error:
        logging.error(f'Ошибка при отправке пользователю: {error}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""

    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.exceptions.RequestException:
        stat_err = homework_statuses.status_code
        message = f"Ошибка при запросе к API: {stat_err}"
        logging.error(message)
        raise requests.exceptions.RequestException(message)

    if homework_statuses.status_code != HTTPStatus.OK:
        logging.error(
            f'Ошибка ответа от API адреса: {homework_statuses.status_code}'
        )
        raise HTTPRequestError(homework_statuses)
    try:
        homework_statuses.json()
    except json.JSONDecodeError as error:
        logging.error(
            f'Ответ от API адреса не преобразован в json(): {error}.'
        )
    return homework_statuses.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    if type(response) is not dict:
        message = 'Тип данных ответа от API адреса не dict.'
        logging.error(message)
        raise TypeError(message)
    try:
        homeworks_list = response.get('homeworks')
    except KeyError:
        message = 'В ответе API отсутствует ожидаемый ключ "homeworks".'
        logging.error(message)
        raise KeyError(message)
    if type(homeworks_list) is not list:
        message = 'формат ответа не соответствует.'
        logging.error(message)
        raise TypeError(message)
    try:
        homework = homeworks_list[0]
    except IndexError:
        message = 'Список работ на проверке пуст.'
        logging.error(message)
        raise IndexError(message)
    return homework


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        message = 'В ответе API отсутствует ожидаемый ключ "homework_name".'
        logging.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'В ответе API отсутствует ожидаемый ключ "status".'
        logging.error(message)
        raise ParseStatusError(message)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        message = ('Обнаружен недокументированный статус '
                   'домашней работы в ответе API.')
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'Отсутствует обязательная переменная окружения.\n'
            'Программа принудительно остановлена.'
        )
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        stream=sys.stdout

    )
    main()
