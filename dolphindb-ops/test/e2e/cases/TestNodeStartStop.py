import Test
import os


class TestNodeStartStop(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "节点频繁启停，系统不稳定，请诊断并处理",
            "节点反复重启，帮忙看看什么情况",
            "数据节点状态不稳定，请排查处理",
        ]

    def cleanup(self):
        ...

    def fault_injector(self):
        script = f"""
        n = pnodeRun(getNodeAlias).node[pnodeRun(getNodeAlias).node != getNodeAlias()][0]
        rpc(getControllerAlias(), stopDataNode{{n}})
        rpc(getControllerAlias(), startDataNode{{n}})
        rpc(getControllerAlias(), stopDataNode{{n}})
        rpc(getControllerAlias(), startDataNode{{n}})
        rpc(getControllerAlias(), stopDataNode{{n}})
        rpc(getControllerAlias(), startDataNode{{n}})
        rpc(getControllerAlias(), stopDataNode{{n}})
        rpc(getControllerAlias(), startDataNode{{n}})
        """
        self.runScript(script)

    def health_checker(self):
        script = """
        1+1
        """
        self.runScript(script)