import Test


class TestLogVolumeOverload(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "日志量过大，磁盘快被写满了，请诊断并处理",
            "节点日志输出异常大量，帮忙看看",
            "日志文件占用空间过多，请排查处理",
        ]

    def cleanup(self):
        script = """
        if(defined("TLVO_log_flag", SHARED)){
            undef("TLVO_log_flag", SHARED);
        }
        """
        self.runScript(script)

    def fault_injector(self):
        script = """
        flagTb = table(1:0, [`flag, `scene, `status], [INT, STRING, STRING]);
        insert into flagTb values (1, "TestLogVolumeOverload", "injecting");
        share flagTb as TLVO_log_flag;

        dnodeAlias = exec first(name) from getClusterPerf(true) where mode = 0;

        def TLVO_write_logs(){
            n = 20000;
            for(i in 0:(n-1)){
                levelTag = "INFO";
                msg = "TLVO_TEST_MARK background task heartbeat ok";

                if(i >= 2000 && i < 2050){
                    x = i % 5;
                    levelTag = iif(x == 2, "ERROR", iif(x == 1 || x == 3, "WARN", "INFO"));
                    msg = iif(x == 0, "TLVO_TEST_MARK node=node2 service=datanode logModule=storage flush task started for partition p202604",
                          iif(x == 1, "TLVO_TEST_MARK node=node2 service=datanode logModule=storage wal queue depth increased to 8192",
                          iif(x == 2, "TLVO_TEST_MARK node=node2 service=datanode logModule=storage disk writer failed: No space left on device",
                          iif(x == 3, "TLVO_TEST_MARK node=node2 service=datanode logModule=storage flush retry scheduled after 5000 ms",
                                     "TLVO_TEST_MARK node=node2 service=datanode logModule=storage tablet write throughput dropped"))));
                }

                if(i >= 8000 && i < 8050){
                    x = i % 5;
                    levelTag = iif(x == 2, "ERROR", iif(x == 3, "WARN", "INFO"));
                    msg = iif(x == 0, "TLVO_TEST_MARK node=node1 service=datanode logModule=config loading cluster node config",
                          iif(x == 1, "TLVO_TEST_MARK node=node1 service=datanode logModule=config parsing volumes configuration",
                          iif(x == 2, "TLVO_TEST_MARK node=node1 service=datanode logModule=config invalid config item: volumes=/data/<ALIAS>",
                          iif(x == 3, "TLVO_TEST_MARK node=node1 service=datanode logModule=config service startup aborted due to invalid configuration",
                                     "TLVO_TEST_MARK node=node1 service=datanode logModule=config node restart attempt finished"))));
                }

                if(i >= 14000 && i < 14100){
                    x = i % 4;
                    levelTag = iif(x == 2, "ERROR", iif(x == 1 || x == 3, "WARN", "INFO"));
                    msg = iif(x == 0, "TLVO_TEST_MARK node=node3 service=computenode logModule=rpc connection pool active=128",
                          iif(x == 1, "TLVO_TEST_MARK node=node3 service=computenode logModule=rpc latency exceeded threshold 3000 ms",
                          iif(x == 2, "TLVO_TEST_MARK node=node3 service=computenode logModule=rpc downstream rpc timeout while querying partition metadata",
                                     "TLVO_TEST_MARK node=node3 service=computenode logModule=rpc retry rpc in 3 seconds")));
                }

                if(i >= 17000 && i < 17030){
                    levelTag = "ERROR";
                    msg = "TLVO_TEST_MARK node=node2 service=computenode logModule=query query execution interrupted by resource contention";
                }

                writeLog("[" + levelTag + "] " + msg);
            }
            return 1;
        }

        rpc(dnodeAlias, TLVO_write_logs);
        """
        self.runScript(script)

    # 但是此案例对于AI agent的要求是日志摘要、异常聚类、关键上下文提取，属于分析型场景，无法定量，后续的health_checker可删去，改成人工检查
    def health_checker(self):
        script = """
        if(defined("TLVO_log_flag", SHARED)){
            throw "TLVO_log_flag is still defined, log overload scenario is not cleared.";
        }
        """
        self.runScript(script)
