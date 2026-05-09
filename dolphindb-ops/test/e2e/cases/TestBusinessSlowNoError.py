import Test


class TestBusinessSlowNoError(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "业务处理很慢但没有报错日志，请诊断一下",
            "系统响应变慢了，但日志里没有错误信息",
            "业务延迟明显增大，帮忙排查什么原因",
        ]

    def cleanup(self):
        script = """
        // 取消订阅，避免重复运行时报错
        try{
            unsubscribeTable(tableName="TBSNE_src", actionName="TBSNE_sub");
        }catch(ex){}

        // 清理共享对象
        if(defined("TBSNE_src", SHARED)){
            undef("TBSNE_src", SHARED);
        }
        if(defined("TBSNE_sink", SHARED)){
            undef("TBSNE_sink", SHARED);
        }
        if(defined("TBSNE_flag", SHARED)){
            undef("TBSNE_flag", SHARED);
        }
        """
        self.runScript(script)

    def fault_injector(self):
        script = """
        // 创建测试状态标记
        flagTb = table(1:0, [`flag, `scene, `status], [INT, STRING, STRING]);
        insert into flagTb values (1, "BusinessSlowNoError", "injecting");
        share flagTb as TBSNE_flag;

        // 源流表：模拟业务请求入口
        src = streamTable(200000:0,
            `eventTime`reqId`userId`payload,
            [TIMESTAMP, STRING, STRING, STRING]);
        share src as TBSNE_src;

        // 结果表：模拟业务处理结果落地
        sink = table(200000:0,
            `eventTime`reqId`userId`payload`processedTime,
            [TIMESTAMP, STRING, STRING, STRING, TIMESTAMP]);
        share sink as TBSNE_sink;

        // 订阅处理函数：本身不报错，只是把数据写到结果表
        def TBSNE_handler(mutable out, msg){
            result = select *, now() as processedTime from msg;
            out.append!(result);
        }

        // 故意设置偏大的 batchSize 和较长的 throttle
        // 这样数据会在缓冲区里积压一段时间，业务表现变慢，但不一定有 ERROR 日志
        subscribeTable(
            tableName="TBSNE_src",
            actionName="TBSNE_sub",
            offset=-1,
            handler=TBSNE_handler{TBSNE_sink},
            msgAsTable=true,
            batchSize=50000,
            throttle=60
        );

        // 快速灌入一批业务数据，制造“请求到了但结果迟迟不出”的现象
        n = 10000;
        tb = table(
            now() + rand(1000, n) as eventTime,
            "req" + string(1..n) as reqId,
            take("userA", n) as userId,
            take("normal_business_payload", n) as payload
        );
        TBSNE_src.append!(tb);
        """
        self.runScript(script)

    def health_checker(self):
        # 这个场景偏分析型，不适合用“问题是否消失”来做强校验
        # 这里保留空实现，以兼容统一测试框架
        pass
