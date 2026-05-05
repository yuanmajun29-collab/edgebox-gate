import redis

redis_database = redis.Redis(host='localhost', port=6379,password="waveRedisAdmin123")
# redis_database = redis.Redis(host='192.168.24.117', port=6379, password="waveRedisAdmin123", decode_responses=True)
