import Test


class TestDataWriteFailed1_2(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "数据写入失败，类型不匹配，请诊断并修复",
            "导入数据时字段类型报错，帮忙看看",
            "数据加载因类型问题失败了，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        TDWF_dbName = "dfs://TDWF_level2_tl"
        TDWF_tbName = "TDWF_trade"

        def dropDBWithTDWF_level2_tl(dbName) {
        if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTDWF_tradeWithTDWF_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        dropTDWF_tradeWithTDWF_level2_tl(TDWF_dbName, TDWF_tbName)
        dropDBWithTDWF_level2_tl(TDWF_dbName)

        undef(all, VAR)
        undef(all, DEF)
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        def dropDBWithTDWF_level2_tl(dbName) {
            if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTDWF_tradeWithTDWF_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        def createDBWithTDWF_level2_tl(dbName) {
            db0 =database(, partitionType = VALUE, partitionScheme = 2020.01.01..2020.01.01);
            db1 =database(, partitionType = HASH, partitionScheme = [SYMBOL,25]);
            database(directory = dbName, partitionType = COMPO, partitionScheme = [db0,db1], engine= `TSDB, atomic = `TRANS, chunkGranularity = `TABLE) 
        }

        def createTDWF_tradeWithTDWF_level2_tl(dbName, tbName) {
            createPartitionedTable(dbHandle = database(dbName),table = table(1:0, ["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["INT","LONG","INT","INT","INT","SYMBOL","INT","DOUBLE","LONG","INT","TIMESTAMP","TIME","INT","SYMBOL","SYMBOL","INT","INT","DOUBLE","LONG"]),tableName = tbName,partitionColumns =["TradeTime","SecurityID"],compressMethods = dict(["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","delta","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4"]),sortColumns = ["Market","SecurityID","TradeTime"],keepDuplicates = ALL,softDelete = false) 
        }

        TDWF_dbName = "dfs://TDWF_level2_tl"
        TDWF_tbName = "TDWF_trade"

        dropTDWF_tradeWithTDWF_level2_tl(TDWF_dbName, TDWF_tbName)
        dropDBWithTDWF_level2_tl(TDWF_dbName)

        createDBWithTDWF_level2_tl(TDWF_dbName)
        createTDWF_tradeWithTDWF_level2_tl(TDWF_dbName, TDWF_tbName)

        dataFilePath = "/ssd/ssd3/xyh/tmp/TDWF_trade_data_2.csv"
        schemaTB=extractTextSchema(dataFilePath)

        update schemaTB set type = "LONG" where name = "ApplSeqNum"
        update schemaTB set type = "INT" where name = "MDStreamID"
        update schemaTB set type = "SYMBOL" where name = "SecurityID"
        update schemaTB set type = "INT" where name = "SecurityIDSource"
        update schemaTB set type = "INT" where name = "ExecType"
        update schemaTB set type = "SYMBOL" where name = "TradeBSFlag"

        t_tmp = loadText(filename = dataFilePath, schema = schemaTB)
        loadTable("dfs://TDWF_level2_tl", "TDWF_trade").append!(t_tmp)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        TDWF_dbName = "dfs://TDWF_level2_tl"
        TDWF_tbName = "TDWF_trade"
        if ((select count(*) as cnt from loadTable(TDWF_dbName, TDWF_tbName))[`cnt][0] <= 0) {
            throw "Test Data write Failed!"
        }
        """
        self.runScript(script)
