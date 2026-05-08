
import os
from flask.views import MethodView
from flask import request,send_file
from Utils.device_misc import make_response_image_jpeg,response_no_image
from config import EMERGENCY_IMG_PATH


class EventImageDBAPI(MethodView):
    
    def getImage(self, image_id, event_time):
        origin_image_binary = b''
        origin_image_folder = EMERGENCY_IMG_PATH

        if image_id is not None:
            per_image_name = image_id + ".jpg" 
            second_dir = str(event_time)            
            second_dir_path = os.path.join(origin_image_folder, second_dir)        
            origin_image_path = os.path.join(second_dir_path, per_image_name)
            if not os.path.exists(origin_image_path):
                origin_image_path = None
            return origin_image_path
            # try:
            #     with open(origin_image_path, 'rb') as fp:                
            #         origin_image_binary = fp.read()
            # except:
            #     print('Error:图片路径不存在')
            #     origin_image_binary = None

        #return origin_image_binary

    def get(self, image_id=None):

        event_time = int(request.args.get('date', None))
        image_path = self.getImage(image_id, event_time)
        if not image_path:
            return response_no_image()
       # return make_response_image_jpeg(image_data)
        fl_name = image_id + '.jpg'
        return send_file(image_path,as_attachment=True,attachment_filename=fl_name,cache_timeout=0)
   
def transfer_img_url(url_head,imgurl):
    imgend = imgurl.split('/',3)[-1]
    url_img = url_head + imgend
    return url_img
