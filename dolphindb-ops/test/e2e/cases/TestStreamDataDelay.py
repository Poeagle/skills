import Test


class TestStreamDataDelay(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "流数据延迟严重，请诊断并处理",
            "流表数据接收明显滞后，帮忙看看什么原因",
            "实时数据延迟超过阈值，请排查处理",
        ]

    # 清理环境时要考虑每一个变量的异常情况
    def cleanup(self):
        script = """
        TSDDStreamName = "TSDDrealtimeData"
        if (existsStreamTable(TSDDStreamName)) {
            dropStreamTable(TSDDStreamName)
        }

        undef(all, VAR)
        undef(all, DEF)
        """
        self.runScript(script)

    # 制造异常情况
    def fault_injector(self):
        script = """
        share streamTable(10000:0, `timestamp`symbol`price`volume`receiveTime, [TIMESTAMP, SYMBOL, DOUBLE, LONG, TIMESTAMP]) as TSDDrealtimeData

        def TSDDdelayedAppend(t, delayMs) {
            sleep(delayMs)
            TSDDrealtimeData.append!(t)
        }

        def TSDDgenerateRealtimeData() {
            interval = 100 
            for(i in 0..100) {
                t = table(now() as timestamp, take(`AAPL, 1) as symbol, rand(100.0, 1) as price, rand(10000, 1) as volume)
                
                // 随机注入延迟：0-1000ms的网络延迟
                delay = rand(1000)
                submitJob("TSDDdelayedWrite", "TSDDdelayedWrite_" + string(i), TSDDdelayedAppend, t, delay)
                
                sleep(interval)
            }
        }

        setStreamTableTimestamp(TSDDrealtimeData, `receiveTime)

        submitJob("TSDDdataGenerator", "TSDDdataGenerator", TSDDgenerateRealtimeData)
        sleep(10000)
        """
        self.runScript(script)

    # 检查失败则抛出异常，不通过返回值判断
    def health_checker(self):
        script = """
        t_data = select *, receiveTime - timestamp as diffTime from TSDDrealtimeData where receiveTime - timestamp >= 1000

        if (t_data.size() > 0) {
             throw "Test Stream Data Delay Failed!"
        }       
        
        """
        self.runScript(script)
