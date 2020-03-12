export SERVICE_NAME="identical_face_check"
export DAEMON_PATH=$(pwd)
# export DAEMON=$(which python)
export DAEMON="/zserver/AI-projects/.virtualenvs/dl-py3-stg/bin/python"
export CONF_FILE=$DAEMON_PATH/server.py

export SERVICE_ENV_SETTING="DEVELOPMENT"

export DAEMONOPTS="-u $CONF_FILE"


export LOG_DIR=$DAEMON_PATH/logs/
export LOG_FILE=$DAEMON_PATH/logs/server.log

export PID_DIR=$DAEMON_PATH/pid/
export PIDFILE=$PID_DIR/$SERVICE_NAME.pid

case "$2" in
production)
    export SERVICE_ENV_SETTING="PRODUCTION"
    ;;

staging)
    export SERVICE_ENV_SETTING="STAGING"
    ;;
*) ;;
esac

list_descendants() {
    local children=$(ps -o pid= --ppid "$1")

    for pid in $children; do
        list_descendants "$pid"
    done

    printf "$children"
}

init_folder() {
    if
        [[ -d "$LOG_DIR" ]]
    then
        echo "$LOG_DIR exists on your filesystem."
    else
        echo "Create $LOG_DIR.."
        mkdir -p $LOG_DIR
    fi

    if
        [[ -d "$PID_DIR" ]]
    then
        echo "$PID_DIR exists on your filesystem."
    else
        echo "Create $PID_DIR.."
        mkdir -p $PID_DIR
    fi

}

case "$1" in
start)
    printf "%-50s" "Starting $SERVICE_NAME..."
    cd $DAEMON_PATH
    echo $SERVICE_ENV_SETTING

    # Check service started
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if ps -p $PID > /dev/null
        
        then
            printf "%s\n" "Service has already been started!"
            exit 1
        fi
    fi

    init_folder
    $DAEMON $DAEMONOPTS $SERVICE_ENV_SETTING >$LOG_FILE 2>&1 &
    PID=$(echo -n $!)
    
    if [ -z $PID ]; then
        printf "%s\n" "Failed"
    else
        echo $PID > $PIDFILE
        printf "%s\n" "Ok"
    fi
    ;;
status)
    printf "%-50s" "Checking $SERVICE_NAME..."
    if [ -f $PIDFILE ]; then
        PID=$(cat $PIDFILE)
        if [ -z "$(ps axf | grep ${PID} | grep -v grep)" ]; then
            printf "%s\n" "Process dead but pidfile exists"
        else
            printf "\nRunning on main process : $PID"
            printf "\nSubprocess : \n---------\n$(list_descendants $PID)\n---------\n"
        fi
    else
        printf "%s\n" "Service not running"
    fi
    ;;

stop)
    printf "Stopping $SERVICE_NAME\n"
    PID=$(cat $PIDFILE)
    cd $DAEMON_PATH
    if [ -f $PIDFILE ]; then
        printf "\n---------\n $PID \t\n$(list_descendants $PID)\n---------\n"
        kill -HUP $(list_descendants $PID)
        kill -HUP $PID
        printf "Ok\n"
        rm -f $PIDFILE
    else
        printf "%s\n" "pidfile not found"
    fi
    ;;

restart)
    $0 stop
    $0 start
    ;;

*)
    echo "Usage: $0 {status|start|stop|restart}"
    exit 1
    ;;
esac
