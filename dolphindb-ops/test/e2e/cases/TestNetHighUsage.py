import Test


class TestNetHighUsage(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "网络带宽异常升高，请诊断并处理",
            "节点网络流量很高，帮忙看看怎么回事",
            "网络流量异常，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        jobs=select * from getRecentJobs() where jobId like "netHighUsageTest%" and endTime is null
        for(i in jobs){
            cancelJob(i.jobId)
            try{
                getJobReturn(i.jobId,true)
            }catch(ex){
            } 
        }
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        def tt(x){
            for(i in 1..x){
                select * from loadTable("dfs://level2_tl_test","entrust") where TradeTime > 2023.02.06 09:00:00.000 and TradeTime < 2023.02.06 10:00:00.000
            }  
        }
        def netHighUsageTest(){
            w=peach(tt,100000..100100) 
        }

        submitJob("netHighUsageTest","netHighUsageTest",netHighUsageTest)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if ((exec count(*) from getRecentJobs() where jobId like "netHighUsageTest%" and endTime is null)>0){
            throw "netHighUsageTest job not canceled"
        }
        """
        self.runScript(script)


if __name__ == "__main__":
    t = TestNetHighUsage()
    t.cleanup()
    t.fault_injector()
    t.cleanup()
    t.health_checker()
