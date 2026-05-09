import Test


class TestHangUp(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "系统疑似挂起了，响应很慢，请诊断并处理",
            "节点无响应，疑似被大量任务堵塞了",
            "系统卡死了，帮忙看看什么原因",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        jobs=select * from getRecentJobs() where jobId like "hangUpTest%" and endTime is null
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
            t=rand(10000000.0,1000000)
            for( i in 1..x){
                t=cumstdp(t)
            }
        }
        def hangUpTest(){
            w=peach(tt,100000..100500)
        }
        for(i in 0..100){
            submitJob("hangUpTest","hangUpTest",hangUpTest)
        }
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if ((exec count(*) from getRecentJobs() where jobId like "hangUpTest%" and endTime is null)>0){
            throw "hangUpTest job not canceled"
        }
        """
        self.runScript(script)


if __name__ == "__main__":
    t = TestHangUp()
    t.cleanup()
    t.fault_injector()
    t.cleanup()
    t.health_checker()
