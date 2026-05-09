import Test


class TestConfigChangeFailure(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "修改配置后节点异常了，请诊断并恢复",
            "配置变更导致服务出问题了，帮忙看看",
            "节点配置修改后无法正常工作，请排查处理",
        ]

    def cleanup(self):
        # 清理配置异常相关环境变量，恢复默认配置
        script = """
        dnode = exec first(site) from getClusterPerf(true) where mode = 0
        ip = exec first(host) from getClusterPerf(true) where site = dnode
        port = exec first(port) from getClusterPerf(true) where site = dnode
        name = exec first(name) from getClusterPerf(true) where site = dnode

        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        configsStr = string(configs)
        pattern = string(name) + ".volumes%"
        configsStr = configsStr[not configsStr like pattern]
        rpc(getControllerAlias(), saveClusterNodesConfigs{configsStr})

        controllerAlias = getControllerAlias()
        rpc(controllerAlias, stopDataNode{[ip + ":" + string(port)]})
        rpc(controllerAlias, startDataNode{[ip + ":" + string(port)]})
        """
        self.runScript(script)

    def fault_injector(self):
        # 制造配置修改异常，引起服务失败
        script = """
        dnode = exec first(site) from getClusterPerf(true) where mode = 0
        ip = exec first(host) from getClusterPerf(true) where site = dnode
        port = exec first(port) from getClusterPerf(true) where site = dnode
        name = exec first(name) from getClusterPerf(true) where site = dnode
        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        path = getHomeDir().strReplace(name, "")
        
        // 修复：转换为字符串向量再追加
        configsStr = string(configs)
        configsStr.append!(name + ".volumes=" + path + "volume/<ALIAS>")
        rpc(getControllerAlias(), saveClusterNodesConfigs{configsStr})
        
        // 修复：通过 RPC 调用 Controller 启停节点
        controllerAlias = getControllerAlias()
        rpc(controllerAlias, stopDataNode{[ip + ":" + string(port)]})
        rpc(controllerAlias, startDataNode{[ip + ":" + string(port)]})
        """
        self.runScript(script)

    def health_checker(self):
        # 检查配置异常是否已被清理
        script = """
        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        configsStr = string(configs)
        if (true in (configsStr like "%.volumes%<ALIAS>%")){
            throw "The config is still wrong."
        }
        """
        self.runScript(script)