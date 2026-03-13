FROM python:3.11-slim

WORKDIR /app

COPY dockerScripts /app/dockerScripts

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com sssekai Pillow

ENV RECEIVER_PORT=3939
ENV API_REGION=cn
ENV PUBLIC_HOST=127.0.0.1
ENV OUTPUT_ROOT=/data
ENV MYSEKAI_RESOURCE_MAP_JSON=/data/config/mysekai_resource_map.json
ENV BOT_MESSAGE_MODE=text+image
ENV MYSEKAI_MAP_IMAGE_SIZE=1024
ENV TZ=Asia/Shanghai

EXPOSE 3939

CMD ["python", "/app/dockerScripts/import http.py"]
