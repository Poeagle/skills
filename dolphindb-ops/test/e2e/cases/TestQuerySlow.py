import Test


class TestQuerySlow(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "查询变得很慢，请诊断并处理",
            "数据库查询响应时间异常长，帮忙看看",
            "查询性能严重下降，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        jobs=select * from getRecentJobs() where jobId like "querySlowTest%" and endTime is null
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
        def querySlowTest(){
            w=peach(tt,100000..100100) 
        }

        submitJob("querySlowTest","querySlowTest",querySlowTest)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if ((exec count(*) from getRecentJobs() where jobId like "querySlowTest%" and endTime is null)>0){
            throw "querySlowTest job not canceled"
        }
        """
        self.runScript(script)


if __name__ == "__main__":
    t = TestQuerySlow()
    t.cleanup()
    t.fault_injector()
    t.cleanup()
    t.health_checker()
