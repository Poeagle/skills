import Test


class TestPartitionAnomaly(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "分区元数据异常，查询结果不对，请诊断并修复",
            "数据分区有损坏，帮忙看看怎么回事",
            "分区数据异常，请排查并恢复",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        TPA_dbName = "dfs://TPA_level2_tl"
        TPA_tbName = "TPA_trade"

         def dropDBWithTPA_level2_tl(dbName) {
            if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTPA_tradeWithTPA_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        dropTPA_tradeWithTPA_level2_tl(TPA_dbName, TPA_tbName)
        dropDBWithTPA_level2_tl(TPA_dbName)

        undef(all, VAR)
        undef(all, DEF)
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        def dropDBWithTPA_level2_tl(dbName) {
            if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTPA_tradeWithTPA_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        def createDBWithTPA_level2_tl(dbName) {
            db0 =database(, partitionType = VALUE, partitionScheme = 2020.01.01..2020.01.01);
            db1 =database(, partitionType = HASH, partitionScheme = [SYMBOL,25]);
            database(directory = dbName, partitionType = COMPO, partitionScheme = [db0,db1], engine= `TSDB, atomic = `TRANS, chunkGranularity = `TABLE) 
        }

        def createTPA_tradeWithTPA_level2_tl(dbName, tbName) {
            createPartitionedTable(dbHandle = database(dbName),table = table(1:0, ["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["INT","LONG","INT","INT","INT","SYMBOL","INT","DOUBLE","LONG","INT","TIMESTAMP","TIME","INT","SYMBOL","SYMBOL","INT","INT","DOUBLE","LONG"]),tableName = tbName,partitionColumns =["TradeTime","SecurityID"],compressMethods = dict(["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","delta","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4"]),sortColumns = ["Market","SecurityID","TradeTime"],keepDuplicates = ALL,softDelete = false) 
        }

        TPA_dbName = "dfs://TPA_level2_tl"
        TPA_tbName = "TPA_trade"

        dropTPA_tradeWithTPA_level2_tl(TPA_dbName, TPA_tbName)
        dropDBWithTPA_level2_tl(TPA_dbName)

        createDBWithTPA_level2_tl(TPA_dbName)
        createTPA_tradeWithTPA_level2_tl(TPA_dbName, TPA_tbName)

        dataFilePath = "/ssd/ssd3/xyh/tmp/TPA_trade_data.csv"
        schemaTB=extractTextSchema(dataFilePath)

        update schemaTB set type = "LONG" where name = "ApplSeqNum"
        update schemaTB set type = "INT" where name = "MDStreamID"
        update schemaTB set type = "SYMBOL" where name = "SecurityID"
        update schemaTB set type = "INT" where name = "SecurityIDSource"
        update schemaTB set type = "INT" where name = "ExecType"
        update schemaTB set type = "SYMBOL" where name = "TradeBSFlag"

        t_tmp = loadText(filename = dataFilePath, schema = schemaTB)
        setMaxTransactionSize("TSDB", 32)
        loadTable(TPA_dbName,TPA_tbName).append!(t_tmp)

        dbPath = "/" + TPA_dbName[6:] + "/"
        tbIndex = (exec physicalIndex from  listTables(TPA_dbName) where tableName = TPA_tbName)[0]
        c_meta = select * from rpc(getControllerAlias(), getClusterChunksStatus) where file.startsWith(dbPath) and file.endsWith(tbIndex)
        chunkInfo = select * from c_meta where chunkId = c_meta.chunkId[0]
        rpc(getControllerAlias(),deleteChunkMetaOnMasterById{chunkInfo.file[0], chunkInfo.chunkId[0]})
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        TPA_dbName = "dfs://TPA_level2_tl"
        TPA_tbName = "TPA_trade"
        totalCountSize = 108307208
        CountSize = exec count(*) from loadTable(TPA_dbName,TPA_tbName) where TradeTime = 2023.02.01
        
        if (totalCountSize != CountSize) {
            throw "Test Partiton Anomaly Failed!"
        }
        """
        self.runScript(script)
