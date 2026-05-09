import Test
import dolphindb as ddb
import os
import time


class TestPortStop(Test.Test):
    """测试端口停止的故障注入测试类 — 通过 SSH 在远程服务器上暂停/恢复 DDB 进程"""

    def __init__(self):
        super().__init__()
        self.TPS_port = int(os.environ.get("DDB_PORT", 7932))
        self.TPS_original_pids = []
        self.TPS_check_table = "TPS_ConnectionStatus"
        self.questions = [
            "节点进程被暂停了，端口无响应，请诊断并恢复",
            "节点服务停止响应了，帮忙看看什么情况",
            "端口服务异常中断，请排查并恢复服务",
        ]

    def _get_remote_pids_on_port(self, port):
        """通过 SSH 获取远程服务器上监听指定端口的进程ID"""
        result = self.ssh_exec(
            f'lsof -nP -iTCP:{port} -sTCP:LISTEN -t 2>/dev/null | sort -u || '
            f'ss -ltnp "sport = :{port}" 2>/dev/null | grep -oP "pid=\\K[0-9]+" | sort -u')
        pids = sorted({int(p) for p in result.stdout.strip().split(
            '\n') if p.strip().isdigit()})
        return pids

    def _get_remote_process_info(self, pid):
        """通过 SSH 获取远程进程信息"""
        result = self.ssh_exec(
            f'cat /proc/{pid}/comm 2>/dev/null || echo "PID_{pid}"')
        return result.stdout.strip()

    def cleanup(self):
        """清理环境"""
        print(f"[{self.__class__.__name__}] 执行清理操作")

        # 1. 恢复之前停止的进程
        if self.TPS_original_pids:
            print(f"准备恢复进程: {self.TPS_original_pids}")
            for pid in self.TPS_original_pids:
                result = self.ssh_exec(f'kill -CONT {pid} 2>/dev/null')
                if result.returncode == 0:
                    print(f"  已恢复进程 {pid}")
                else:
                    print(f"  恢复进程 {pid} 失败（可能已退出）")
            self.TPS_original_pids = []

        # 2. 清理 DolphinDB 测试表
        try:
            time.sleep(1)
            self.runScript(f"""
            if(existsTable("dfs://{self.TPS_check_table}", "{self.TPS_check_table}"))
                dropTable(database("dfs://{self.TPS_check_table}"), "{self.TPS_check_table}");
            """)
            print("已清理测试表")
        except Exception as e:
            print(f"清理测试表时出错（可能连接已中断）: {e}")

        # 3. 检查端口上的进程
        current_pids = self._get_remote_pids_on_port(self.TPS_port)
        if current_pids:
            print(f"端口 {self.TPS_port} 当前运行的进程: {current_pids}")
        else:
            print(f"警告: 端口 {self.TPS_port} 没有 DolphinDB 进程在运行")

        time.sleep(2)
        print(f"[{self.__class__.__name__}] 清理完成")

    def fault_injector(self):
        """制造异常 — 通过 SSH 在远程服务器上暂停 DDB 进程"""
        print(f"[{self.__class__.__name__}] 开始注入故障")

        # 1. 获取端口上的进程
        self.TPS_original_pids = self._get_remote_pids_on_port(self.TPS_port)
        if not self.TPS_original_pids:
            raise Exception(f"端口 {self.TPS_port} 没有找到 DolphinDB 进程")

        print(f"端口 {self.TPS_port} 的进程: {self.TPS_original_pids}")
        for pid in self.TPS_original_pids:
            info = self._get_remote_process_info(pid)
            print(f"  - PID {pid}: {info}")

        # 2. 在 DolphinDB 中创建测试表
        try:
            self.runScript(f"""
            if(!existsDatabase("dfs://{self.TPS_check_table}")){{
                db = database("dfs://{self.TPS_check_table}", VALUE, 2023.01.01..2023.01.31);
            }}else{{
                db = database("dfs://{self.TPS_check_table}");
            }}
            t = table(take(1..100, 100) as id, take(`A`B`C, 100) as symbol, rand(100.0, 100) as price);
            db.createTable(t, "{self.TPS_check_table}");
            """)
            print("测试表创建成功")
        except Exception as e:
            print(f"创建测试表时出错: {e}")

        # 3. 通过 SSH 发送 SIGSTOP 暂停进程
        print("开始暂停进程...")
        stopped = []
        for pid in self.TPS_original_pids:
            result = self.ssh_exec(f'kill -STOP {pid}')
            if result.returncode == 0:
                print(f"  已暂停进程 {pid}")
                stopped.append(pid)
            else:
                print(f"  暂停进程 {pid} 失败")

        if not stopped:
            raise Exception("没有成功暂停任何进程")

        self.TPS_stop_time = time.time()
        print(f"[{self.__class__.__name__}] 故障注入完成，已暂停进程 {stopped}")

    def health_checker(self):
        """检查异常是否处理完成"""
        print(f"[{self.__class__.__name__}] 开始健康检查")

        # 1. 先恢复进程
        if self.TPS_original_pids:
            print(f"恢复停止的进程: {self.TPS_original_pids}")
            for pid in self.TPS_original_pids:
                self.ssh_exec(f'kill -CONT {pid} 2>/dev/null')
            time.sleep(3)

        # 2. 检查端口上是否有运行的进程
        current_pids = self._get_remote_pids_on_port(self.TPS_port)
        if not current_pids:
            raise Exception(f"端口 {self.TPS_port} 没有 DolphinDB 进程在运行")
        print(f"端口 {self.TPS_port} 当前运行的进程: {current_pids}")

        # 3. 尝试连接 DolphinDB
        print("尝试连接 DolphinDB...")
        try:
            result = self.session.run("1+1")
            if result != 2:
                raise Exception("会话响应异常")
            print("连接正常")
        except Exception:
            print("现有会话异常，尝试重新连接...")
            self.session.close()
            self.session = ddb.session()
            self.session.connect(
                os.environ["DDB_IP"], int(os.environ["DDB_PORT"]),
                os.environ["DDB_USER"], os.environ["DDB_PASSWORD"])
            print("重新连接成功")

        if hasattr(self, 'TPS_stop_time'):
            recovery_time = time.time() - self.TPS_stop_time
            print(f"服务恢复时间: {recovery_time:.2f}秒")

        print(f"[{self.__class__.__name__}] 健康检查通过")
        return True