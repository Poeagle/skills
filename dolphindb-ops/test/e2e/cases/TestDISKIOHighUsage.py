import Test


class TestDISKIOHighUsage(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "磁盘 IO 很高，系统响应变慢了，请诊断并处理",
            "磁盘读写压力很大，帮忙看看什么情况",
            "IO 负载异常偏高，查询都变慢了",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        jobs=select * from getRecentJobs() where jobId like "diskIOHighUsageTest%" and endTime is null
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
                select avg(Price),std(Price),sum(Price) from loadTable("dfs://level2_tl_test","entrust") group by SecurityID
            }  
        }
        def diskIOHighUsageTest(){
            w=peach(tt,100000..100100) 
        }

        submitJob("diskIOHighUsageTest","diskIOHighUsageTest",diskIOHighUsageTest)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if ((exec count(*) from getRecentJobs() where jobId like "diskIOHighUsageTest%" and endTime is null)>0){
            throw "diskIOHighUsageTest job not canceled"
        }
        """
        self.runScript(script)


if __name__ == "__main__":
    t = TestDISKIOHighUsage()
    t.cleanup()
    t.fault_injector()
    t.cleanup()
    t.health_checker()
