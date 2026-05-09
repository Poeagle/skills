import Test


class TestDataNotConsistent(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "数据副本不一致，请诊断并修复",
            "查询不同副本返回的数据不一样，帮忙看看",
            "分区副本数据出现差异，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        TDNC_dbName = "dfs://TDNC_level2_tl"
        TDNC_tbName = "TDNC_trade"

        def dropDBWithTDNC_level2_tl(dbName) {
            if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTDNC_tradeWithTDNC_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        dropTDNC_tradeWithTDNC_level2_tl(TDNC_dbName, TDNC_tbName)
        dropDBWithTDNC_level2_tl(TDNC_dbName)

        undef(all, VAR)
        undef(all, DEF)
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        def dropDBWithTDNC_level2_tl(dbName) {
            if (existsDatabase(dbName)) {
                dropDatabase(dbName)
            } 
        }

        def dropTDNC_tradeWithTDNC_level2_tl(dbName, tbName) {
            if (existsTable(dbName, tbName)) {
                dropTable(database(dbName), tbName)
            }
        }

        def createDBWithTDNC_level2_tl(dbName) {
            db0 =database(, partitionType = VALUE, partitionScheme = 2020.01.01..2020.01.01);
            db1 =database(, partitionType = HASH, partitionScheme = [SYMBOL,25]);
            database(directory = dbName, partitionType = COMPO, partitionScheme = [db0,db1], engine= `TSDB, atomic = `TRANS, chunkGranularity = `TABLE) 
        }

        def createTDNC_tradeWithTDNC_level2_tl(dbName, tbName) {
            createPartitionedTable(dbHandle = database(dbName),table = table(1:0, ["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["INT","LONG","INT","INT","INT","SYMBOL","INT","DOUBLE","LONG","INT","TIMESTAMP","TIME","INT","SYMBOL","SYMBOL","INT","INT","DOUBLE","LONG"]),tableName = tbName,partitionColumns =["TradeTime","SecurityID"],compressMethods = dict(["ChannelNo","ApplSeqNum","MDStreamID","BidApplSeqNum","OfferApplSeqNum","SecurityID","SecurityIDSource","TradePrice","TradeQty","ExecType","TradeTime","LocalTime","SeqNo","TradeBSFlag","Market","DataStatus","TradeIndex","TradeMoney","BizIndex"],["lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4","delta","lz4","lz4","lz4","lz4","lz4","lz4","lz4","lz4"]),sortColumns = ["Market","SecurityID","TradeTime"],keepDuplicates = ALL,softDelete = false) 
        }

        TDNC_dbName = "dfs://TDNC_level2_tl"
        TDNC_tbName = "TDNC_trade"

        dropTDNC_tradeWithTDNC_level2_tl(TDNC_dbName, TDNC_tbName)
        dropDBWithTDNC_level2_tl(TDNC_dbName)

        createDBWithTDNC_level2_tl(TDNC_dbName)
        createTDNC_tradeWithTDNC_level2_tl(TDNC_dbName, TDNC_tbName)

        dataFilePath = "/ssd/ssd3/xyh/tmp/TDNC_trade_data.csv"
        schemaTB=extractTextSchema(dataFilePath)

        update schemaTB set type = "LONG" where name = "ApplSeqNum"
        update schemaTB set type = "INT" where name = "MDStreamID"
        update schemaTB set type = "SYMBOL" where name = "SecurityID"
        update schemaTB set type = "INT" where name = "SecurityIDSource"
        update schemaTB set type = "INT" where name = "ExecType"
        update schemaTB set type = "SYMBOL" where name = "TradeBSFlag"

        t_tmp = loadText(filename = dataFilePath, schema = schemaTB)
        setMaxTransactionSize("TSDB", 32)
        loadTable(TDNC_dbName,TDNC_tbName).append!(t_tmp)

        dbPath = "/" + TDNC_dbName[6:] + "/"
        tbIndex = (exec physicalIndex from  listTables(TDNC_dbName) where tableName = TDNC_tbName)[0]
        
        hashKey = 0
        hashExp = "%Key" + string(hashKey) + "%"
        c_meta = select * from rpc(getControllerAlias(), getClusterChunksStatus) where file.startsWith(dbPath) and file.endsWith(tbIndex) and  replicaCount == 2 and file like hashExp
       
        
        if (c_meta.size() > 0) {
            chunkId_0 = c_meta.chunkId[0]
            chunkReplicas = select * from pnodeRun(getAllChunks) where chunkId = chunkId_0
            RepNode1 = chunkReplicas.site[0]
            RepNode2 = chunkReplicas.site[1]
            TradeDate = 2023.02.01
            
            shell("rm -rf " + chunkReplicas.path[1])
            
            RepNode1Data = rpc(RepNode1, def(dbName, tnName, date, key) {
                return select * from loadTable(dbName, tnName) where TradeTime = date and hashBucket(SecurityID, 25) = key
            }, TDNC_dbName, TDNC_tbName, TradeDate, hashKey)
            
            
            RepNode2Data  = rpc(RepNode2, def(dbName, tnName, date, key) {
                return select * from loadTable(dbName, tnName) where TradeTime = date and hashBucket(SecurityID, 25) = key
            }, TDNC_dbName, TDNC_tbName, TradeDate, hashKey)
            
            if(RepNode1Data.size() != RepNode2Data.size()) {
                print(RepNode1Data.size())
                print(RepNode2Data.size())
                print("副本数据不一致！")
            }
   
        }
        
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        TDNC_dbName = "dfs://TDNC_level2_tl"
        TDNC_tbName = "TDNC_trade"

        hashKey = 0
        hashExp = "%Key" + string(hashKey) + "%"
        c_meta = select * from rpc(getControllerAlias(), getClusterChunksStatus) where file.startsWith(dbPath) and file.endsWith(tbIndex) and  replicaCount == 2 and file like hashExp
       
        
        if (c_meta.size() > 0) {
            chunkId_0 = c_meta.chunkId[0]
            chunkReplicas = select * from pnodeRun(getAllChunks) where chunkId = chunkId_0
            RepNode1 = chunkReplicas.site[0]
            RepNode2 = chunkReplicas.site[1]
            TradeDate = 2023.02.01
            
            RepNode1Data = rpc(RepNode1, def(dbName, tnName, date, key) {
                return select * from loadTable(dbName, tnName) where TradeTime = date and hashBucket(SecurityID, 25) = key
            }, TDNC_dbName, TDNC_tbName, TradeDate, hashKey)
            
            
            RepNode2Data  = rpc(RepNode2, def(dbName, tnName, date, key) {
                return select * from loadTable(dbName, tnName) where TradeTime = date and hashBucket(SecurityID, 25) = key
            }, TDNC_dbName, TDNC_tbName, TradeDate, hashKey)

            if(RepNode1Data.size() != RepNode2Data.size()) {
                throw "Test Partiton Anomaly Failed!"
            }
        }

        
        
        """
        self.runScript(script)
