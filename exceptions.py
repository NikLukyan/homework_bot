class HTTPRequestError(Exception):
    def __init__(self, response):
        message = (
            f'Эндпоинт {response.url} недоступен. '
            f'Код ответа API: {response.status_code}]'
        )
        super().__init__(message)


class ParseStatusError(Exception):
    def __init__(self, text):
        message = (
            f'Парсинг ответа API: {text}'
        )
        super().__init__(message)


class CheckResponseError(Exception):
    def __init__(self, text):
        message = (
            f'Проверка ответа API: {text}'
        )
        super().__init__(message)