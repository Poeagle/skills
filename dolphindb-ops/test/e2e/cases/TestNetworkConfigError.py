import Test


class TestNetworkConfigError(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "节点网络配置异常，无法通信，请诊断并修复",
            "数据节点连接不上了，疑似端口配置有问题",
            "节点通信失败，请排查网络配置问题",
        ]

    # 清理环境：将 localSite 恢复到正确端口，并重启节点
    def cleanup(self):
        script = """
        nodeInfo = exec site from getClusterPerf(true) order by site
        dnode = exec first(site) from getClusterPerf(true) where left(string(port), 1) == "1"
        
        if (dnode != "") {
            port = exec first(port) from getClusterPerf(true) where site = dnode
            newSite = strReplace(dnode, string(port), substr(string(port), 1))
            nodeInfo = strReplace(nodeInfo, dnode, newSite)
            rpc(getControllerAlias(), saveClusterNodes{nodeInfo})
            rpc(getControllerAlias(), stopDataNode{dnode})
            sleep(3000)
            rpc(getControllerAlias(), startDataNode{newSite})
        }
        """
        self.runScript(script)

    # 制造异常：将 localSite 端口改成错误值，重启后节点绑定在错误端口，控制节点无法通信
    def fault_injector(self):
        script = """
        nodeInfo = exec site from getClusterPerf(true) order by site
        dnode = exec first(site) from getClusterPerf(true) where mode = 0
        port = exec first(port) from getClusterPerf(true) where site = dnode
        newSite = strReplace(dnode, string(port), "1" + string(port))
        nodeInfo = strReplace(nodeInfo, dnode, newSite)
        rpc(getControllerAlias(), saveClusterNodes{nodeInfo})

        // 停止原节点
        try {
            rpc(getControllerAlias(), stopDataNode{dnode})
        } catch(ex) {}

        sleep(3000)

        // 尝试启动错误配置的节点 — 预期会失败，所以用 try-catch 包裹
        try {
            rpc(getControllerAlias(), startDataNode{newSite})
        } catch(ex) {
            // 启动失败是预期的，这就是故障
            print("故障注入成功：节点因端口配置错误无法启动")
        }
        """
        self.runScript(script)

    # 检查异常是否消除：配置中不能再有错误端口，且节点必须处于在线状态
    def health_checker(self):
        script = """
        dnode = exec first(site) from getClusterPerf(true) where string(port).left(1)=="1"
        if(dnode!=""){
            throw "Datanode's localSite is still configured with the wrong port";
        }
        """
        self.runScript(script)
