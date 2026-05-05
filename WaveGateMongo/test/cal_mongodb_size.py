import pymongo

if __name__ == '__main__':
    # mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
    mongo_client = pymongo.MongoClient(host="127.0.0.1", port=27017)
    select_db = "wavedevice"
    mongo_db = mongo_client[select_db]
    db_collections = mongo_db.list_collection_names()
    cal_info = list()
    for db_collection in db_collections:
        collection_info = mongo_db[db_collection]
        document_count = collection_info.estimated_document_count()
        stats = mongo_db.command("collStats", db_collection)
        size_in_bytes = stats["size"]
        storage_size = stats["storageSize"]
        cal_info.append((db_collection, document_count, size_in_bytes, storage_size))

    cal_info = sorted(cal_info, key=lambda x: x[-1], reverse=True)
    for cal_tuple in cal_info:
        collection_name, document_count, size_in_bytes, storage_size = cal_tuple
        print(
            "collection_name: {}, document_count: {}, size: {}, storage_size: {}".format(collection_name,
                                                                                         document_count,
                                                                                         size_in_bytes, storage_size))
