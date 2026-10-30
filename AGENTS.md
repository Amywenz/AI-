# AGENTS.md — Al_Cutout 项目协作约定

> 这是 AI agent 进入项目时的第一份阅读材料。任何会话开始前先读本文件 + MEMORY.md。

## 项目基本信息（自动推断，可修正）

- **项目名**：Al_Cutout
- **创建/接入日期**：2026-09-22
- **位置**：`f:\Al_Cutout`
- **当前 Python 解释器**：`f:\Al_Cutout\.venv`（Python 3.13.15）
- **类型**：B2C 工具型 Web 应用（AI 证件照生成器）
- **部署目标**：Docker 容器（Linux；nginx 反代 + waitress app，两容器同 network）

## 项目目标

基于 ONNX 模型（BriaRMBG）做背景去除 + 自定义底色 + 自定义尺寸的证件照生成 Web 服务。

- 前端：单页 `templates/index.html`（Bootstrap 5），通过 `/api/process` 提交 FormData。
- 后端：Flask，路由 `/` 渲染 index，`/api/process` 处理图片，`/static/outputs/<file>` 提供结果。
- 推理：`ai_cutout.py` 调用 `onnxruntime` 跑 BriaRMBG 模型，输出抠图 mask，再合成纯色背景。

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | Flask 3.1 + flask-cors 6.0 |
| 推理运行时 | onnxruntime 1.22（CPU） |
| 模型 | BriaRMBG ONNX（`home/aistudio/rmbg/onnx/model.onnx`） |
| 图像处理 | Pillow 12 + opencv-python + scikit-image 0.26 |
| 数值 | numpy 2.5 |
| 前端 | Bootstrap 5.3 CDN（无构建步骤） |

## 关键路径与命令

```bash
# 激活虚拟环境（Windows PowerShell）
.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 本地开发服务器（Werkzeug，debug=False 默认，127.0.0.1:5000）
python app.py
# 本地调试模式（开 debug + 自动重载）
$env:FLASK_DEBUG="1"; python app.py

# 生产模式（waitress，多线程，0.0.0.0:5000，由反代暴露公网）
$env:PROD="1"; $env:HOST="0.0.0.0"; $env:PORT="5000"; python app.py
# 可选环境变量：THREADS（waitress 线程数，默认 4）、MAX_UPLOAD_MB（上传上限，默认 5）

# 系统依赖（仅 Windows 开发机）：MSVC 2022 Redistributable 必装
winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-source-agreements --accept-package-agreements

# Docker 部署（生产，Linux 容器，自带 glibc 不需要 vcredist）
docker compose up -d --build              # 构建并启动（首次）
docker compose logs -f app                # 看 app 日志
docker compose down                       # 停止
docker compose pull && docker compose up -d  # 更新镜像
```

- 入口文件：`app.py`（**唯一指定入口**，旧 `main.py` 已删）
- 模型路径：`models/rmbg/onnx/model.onnx`（`ai_cutout.py` 用 `__file__` 拼绝对路径，无需配置）
- Docker 部署文件：[Dockerfile](file:///f:/Al_Cutout/Dockerfile) + [docker-compose.yml](file:///f:/Al_Cutout/docker-compose.yml) + [nginx/nginx.conf](file:///f:/Al_Cutout/nginx/nginx.conf)

## 代码约定

- **语言**：中文注释为主，代码标识符（变量、函数、类）用英文
- **风格**：遵循现有 PEP 8 风格，不做无关重构
- **错误处理**：边界（用户输入、外部 IO）必须 try/except + 日志；内部代码不做防御式编程
- **依赖管理**：所有运行时依赖必须出现在 `requirements.txt`（之前缺 flask/flask-cors 已修正）
- **模型加载**：模块顶层加载一次，禁止在请求路径内重复 `InferenceSession`
- **不创建文档**：除非用户明确要求，不主动新建 `*.md` 文件

## 工作流约束

1. 任何会话开始前先读 `AGENTS.md` + `MEMORY.md`
2. 改结构 → 先改文档再改代码
3. 学到新东西主动回写 `MEMORY.md`
4. 凭据只记位置不记值
5. 不要"顺手改进"无关代码（Karpathy 外科手术式改动）
6. 不清楚就停下问，不要默默选一种解读

## 已知 TODO（按优先级）

- [x] ~~删除 `_ort_probe311/`（探针残留）~~（2026-09-22 完成）
- [x] ~~重命名 `home/aistudio/rmbg/` → `models/rmbg/`，同步改 `ai_cutout.py` 路径~~（2026-09-22 完成）
- [x] ~~删除 `templates/result.html`（死文件）~~（2026-09-22 完成）
- [x] ~~清理 `__pycache__/ai_cutout.cpython-37.pyc`~~（2026-09-22 完成）
- [x] ~~替换 `MAX_CONTENT_LENGTH = 5MB` 为可配置项~~（2026-09-22 完成，环境变量 `MAX_UPLOAD_MB`）
- [x] ~~灰度图 IndexError 修复~~（2026-09-22 完成，`ai_cutout.py` 加 `ndim == 3` 守卫）
- [x] ~~生产 WSGI 服务器~~（2026-09-22 完成，waitress 入口，`PROD=1` 启用）
- [x] ~~加反代（Nginx）配置文件~~（2026-09-22 完成，Docker 部署：`Dockerfile` + `docker-compose.yml` + `nginx/nginx.conf`）
- [ ] 生产部署前：CORS 限定具体 origin（**Docker nginx 同源反代时不需要**；仅当前后端分离部署时才需在 `app.py` 加 `ALLOWED_ORIGINS` 支持）

## 待用户补充

下列字段我无法从代码推断，请你补充后我回写：

- ~~部署目标~~：Docker 容器（2026-09-22 已确认）
- 是否需要对接任何外部 API（OSS、登录、支付）？
- 是否计划把这个项目变成商业产品还是个人工具？
- 部署域名（套 SSL 后用于 nginx server_name 与证书）？
