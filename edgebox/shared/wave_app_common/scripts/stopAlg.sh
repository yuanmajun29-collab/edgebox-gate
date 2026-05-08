#!/bin/bash
exe_id=`ps -ef|grep  'alg/monitor.sh'|grep -v grep|awk '{print $2}'|uniq`

for pid in ${exe_id[*]}
    do
        kill -9 $pid
    done

rm -rf /data/ebox/alg/
nohup /data/ebox/alg/monitor.sh EcalculateBox backgroud >/dev/null 2>&1  &
