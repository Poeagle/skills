import Test


class TestAlertStorm(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "系统告警数量突然暴增，请诊断并处理",
            "告警风暴了，大量告警涌入，帮忙看看怎么回事",
            "告警队列积压严重，请排查处理",
        ]

    # 清理环境
    def cleanup(self):
        script = r'''
// 顺序：退订 -> 删 engine -> 停任务 -> 等待 -> 删流表 -> 删共享表
// 1. 退订
try{
    unsubscribeTable(tableName="TAS_input", actionName="TAS_slow_consumer");
}catch(ex){}

try{
    unsubscribeTable(tableName="TAS_metric_stream", actionName="TAS_alert_sub");
}catch(ex){}

try{
    unsubscribeTable(tableName="TAS_alerts_raw", actionName="TAS_alert_formatter_sub");
}catch(ex){}

// 2. 删除旧 engine
try{
    dropStreamEngine("TAS_alert_engine");
}catch(ex){}

// 3. 停掉所有 TAS_ 前缀后台任务
TAS_jobs = select * from getRecentJobs() where jobId like "TAS_%";
if(size(TAS_jobs) > 0){
    for(i in 0:size(TAS_jobs)-1){
        jid = TAS_jobs.jobId[i];
        if(not isNull(jid)){
            try{
                cancelJob(jid);
            }catch(ex){}
        }
    }
}

sleep(3000);

// 4. 删除流表
try{ dropStreamTable("TAS_alerts_raw", true); }catch(ex){}
try{ dropStreamTable("TAS_metric_stream", true); }catch(ex){}
try{ dropStreamTable("TAS_output", true); }catch(ex){}
try{ dropStreamTable("TAS_input", true); }catch(ex){}

// 5. 删除共享表
if(defined("TAS_metrics", SHARED)){
    try{ undef("TAS_metrics", SHARED); }catch(ex){}
}
if(defined("TAS_alerts", SHARED)){
    try{ undef("TAS_alerts", SHARED); }catch(ex){}
}

sleep(2000);
'''
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = r'''

TAS_runStart = now();

// 1. 创建固定名字共享对象
share streamTable(10000:0,
    `msgId`sourceId`eventTime`value`batchNo,
    [LONG, STRING, TIMESTAMP, DOUBLE, INT]
) as TAS_input;

share streamTable(10000:0,
    `msgId`sourceId`eventTime`processedTime`value`batchNo,
    [LONG, STRING, TIMESTAMP, TIMESTAMP, DOUBLE, INT]
) as TAS_output;

share table(100000:0,
    `checkTime`sourceNode`inputCnt`outputCnt`backlog`backlogGrowth`maxDelayMs`avgDelayMs,
    [TIMESTAMP, STRING, LONG, LONG, LONG, DOUBLE, LONG, DOUBLE]
) as TAS_metrics;

share streamTable(10000:0,
    `checkTime`sourceNode`inputCnt`outputCnt`backlog`backlogGrowth`maxDelayMs`avgDelayMs,
    [TIMESTAMP, STRING, LONG, LONG, LONG, DOUBLE, LONG, DOUBLE]
) as TAS_metric_stream;

share streamTable(10000:0,
    `checkTime`sourceNode`anomalyType`anomalyString,
    [TIMESTAMP, STRING, INT, STRING]
) as TAS_alerts_raw;

share table(200000:0,
    `alertId`eventTime`sourceNode`component`severity`alertName`message`groupKey`metricValue,
    [STRING, TIMESTAMP, STRING, STRING, STRING, STRING, STRING, STRING, DOUBLE]
) as TAS_alerts;

// 2. 慢消费者
def TAS_slowConsumer(mutable msg){
    sleep(500);

    tb = select
        msgId,
        sourceId,
        eventTime,
        now() as processedTime,
        value,
        batchNo
    from msg;

    append!(TAS_output, tb);
}

subscribeTable(
    tableName="TAS_input",
    actionName="TAS_slow_consumer",
    offset=-1,
    handler=TAS_slowConsumer,
    msgAsTable=true,
    batchSize=500,
    throttle=0.1
);

// 3. 高频生产者
def TAS_producer(rounds, batchSize, producerSleepMs){
    baseId = 1;

    for(r in 1..rounds){
        srcIdx = rand(300, batchSize) + 1;
        srcIds = "SRC_" + lpad(string(srcIdx), 4, "0");

        tb = table(
            long(baseId..(baseId + batchSize - 1)) as msgId,
            srcIds as sourceId,
            take(now(), batchSize) as eventTime,
            rand(1000.0, batchSize) as value,
            take(r, batchSize) as batchNo
        );

        append!(TAS_input, tb);

        baseId = baseId + batchSize;
        sleep(producerSleepMs);
    }
}

// 4. 统一结构化告警写入
def TAS_appendAlert(alertId, eventTime, sourceNode, component, severity, alertName, message, groupKey, metricValue){
    tb = table(
        [alertId] as alertId,
        [eventTime] as eventTime,
        [sourceNode] as sourceNode,
        [component] as component,
        [severity] as severity,
        [alertName] as alertName,
        [message] as message,
        [groupKey] as groupKey,
        [double(metricValue)] as metricValue
    );
    append!(TAS_alerts, tb);
}

// 5. monitor: 采集本次运行指标
def TAS_monitor(rounds, monitorSleepMs, runStartTs){
    prevBacklog = 0l;

    for(i in 1..rounds){
        nowTs = now();

        inputCnt = exec count(*) from TAS_input where eventTime >= runStartTs;
        outputCnt = exec count(*) from TAS_output where processedTime >= runStartTs;
        backlog = inputCnt - outputCnt;
        backlogGrowth = double(backlog - prevBacklog);

        if(inputCnt == 0){
            maxDelayMs = 0l;
            avgDelayMs = 0.0;
        }else{
            recentInput = select top 1000 eventTime
                          from TAS_input
                          where eventTime >= runStartTs
                          order by eventTime asc;

            recentInputCnt = exec count(*) from recentInput;

            if(recentInputCnt == 0){
                maxDelayMs = 0l;
                avgDelayMs = 0.0;
            }else{
                delayTb = select long(nowTs - eventTime) as delayMs from recentInput;
                maxDelayMs = exec max(delayMs) from delayTb;
                avgDelayMs = exec avg(delayMs) from delayTb;
            }
        }

        metricTb = table(
            [nowTs] as checkTime,
            ["node_local"] as sourceNode,
            [long(inputCnt)] as inputCnt,
            [long(outputCnt)] as outputCnt,
            [long(backlog)] as backlog,
            [double(backlogGrowth)] as backlogGrowth,
            [long(maxDelayMs)] as maxDelayMs,
            [double(avgDelayMs)] as avgDelayMs
        );

        append!(TAS_metrics, metricTb);
        append!(TAS_metric_stream, metricTb);

        prevBacklog = backlog;
        sleep(monitorSleepMs);
    }
}

// 6. 创建异常检测引擎
TAS_engine = createAnomalyDetectionEngine(
    name="TAS_alert_engine",
    metrics=<[
        backlog >= 100000,
        backlog >= 300000,
        backlogGrowth >= 50000,
        maxDelayMs >= 1000,
        maxDelayMs >= 3000
    ]>,
    dummyTable=TAS_metric_stream,
    outputTable=TAS_alerts_raw,
    timeColumn=`checkTime,
    keyColumn=`sourceNode,
    anomalyDescription=[
        "backlog >= 100000",
        "backlog >= 300000",
        "backlogGrowth >= 50000",
        "maxDelayMs >= 1000",
        "maxDelayMs >= 3000"
    ]
);

subscribeTable(
    tableName="TAS_metric_stream",
    actionName="TAS_alert_sub",
    offset=-1,
    handler=append!{TAS_engine},
    msgAsTable=true
);

// 7. 原始异常结果格式化为最终告警
def TAS_formatRawAlerts(mutable msg){
    n = size(msg);
    if(n == 0){
        return 0;
    }

    for(i in 0:n-1){
        eventTime = msg.checkTime[i];
        sourceNode = msg.sourceNode[i];
        anomalyString = string(msg.anomalyString[i]);

        if(isNull(eventTime) or isNull(msg.anomalyString[i]) or anomalyString == ""){
            continue;
        }

        severity = "WARN";
        alertName = "";
        message = "";
        component = "";
        metricValue = 0.0;
        groupKey = "";
        matched = false;

        if(like(anomalyString, "%backlog >= 300000%")){
            severity = "ERROR";
            alertName = "BacklogHigh";
            message = "Backlog is very high";
            component = "queue";
            metricValue = 300000.0;
            groupKey = "backlog_high";
            matched = true;
        }
        else if(like(anomalyString, "%backlog >= 100000%")){
            severity = "WARN";
            alertName = "BacklogHigh";
            message = "Backlog is elevated";
            component = "queue";
            metricValue = 100000.0;
            groupKey = "backlog_high";
            matched = true;
        }
        else if(like(anomalyString, "%backlogGrowth >= 50000%")){
            severity = "ERROR";
            alertName = "QueuePressureHigh";
            message = "Backlog is growing rapidly";
            component = "queue";
            metricValue = 50000.0;
            groupKey = "queue_pressure";
            matched = true;
        }
        else if(like(anomalyString, "%maxDelayMs >= 3000%")){
            severity = "ERROR";
            alertName = "ProcessingDelayHigh";
            message = "Processing delay is critically high";
            component = "stream_pipeline";
            metricValue = 3000.0;
            groupKey = "processing_delay";
            matched = true;
        }
        else if(like(anomalyString, "%maxDelayMs >= 1000%")){
            severity = "WARN";
            alertName = "ProcessingDelayHigh";
            message = "Processing delay is elevated";
            component = "stream_pipeline";
            metricValue = 1000.0;
            groupKey = "processing_delay";
            matched = true;
        }

        if(matched){
            alertId = "TAS_" + string(eventTime) + "_" + string(i);

            TAS_appendAlert(
                alertId,
                eventTime,
                sourceNode,
                component,
                severity,
                alertName,
                message,
                groupKey,
                metricValue
            );
        }
    }

    return n;
}

subscribeTable(
    tableName="TAS_alerts_raw",
    actionName="TAS_alert_formatter_sub",
    offset=-1,
    handler=TAS_formatRawAlerts,
    msgAsTable=true
);

// 8. 启动作业
submitJob("TAS_producer_job", "TAS_producer_job", TAS_producer, 600, 4000, 5);
submitJob("TAS_monitor_job", "TAS_monitor_job", TAS_monitor, 240, 500, TAS_runStart);
sleep(130000);
TAS_alert_cnt = exec count(*) from TAS_alerts;
if(TAS_alert_cnt <= 0){
    throw "TAS_alerts is empty after fault injection";
}
'''
        self.runScript(script)

    # 检查AI处理后告警是否降到可接受范围
    def health_checker(self):
        alert_threshold = 20

        exists = self.session.run('defined("TAS_alerts", SHARED)')
        if not exists:
            return

        script = "exec count(*) from TAS_alerts"
        current_alert_count = self.session.run(script)

        if current_alert_count >= alert_threshold:
            raise ValueError(
                f"TestAlertStorm failed, alerts are still too many. "
                f"threshold={alert_threshold}, now={current_alert_count}"
            )
