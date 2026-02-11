FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN echo "Acquire::http::Timeout \"60\";" > /etc/apt/apt.conf.d/99timeout && \
    echo "Acquire::ftp::Timeout \"60\";" >> /etc/apt/apt.conf.d/99timeout && \
    sed -i 's/deb.debian.org/ftp.uni-stuttgart.de/g' /etc/apt/sources.list.d/debian.sources || true

RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY team5/requirements.txt /app/team5/requirements.txt
RUN pip install --upgrade pip
RUN pip install --default-timeout=100 -r /app/team5/requirements.txt

COPY . /app/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]