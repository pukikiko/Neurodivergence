FROM python
RUN mkdir /data
WORKDIR /data
COPY . /data
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install -r /data/requirements.txt
RUN chmod +x /data/docker-entrypoint.sh
ENTRYPOINT ["/data/docker-entrypoint.sh"]