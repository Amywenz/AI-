# 在py文件里面运行环境
import sys
import os
from PIL import Image, ImageDraw
import cv2
import numpy as np
import onnxruntime as ort
import re
from skimage import io
from io import BytesIO


class BriaRMBG_ONNX:
    def __init__(self, model_path):
        # 显式指定 providers，消除 onnxruntime 1.22 不传 providers 的警告
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider'],
        )

    def __call__(self, input_tensor):
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: input_tensor})
        return outputs


# 模块级常量：模型路径基于 __file__ 拼绝对路径，不依赖工作目录
# 历史路径 home/aistudio/rmbg/onnx/ 是百度 AI Studio 残留，规范化为 models/rmbg/onnx/
_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models", "rmbg", "onnx", "model.onnx"
)

# 模块加载时构造一次 InferenceSession，避免每次请求重复加载（秒级开销）
# 加载失败时 _NET 保持 None，rmbg() 内会检查并返回 None，保留原 fallback 语义
_NET = None
if os.path.exists(_MODEL_PATH):
    try:
        _NET = BriaRMBG_ONNX(_MODEL_PATH)
    except Exception as e:
        print(f"启动时加载模型失败: {e}")
else:
    print(f"警告: 找不到模型文件 '{_MODEL_PATH}'，服务将无法处理图片")


def convert_to_png(input_path):
    """
    将任意格式的图片转换为PNG格式并返回路径
    :param input_path: 输入图片路径
    :return: 转换后的PNG图片路径
    """
    if input_path.lower().endswith('.png'):
        return input_path

    # 创建临时文件名
    base_path = os.path.splitext(input_path)[0]
    output_path = f"{base_path}_temp.png"

    try:
        img = Image.open(input_path)
        # 如果是RGBA模式且包含透明度，直接保存为PNG
        if img.mode == 'RGBA':
            img.save(output_path, 'PNG')
        else:
            # 其他模式转换为RGB再保存为PNG
            img.convert('RGB').save(output_path, 'PNG')
        return output_path
    except Exception as e:
        print(f"图片转换失败: {e}")
        return None


def preprocess_image(im: np.ndarray, model_input_size: list) -> np.ndarray:
    """
    预处理图像
    :param im: 输入图像
    :param model_input_size: 模型输入尺寸
    :return: 预处理后的图像
    """
    if len(im.shape) < 3:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)  # 将灰度图像转换为BGR格式
    im = cv2.resize(im, model_input_size, interpolation=cv2.INTER_LINEAR)  # 调整图像大小
    im = im.astype(np.float32)  # 将图像数据类型转换为float32
    im /= 255.0  # 归一化到[0, 1]范围
    mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    std = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    im = (im - mean) / std
    return im[np.newaxis, :, :, :].astype(np.float32)  # 确保输出是float32类型


def postprocess_image(result: np.ndarray, im_size: list) -> np.ndarray:
    """
    后处理图像
    :param result: 模型输出结果
    :param im_size: 原始图像尺寸
    :return: 后处理后的图像
    """
    result = result[0]  # 移除batch维度
    ma = np.max(result)
    mi = np.min(result)
    # 全黑/全白图：ma == mi 时除零产生 NaN，返回全 0 mask（无主体可抠）
    if ma == mi:
        return np.zeros((im_size[0], im_size[1]), dtype=np.uint8)
    result = (result - mi) / (ma - mi)  # 归一化到[0, 1]范围
    result = (result * 255).astype(np.uint8)  # 将数据类型转换回uint8
    result = cv2.resize(result, [im_size[1], im_size[0]], interpolation=cv2.INTER_LINEAR)  # 调整图像大小
    return result


def add_background_to_image(input_image_path, output_image_path, background_color=None, out_size=None):
    """
    给透明背景的PNG人像图像添加任意颜色的背景
    :param input_image_path: 输入图像的路径
    :param output_image_path: 输出图像的路径
    :param background_color: 背景颜色 (R, G, B)
    :param out_size: 输出图像的大小 (width, height) 默认与输入图像相同
    """
    image = Image.open(input_image_path)
    if image.format != 'PNG':
        image = image.convert('RGBA')
    if out_size is None:
        out_size = image.size

    out_image = Image.new('RGB', out_size, background_color)
    # 居中放置图像
    if out_size != image.size:
        position = ((out_size[0] - image.size[0]) // 2, (out_size[1] - image.size[1]) // 2)
        out_image.paste(image, position, image)
    else:
        out_image.paste(image, (0, 0), image)

    # 根据输出路径的扩展名保存为相应格式
    ext = os.path.splitext(output_image_path)[1].lower()
    if ext == '.jpg' or ext == '.jpeg':
        out_image.save(output_image_path, 'JPEG', quality=95)
    elif ext == '.webp':
        out_image.save(output_image_path, 'WEBP', quality=95)
    else:
        out_image.save(output_image_path, 'PNG')


def rmbg(input_image_path, background_color, out_size_w, out_size_h, size_opt):
    """
    处理图像并添加背景
    :param input_image_path: 输入图像路径
    :param background_color: 背景颜色
    :param out_size_w: 输出图像宽度
    :param out_size_h: 输出图像高度
    :param size_opt: 尺寸选项
    :return: 输出路径和输出图像路径
    """
    # 首先转换图片格式为PNG
    converted_path = convert_to_png(input_image_path)
    if not converted_path:
        print("图片格式转换失败!")
        return None, None

    if size_opt == "保持原图大小":
        shape = cv2.imread(converted_path).shape
        out_size = (int(shape[1]), int(shape[0]))
    else:
        out_size = (int(out_size_w), int(out_size_h))

    # 解析原始文件名和扩展名
    base_path, ext = os.path.splitext(input_image_path)
    out_path = f"{base_path}_rmbg.png"  # 抠图结果总是保存为PNG
    output_image_path = f"{base_path}_bg{ext}"  # 证件照使用原始格式

    # 模型在模块加载时已构造一次，这里直接复用
    if _NET is None:
        print("模型未加载，无法处理图片")
        return None, None

    # prepare input
    model_input_size = [1024, 1024]
    orig_im = io.imread(converted_path)

    # 对于4通道图像，转换为3通道；灰度图（2D）交给 preprocess_image 内部 cvtColor 处理
    if orig_im.ndim == 3 and orig_im.shape[2] == 4:
        img = Image.open(converted_path).convert("RGB")
        temp_path = f"{base_path}_temp_rgb.png"
        img.save(temp_path)
        orig_im = io.imread(temp_path)
        os.remove(temp_path)  # 删除临时文件

    orig_im_size = orig_im.shape[0:2]
    image = preprocess_image(orig_im, model_input_size)
    image = np.transpose(image, (0, 3, 1, 2))  # ONNX通常需要CHW格式

    # inference
    result = _NET(image)

    # post process
    result_image = postprocess_image(result[0][0], orig_im_size)

    pil_im = Image.fromarray(result_image)
    no_bg_image = Image.new("RGBA", pil_im.size, (0, 0, 0, 0))
    orig_image = Image.open(converted_path)
    no_bg_image.paste(orig_image, mask=pil_im)
    no_bg_image.save(out_path)

    # 如果转换了图片格式，删除临时文件
    if converted_path != input_image_path:
        os.remove(converted_path)

    add_background_to_image(out_path, output_image_path, background_color, out_size)

    return out_path, output_image_path