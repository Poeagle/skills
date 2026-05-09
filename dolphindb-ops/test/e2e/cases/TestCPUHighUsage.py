import Test


class TestCPUHighUsage(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "节点 CPU 使用率一直很高，请诊断并处理",
            "CPU 快跑满了，帮忙看看什么情况",
            "CPU 使用率异常偏高，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        jobs=select * from getRecentJobs() where jobId like "cpuHighUsageTest%" and endTime is null
        for(i in jobs){
            cancelJob(jobs.jobId)
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
        def cpuHighUsageTest(){
            w=peach(tt,100000..100500)
        }
        submitJob("cpuHighUsageTest","cpuHighUsageTest",cpuHighUsageTest)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if ((exec count(*) from getRecentJobs() where jobId like "cpuHighUsageTest%" and endTime is null)>0){
            throw "cpuHighUsageTest job not canceled"
        }
        """
        self.runScript(script)
