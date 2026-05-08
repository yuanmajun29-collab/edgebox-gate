#!/bin/bash
# 统一控制 products 下各产品 app.py：start | stop | restart | status
# 用法:
#   ./run.sh start                    # 默认 mongo（或环境变量 EDGEBOX_PROFILE）
#   ./run.sh start ai_spirit          # action 在前
#   ./run.sh energy stop              # profile 在前
# profile（mongo | ai_spirit | energy）与 edgebox/apps/<产品线>/ 对应

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR" || exit 1

is_action() {
    case "$1" in start | stop | restart | status) return 0 ;; *) return 1 ;; esac
}

resolve_profile() {
    local k
    k="$(echo "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr '-' '_')"
    case "$k" in
    mongo | wavegatemongo | wave_gate_mongo | mongogate) echo mongo ;;
    ai_spirit | wave_ai_spirit | spirits) echo ai_spirit ;;
    energy | wave_energy | wave_energy_station | energy_station) echo energy ;;
    *) echo "" ;;
    esac
}

profile_to_relpath() {
    case "$1" in
    mongo) echo "edgebox/apps/mongo/app.py" ;;
    ai_spirit) echo "edgebox/apps/ai_spirit/app.py" ;;
    energy) echo "edgebox/apps/energy/app.py" ;;
    *) echo "" ;;
    esac
}

ACTION=""
PROFILE=""

if [ "${1-}" = "" ]; then
    echo "用法: $0 <start|stop|restart|status> [profile]"
    echo "   或: $0 <profile> <start|stop|restart|status>"
    echo "profile 默认 mongo，也可用环境变量 EDGEBOX_PROFILE；可选: mongo | ai_spirit | energy"
    exit 1
fi

if [ $# -eq 1 ]; then
    if ! is_action "$1"; then
        echo "参数错误: 单参数须为 start|stop|restart|status（默认 profile=mongo 或 \$EDGEBOX_PROFILE）"
        exit 1
    fi
    ACTION="$1"
    PROFILE="$(resolve_profile "${EDGEBOX_PROFILE:-mongo}")"
    if [ -z "$PROFILE" ]; then
        echo "未知 EDGEBOX_PROFILE=${EDGEBOX_PROFILE:-}(空则 mongo)"
        exit 1
    fi
elif [ $# -eq 2 ]; then
    if is_action "$1"; then
        ACTION="$1"
        PROFILE="$(resolve_profile "$2")"
    elif is_action "$2"; then
        PROFILE="$(resolve_profile "$1")"
        ACTION="$2"
    else
        echo "参数错误: 须包含一个动作 start|stop|restart|status"
        exit 1
    fi
    if [ -z "$PROFILE" ]; then
        echo "未知 profile，可选: mongo | ai_spirit | energy"
        exit 1
    fi
else
    echo "参数过多"
    exit 1
fi

APP_REL="$(profile_to_relpath "$PROFILE")"
APP_PATH="$ROOT_DIR/$APP_REL"
if [ ! -f "$APP_PATH" ]; then
    echo "未找到 $APP_PATH"
    exit 1
fi

# 与旧脚本一致：用于 ps/grep 的稳定片段（相对仓库根）
APP_GREP="$APP_REL"

if [ "$ACTION" == start ]; then

    PYTHON_PID=$(ps -ef | grep "$APP_GREP" | grep -v grep | wc -l)
    if [ "$PYTHON_PID" -le 0 ]; then
        echo "python后台服务启动中......."
        nohup python3 -u "$APP_PATH" > "$ROOT_DIR/nohup.out" 2>&1 &
        echo "--python后台服务启动成功"
    fi

elif [ "$ACTION" == stop ]; then
    exe_id=$(ps -ef | grep "$APP_GREP" | grep -v grep | awk '{print $2}' | uniq)
    for pid in ${exe_id[*]}; do
        kill -9 "$pid"
        echo "python后台关闭成功"
    done

elif [ "$ACTION" == restart ]; then
    exe_id=$(ps -ef | grep "$APP_GREP" | grep -v grep | awk '{print $2}' | uniq)
    for pid in ${exe_id[*]}; do
        kill -9 "$pid"
        echo "1、python后台关闭成功"
    done
    nohup python3 -u "$APP_PATH" > "$ROOT_DIR/nohup.out" 2>&1 &
    echo "2、python后台重新启动成功"

elif [ "$ACTION" == status ]; then
    normal_num=0
    exe_id=$(ps -ef | grep "$APP_GREP" | grep -v grep | awk '{print $2}' | uniq)
    for pid in ${exe_id[*]}; do
        tmp=$(ps "$pid" | grep python3 | wc -l)
        if [ "$tmp" -ge 1 ]; then
            normal_num=1
        fi
    done
    if [ "$normal_num" -eq 0 ]; then
        echo "python后台没在运行"
    else
        echo "python后台正在运行"
    fi
else
    echo "参数错误"
    exit 1
fi
