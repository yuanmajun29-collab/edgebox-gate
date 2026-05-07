import numpy as np
import cv2
import json
import base64
from PIL import Image, ImageDraw
import Utils.logger as logger

mainlogger = logger.getLogger('main')


def cv2ImgAddText(img, text, left, top, textColor=(0, 255, 0), textSize=20):
    if (isinstance(img, np.ndarray)):  # 判断是否OpenCV图片类型
        img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    # 创建一个可以在给定图像上绘图的对象
    draw = ImageDraw.Draw(img)
    # 字体的格式
    # fontStyle = ImageFont.truetype(
    #     "/data/ebox/simsun.ttc", textSize, encoding="utf-8")
    # 绘制文本
    draw.text((left, top), text, textColor)
    # 转换回OpenCV格式
    return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)


def draw_rectangle(imgpath, extra_info, type=0, model_path=None):
    '''
    imgpath:图片路径
    extra_info:框的位置信息
    type: 0表示图片路径  1表示图片base64数据
    '''
    try:
        if type == 0:
            img = cv2.imread(imgpath)
        elif type == 1:
            img_b64decode = base64.b64decode(imgpath)
            img_array = np.fromstring(img_b64decode, np.uint8)
            img = cv2.imdecode(img_array, cv2.COLOR_BGR2RGB)
        extra_info = json.loads(extra_info)
        for info in extra_info:
            top_x = info['x']
            top_y = info['y']
            bottom_x = info['x'] + info['width']
            bottom_y = info['y'] + info['height']
            img = cv2.rectangle(img, (top_x, top_y), (bottom_x, bottom_y), (255, 0, 0), 2)
    #            img = cv2ImgAddText(img,model_path,top_x,top_y+10, (0, 0 , 139), 20)

    except Exception as e:
        mainlogger.info('Error(draw_rectangle) : %s' % e)
        return
    return img


def draw_polylines(imgpath, extra_info, type=0, model_path=None):
    '''
    imgpath:图片路径
    extra_info:框的位置信息
    type: 0表示图片路径  1表示图片base64数据
    '''
    try:
        if type == 0:
            img = cv2.imread(imgpath)
        elif type == 1:
            img_b64decode = base64.b64decode(imgpath)
            img_array = np.fromstring(img_b64decode, np.uint8)
            img = cv2.imdecode(img_array, cv2.COLOR_BGR2RGB)
        points_total = []
        extra_info = json.loads(extra_info)
        for info in extra_info:
            points = info['points']
            length = len(points)
            item = []
            for i in range(length - 1):
                point = [points[i]['x'], points[i]['y']]
                item.append(point)
            points_total.append(item)
            pts = np.array(points_total)
            img = cv2.polylines(img, pts, True, (0, 0, 255), 2)

    except Exception as e:
        mainlogger.info('Error(draw_polylines) : %s' % e)
        return
    return img


def draw_frame(imgpath, extra_info, alg_num, type=0, model_path=None):
    '''
    alg_num:str 算法常量
    '''
    origin_img = open(imgpath, 'rb')
    try:
        # 尾随、离岗、人流量密度
        if alg_num in ["5", "114", '128']:
            imgdata = draw_polylines(imgpath, extra_info, type=type, model_path=model_path)
        else:
            imgdata = draw_rectangle(imgpath, extra_info, type=type, model_path=model_path)
    except Exception as e:
        mainlogger.info('Error(draw_frame) : %s' % e)

        return origin_img.read()
    res = cv2.imencode('.jpg', imgdata)[1]
    return res
