#!/bin/bash
if [ $1 == start ];then

    PYTHON_PID=$(ps -ef | grep WaveGateMongo | grep -v grep | wc -l)
    if [ $PYTHON_PID -le 0 ];then
        echo "python后台服务启动中......."
        nohup python3 -u ./WaveGateMongo/app.py > ./nohup.out  2>&1 &    
        echo "--python后台服务启动成功"    
    fi
    
elif [ $1 == stop ];then
    exe_id=`ps -ef|grep  'WaveGateMongo'|grep -v grep|awk '{print $2}'|uniq`
    for pid in ${exe_id[*]}
    do
        kill -9 $pid
        echo "python后台关闭成功"
    done

elif [ $1 == restart ];then
    exe_id=`ps -ef|grep  'WaveGateMongo'|grep -v grep|awk '{print $2}'|uniq`
    for pid in ${exe_id[*]}
    do
        kill -9 $pid
        echo "1、python后台关闭成功"
    done
    nohup python3 -u ./WaveGateMongo/app.py > ./nohup.out  2>&1 &    
    echo "2、python后台重新启动成功" 

elif [ $1 == status ];then
    normal_num=0
    exe_id=`ps -ef|grep  'WaveGateMongo'|grep -v grep|awk '{print $2}'|uniq`
    for pid in ${exe_id[*]}
    do
        tmp=`ps $pid|grep python3|wc -l`
        if [ $tmp -ge 1 ];then
                normal_num=1
        fi
    done
        if [ $normal_num -eq 0 ];then
                echo "python后台没在运行"
        else
                echo "python后台正在运行"
        fi
else
    echo "参数错误"
fi
