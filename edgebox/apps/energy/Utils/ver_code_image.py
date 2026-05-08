import base64
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import random

# 定义验证码长度、字体大小等参数
code_length = 4
font_size = 30
image_width = code_length * font_size + 15
image_height = font_size + 20


def generate_verification_code():
    # 创建空白图像对象
    image = Image.new('RGB', (image_width, image_height), color=(255, 255, 255))

    draw = ImageDraw.Draw(image)
    _font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "arial.ttf")
    font = ImageFont.truetype(_font_path, size=font_size)

    # font = ImageFont.truetype("./fonts/arial.ttf", size=font_size)

    # 生成随机颜色
    def get_random_color():
        return tuple([random.randint(64, 255) for _ in range(3)])

    # 生成随机字符串作为验证码
    login_verification_code = ''.join(chr(random.randint(97, 122)) for _ in range(code_length))

    # 在图像上绘制验证码
    draw.text((8, 8), login_verification_code, fill=get_random_color(), font=font)

    # 添加干扰线条
    for i in range(random.randint(2, 5)):
        x1 = random.randint(0, image_width - 1)
        y1 = random.randint(0, image_height - 1)
        x2 = random.randint(0, image_width - 1)
        y2 = random.randint(0, image_height - 1)
        draw.line((x1, y1, x2, y2), fill=get_random_color())

    # 保存图像到本地文件（示例）
    # image.save(".././vercode/verification_code.png")
    image.save("./vercode/verification_code.png")

    # 将图像转换为Base64格式（示例）
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    base64_data = "data:image/jpeg;base64," + str(base64.b64encode(buffered.getvalue()))[2:-1]

    return login_verification_code, base64_data


# if __name__ == "__main__":
#     verification_code, base64_data = generate_verification_code()
#     print("Verification Code: ", verification_code)
#     print("Base64 Data: ", base64_data)


def make_ver_code():
    # 创建空白图片
    height, width = 50, 100
    image = np.zeros((height, width, 3), dtype=np.uint8)

    # 加载本地字体
    font = cv2.FONT_HERSHEY_SIMPLEX

    # 绘制验证码字符
    data = '1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    code = ''.join(random.sample(data, 4))
    img = cv2.putText(image, code, (10, 30), font, 1, (255, 255, 255), 1)

    # 保存图片
    cv2.imwrite('/data/ebox/wavegate/wave-energy-station/vercode/captcha.png', img)

    # 读取图片并转换为Base64编码的字符串
    encoded_bytetype = cv2.imencode('.png', img)[1]
    encoded_base64 = 'data:image/png;base64,' + base64.b64encode(encoded_bytetype).decode('utf-8')
    return code, encoded_base64

# if __name__ == "__main__":
#     code, base64_data = make_ver_code()
#     print(code)
#     print(base64_data)
