FROM --platform=$BUILDPLATFORM python AS build
RUN mkdir /data
WORKDIR /data
COPY . /data
RUN pip install -r /data/requirements.txt
RUN chmod +x /data/docker-entrypoint.sh
ENTRYPOINT ["/data/docker-entrypoint.sh"]