
import os
from flask.views import MethodView
from flask import request,send_file
from Utils.device_misc import make_response_image_jpeg,response_no_image
from config import EMERGENCY_IMG_PATH
import Utils.logger as logger
import shutil
import requests

mainlogger = logger.getLogger('main')

def deletefile(filepath):
    """
    删除文件，若删除后为空文件夹，则删除文件夹
    """
    if os.path.exists(filepath):
        os.remove(filepath)
    filedir = filepath.split('/')[0]
    if not os.listdir(filedir):
        shutil.rmtree(filedir)
    return

def get_minio_img(minio_url,imgpath):
    '''
    下载minio的图，存到指定路径
    '''
    mainlogger.debug("写入底图：%s"%imgpath)
    response = requests.get(minio_url)
    filedir = imgpath.rsplit('/',1)[0]
    if not os.path.exists(filedir):
        os.mkdir(filedir)
    with open(imgpath,'wb') as fp:
        fp.write(response.content)
    return

def delete_pic(items,emergency_col):
    '''
    参数：items  odin_business_emergency_record表查到的
    '''
    for item in items:
        try:
            sub_source_id = item['sub_source_id']
            query = {'sub_source_id':sub_source_id}
            samepic_items = emergency_col.find(query)
            if samepic_items.count() > 1:
                continue
            emergency_time = item['emergency_time']
            temp = emergency_time.split(" ")[0].split('-')
            filedir = ''.join(temp)
            filepath = EMERGENCY_IMG_PATH + filedir +'/' + sub_source_id + '.jpg'
            if not os.path.exists(filepath):
                continue
            os.remove(filepath)
        except Exception as e:
            mainlogger.debug('Delete Error : %s'%e)

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

        event_time = request.args.get('date', None)
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
