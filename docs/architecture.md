# Архитектура проекта Enterprise Copilot

## Общее описание
Enterprise Copilot — это AI-система для работы с бизнес-документами.

Пользователь загружает документы, система обрабатывает их, разбивает на части, создает embeddings, сохраняет их в векторное хранилище и затем использует для поиска и ответов на вопросы.

## Общий поток работы
1. Пользователь загружает PDF или DOCX
2. Backend извлекает текст
3. Текст разбивается на chunks
4. Для chunks создаются embeddings
5. Chunks сохраняются в vector storage
6. Пользователь выполняет поиск или задает вопрос
7. Система находит релевантные chunks
8. LLM формирует ответ
9. Ответ возвращается пользователю с указанием источников

## Основные компоненты

### Frontend
- Авторизация
- Загрузка документов
- Список документов
- Поиск
- Чат
- Summary

### Backend
- Auth API
- Document API
- Search API
- Chat API
- Summary API

### Database
- Users
- Documents
- Document Chunks
- Chat Sessions
- Chat Messages

### ML / NLP Layer
- Embedding model
- Vector search
- Retrieval
- LLM generation

## Простая схема

```text
[ Пользователь ]
      |
      v
[ Frontend (React) ]
      |
      v
[ Backend (FastAPI) ]
      |
      +-------------------+
      |                   |
      v                   v
[ PostgreSQL ]      [ Redis / Jobs ]
      |
      v
[ Document Chunks ]
      |
      v
[ Embeddings ]
      |
      v
[ Vector Store ]
      |
      v
[ Retrieval ]
      |
      v
[ LLM ]
      |
      v
[ Ответ с источниками ]