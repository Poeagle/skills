import Test


class TestPermissionDenied(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "用户权限被拒绝了，无法访问数据，请诊断并处理",
            "查询报权限不足错误，帮忙看看怎么回事",
            "权限异常导致操作失败，请排查处理",
        ]

    # 清理环境：删除测试库和测试用户
    def cleanup(self):
        script = """
        if(existsDatabase("dfs://TPD_db")){
            dropDatabase("dfs://TPD_db");
        }
        if("TPD_user" in getUserList()){
            deleteUser("TPD_user");
        }
        """
        self.runScript(script)

    # 制造异常：建库建表，创建用户，显式拒绝其读权限
    def fault_injector(self):
        script = """
        db = database("dfs://TPD_db", VALUE, `A`B`C);
        t = table(1:0, ["sym","val"], [SYMBOL, DOUBLE]);
        db.createPartitionedTable(t, "TPD_pt", "sym");
        createUser("TPD_user", "P@ssw0rd123");
        deny("TPD_user", TABLE_READ, "dfs://TPD_db/TPD_pt");
        """
        self.runScript(script)

    # 检查异常是否消除：用户必须对 TPD_pt 有 TABLE_READ 且无显式 deny
    def health_checker(self):
        script = """
        access = getUserAccess("TPD_user");
        deniedCount = exec count(*) from access
                      where TABLE_READ_denied like "dfs://TPD_db/TPD_pt%"
        if(deniedCount > 0){
            throw "TPD_user is still explicitly denied TABLE_READ on TPD_pt";
        }
        """
        self.runScript(script)
