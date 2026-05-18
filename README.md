# PPTX Proofreader MVP

Локальный MVP для проверки презентаций `.pptx` на опечатки, орфографию и простые ошибки согласования.

## Запуск

```bash
docker-compose up --build
```

Если используется старый `docker-compose 1.29.x` и при пересоздании контейнера появляется ошибка
`KeyError: 'ContainerConfig'`, сначала удалите старые контейнеры проекта:

```bash
docker-compose down --remove-orphans
docker-compose up --build
```

После запуска:

- frontend: http://localhost:3005
- backend health: http://localhost:8005/health
- API загрузки из интерфейса: `POST /api/check-pptx` на frontend, дальше Nuxt проксирует запрос в `backend:8000`

При запуске на виртуалке открывайте фронт как `http://<ip-виртуалки>:3005`. Интерфейс не обращается к `localhost:8005` из браузера, поэтому запросы не уходят на машину пользователя и не ловят CORS.

## Состав

- `backend` - FastAPI, `python-pptx`, `symspellpy`, `pymorphy3`, опциональный `language-tool-python`.
- `frontend` - Nuxt 4, TypeScript, Tailwind, Vuetify.
- `docker-compose.yml` - запуск всего стека одной командой.

Документы обрабатываются локально. Исходный файл не изменяется, временный файл удаляется после проверки.

## Опциональный Ollama-режим

Для локальной LLM-проверки можно поднять Ollama рядом с приложением:

```bash
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

Для старого `docker-compose 1.29.x` перед повторным запуском Ollama-стека:

```bash
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml down --remove-orphans
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

Затем один раз загрузить модель:

```bash
docker-compose -f docker-compose.yml -f docker-compose.ollama.yml exec ollama ollama pull qwen2.5:7b
```

После этого включите переключатель `Ollama` в интерфейсе.
