import Test
import os


class TestJobTimeoutRisk(Test.Test):
    def __init__(self):
        super().__init__()
        self.db_path = "dfs://TJTR_testdb"
        self.table_name = "TJTR_entrust"
        self.questions = [
            "有一个任务运行了很长时间还没结束，请诊断并处理",
            "后台有个作业跑了很久了，帮忙看看什么情况",
            "任务执行时间远超预期，请排查处理",
        ]

    # 清理预计导入的数据库，避免数据类型不匹配的错误
    def cleanup(self):
        script = f"""
        if(existsDatabase("{self.db_path}")){{
            dropDatabase("{self.db_path}")
        }}

        Jobs = select * from getRecentJobs() where jobId like "TJTR_test%" and endTime is null
        for(job in Jobs){{
            cancelJob(job.jobId)
        }}
        """
        self.runScript(script)

    # 异常任务：写入缓慢
    def fault_injector(self):
        script = f"""

        def TJTR_prepareTable(dbPath, tbName){{
            if(existsDatabase(dbPath)){{
                return true
            }}

            tradeDates = 2023.02.01..2023.02.20
            dbDate = database("", VALUE, tradeDates)
            dbSym = database("", HASH, [SYMBOL, 32])
            db = database(dbPath, COMPO, [dbDate, dbSym])

            schemaTb = table(1:0,
                `TradeDate`TradeTime`SecurityID`Price`Qty`Amount`BSFlag,
                [DATE, TIMESTAMP, SYMBOL, DOUBLE, INT, DOUBLE, SYMBOL]
            )

            createPartitionedTable(db, schemaTb, tbName, `TradeDate`SecurityID)
            return true
        }}

        def TJTR_test(dbPath, tbName){{
            totalLoops = 2000
            pt = loadTable(dbPath, tbName)

            syms = symbol(string(500000 + 0..49999) + ".SH")

            for(i in 1..totalLoops){{
                batchRows = 2000
                curDate = 2023.02.01 + ((i - 1) % 20)

                securityIds = rand(syms, batchRows)
                tradeDateCol = take(curDate, batchRows)
                tradeTimeCol = take(timestamp(curDate), batchRows)
                priceCol = round(rand(20000, batchRows) / 100.0 + 5, 2)
                qtyCol = rand(10000, batchRows) + 1
                amountCol = priceCol * qtyCol
                bsFlagCol = rand(`B`S, batchRows)

                tmp = table(
                    tradeDateCol as TradeDate,
                    tradeTimeCol as TradeTime,
                    securityIds as SecurityID,
                    priceCol as Price,
                    qtyCol as Qty,
                    amountCol as Amount,
                    bsFlagCol as BSFlag
                )

                append!(pt, tmp)
            }}

            return true
        }}

        TJTR_prepareTable("{self.db_path}", "{self.table_name}")
        submitJob("TJTR_test", "Test job timeout risk", TJTR_test, "{self.db_path}", "{self.table_name}")
        """
        self.runScript(script)

    # 检查最近任务列表中已不存在该异常长任务
    def health_checker(self):
        script = """
        if((exec count(*) from getRecentJobs() where jobId like "TJTR_test%" and endTime is null) > 0){
            throw "Longtime running job is still active in recent job list";
        }
        """
        self.runScript(script)
