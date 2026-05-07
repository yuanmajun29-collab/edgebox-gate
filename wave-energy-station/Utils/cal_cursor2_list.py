import datetime
 
def get_days_in_current_month():
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    end_of_month = datetime.datetime(next_year, next_month, 1) - datetime.timedelta(days=1)
    return end_of_month.day

def merge_cursor_to_list(cursor_device, cursor_dynamic, field_name):
    top_five = []
    if cursor_device.count() and cursor_dynamic.count():
        cursor = list(cursor_device) + list(cursor_dynamic)
        cursor = sorted(cursor, key=lambda doc: doc.get(field_name), reverse=True)
        top_five = cursor[:5]
    elif cursor_device.count():
        top_five = list(cursor_device)
    elif cursor_dynamic.count():
        top_five = list(cursor_dynamic)
    return top_five

def merge_emergency_by_month(cursor_device, cursor_dynamic,month_begin):
    data_device = list(cursor_device)
    data_dynamic = list(cursor_dynamic)
    res1 = {}
    if  data_device:
        for item in data_device:
            res1[item['_id']] = item['count']

    res2 = {}
    if  data_dynamic:
        for item in data_dynamic:
            res2[item['_id']] = item['count']

    num_days = get_days_in_current_month()
    result = []
    for i in range(num_days):
        today = month_begin + datetime.timedelta(days=i)
        today_str = today.strftime('%m-%d')
        item = {'id':today_str,'count':0}
        num_emergeny = res1.get(i+1,0)
        num_dynamic = res2.get(i+1,0)
        item['count'] += num_emergeny
        item['count'] += num_dynamic
        result.append(item)
    return result

def merge_command_cursor_addition_list(cursor_device, cursor_dynamic, field_name, field_count):
    top_five = []
    if cursor_device.alive and cursor_dynamic.alive:
        data_device = list(cursor_device)
        data_dynamic = list(cursor_dynamic)
        for device, dynamic in zip(data_device, data_dynamic):
            if device[field_name] == dynamic[field_name]:
                device[field_count] += dynamic[field_count]  # 或者其他数学运算，如相加、相减等
                top_five.append(device)
    elif cursor_device.alive:
        top_five = list(cursor_device)
    elif cursor_dynamic.alive:
        top_five = list(cursor_dynamic)
    return top_five

def merge_emergency(cursor_device, cursor_dynamic):
    data_device = list(cursor_device)
    data_dynamic = list(cursor_dynamic)
    res1 = {}
    if  data_device:
        for item in data_device:
            res1[item['hour']] = item['count']

    res2 = {}
    if  data_dynamic:
        for item in data_dynamic:
            res2[item['hour']] = item['count']

    result = []
    for i in range(24):
        item = {'id':i,'count':0}
        num_emergeny = res1.get(i,0)
        num_dynamic = res2.get(i,0)
        item['count'] += num_emergeny
        item['count'] += num_dynamic
        result.append(item)
    return result