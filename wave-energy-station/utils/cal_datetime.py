import calendar
from datetime import datetime, timedelta

'''
时间工具类
'''


def calculating_today_time():
    """今天"""
    today = datetime.now().date()
    start_of_day = datetime(today.year, today.month, today.day, 0, 0, 0)
    end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)
    return start_of_day, end_of_day


def calculating_yesterday_time():
    """昨天"""
    # 获取昨天的日期
    yesterday = datetime.now() - timedelta(days=1)
    # 计算昨天的日期范围（开始时间和结束时间）
    start_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
    end_of_yesterday = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)
    return start_of_yesterday, end_of_yesterday


def calculating_month_time():
    """本月时间"""
    now = datetime.now()
    first_day_of_month = datetime(now.year, now.month, 1, 0, 0, 0)
    last_day_of_month = datetime(now.year, now.month, now.day, 23, 59, 59)
    return first_day_of_month, last_day_of_month


def calculating_last_month_time():
    """上月时间"""
    now = datetime.now()
    first_day_of_last_month = datetime(now.year, now.month, 1) - timedelta(days=1)
    first_day_of_this_month = datetime(now.year, now.month, 1)
    return first_day_of_last_month, first_day_of_this_month


def calculating_year_time():
    """本年时间"""
    now = datetime.now()
    first_day_of_year = datetime(now.year, 1, 1, 0, 0, 0)
    last_day_of_year = datetime(now.year, 12, 31, 23, 59, 59)
    return first_day_of_year, last_day_of_year


def calculating_last_year_time():
    """上年时间"""
    # 获取当前日期并减去一年
    one_year_ago = datetime.now() - timedelta(days=365)

    # 计算去年的第一天和最后一天
    first_day_of_last_year = datetime(one_year_ago.year, 1, 1)
    last_day_of_last_year = datetime(one_year_ago.year, 12, 31)
    return first_day_of_last_year, last_day_of_last_year


def calculating_15day_time():
    """近15日计算"""
    now = datetime.now()
    start_time = datetime.now() - timedelta(days=15)
    start_date = start_time.strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    return start_date, end_date


def days_of_the_month():
    """查询当前日期的所在月的天数"""
    now = datetime.now()
    cur_date = now.date()
    year = cur_date.year
    month = cur_date.month
    init_days_weekday, month_last_day = calendar.monthrange(year, month)  # a,b——weekday的第一天是星期几（0-6对应星期一到星期天）和这个月的所有天数
    return month_last_day
