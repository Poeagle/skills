import Test


class TestFailedJobRetry(Test.Test):
    def __init__(self):
        super().__init__()
        self.success = 0
        self.questions = [
            "有一个后台任务执行失败了，请诊断并处理",
            "最近有作业报错退出了，帮忙看看怎么回事",
            "后台任务执行报错了，请排查处理",
        ]

    # 初始化：统计已有的成功任务
    def cleanup(self):
        script = """
            exec count(*) from getRecentJobs() where jobId like "TFJR_test%" and errorMsg is null
        """
        i = self.session.run(script)
        self.success = self.success + i

    # 执行任务
    def fault_injector(self):
        script = """
        def TFJR_test(){
            price = 1 2 3
            num = 3 2 1
            t = table(price, num)
            expr = parseExpr("select * from t")
            res = expr.eval()
            return true
        }
        submitJob("TFJR_test", "Failed Job test", TFJR_test)
        """
        self.runScript(script)

    # 检查列表中是否有新的成功任务
    def health_checker(self):
        script = f"""
        if((exec count(*) from getRecentJobs() where jobId like "TFJR_test%" and errorMsg is null) <= {self.success}){{
            throw "Cannot find successed Job";
        }}
        """
        self.runScript(script)
