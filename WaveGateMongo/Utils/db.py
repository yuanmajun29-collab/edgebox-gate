# import pymysql.cursors
from pyexpat.errors import XML_ERROR_INCORRECT_ENCODING
from re import M
import pymongo
from bson.code import Code
# from conf.db_config import *


class ToMongo:
    """
    MongoDB shell version v4.0.22
    git version: 1741806fb46c161a1d42870f6e98f5100d196315
    OpenSSL version: OpenSSL 1.0.2g  1 Mar 2016
    allocator: tcmalloc
    modules: none
    build environment:
        distmod: ubuntu1604
        distarch: x86_64
        target_arch: x86_64
    """
    def __init__(self,dbclint=None):
        self.myclient = pymongo.MongoClient(host="127.0.0.1", port=27017)
        self.mydb = self.myclient[dbclint]

    def close_conn(self):
        self.myclient.close()

    def get_col(self, col):
        """
        获取集合
        :param col:
        :return: 返回集合对象
        """
        try:
            result = self.mydb[col]
            return result
        except Exception as e:
            self.myclient.close()
            print('===============get_col===============\n', e)

    def update(self, col, query, new, is_one=True):
        """
        修改
        :param col: 集合名称
        :param query: 匹配修改文档
        :param new: 需要修改为新的文档
        :param is_one: 是否只修改一个，默认为是
        :return: 返回修改的结果
        """
        try:
            mycol = self.mydb[col]
            if is_one:
                result = mycol.update_one(query, new, upsert=False)
            else:
                result = mycol.update_many(query, new)
            return result
        except Exception as e:
            self.myclient.close()
            print('==============update================\n', e)

    def insert(self, col, value):
        """
        插入新数据
        :param col: 插入的集合名称
        :param value: 插入的数据值
        :return: 返回插入结果
        """
        try:
            mycol = self.mydb[col]
            if type(value) == dict:
                result = mycol.insert_one(value)
            else:
                result = mycol.insert_many(value)
            return result
        except Exception as e:
            self.myclient.close()
            print('==============insert================\n', e)

    def delete(self, col, doc, is_one=True):
        """
        删除
        :param col: 集合名称
        :param doc: 筛选需要删除的文档
        :param is_one: True只删一个,False则符合条件的全删除
        :return: 删除结果
        """
        try:
            mycol = self.mydb[col]
            if is_one:
                result = mycol.delete_one(doc)
            else:
                result = mycol.delete_many(doc)
            return result
        except Exception as e:
            self.myclient.close()
            print('==============delete================\n', e)

    def get_all_collections(self):
        """
        获取所有的集合
        :return: 集合名称列表
        """
        cls = self.mydb.list_collection_names()
        return cls

    def get_collection_keys(self, col):
        """
        获取所有的字段名称
        :param col: 集合名
        :return: 所有的字段列表
        """
        datas = self.mydb[col].find({})
        nameList = []
        for data in datas:
            for key in data.keys():
                if key not in nameList:
                    nameList.append(key)
        return nameList

    def get_aggregate(self,col,query):
        """
        聚合查询代替count()统计功能
        :param col: 集合名
        """
        try:
            my_col = self.mydb[col]
            param = [{"$match":query},{"$group":{"_id":None,"count":{"$sum":1}}}]
            res = list(my_col.aggregate(param))
            if not res:
                return 0
            return res[0]['count']
        except Exception as e:
            self.myclient.close()
            print('==============aggregate================\n', e)

    def get_keyvalues(self, col , key):
        """
        获取某个字段下所有的值
        :param col: 集合名
        :return: 对应字段下所有的值
        """
        datas = self.mydb[col]
        valueList = list()
        try:
            valueList = datas.distinct(key)
        except Exception as e:
            self.myclient.close()
            print('==============distinct================\n', e)
        return valueList

    def get_keys_in_limitation(self, col , key , query):
        """
        获取某个字段下所有的值
        :param col: 集合名
        :return: 对应字段下所有的值
        """
        datas = self.mydb[col]
        valueList = list()
        try:
            valueList = datas.distinct(key,query)
        except Exception as e:
            self.myclient.close()
            print('==============distinct================\n', e)
        return valueList

    def get_collection_keys_map_reduce(self, col):
        """
        用map,reduce 查询集合的所有字段名
        :param col: 集合名称
        :return: 字段列表
        """
        map = Code("function() { for (var key in this) { emit(key, null); } }")
        reduce = Code("function(key, stuff) { return null; }")
        result = self.mydb[col].map_reduce(map, reduce, "results")
        return result.distinct('_id')

    def fuzzy_search(self, col, skey=None):
        """
        使用正则表达式进行关键字模糊查询
        :param col: 集合名
        :param skey: 关键字
        :return: 文档结果列表
        """
        dList = []
        try:
            if skey != None:
                cList = []  # 用于存储所有字段的模糊查询条件
                nameList = self.get_collection_keys_map_reduce(col)
                for name in nameList:
                    condition = {name: {"$regex": str(skey)}}
                    cList.append(condition)  # 将每个字段模糊查询条件压入数组
                datas = self.mydb[col].find(filter={"$or": cList})  # 用$or表示或的关系，$and表示与
            else:
                datas = self.mydb[col].find({})
            for d in datas:
                dList.append(d)
            return dList
        except Exception as e:
            self.myclient.close()
            print('==============fuzzy_search================\n', e)

    def insert_img(self, filename, data):
        """
        插入一个二进制图片
        :param filename:
        :param data:
        读取文件
        with open('./static/images/logo.png', 'rb') as file:
        data = file.read()
        file.close()
        """
        coll = self.mydb['images']
        result = coll.insert_one({'name': filename, 'data': data})
        return result

    def get_img(self, filename):
        """
        获取一个二进制的图像数据
        :param filename:
        :return:二进制

        # 数据库中的BSON数据写回文件
        ret = users.find_one({'name': 'zhifubao.jpg'})
        with open(os.path.join(os.getcwd(), 'new.png'), 'wb') as file:
        file.write(ret.get('data'))
        """
        try:
            coll = self.mydb['images']
            img = coll.find_one({'name': filename})
            # with open(filename, 'wb') as file:
            #     file.write(img.get('data'))
            #     file.close()
            return img.get('data')
        except Exception as e:
            self.myclient.close()
            print('==============get_img================\n', e)

def cameraedit_switch(res):
    item = {}

    item['cameraAccount'] = res['camera_account']
    item['cameraCreateTime'] = res['create_time']
    item['cameraId'] = res['camera_id']
    item['cameraIp'] = res['camera_ip']
    item['cameraIpLabel'] = res['camera_ip_label']
    item['cameraMac'] = res['camera_mac']
    item['cameraName'] = res['camera_name']
    item['cameraNum'] = res['camera_num']
    item['cameraPassword'] = res['camera_password']
    item['cameraRemarks'] = res['camera_remarks']
    item['cameraSource'] = res['camera_source']
    item['cameraStatus'] = res['camera_status']
    item['cameraType'] = res['camera_type']
    item['cameraUpdateTime'] = res['update_time']
    item['extendInfo'] = res['extend_info']
    item['mainUrl'] = res['main_url']
    item['organizationId'] = res['organization_id']
    item['rtspPort'] = res['rtsp_port']
    item['productKey'] = res['product_key']

    return item

def position_switch(res):
    item = {}
    if res:       
        item['positionArea'] = res['position_area']
        item['positionCity'] = res['position_city']
        item['positionCounty'] = res['position_county']
        item['positionDesc'] = res['position_desc']
        item['positionId'] = res['position_id']
        item['positionProvince'] = res['position_province']
        item['lonAndLat'] = res['lon_and_lat']

    else:
        item['positionArea'] = None
        item['positionCity'] = None
        item['positionCounty'] = None
        item['positionDesc'] = None
        item['positionId'] = None
        item['positionProvince'] = None
        item['lonAndLat'] = None
  
    return item

    