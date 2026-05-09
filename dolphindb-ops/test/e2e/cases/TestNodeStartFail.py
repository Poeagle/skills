import Test
import os
import time


class TestNodeStartFail(Test.Test):
    def __init__(self):
        super().__init__()
        self.TNSF_prefix = "TNSF_"
        self.target_dir = "/hdd/hdd8/ymchen/ddb-test/dolphindb/server/clusterDemo"
        self.target_user = "node_test"
        self.original_owner_group = None

        self.questions = [
            "节点启动失败了，请诊断并修复",
            "数据节点无法正常启动，帮忙看看什么原因",
            "节点启动报错了，请排查处理",
        ]

    def cleanup(self):
        """清理环境"""
        print(f"清理环境: 恢复 {self.target_dir} 的权限")
        try:
            # 优先恢复原始 owner:group；拿不到则回退 root:root
            owner_group = self.original_owner_group or "root:root"
            self.ssh_exec(
                f'sudo chown -R {owner_group} "{self.target_dir}"',
                check=False
            )
            print(f"✅ 恢复权限完成: {self.target_dir} -> {owner_group}")
        except Exception as e:
            print(f"⚠️ 恢复权限失败（可忽略）: {e}")
        finally:
            super().closeConnection()

    def fault_injector(self):
        """制造异常：修改目录权限并触发启动失败"""
        print(f"制造故障: 修改 {self.target_dir} 权限")

        # 1. 检查目录是否存在
        if not self.ssh_file_exists(self.target_dir):
            raise Exception(f"目标目录不存在: {self.target_dir}")

        # 2. 检查用户是否存在
        result = self.ssh_exec(f'id "{self.target_user}"', check=False)
        if result.returncode != 0:
            raise Exception(f"用户 {self.target_user} 不存在，请先创建")

        # 3. 记录原始 owner:group
        result = self.ssh_exec(f'stat -c "%U:%G" "{self.target_dir}"', check=True)
        self.original_owner_group = (result.stdout or "").strip() or "root:root"
        print(f"原始所有者: {self.original_owner_group}")

        # 4. 修改目录所有者（故障注入）
        self.ssh_exec(
            f'sudo chown -R {self.target_user}:{self.target_user} "{self.target_dir}"',
            check=True
        )
        print(f"✅ 故障注入成功: {self.target_dir} -> {self.target_user}:{self.target_user}")

        # 5. 先停再启；预期启动失败
        stop_script = """
try {
    rpc(getControllerAlias(), stopDataNode{getNodeAlias()})
} catch(ex) {
    // ignore
}
"""
        self.runScript(stop_script)
        time.sleep(1)

        start_script = """
dnode = getNodeAlias()
try {
    rpc(getControllerAlias(), startDataNode{dnode})
    return "START_OK"
} catch(ex) {
    return "START_FAIL:" + string(ex)
}
"""
        start_result = str(self.runScript(start_script))
        print(f"start result: {start_result}")

        if "START_OK" in start_result:
            raise Exception("故障注入后节点仍可正常启动，未形成有效'启动失败'场景")

        return True

    def health_checker(self):
        """检查 Agent 是否修复完成"""
        print("[health] 开始健康检查")

        # 1) 检查目录 owner 是否已不再是 target_user
        result = self.ssh_exec(f'stat -c "%U" "{self.target_dir}"', check=True)
        current_owner = (result.stdout or "").strip()
        if current_owner == self.target_user:
            raise Exception(f"目录所有者仍为 {self.target_user}，Agent 未修复权限问题")

        # 2) 检查连接与查询
        try:
            self._ensure_session_connected()
            r = self.session.run("1+1")
            if r != 2:
                raise Exception(f"查询异常: 1+1={r}")
        except Exception:
            self.session = self._create_session()
            self._connect_session(raise_on_failure=True)
            r = self.session.run("1+1")
            if r != 2:
                raise Exception(f"重连后查询仍异常: 1+1={r}")

        # 3) 检查节点状态
        state_script = """
dnode = getNodeAlias()
st = exec state from rpc(getControllerAlias(), getClusterPerf) where site = dnode
if (size(st) == 0) {
    return -999
}
return st[0]
"""
        st = int(self.runScript(state_script))
        if st != 0:
            raise Exception(f"节点状态异常，state={st}")

        print("✅ 健康检查通过")
        return True