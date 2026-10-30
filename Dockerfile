FROM python:3.13-slim

# 系统依赖：libgl1（cv2）、libglib2.0-0（Pillow/scikit-image）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker layer cache，代码改动不重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝代码（模型、uploads、outputs 通过 volume 挂载，不进镜像）
COPY app.py ai_cutout.py ./
COPY templates/ ./templates/

# 声明挂载点
VOLUME ["/app/models", "/app/uploads", "/app/static/outputs"]

EXPOSE 5000

# 生产模式默认参数
ENV PROD=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    THREADS=4 \
    MAX_UPLOAD_MB=5 \
    FLASK_DEBUG=

CMD ["python", "app.py"]
