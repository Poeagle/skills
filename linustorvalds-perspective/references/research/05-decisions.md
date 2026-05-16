# Linus Torvalds 重大决策与行动记录

> 本文档系统梳理 Linus Torvalds 职业生涯中的关键决策节点，聚焦决策背后的思考逻辑、动机演变和事后反思。

---

## 一、创建 Linux（1991）：从"爱好"到改变世界的操作系统

### 1.1 决策背景

1991 年，21 岁的 Linus Torvalds 是赫尔辛基大学计算机科学系的学生。他刚购买了一台搭载 Intel 80386 处理器的 IBM PC 兼容机，希望充分利用这台新机器的硬件能力。当时他手头只有 MINIX——一个由 Andrew Tanenbaum 教授为教学目的开发的类 Unix 微型操作系统。MINIX 的许可证禁止大规模修改和再分发，且在设计上刻意简化以适合教学。

促使他动手的关键因素：
- **自由内核的缺失**：当时没有一个被广泛采用的自由（free）操作系统内核。他后来坦言，如果 GNU Hurd 或 386BSD 在当时已经可用，"他很可能不会自己写一个内核"。
- **硬件驱动的创造欲**：他想充分探索 80386 架构的特性，而现有操作系统限制了他。
- **学习动机**：他在阅读 Tanenbaum 的《操作系统：设计与实现》后，对操作系统设计产生了浓厚兴趣。

### 1.2 决策过程

- **1991 年 7 月 3 日**：他在 comp.os.minix 新闻组尝试获取 POSIX 标准文档的电子版未果，转而通过赫尔辛基大学的 SunOS 文档推断系统调用行为。
- **1991 年 8 月 25 日**：他在 comp.os.minix 发布著名的公告："I'm doing a (free) operating system (just a hobby, won't be big and professional like gnu) for 386(486) AT clones." 此时他已成功移植了 bash 1.08 和 gcc 1.40。
- **原始内核命名**：他想命名为 Freax（free + freak + X），但朋友 Ari Lemmke 在管理 FTP 服务器时将目录命名为 linux。Torvalds 最初觉得这过于自我中心，但最终还是接受了这个命名。

### 1.3 关键细节与反思

- Linux 0.01 仅约 10,000 行代码；到 4.15 版本已增长至超过 2,330 万行（2018 年）。
- Torvalds 后来多次强调，Linux 的成功在相当程度上是"运气大于智慧"——时机恰到好处，自由软件运动正在兴起，GNU 生态提供了完整工具链（bash、gcc、glibc），而 386 处理器使普通个人能拥有强大的开发机器。
- **矛盾之处**：他声称这只是一个"爱好"，但从早期投入的程度（几天内即得到大量反馈和贡献）来看，这并非漫不经心的爱好，而是高度专注的狂热钻研。

**来源**：
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds
- Wikipedia — History of Linux: https://en.wikipedia.org/wiki/History_of_Linux

---

## 二、选择 GPL v2 许可证（1992）：从封闭到开放的转折点

### 2.1 决策背景

Linux 内核最初采用 Linus 自己编写的许可协议，其中包含一条**禁止商业分发**的条款：
> "You may not distribute this for a fee, not even 'handling' costs."

这意味着早期 Linux 本质上是一个"买者自负"的共享软件式许可，禁止任何商业用途。然而随着贡献者增多，这种限制性协议成为项目发展的阻碍。

### 2.2 决策过程

- **1991 年秋**：另一位讲瑞典语的计算机学生 Lars Wirzenius 带他去赫尔辛基理工大学，听 Richard Stallman 关于自由软件的演讲。这场演讲深刻影响了他的思维方式。
- **来自社区的压力**：多位贡献者要求将许可改为 GNU GPL，使其与 GNU copyleft 兼容。
- **1992 年 2 月 1 日**：GPL 正式生效，Linux 0.12 版本发布说明中首次宣布这一转变。
- **1992 年 3 月 7 日**：Linux 0.95 版本已完全采用 GNU GPL。

### 2.3 事后反思

Torvalds 在多个场合明确表示：
> "Making Linux GPLed was definitely the best thing I ever did."

他认为这一决策直接决定了 Linux 的生态命运——如果保持封闭许可，Linux 很可能像 MINIX 一样仅作为教学工具存在，而不会成为全球协作工程。

### 2.4 关于"GPLv2 而非 GPLv3"的后续决策

- **2000 年左右**：Torvalds 明确表示 Linux 内核**仅使用 GPLv2**，不包含常见的"或更高版本"条款。
- **2007 年 GPLv3 发布**后：Torvalds 和大多数内核开发者决定**不采用新版本**。
- **核心理由**：他认为 GPLv2 更符合内核项目"技术优先"的理念，而 GPLv3 是 FSF 推动的"自由信仰"路线，引入了诸如 anti-TiVoization 等政治化条款。这不是技术中立的选择。
- **矛盾提示**：Torvalds 一面高度推崇开放协作，一面拒绝 FSF 的"自由软件道德观"，展现出他独特的实用主义自由观——工具理性高于意识形态纯粹性。

**来源**：
- Wikipedia — History of Linux: https://en.wikipedia.org/wiki/History_of_Linux
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds

---

## 三、创建 Git（2005）：BitKeeper 事件驱动的自救行动

### 3.1 决策背景

2002 年起，Linux 内核开发团队使用 BitKeeper——Larry McVoy 开发的专有版本控制系统。BitKeeper 在免费许可下提供给开源项目使用，其分布式模型恰好满足内核开发的需求。

**BitKeeper 事件**：
- 2005 年 4 月，BitKeeper 的版权持有者 Larry McVoy 指控 Andrew Tridgell（Samba 项目的创始人）反向工程了 BitKeeper 的协议，开发了 SourcePuller 工具。
- McVoy 因此撤销了 Linux 内核项目的 BitKeeper 免费许可。
- 值得注意的是，Tridgell 和 Torvalds 私交甚好，Torvalds 后来表示对 Larry McVoy 的处理方式感到失望。

### 3.2 评估现有方案

Torvalds 考察了当时可用的所有自由版本控制系统，结论是"没有一个自由系统能满足他的需求"：
- **CVS**：被他视为"反面教材"，集中式架构、分支成本高、不支持离线工作。
- **Subversion**：当时刚起步，仍基于集中式模型。
- **Monotone**：分布式但性能太差——应用一个 patch 需要 30 秒，而内核维护者一次同步可能需要 250 个这样的操作。这完全不可接受。

### 3.3 决策与设计

- **2005 年 4 月 3 日**：在 Linux 2.6.12-rc2 发布后，现有系统都不满足需求，Torvalds 决定自己写一个。
- **仅 3 天后**（4 月 6 日）：他宣布了项目的存在。速度之快令人咋舌。
- **设计原则**：
  1. **反 CVS 哲学**：当不确定设计选择时，"做相反的决定"。
  2. **BitKeeper 式分布式工作流**：支持去中心化协作。
  3. **强完整性保护**：内置加密验证机制，防止意外或恶意损坏。
- **性能目标**：patching 耗时不超过 3 秒（而 Monotone 需要 30 秒）。
- **工具箱范式**：Git 最初由一系列 C 程序和 shell 脚本包装器组成，刻意设计为可组合的小工具。

### 3.4 设计中的独创性

- **分支仅是引用**：在 Git 中，分支只是一个指向 commit 的指针，分支操作因而极其轻量。
- **内容寻址文件系统**：Torvalds 从文件系统专家的视角设计 Git——它本质上是一个"内容可寻址的文件系统，加上版本控制的概念"。
- **快照而非增量**：不同于 SCCS 或 RCS 追踪单个文件的修订历史，Git 对整个目录树做快照。Torvalds 明确拒绝"逐文件追踪变更"的概念。

### 3.5 移交维护权

2005 年 7 月 26 日（即项目启动约 3.5 个月后），Torvalds 将维护权移交给 Junio Hamano——他已成为 Git 的主要贡献者。Hamano 在 2005 年 12 月 21 日引领了 1.0 发布。

### 3.6 事后反思

- 这可能是 Torvalds 最具代表性的决策模式：**遇到瓶颈 → 评估现有方案 → 发现都不行 → 自己动手造轮子**。同样的模式也出现在 Linux 的创建上。
- 他后来提到 Git 的名字时有句著名调侃："I'm an egotistical bastard, and I name all my projects after myself. First 'Linux', now 'git'."
- Git 的 README 中提供了两个后向缩写的解释：顺利时是 "Global Information Tracker"，出错时是 "Goddamn Idiotic Truckload of Sh*t"。

**来源**：
- Wikipedia — Git: https://en.wikipedia.org/wiki/Git
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds

---

## 四、对 Linux 内核二进制模块的立场：技术手段围堵，而非法律禁止

### 4.1 核心立场

Torvalds 对闭源二进制内核模块（专有驱动程序）的态度有一个独特的特征：他**不使用法律或政策性的禁令**，而是通过技术架构设计来驱赶它们。

### 4.2 技术手段

- **无稳定的设备驱动 ABI**：内核特意不提供稳定的二进制内核接口（ABI），这意味着所有外部树模块（包括专有模块）在每次内核版本更新时都必须重新编译。
- **EXPORT_SYMBOL_GPL() 机制**：内核 API 使用此宏将某些符号"保留给 GPL 兼容许可证下发布的模块"。专有模块不能访问这些符号而不违反许可证。
- **结论**：设计选择——而非文字禁令——使闭源驱动的维护成本极高，从而在实践上限制其存在。

### 4.3 公开表态

- **2012 年 6 月（NVIDIA 事件）**：在阿尔托大学演讲时，Torvalds 当众对 NVIDIA 竖起中指并爆粗口："Nvidia has been the worst company we've ever dealt with." 这是因为 NVIDIA 持续发布闭源的 Linux 驱动，且拒绝协作。这成为他公开反对闭源模块的标志性时刻。
- **2015 年 3 月（VMware 诉讼）**：当 Christoph Hellwig 起诉 VMware 在专有产品中侵犯内核代码版权时，Torvalds 公开与诉讼保持距离，称"律师是溃烂的疾病（festering disease）"。这揭示了他立场的微妙之处：他原则性反对专有驱动，但对法律强制手段同样持敌对态度。

### 4.4 决策逻辑

这段历史体现了一个关键模式：**Torvalds 倾向于用技术手段解决治理问题，而非法律手段**。他希望社区驱动的技术优势（而不是诉讼）来证明开放优于封闭。

### 4.5 言行一致性问题

- **完全一致**：他本人始终使用 GPL 许可证发布代码，从未参与专有内核模块开发。
- **略显不一致**：虽然他厌恶闭源模块，但他并未在内核中完全禁止它们加载。`modprobe` 和 `insmod` 仍然允许加载非 GPL 模块（只是不能调用 GPL-only 符号）。这种"半开放"反映了实用主义与技术自由主义之间的平衡。

**来源**：
- Wikipedia — Linux kernel (Binary modules): https://en.wikipedia.org/wiki/Linux_kernel
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds

---

## 五、对 systemd 的态度：对开发方式不满，但对架构之争中立

### 5.1 基本立场

Torvalds 对 systemd 的态度经常被误解。事实是：他**没有公开反对 systemd 的架构设计**，而是对 systemd 核心开发者处理社区反馈的方式表示不满。

### 5.2 具体事件

- **2014 年 4 月**：Torvalds 对 Kay Sievers（systemd 核心开发者）提交的内核变更以及与用户的交互方式提出了意见。这不是对 systemd 本身的技术批判，而是对开发团队态度的批评。
- **关于功能膨胀（Feature Creep）**：据 ZDNet 报道，Torvalds 和其他批评者指出 systemd"遭受功能膨胀之苦"并创造了"更大的攻击面"。但需要注意的是，这些批评在报道中更多归类为"systemd 批评者的观点"，Torvalds 是否完全认同这些表述存在争议。

### 5.3 决策逻辑

Torvalds 对 systemd 的沉默（或克制）可能源于他的核心原则：**内核之上运行什么 init 系统不属于内核维护者的管辖权**。只要 systemd 不破坏内核的稳定性和用户空间接口，他就没有立场干涉。

**来源**：
- Wikipedia — Systemd (Controversies): https://en.wikipedia.org/wiki/Systemd#Controversies
- ZDNet — Linus Torvalds and others on Linux's systemd（引用不可直接访问）

---

## 六、2018 年休假：从"不友善"到"学习理解他人"的反思

### 6.1 事件背景

2018 年是 Torvalds 个人风格的转折点。

- **长期积累的问题**：多年来，Torvalds 以尖刻的沟通风格著称。他曾在邮件列表中称其他开发者"idiot"、"moron"、"brain-damaged"，这种行为虽然有助于高效过滤掉他认为质量低的代码，但也造成了严重的人际紧张。
- **《纽约客》的调查**：当时《纽约客》杂志正在撰写一篇关于他的报道，其中提出了大量关于他行为方式的问题。据推测，这篇报道（但尚未发表时）的影响力促成了他最终的道歉。
- **行为准则的突然替换**：2018 年 9 月 16 日，Linux 内核的《冲突准则》被替换为由 Contributor Covenant 修改而来的《行为准则》（Code of Conduct）。

### 6.2 道歉与休假

同日，Torvalds 在 Linux 4.19-rc4 的发布说明中发布了著名的道歉：

- 他承认个人攻击 "unprofessional and uncalled for"。
- 他宣布休假一段时间，目的是 "to get some assistance on how to understand people's emotions and respond appropriately"（获得一些帮助，以学习如何理解他人情绪并做出适当回应）。
- 他表示自己多年来一直试图变得友善但失败了，现在需要真正的帮助。

### 6.3 回归与变化

- **2018 年 10 月 22 日**：Linux 4.19 发布后，Torvalds 回归内核维护工作。
- 回归后，他的沟通风格发生了实质性的软化。虽然他仍然会在技术问题上直言不讳，但**不再针对个人进行攻击**。
- 在 2019 年的一次访谈中，他承认自己"确实需要改变"，并且"改变是可能的"。

### 6.4 事后反思与本质矛盾

这次事件揭示了 Torvalds 决策模型中一个长期存在的张力：

- 他的尖刻风格被认为对维护代码质量是"必要的恶"——这是他早年最常使用的辩护理由。
- 但在 2018 年，他意识到这种风格已经**反噬了项目本身**——社区中的有才华的贡献者因惧怕他的反应而不敢提交代码。
- 这是一个"事后反思"的典型案例：他**公开承认过去的方式是错误的**，并主动寻求改变路径。

### 6.5 言行一致性分析

- **完全一致**：休假后的邮件列表记录证实了他确实做出了实质性的风格改变。
- **不完全一致**：他此前多次说过"我就是这样的人，改不了"，并认为这是个性使然。2018 年的转变说明这句话只是借口而非事实。

**来源**：
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds

---

## 七、移居美国的决策：职业路径的实用主义选择

### 7.1 决策时间线

移居美国不是一个一次性决策，而是一个渐进的过程：

- **1996 年底**：Torvalds 访问了 Transmeta 公司（一家专注于低功耗 x86 兼容 CPU 的初创公司）。
- **1997 年 2 月 — 2003 年 6 月**：他搬到加利福尼亚州，在 Transmeta 全职工作。他在 Transmeta 的工作是保密的，后来披露他参与了 Crusoe 处理器的开发。他选择 Transmeta 的原因包括：对 CPU 架构的兴趣以及该公司允许他继续维护 Linux 内核。
- **2003 年**：离开 Transmeta 后，他加入 Open Source Development Labs（OSDL），这是一个非营利组织，旨在推动 Linux 的企业级应用。
- **2004 年 6 月**：他与家人搬到俄勒冈州 Dunthorpe，靠近 OSDL 在 Beaverton 的总部。
- **2010 年**：他成为美国公民并登记投票，公开表示自己不属于任何美国政党，"quite frankly"认为自己的自尊心不允许与其中任何一个相关联。

### 7.2 决策逻辑

- 移居美国主要是**职业务实主义**的体现——Linux 逐渐成为主流技术，而美国是技术产业的核心地带。
- Transmeta 提供了稳定的收入，同时允许他继续维护内核——这是他选择雇主的核心条件。
- OSDL（后来与 Free Standards Group 合并为 Linux Foundation）的成立，使 Linux 获得了企业级的组织支撑。

**来源**：
- Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds

---

## 八、对 Rust 进入 Linux 内核的支持：谨慎乐观，遗憾"太慢"

### 8.1 决策立场

Torvalds 对 Rust 进入内核的态度可以用"谨慎乐观"来概括——他支持这个方向，但对进展速度感到不满。

### 8.2 关键事件

- **2022 年开源峰会**：Torvalds 表示 Rust 集成可能在 Linux 5.20（后更名为 6.0）中开始。
- **Linux 6.0-rc1 发布说明**：他表达失望："I actually was hoping that we'd get some of the first rust infrastructure... but neither of them happened this time around."
- **2022 年 9 月**：他在邮件中表示："Unless something odd happens, it [Rust] will make it into 6.1."
- **2022 年 10 月**：尽管此前多次延迟，托瓦尔兹最终**批准了 Rust for Linux 的 pull request**，使其落地至 Linux 6.1。然而 6.1 中的 Rust 支持被"刻意保持最小化"，以方便测试。
- **2025 年 12 月**：Rust 开发成为内核开发的"正式组成部分"——不再标记为实验性质。

### 8.3 决策逻辑

Torvalds 支持 Rust 进入内核的原因包括：
- **内存安全**：内核中约 2/3 的 CVE 源于内存安全问题，Rust 能在编译期杜绝此类漏洞。
- **不排挤 C**：他强调 Rust 不会替代 C——"C is still the lingua franca of the kernel"——Rust 仅用于合适的地方。

### 8.4 言行一致性

这是一个 Torvalds 将"实用主义"压过"对 C 的个人偏好"的典型案例。他本人是 C 语言的忠实倡导者（他对 C++ 的批评是公开而高频的），但对 Rust 的支持表明他愿意为了内核安全性和长期健康，接受一种新的、他认为"不是最优"的工具。

**来源**：
- Wikipedia — Rust for Linux: https://en.wikipedia.org/wiki/Rust_for_Linux

---

## 九、对 AI/ML 的态度：90% 营销，10% 现实

### 9.1 核心立场

Torvalds 对当前 AI/ML 热潮持有**高度怀疑**的态度，但并非全盘否定技术本身。

### 9.2 标志性言论

**2024 年 Linux 基金会活动**上的核心表述：
> "AI is 90% marketing and 10% reality."

他对此的解释：
- AI 领域的炒作远远超过了实际的技术进展。
- 他承认 AI/ML 在某些领域有用，但不认为它会接管世界。
- 在他看来，当前 AI 热潮与历史上的"加密货币狂热"相似——大量资金追逐一个概念，最终大多数参与者将损失惨重。
- 但他也明确表示，AI 作为工具（尤其是代码自动补全、模式识别等）有价值，问题在于**营销和现实之间的巨大落差**。

### 9.3 决策逻辑

Torvalds 的 AI 立场与他的一贯思维一致：
- **实用主义至上**：他只关注技术实际解决的问题，不接受宏大叙事。
- **历史类比思维**：他将 AI 热潮比作加密货币泡沫，表明他倾向于用历史经验审视新技术的生命周期。
- **反炒作本能**：作为经历了多次"技术革命"的资深工程师，他对于过度宣传有天然的免疫力。

### 9.4 言行一致性

他表达对 AI 炒作的厌恶，但同时 Linux 内核社区本身也在探索使用 AI 辅助代码审查和漏洞检测（如 Coccinelle、sparse 等工具），这种"怀疑但不拒绝"的态度与他对二进制模块的立场高度一致——不禁止，但保持清醒。

**来源**：
- Tom's Hardware — Linus Torvalds on AI: "It's 90% marketing and 10% reality": https://www.tomshardware.com/tech-industry/artificial-intelligence/linus-torvalds-on-ai-its-90-marketing-and-10-reality

---

## 十、重要补充决策：其他关键节点

### 10.1 拒绝苹果的工作邀约（2000 年）

Steve Jobs 曾提议 Torvalds 加入苹果公司，转而开发 macOS 内核，条件是他必须**停止 Linux 内核工作**。Torvalds 拒绝了该提议，理由是 Mach 微内核架构与 Linux 的单内核设计差异太大，且他不愿意放弃 Linux。

**决策逻辑**：
- 技术信念优先于经济利益。即使苹果当时是世界上最炙手可热的科技公司之一，他也不愿意为一个他认为架构上"不优"的系统工作。
- 对 Linux 社区的承诺是决定性的——他不愿抛弃自己创建的社区。

### 10.2 对 C++ 的公开鄙视

Torvalds 多次公开批评 C++，在 2007 年的一封邮件中他写道：
> "C++ is a horrible language. It's made more horrible by the fact that a lot of substandard programmers use it, to the point where it's much much easier to generate total and utter crap with it."

这是 Torvalds 决策中**审美判断直接影响技术取舍**的典型表现：他不仅因为技术原因拒绝 C++ 进入内核，还因为他对使用该语言的社区文化的排斥。

### 10.3 2024 年俄罗斯开发者争议

当一些俄罗斯开发者因合规要求被从内核维护者名单中移除时，Torvalds 的回应既直接又充满个人色彩：
> "I'm Finnish. Did you think I'd be supporting Russian aggression?"

同时他声称移除行动是出于政府合规要求和法律问题。这显示了他的**国家身份和政治立场**有时会渗入他声称"纯技术"的决策中——这与其"技术优先"的自我定义形成张力。

### 10.4 宗教信仰立场："完全无宗教—无神论者"

Torvalds 公开自认为 atheist，称宗教"反而削弱了对自然和道德的真正欣赏"。他虽然不推动自己的价值观进入内核开发，但这一立场影响了他对涉及宗教因素的社区争议的仲裁方式。

---

## 十一、矛盾与冲突总结

### 11.1 言行一致案例

| 案例 | 一致性 | 说明 |
|------|--------|------|
| GPL v2 选择 | 完全一致 | 始终使用 GPL v2，拒绝 v3 |
| 反闭源模块 | 基本一致 | 技术围堵，自己也从不发布闭源代码 |
| 2018 改进沟通 | 一致 | 休假后确实改变了风格 |
| 反法律手段 | 一致 | 对 VMware 诉讼保持距离 |
| 拒绝苹果 | 一致 | 放弃经济利益，坚持技术信念 |

### 11.2 言行不完全一致的案例

| 案例 | 不一致之处 | 说明 |
|------|------------|------|
| "爱好" vs 投入深度 | 声称 Linux 是"爱好" | 但 0.01 的发布时机和社区响应速度不符合"业余爱好"的定义 |
| "改不了" vs 2018 改变 | 前称无法改变沟通风格 | 2018 年证明了改变是可能的 |
| "纯技术决策" vs 政治表态 | 声称核心理工性 | 2024 年俄罗斯开发者事件中个人政治表达凸显 |
| 反二进制模块 vs 不完全禁止 | 反对闭源但不禁止加载 | "半开放"姿态反映实用主义而非纯粹主义 |
| 反 C++ vs 支持 Rust | 以审美/技术原因拒绝 C++ | 但对 Rust 的接纳标准更宽松（注重安全性 > 语法偏好） |

### 11.3 事后反思案例

1. **GPL 化**："the best thing I ever did"——明确的正面事后确认。
2. **2018 休假**：公开承认之前的沟通方式"unprofessional and uncalled for"——明确的事后否定。
3. **Rust 引入的延迟**：在发布说明中公开表示"希望更快"——对决策节奏有遗憾。
4. **GNOME 3 的批评**：他在 2011 年公开批评 GNOME 3 的设计方向，但后来承认他对桌面环境的抱怨更多是个人偏好而非真正的维护问题，调整了参与度。

---

## 十二、决策模式总结

### 12.1 核心决策框架

```
遇到瓶颈（技术、许可、工具）
    ↓
评估现有解决方案
    ↓
是否有满意项？──是──→ 采用
    ↓ 否
现有方案都不可接受
    ↓
自己动手造轮子
    ↓
用技术架构（而非政策）解决问题
```

### 12.2 驱动因素优先级

1. **技术实用主义** > 意识形态：GPLv2 而非 v3、支持 Rust 而非拒绝一切新语言。
2. **社区健康** > 个人偏好：2018 改变风格以保护社区参与。
3. **长期生态** > 短期利益：拒绝苹果、坚持开放许可。
4. **维护效率** > 政治正确：严格的代码审查和尖锐反馈（虽然后者已调整）。

### 12.3 不变的底色

- **高度自信**：对自己判断的信念从不动摇。
- **反权威本能**：无论是 FSF、苹果还是 AI 热潮，他对任何"高大上"的叙事天然警惕。
- **动手第一**：谈论不如编码，批评不如做出更好的替代方案。

---

## 来源汇总

1. Wikipedia — Linus Torvalds: https://en.wikipedia.org/wiki/Linus_Torvalds
2. Wikipedia — History of Linux: https://en.wikipedia.org/wiki/History_of_Linux
3. Wikipedia — Git: https://en.wikipedia.org/wiki/Git
4. Wikipedia — Systemd (Controversies): https://en.wikipedia.org/wiki/Systemd#Controversies
5. Wikipedia — Rust for Linux: https://en.wikipedia.org/wiki/Rust_for_Linux
6. Wikipedia — Linux kernel (binary modules): https://en.wikipedia.org/wiki/Linux_kernel
7. Tom's Hardware — Linus Torvalds on AI: https://www.tomshardware.com/tech-industry/artificial-intelligence/linus-torvalds-on-ai-its-90-marketing-and-10-reality
8. ZDNet — Linus Torvalds and others on Linux's systemd（引用于 Wikipedia systemd 页面）
9. Wikipedia — Contributor Covenant adoption in Linux kernel（2018 CoC 事件）
