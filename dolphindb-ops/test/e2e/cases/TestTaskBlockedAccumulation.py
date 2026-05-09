import Test


class TestTaskBlockedAccumulation(Test.Test):
    def __init__(self):
        super().__init__()
        self.db_path = "dfs://TTBA_testdb"
        self.source_table = "source_ticks"
        self.window_table = "window_cache"
        self.result_table = "daily_factor_result"
        self.symbol_count = 8000
        self.batch_rows = 50000
        self.window_days = 10
        self.compute_rounds = 4
        self.submit_interval_ms = 1000
        self.questions = [
            "任务队列积压严重，请诊断并处理",
            "后台任务越来越多，帮忙看看什么情况",
            "待执行任务持续累积，请排查处理",
        ]

    # 清理环境：删除测试库并取消残留任务
    def cleanup(self):
        script = """
        if(existsDatabase("dfs://TTBA_factor")){
            dropDatabase("dfs://TTBA_factor")
        }
        Jobs = select * from getRecentJobs() where jobId like "TTBA_test%" and endTime is null
        for(job in Jobs){
            cancelJob(job.jobId)
        }
        """
        self.runScript(script)

    # 异常制造：先造基础数据，再持续提交多个复杂慢日任务
    def fault_injector(self):
        script = """
        create database "dfs://TTBA_factor"
        partitioned by RANGE(date(datetimeAdd(1980.01M,0..80*12,'M'))), VALUE(`f1`f2),
        engine='TSDB',
        atomic='CHUNK'

        create table "dfs://TTBA_factor"."TTBA_factor_day"(
            SecurityID SYMBOL,
            TradeDate DATE[comment="时间列", compress="delta"],
            Value DOUBLE,
            FactorName SYMBOL,
            UpdateTime TIMESTAMP,
        )
        partitioned by TradeDate, FactorName
        sortColumns=[`SecurityID, `TradeDate],
        keepDuplicates=LAST, //支持重复写入，保留最新写入的因子值
        sortKeyMappingFunction=[hashBucket{, 500}]

        def TTBA_test(){
            dataTB = loadTable("dfs://level2_tl_test", "entrust")
            resTB = loadTable("dfs://TTBA_factor", "TTBA_factor_day")
            startTime = 09:30:00.000
            endTime = 14:57:00.000
            ds = select SecurityID, TradeTime.date() as TradeDate, TradeTime.time() as TradeTime, Price as TradePrice, Side as TradeBSFlag, last(Price) as ClosePrice from dataTB where TradeTime.date() >= 2023.02.06 and TradeTime.date() <= 2023.02.07 and (TradeTime.time() between startTime and endTime) and (SecurityID like "00%" or SecurityID like "30%" or SecurityID like "6%") and Price>0 context by TradeTime.date(), SecurityID
            res = select SecurityID, TradeDate, mean(iif(TradePrice<ClosePrice, TradePrice, NULL))\last(ClosePrice)-1 as value, "lcp" as factorName, now() as updateTime from ds where TradeBSFlag=`S group by TradeDate, SecurityID
            upsert!(resTB, res, keyColNames = `TradeDate`SecurityID)
            return true
        }

        for(i in 0..40){
            submitJob("TTBA_test_" + string(i), "Test Blocked tasks", TTBA_test)
            sleep(2000)
        }
        """
        self.runScript(script)

    # 这里先留最小占位，后续可按“异常已解决”的标准补充验收逻辑
    def health_checker(self):
        script = """
        if((exec count(*) from getRecentJobs() where jobId like "TTBA_test%" and endTime is null) > 5){
            throw "Jobs is still active in recent job list";
        }
        """
        self.runScript(script)
