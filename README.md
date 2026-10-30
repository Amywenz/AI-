# Al_Cutout — AI 证件照生成器

上传一张人像照片，自动抠掉背景，换上指定底色并按指定尺寸导出标准证件照。

## 技术栈

- 后端：Flask 3.1 + flask-cors，生产模式用 waitress
- 推理：onnxruntime 1.22（CPU）+ BriaRMBG ONNX 模型
- 图像处理：Pillow / opencv-python / scikit-image / numpy
- 前端：单页 Bootstrap 5（无构建步骤）

## 模型文件（必须自行下载）

`models/rmbg/onnx/model.onnx` 约 168MB，超过 GitHub 单文件限制，未纳入仓库，需要自行下载后放到该路径：

- 来源：https://huggingface.co/briaai/RMBG-1.4
- 放置位置：`models/rmbg/onnx/model.onnx`

`ai_cutout.py` 用 `__file__` 拼绝对路径，放到该位置即可，无需配置。

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式（127.0.0.1:5000）
python app.py

# 生产模式（waitress）
PROD=1 HOST=0.0.0.0 PORT=5000 python app.py
```

可选环境变量：`THREADS`（waitress 线程数，默认 4）、`MAX_UPLOAD_MB`（上传上限，默认 5）、`FLASK_DEBUG=1`（开发调试）。

Windows 开发机需安装 MSVC 2022 Redistributable，否则 onnxruntime 加载 DLL 失败。

## Docker 部署

```bash
docker compose up -d --build
```

模型文件通过 volume 挂载进容器，不进镜像。

## 接口

- `GET /` — 前端页面
- `POST /api/process` — FormData：`file`、`bg_color`（hex，默认 `#FFFFFF`）、`keep_size`（`true`/`false`）、`width`/`height`（默认 295x413）
- `GET /static/outputs/<file>` — 结果图片
