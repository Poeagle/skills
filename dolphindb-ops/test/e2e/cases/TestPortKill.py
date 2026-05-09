import Test
import os
import time


class TestPortKill(Test.Test):
    def __init__(self, port=7930):
        super().__init__()
        self.port = int(os.environ.get("DDB_PORT", port))
        self.questions = [
            "节点进程被强制终止了，请诊断并恢复",
            "端口服务异常中断，帮忙看看什么情况",
            "节点崩溃了，请排查并恢复服务",
        ]

    def cleanup(self):
        ...

    def _get_remote_pid_on_port(self, port):
        """通过 SSH 获取远程服务器上占用指定端口的进程ID"""
        result = self.ssh_exec(
            f'lsof -ti :{port} 2>/dev/null || ss -tlnp sport = :{port} 2>/dev/null | grep -oP "pid=\\K[0-9]+"')
        pids = [int(p) for p in result.stdout.strip().split(
            '\n') if p.strip().isdigit()]
        return pids

    def fault_injector(self):
        """制造异常：通过 SSH 在远程服务器上模拟节点宕机"""
        print(f"开始制造节点宕机故障: 端口 {self.port}")

        # 1. 获取远程进程PID
        pids = self._get_remote_pid_on_port(self.port)
        if not pids:
            print(f"未找到占用端口 {self.port} 的进程")
            return False

        target_pid = pids[0]
        print(f"找到占用端口 {self.port} 的进程: PID={target_pid}")

        # 2. 通过 SSH 发送 SIGSEGV 信号终止进程
        print(f"发送SIGSEGV(11)信号终止进程 {target_pid}...")
        self.ssh_exec(f'kill -SEGV {target_pid}')

        # 3. 等待进程终止
        for _ in range(10):
            time.sleep(0.5)
            pids = self._get_remote_pid_on_port(self.port)
            if not pids:
                print(f"✅ 故障注入成功: 端口 {self.port} 已释放")
                return True

        print("⚠️ 进程终止但端口可能未立即释放")
        return True

    def health_checker(self):
        script = """
        1+1
        """
        self.runScript(script)
