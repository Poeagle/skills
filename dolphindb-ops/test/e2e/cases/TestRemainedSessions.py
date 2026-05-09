import os
import dolphindb as ddb
import Test


class TestRemainedSessions(Test.Test):
    def __init__(self):
        super().__init__()
        self.remained_sessions = []
        self.questions = [
            "有会话没有正常关闭，存在残留连接，请诊断并处理",
            "发现会话泄漏，连接没有被正确释放",
            "残留连接越来越多，请排查处理",
        ]

    # 清理环境：查看初始连接数
    def cleanup(self):
        if (len(self.remained_sessions) > 0):
            self.remained_sessions = []

    # 制造异常：创建会话并不关闭
    def fault_injector(self):
        ip = os.environ["DDB_IP"]
        port = int(os.environ["DDB_PORT"])
        user = os.environ["DDB_USER"]
        password = os.environ["DDB_PASSWORD"]

        s = ddb.session()
        s.connect(ip, port, user, password)
        s.run("1+1")
        self.remained_sessions.append(s)

    # 检查是否已把会话关闭
    def health_checker(self):
        alive_count = 0
        if (len(self.remained_sessions) > 0):
            for s in self.remained_sessions:
                try:
                    s.run("1+1")
                    alive_count += 1
                except Exception:
                    # run 失败，说明这个 session 大概率已经断了
                    pass

            if alive_count > 0:
                raise ValueError(f"仍有会话残留，存活连接数: {alive_count}")
