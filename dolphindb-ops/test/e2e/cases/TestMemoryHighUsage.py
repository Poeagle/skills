import Test


class TestMemoryHighUsage(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "节点内存使用率异常偏高，请诊断并处理",
            "内存快要满了，帮忙看看怎么回事",
            "内存告警了，请帮忙排查处理一下",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        if(defined("TMHU_shared",SHARED)){
            undef("TMHU_shared",SHARED);
        }
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        share table(1:10000000,['symbol','time','value'],[STRING,TIMESTAMP,DOUBLE]) as TMHU_shared;
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        if(defined("TMHU_shared",SHARED)){
            throw "TMHU_shared is still defined";
        }
        """
        self.runScript(script)
