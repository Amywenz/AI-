from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from ai_cutout import rmbg
import os
from PIL import Image
import uuid
import logging
from flask_cors import CORS

# 初始化Flask应用
app = Flask(__name__)
# TODO 生产部署前：限定具体 origin（如 https://your-domain.com），当前全开仅供本地开发
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'static/outputs'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
# 上传上限通过环境变量 MAX_UPLOAD_MB 配置，默认 5MB
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', '5')) * 1024 * 1024

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def ensure_directory_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        logger.info(f"创建目录: {path}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/process', methods=['POST'])
def process_image():
    try:
        # 检查文件上传
        if 'file' not in request.files:
            logger.error("未收到文件")
            return jsonify({'error': 'No file uploaded', 'code': 400}), 400

        file = request.files['file']
        if file.filename == '':
            logger.error("收到空文件名")
            return jsonify({'error': 'No selected file', 'code': 400}), 400

        if not allowed_file(file.filename):
            logger.error(f"不支持的文件类型: {file.filename}")
            return jsonify({'error': 'Invalid file type', 'code': 400}), 400

        # 获取参数
        bg_color = request.form.get('bg_color', '#FFFFFF')
        keep_size = request.form.get('keep_size', 'false') == 'true'
        custom_width = int(request.form.get('width', 295))
        custom_height = int(request.form.get('height', 413))

        logger.info(f"开始处理文件: {file.filename}")
        logger.info(f"参数: bg_color={bg_color}, keep_size={keep_size}, size={custom_width}x{custom_height}")

        # 确保目录存在
        ensure_directory_exists(app.config['UPLOAD_FOLDER'])
        ensure_directory_exists(app.config['OUTPUT_FOLDER'])

        # 保存上传文件
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:8]
        base_name, ext = os.path.splitext(filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_{unique_id}{ext}")
        file.save(upload_path)
        logger.info(f"文件保存到: {upload_path}")

        # 处理图片
        rgb_color = hex_to_rgb(bg_color)
        size_opt = "保持原图大小" if keep_size else "不保持原图大小"

        out_path, output_path = rmbg(
            upload_path,
            rgb_color,
            custom_width,
            custom_height,
            size_opt
        )

        if not out_path or not output_path:
            logger.error("图片处理失败")
            return jsonify({'error': 'Image processing failed', 'code': 500}), 500

        # 生成结果文件名
        result_filename = f"result_{unique_id}.png"
        result_path = os.path.join(app.config['OUTPUT_FOLDER'], result_filename)

        # 复制结果文件到输出目录
        with Image.open(output_path) as img:
            img.save(result_path)
        logger.info(f"结果保存到: {result_path}")

        # 清理临时文件
        for temp_file in [upload_path, out_path, output_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"删除临时文件: {temp_file}")

        return jsonify({
            'success': True,
            'result_url': f"/static/outputs/{result_filename}",
            'code': 200
        })

    except Exception as e:
        logger.error(f"处理过程中出错: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': str(e),
            'code': 500
        }), 500


@app.route('/static/outputs/<filename>')
def serve_result(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)


if __name__ == '__main__':
    ensure_directory_exists(UPLOAD_FOLDER)
    ensure_directory_exists(OUTPUT_FOLDER)

    # 生产模式（PROD=1）：用 waitress（Windows 友好；gunicorn 不支持 Windows）
    # 本地调试：FLASK_DEBUG=1 python app.py（Werkzeug，debug=False 默认）
    # 生产启动：PROD=1 python app.py（waitress，多 worker）
    if os.environ.get('PROD') == '1':
        from waitress import serve
        host = os.environ.get('HOST', '0.0.0.0')
        port = int(os.environ.get('PORT', '5000'))
        logger.info(f"production serve on {host}:{port} (waitress)")
        serve(app, host=host, port=port, threads=int(os.environ.get('THREADS', '4')))
    else:
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=os.environ.get('FLASK_DEBUG') == '1',
        )