a = {
        "itc_server_id" : "001684466599474145499",
        "itc_server_address" : "192.168.5.237",
        "itc_server_port" : 81,
        "itc_server_account" : "admin",
        "itc_server_password" : "123456"
}


# a = {'roiAreaInfo': '{"sourceWidth":1920,"sourceHeight":1080,"left":464,"top":238,"points":[{"x":466,"y":238},{"x":464,"y":808},{"x":1392,"y":824},{"x":1404,"y":248},{"x":466,"y":238}]}', 'createTime': 1678930279000, 'organizationId': '001611544223344645607', 'roiId': 1, 'roiName': '123', 'algorithmConstantId': '19', 'roiAreaRecordId': '001678930278708646171', 'cameraId': '001678529068907865100'}
print(a.keys())

b=a.keys()
c= []
for item in b:
    x = list(item)
    n= len(x)
    for i in range(n):
        if x[i] == '_':
            x[i+1]=x[i+1].upper()
        item = "".join(x)
    y=item.split('_')
    res = "".join(y)
    c.append(res)
print(c)


# b = a.keys()
# c = []
# for item in b:
#     num= len(item)
#     for i in range(num):
#         if item[i].upper() == item[i]:
#             x='_'+item[i].lower()
#             letter = list(item)
#             letter[i] = x
#             item = "".join(letter)

#     c.append(item)
# print(c)

# from datetime import datetime,timedelta
# a = "2023-03-16 17:15:05"
# a1= datetime.strptime(a,"%Y-%m-%d %H:%M:%S")
# b = "2023-03-17 23:15:05"
# b1= datetime.strptime(b,"%Y-%m-%d %H:%M:%S")

# c = {'time':b1-a1}
# d = timedelta(days=0.5)
# print(b1-a1>d)

