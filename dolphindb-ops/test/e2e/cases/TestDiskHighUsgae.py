import Test
import os
LOG_DIR = "/hdd/hdd8/ymchen/ddb-test/dolphindb/server/clusterDemo/log"
FAKE_LOG = LOG_DIR + "/20260314020112_controller.log"


class TestDiskHighUsgae(Test.Test):
    def __init__(self):
        super().__init__()
        self.questions = [
            "磁盘空间快满了，请诊断并处理",
            "磁盘使用率很高，帮忙看看怎么回事",
            "磁盘空间不足告警，请排查处理",
        ]

    def cleanup(self):
        self.ssh_exec(f'rm -f "{FAKE_LOG}"')

    def fault_injector(self):
        self.ssh_exec(
            f'dd if=/dev/zero of="{FAKE_LOG}" bs=2GB count=11', check=True)
        # 追加换行符，避免 tail 因全零文件无换行而卡死
        self.ssh_exec(f'printf "\\n%.0s" {{1..10}} >> "{FAKE_LOG}"')
        self.ssh_exec(f'chmod 777 "{FAKE_LOG}"')

    def health_checker(self):
        if self.ssh_file_exists(FAKE_LOG):
            raise ValueError(
                "TestDiskHighUsgae failed, log file still exists.")


if __name__ == "__main__":
    t = TestDiskHighUsgae()
    t.cleanup()
    t.fault_injector()
    t.cleanup()
    t.health_checker()
