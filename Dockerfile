# Imagem da aplicação web (Django) do Data Analyst AI
FROM python:3.14-slim

# Logs aparecem na hora no Docker Desktop e o Python não grava .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instala as dependências primeiro: só reinstala quando o requirements.txt mudar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 0.0.0.0 permite acessar o servidor de fora do container
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
