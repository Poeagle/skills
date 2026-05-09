import Test


class TestLogNavigationFailure(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "日志中出现大量报错信息，请诊断并处理",
            "控制节点日志出现异常错误，帮忙看看",
            "节点操作报错了，请排查日志并处理",
        ]

    def cleanup(self):
        script = """
        // cleanup 只负责删除测试状态标记
        if(defined("TLNF_flag", SHARED)){
            undef("TLNF_flag", SHARED);
        }
        """
        self.runScript(script)

    def fault_injector(self):
        script = """
        // 创建测试状态标记
        flagTb = table(1:0, [`flag, `scene, `status], [INT, STRING, STRING]);
        insert into flagTb values (1, "LogNavigationFailure", "injecting");
        share flagTb as TLNF_flag;

        // 自动选择一个当前 data node
        dnode = exec first(site) from getClusterPerf(true) where mode = 0;
        ip = exec first(host) from getClusterPerf(true) where site = dnode;
        port = exec first(port) from getClusterPerf(true) where site = dnode;
        name = exec first(name) from getClusterPerf(true) where site = dnode;
        nameStr = string(name);

        // 不 stop，直接让 controller 再次启动这个已经在线的 data node
        // 这样 agent.log 会稳定产生 bind/startDataNodeAgent 相关错误
        rpc(getControllerAlias(), startDataNode{[ip + ":" + string(port)]});
        """
        self.runScript(script)

    def health_checker(self):
        # 这个场景属于“日志导航型”，应该先定位到agent.log
        pass
