import dolphindb as ddb
import os
import subprocess


class Test:
    # 初始化，创建连接
    def __init__(self):
        self._ddb_host = os.environ["DDB_IP"]
        self._ddb_port = int(os.environ["DDB_PORT"])
        self._ddb_user = os.environ["DDB_USER"]
        self._ddb_password = os.environ["DDB_PASSWORD"]
        self._ddb_read_timeout = int(
            os.environ.get("DDB_SESSION_READ_TIMEOUT", "5"))
        self._ddb_write_timeout = int(
            os.environ.get("DDB_SESSION_WRITE_TIMEOUT", "5"))
        self.session = self._create_session()
        # SSH 连接信息（由后端注入环境变量）
        self._ssh_host = os.environ.get("SSH_HOST")
        self._ssh_user = os.environ.get("SSH_USER")
        self._ssh_port = os.environ.get("SSH_PORT", "22")
        self._ssh_key_path = os.environ.get("SSH_KEY_PATH")
        self._ssh_password = os.environ.get("SSH_PASSWORD")
        self._connect_session(raise_on_failure=False)

    def _create_session(self):
        return ddb.session()

    def _connect_session(self, session=None, raise_on_failure=True):
        target = session or self.session
        try:
            connected = target.connect(
                self._ddb_host,
                self._ddb_port,
                self._ddb_user,
                self._ddb_password,
                readTimeout=self._ddb_read_timeout,
                writeTimeout=self._ddb_write_timeout,
            )
        except Exception as e:
            if raise_on_failure:
                raise RuntimeError(f"DolphinDB connect failed: {e}") from e
            print(f"[DDB] 初始连接失败，后续按需重试: {e}")
            return False

        if not connected:
            if raise_on_failure:
                raise RuntimeError(
                    "DolphinDB connect failed: connect returned False")
            print("[DDB] 初始连接失败，后续按需重试: connect returned False")
            return False

        return True

    def _ensure_session_connected(self):
        if self.session is None:
            self.session = self._create_session()
        try:
            return self._connect_session(self.session, raise_on_failure=True)
        except Exception:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = self._create_session()
            return self._connect_session(self.session, raise_on_failure=True)

    # 关闭连接
    def closeConnection(self):
        if self.session is None:
            return
        self.session.close()

    # 执行脚本（连接断开时自动重连）
    def runScript(self, script):
        self._ensure_session_connected()
        try:
            return self.session.run(script)
        except Exception:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = self._create_session()
            self._connect_session(self.session, raise_on_failure=True)
            return self.session.run(script)

    def ssh_exec(self, cmd, check=False):
        """在 DDB 节点所在服务器上通过 SSH 执行 shell 命令

        Args:
            cmd: 要执行的 shell 命令字符串
            check: 如果为 True，命令失败时抛出异常

        Returns:
            subprocess.CompletedProcess 对象（stdout, stderr, returncode）
        """
        if not self._ssh_host or not self._ssh_user:
            raise RuntimeError("SSH_HOST/SSH_USER 未配置，无法远程执行 shell 命令")

        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", self._ssh_port,
        ]
        if self._ssh_key_path:
            ssh_cmd += ["-i", self._ssh_key_path]
        ssh_cmd += [f"{self._ssh_user}@{self._ssh_host}", cmd]

        print(f"[SSH] {self._ssh_user}@{self._ssh_host}: {cmd}")
        result = subprocess.run(
            ssh_cmd, capture_output=True, text=True, timeout=120)

        if result.stdout.strip():
            print(f"[SSH stdout] {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"[SSH stderr] {result.stderr.strip()}")

        if check and result.returncode != 0:
            raise RuntimeError(
                f"SSH 命令失败 (rc={result.returncode}): {result.stderr.strip()}")
        return result

    def ssh_file_exists(self, path):
        """检查远程服务器上的文件是否存在"""
        result = self.ssh_exec(
            f'test -e "{path}" && echo EXISTS || echo MISSING')
        return "EXISTS" in result.stdout
