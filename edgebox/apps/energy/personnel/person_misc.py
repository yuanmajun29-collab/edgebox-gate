import os
from flask.views import MethodView
from Utils.device_misc import make_response_image_jpeg, response_no_image
from config import FACE_IDENT_URL, PERSON_IMG_URL
import time, datetime


class FaceImageDBAPI(MethodView):

    def getImage(self, image_id):
        origin_image_binary = b''
        origin_image_folder = PERSON_IMG_URL

        if image_id is not None:
            per_image_name = image_id + ".jpg"
            second_dir = image_id
            second_dir_path = os.path.join(origin_image_folder, second_dir)
            origin_image_path = os.path.join(second_dir_path, per_image_name)
            try:
                with open(origin_image_path, 'rb') as fp:
                    origin_image_binary = fp.read()
            except:
                print('Error:人脸图路径不存在')
                origin_image_binary = None

        return origin_image_binary

    def put(self, image_id=None):
        image_id = image_id.split(".")[0]
        image_data = self.getImage(image_id)
        if not image_data:
            return response_no_image()
        return make_response_image_jpeg(image_data)

    def get(self, image_id=None):
        image_id = image_id.split(".")[0]
        image_data = self.getImage(image_id)
        if not image_data:
            return response_no_image()
        return make_response_image_jpeg(image_data)


class FaceFeatureDBAPI(MethodView):

    def getFeature(self, image_id):
        origin_featue_folder = FACE_IDENT_URL

        if image_id is not None:
            file_name = image_id + ".json"
            second_dir = image_id
            second_dir_path = os.path.join(origin_featue_folder, second_dir)
            origin_feature_path = os.path.join(second_dir_path, file_name)
            try:
                with open(origin_feature_path) as fp:
                    face_features = fp.read()
            except:
                face_features = None
                print('人脸特征值路径不存在')

        return face_features

    def get(self, image_id=None):
        feature_id = image_id.split(".")[0]
        feature_data = self.getFeature(feature_id)
        return feature_data


def verify_social_num(social_num: str):
    coeff = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check = [1, 0, 'X', 9, 8, 7, 6, 5, 4, 3, 2]
    today = datetime.datetime.now().strftime('%Y%m%d')
    year = time.localtime(time.time())[0]
    if len(social_num) != 18:
        return False
    if not social_num[0:17].isdigit():
        return False
    if int(social_num[6:10]) not in range(1900, year + 1):
        return False
    if int(social_num[6:14]) > int(today):
        return False
    try:
        time.strptime(social_num[6:14], "%Y%m%d")
        tmp = 0
        for i in range(0, 17):
            tmp = tmp + int(social_num[i]) * coeff[i]
        mod = tmp % 11
        sex = '女' if int(social_num[-2]) % 2 == 0 else '男'
        if str(check[mod]) != social_num[-1]:
            return False
    except:
        return False
    return True
