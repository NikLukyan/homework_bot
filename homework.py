import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import HTTPRequestError, ParseStatusError, NikitaError, NotSendMessageTelegram

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
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Пробуем отправить сообщение в Telegram.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.exception(f'Ошибка при отправке пользователю: {error}')
    except telegram.error:
        raise NotSendMessageTelegram()
    else:
        logging.debug('Отправка сообщения в Telegram прошла удачно.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    logging.info(f'Отправка запроса на {ENDPOINT} с параметрами {payload}')
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=payload)
    except requests.exceptions.RequestException:
        stat_err = homework_statuses
        message = f"Ошибка при запросе к API {stat_err}"
        logging.error(message)
        raise requests.exceptions.RequestException(message)
    except Exception as error:
        logging.error(f'Ошибка запроса к API адресу: {error}')
        raise HTTPRequestError(homework_statuses)
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
    if not isinstance(response, dict):
        message = 'Тип данных ответа от API адреса не dict.'
        logging.error(message)
        raise TypeError(message)
    try:
        homeworks_list = response['homeworks']
    except KeyError:
        message = 'В ответе API отсутствует ожидаемый ключ "homeworks".'
        logging.error(message)
        raise KeyError(message)
    if not isinstance(homeworks_list, list):
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
    try:
        homework['status']
    except Exception as err:
        message = f'В ответе API отсутствует ожидаемый ключ "status".{err}'
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
        message = (
            'Отсутствует обязательная переменная окружения.\n'
            'Программа принудительно остановлена.'
        )
        logging.critical(message)
        sys.exit(message)
    error_message = ''
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
        except NikitaError as err:
            message = f'Приключилась такая беда: {err}'
            logging.error(message)
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            if error != error_message:
                send_message(bot, message)
                error_message = error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s [%(levelname)s] | '
            '(%(filename)s).%(funcName)s:%(lineno)d | %(message)s'
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
