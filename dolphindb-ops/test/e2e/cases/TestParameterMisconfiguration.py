import Test


class TestParameterMisconfiguration(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "参数配置不合理，节点异常，请诊断并修复",
            "节点参数被改成了不合理的值，帮忙看看",
            "配置参数异常导致节点问题，请排查处理",
        ]

    def cleanup(self):
        # 恢复合理参数配置，清理异常
        script = """
        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        configsStr = string(configs)
        configsStr = configsStr[not configsStr like "TSDBCacheEngineSize%"]
        configsStr.append!("TSDBCacheEngineSize=6")
        rpc(getControllerAlias(), saveClusterNodesConfigs{configsStr})

        dnode = exec first(site) from getClusterPerf(true) where mode = 0
        ip = exec first(host) from getClusterPerf(true) where site = dnode
        port = exec first(port) from getClusterPerf(true) where site = dnode

        controllerAlias = getControllerAlias()
        rpc(controllerAlias, stopDataNode{[ip + ":" + string(port)]})
        rpc(controllerAlias, startDataNode{[ip + ":" + string(port)]})
        """
        self.runScript(script)

    def fault_injector(self):
        # 制造阈值和资源参数不合理异常
        script = """
        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        configsStr = string(configs)
        configsStr = configsStr[not configsStr like "TSDBCacheEngineSize%"]
        configsStr.append!("TSDBCacheEngineSize=60")
        rpc(getControllerAlias(), saveClusterNodesConfigs{configsStr})
        
        dnode = exec first(site) from getClusterPerf(true) where mode = 0
        ip = exec first(host) from getClusterPerf(true) where site = dnode
        port = exec first(port) from getClusterPerf(true) where site = dnode
        
        controllerAlias = getControllerAlias()
        rpc(controllerAlias, stopDataNode{[ip + ":" + string(port)]})
        rpc(controllerAlias, startDataNode{[ip + ":" + string(port)]})
        """
        self.runScript(script)

    def health_checker(self):
        # 检查参数是否恢复正常（合理值）
        script = """
        configs = rpc(getControllerAlias(), loadClusterNodesConfigs)
        configsStr = string(configs)
        if (true in (configsStr like "TSDBCacheEngineSize=60%")){
            throw "The config is still wrong."
        }
        """
        self.runScript(script)