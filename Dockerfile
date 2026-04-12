FROM python
RUN mkdir /data
WORKDIR /data
COPY . /data
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -r /data/requirements.txt
RUN chmod +x /data/docker-entrypoint.sh
ENTRYPOINT ["/data/docker-entrypoint.sh"]
