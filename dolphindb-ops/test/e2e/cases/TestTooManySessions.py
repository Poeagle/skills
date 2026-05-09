import os
import dolphindb as ddb
import Test

class TestTooManySessions(Test.Test):
    def __init__(self):
        super().__init__()
        self.leaked_sessions = []
        self.session_init = 0
        self.session_count = 200
        self.questions = [
            "连接数过多，资源即将耗尽，请诊断并处理",
            "会话数量异常大，帮忙看看怎么回事",
            "连接数远超正常水平，请排查处理",
        ]

    # 清理环境：查看初始连接数
    def cleanup(self):
        # ===== 修改点3：cleanup 先真正关闭 leaked_sessions =====
        # 原来的 cleanup 只是查初始连接数，没有清掉前一次故障注入出来的 session，
        # 这样下一轮测试的基线会被污染。
        if len(self.leaked_sessions) > 0:
            for s in self.leaked_sessions:
                try:
                    s.close()
                except Exception:
                    # 某些 session 可能已经断了，忽略即可
                    pass
            self.leaked_sessions = []

        # ===== 修改点4：获取基线连接数时，直接用 session.run 拿返回值 =====
        # 比 self.runScript 更明确，因为这里我们需要把 count 赋给 self.session_init。
        script = '''
        exec count(*) from getConnections()
        '''
        self.session_init = self.session.run(script)

    # 制造异常：短时间创建大量会话并保持不关闭
    def fault_injector(self):
        ip = os.environ["DDB_IP"]
        port = int(os.environ["DDB_PORT"])
        user = os.environ["DDB_USER"]
        password = os.environ["DDB_PASSWORD"]

        for i in range(self.session_count):
            s = ddb.session()
            s.connect(
                ip,
                port,
                user,
                password,
                readTimeout=self._ddb_read_timeout,
                writeTimeout=self._ddb_write_timeout,
            )
            s.run("1+1")
            self.leaked_sessions.append(s)

    # 检查是否已把会话全部关闭
    def health_checker(self):
        # ===== 修改点5：修复 DolphinDB if(exec ...) 的解析问题 =====
        # 原来的写法：
        # if(exec count(*) from getConnections() > {self.session_init} + 5){...}
        # 会被 DolphinDB 解析错。
        #
        # 正确写法要把 exec 的结果先括起来，或者先赋值再比较。
        # 这里用最简单稳定的方式：先赋值，再比较。
        script = f'''
        curConn = exec count(*) from getConnections()
        if(curConn > {self.session_init} + 5){{
            throw "Sessions are still too many!"
        }}
        '''
        self.runScript(script)
