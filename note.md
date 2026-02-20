# Geant4 Cherenkov 项目物理知识补强笔记（学习版·更详细）

面向目标：
- 你已经把 Geant4+PHSP+Cherenkov 输出 + 可选 Dose + kernel 构建写完
- 现在要把“物理概念 ↔ 代码实现 ↔ 数据现象”一一对上
- 最终能解释：为什么图长这样、为什么 kernel 深度分布这样、为什么 Cherenkov 和 dose 有/无相关

适用场景：
- 6MV 医用直线加速器光子束（TrueBeam PHSP）
- 水体（折射率 ~1.33，介质透明）
- 输出 Cherenkov 光子 PHSP + （可选）能量沉积 dose
- 构建 Cherenkov / dose voxel kernel

---

# 0. 你要建立的“物理-代码-数据”思维框架

任何一个模拟结果，你都要能回答三类问题：

A. 物理上为什么会发生？
   - 哪个过程导致的？阈值是什么？主要贡献来自谁？

B. 代码里是怎么实现/近似的？
   - 在 Geant4 的哪一个 PhysicsProcess / Step / Track 时刻触发？
   - 你记录的是“产生点”还是“传播后的到达点”？是不是会改变 interpretation？

C. 数据为什么长这样？
   - 能量谱为什么不是你直觉的范围？
   - 空间分布为什么出现边界截断？
   - Cherenkov–Dose 为什么深度上比例会变？

你现在缺的不是“再写功能”，而是把 A/B/C 串起来。

---

# 1. 6MV 直线加速器：从“6MV”到“你读到的 PHSP”

## 1.1 6MV 的定义：不是“6MeV 单能光子”

临床说的 “6MV photon beam” 本质是：

$$
\text{电子束（标称 } \sim 6\ \mathrm{MeV}\text{）}
\rightarrow \text{打钨靶}
\rightarrow \text{Bremsstrahlung}
\rightarrow \text{光子束}
$$

其中 **Bremsstrahlung（制动辐射）** 指：
- 高速电子在原子核电场中被偏转/减速时，将部分动能以光子形式辐射出来；
- 在医用直线加速器里，就是“电子打钨靶产生高能 X 射线（光子束）”的核心机制；
- 产生的是**连续能谱**光子，而不是单能光子。

关键结论：
- 光子能谱近似连续，可写为 \(E_\gamma \in (0, E_0]\)（其中 \(E_0\) 为入射电子束初始动能上限，6MV 束中约为 MeV 量级）
- 平均能量通常在 ~2 MeV 量级（受滤波/几何影响）
- 临床束里还会混入少量电子、正电子（由相互作用产生）

你项目里的 PHSP（IAEA/Varian TrueBeam）记录的是某个平面处通过的粒子：
- 粒子类型（photon / \(e^-\) / \(e^+\)）
- 位置 (x,y,z)
- 方向 (u,v,w) 或 (u,v) + 推导 w
- 能量 E
- 有时还有权重 weight（你用的可能是 constant weight）

你要理解一个重要事实：

    PHSP 不是“源头”
    PHSP 是“束流在某个平面截面的统计描述”

所以：
- 你下游几何必须覆盖 PHSP 的空间范围（尤其是 x,y）
- PHSP 的方向分布决定了你水体能吃到多少粒子

---

## 1.2 为什么你之前会看到“离谱能量/方向”？（概念解释）

你之前遇到过：
- 粒子数不是整数
- 能量超出 6 MeV
- 方向分量巨大异常

这类现象在物理上通常不可能（尤其是 6MV 的上限约束），因此往往是：
- 二进制读取 dtype / byte-order / header offset 解析错
- 单位换算错（eV vs MeV vs keV；cm vs mm）
- 记录字段顺序错（把 float 当成 int 等）

学习要点：
- 物理常识是你 debug 二进制解析的“第一道防线”
- 6MV 束：光子能量不能大面积超过 6 MeV
- 粒子数统计必须是整数计数（除非是权重加权统计）

---

# 2. 光子在水中发生什么：决定 Cherenkov 的“上游物理”

你的 Cherenkov 来自水里产生的带电粒子（主要是电子），而电子来自光子相互作用。

水中 6 MeV 光子最重要的相互作用：

2.1 光电效应（Photoelectric）
- 在低能（几十 keV）更重要
- 对 6MeV 临床束贡献很小

2.2 康普顿散射（Compton scattering）
- 在 MeV 量级主导
- 是“产生次级高能电子”的主要机制
- 因此是 Cherenkov 的最主要来源

补充说明（康普顿散射是什么）：
- 定义：高能光子与近似自由电子散射后，光子改变方向且能量降低，电子获得反冲动能。
- 物理图像：不是“光子消失”，而是“光子 + 电子”两体散射并重新分配能量与动量。
- 在 6MV 放疗束水中：它通常是最主要的相互作用通道，因此决定了大量次级电子的产生。

常用能量关系（光子散射后能量）：
$$
E'=\frac{E}{1+\left(\frac{E}{m_ec^2}\right)\left(1-\cos\theta\right)}
$$

其中：
- \(E\)：散射前光子能量
- \(E'\)：散射后光子能量
- \(\theta\)：光子散射角
- \(m_ec^2=0.511\ \mathrm{MeV}\)

电子获得动能：
$$
T_e = E - E'
$$

与本项目的关系：
- \(T_e\) 决定电子是否超过 Cherenkov 阈值（约 \(0.2\ \mathrm{MeV}\) 量级）；
- 超阈值电子在水中运动会产生 Cherenkov 光；
- 同时电子在介质中沉积能量，形成 dose。

你应能解释：
- 为什么 Cherenkov 在束轴附近最强（电子产生密度最大）。
- 为什么随着深度增加，谱会“软化”，Cherenkov 与 dose 的比例会变化。

简要物理解释：
- 束轴附近入射粒子通量最高，康普顿散射更频繁，产生的次级电子密度更大；超过 Cherenkov 阈值的电子更多，因此 Cherenkov 产额在束轴附近通常更强。
- 随深度增加，光子与电子能谱整体软化（平均能量下降），越来越多电子接近或低于 Cherenkov 阈值；而 dose 仍可由低能电子持续沉积，因此 Cherenkov/dose 比值往往随深度变化而非常数。

2.3 成对产生（Pair production）
- 阈值：1.022 MeV
- 在 6MeV 下存在但不是绝对主导
- 会产生 \(e^-\) 与 \(e^+\)（也会产生 Cherenkov，前提是能量够）
- 中文术语：规范叫“成对产生”（也常写“电子-正电子对产生”或“电子对效应”）。

补充说明（成对产生是什么）：
- 定义：高能光子在原子核（或电子）附近转化为 \(e^-\) 与 \(e^+\) 一对带电粒子。
- 物理图像：光子“消失”，转化为物质粒子对；原子核（或电子）提供动量守恒所需的反冲。
- 在 6MV 放疗束水中：该过程存在并贡献次级电子/正电子，但通常不如康普顿散射主导。

典型反应式（核场成对产生）：
$$
\gamma + Z \rightarrow e^- + e^+ + Z
$$

阈值条件：
$$
E_\gamma \ge 2m_ec^2 = 1.022\ \mathrm{MeV}
$$

（忽略核反冲时）可用于直觉估算的动能关系：
$$
T_{e^-}+T_{e^+}\approx E_\gamma - 2m_ec^2
$$

与本项目的关系：
- 产生的 \(e^\pm\) 若能量高于 Cherenkov 阈值，会产生 Cherenkov 光；
- 同时 \(e^\pm\) 在介质中沉积能量，贡献 dose；
- 正电子末端还会湮灭并产生 \(511\ \mathrm{keV}\) 光子，影响后续输运与沉积分布。

结论（对你的项目最重要）：

$$
\text{Cherenkov 产额} \approx \text{由 Compton 电子的能谱与路径长度决定}
$$

---

# 3. Cherenkov 的核心：阈值、角度、光谱、产额

这一章是你未来所有解释（图、kernel、相关性）的根。

---

## 3.1 为什么光子本身不产生 Cherenkov

符号说明（本节会用到）：
- \(v\)：粒子速度
- \(c\)：真空光速
- \(n\)：介质折射率
- \(\beta\)：无量纲速度，定义为 \(\beta=v/c\)

先把条件写完整（这是逻辑起点）：
- 必须是**带电粒子**；
- 且满足速度阈值 \(v > c/n\)，等价于 \(\beta n > 1\)。

这里的“\(>1\)”要这样理解：
- \(\beta n > 1 \iff v > c/n\)，表示粒子速度超过的是**介质中的光速**（相速度）\(c/n\)；
- 不是超过真空光速 \(c\)。由于 \(n>1\)，通常有 \(c/n < c\)，所以带电粒子完全可能满足 \(v>c/n\) 且仍然 \(v<c\)；
- 因此 Cherenkov 条件与“真空光速不可超越”并不矛盾。

$$
\beta n > 1
$$

对光子而言，在介质中的相速度是：

$$
v=\frac{c}{n}
$$

因此它的无量纲速度参数为：

$$
\beta = \frac{v}{c}=\frac{1}{n}
$$

代入阈值判据得到：

$$
\beta n = 1
$$

也就是说，光子永远只能“等于 1”，达不到 Cherenkov 需要的“严格大于 1”。

结论：

$$
\text{光子不产生 Cherenkov}
$$

$$
\text{Cherenkov 来自带电粒子（主要是电子/正电子）}
$$

---

## 3.2 Cherenkov 阈值推导（你必须会算一遍）

符号说明（本节新增）：
- 下标 \(\mathrm{th}\)：threshold（阈值）
- \(\gamma\)：洛伦兹因子
- \(m_e\)：电子静质量
- \(m_ec^2\)：电子静止能（\(0.511\ \mathrm{MeV}\)）
- \(T_{\mathrm{th}}\)：电子 Cherenkov 阈值动能

条件：

$$
\beta > \frac{1}{n}
$$

电子的相对论关系：

$$
\gamma=\frac{1}{\sqrt{1-\beta^2}}
$$

阈值时：

$$
\beta_{\mathrm{th}}=\frac{1}{n}
$$

$$
\gamma_{\mathrm{th}}=\frac{1}{\sqrt{1-\frac{1}{n^2}}}
$$

电子动能（阈值）：

$$
T_{\mathrm{th}}=(\gamma_{\mathrm{th}}-1)m_e c^2
$$

取（示例参数）：
$$
n=1.33,\qquad m_ec^2=0.511\ \mathrm{MeV}
$$

其中 \(n=1.33\) 指的是**水介质**在可见光波段常用的折射率近似值。

计算会得到：

$$
T_{\mathrm{th}} \approx 0.18\sim 0.26\ \mathrm{MeV}
$$

为什么是“范围”而不是单值：
- 折射率是频散量，严格应写成 \(n(\lambda)\)，不同波长对应不同 \(n\)；
- 将不同 \(n\) 代入 \(T_{\mathrm{th}}=(\gamma_{\mathrm{th}}-1)m_ec^2\) 会得到不同阈值；
- 因此实际常写成一个区间（如 \(0.18\sim0.26\ \mathrm{MeV}\)），用于工程近似。

学习点：
- 折射率 \(n\) 会随波长变化（频散），所以阈值不是严格单值
- 但 “~0.2 MeV” 是非常实用的工程判断

---

## 3.3 Cherenkov 角：为什么形成锥

Cherenkov 角公式：

$$
\cos\theta=\frac{1}{\beta n}
$$

角度定义要明确：
- 这里的 \(\theta\) 是在发射点处，**光子传播方向**与**带电粒子瞬时速度方向**之间的夹角；
- 等价地说，\(\theta\) 是 Cherenkov 光锥相对粒子轨迹轴线的半顶角（half-angle）。

当电子很快（β≈1）时：

$$
\cos\theta \approx \frac{1}{n}
$$

$$
\theta \approx \arccos\left(\frac{1}{1.33}\right)\approx 41^\circ
$$

解释要点：
- Cherenkov 光沿电子轨迹形成圆锥面
- 电子越快，角度越大（直到 β→1 极限）

对你的数据意义：
- 你记录方向（init/final dir）
- 方向分布会体现“锥形发射 + 后续散射/边界效应”

---

## 3.4 Frank–Tamm 公式：光子数来自哪里

光子数谱密度：

$$
\frac{d^2N}{dx\,d\lambda}=\frac{2\pi\alpha}{\lambda^2}\left(1-\frac{1}{\beta^2 n^2}\right)
$$

逐项理解：
- \(\alpha\)：精细结构常数，决定电磁相互作用强度
- \(\frac{1}{\lambda^2}\)：短波长更强（蓝/紫外更多）
- \(\left(1-\frac{1}{\beta^2 n^2}\right)\)：越快越强；接近阈值时趋近 0

重要结论（非常关键）：

$$
\text{Cherenkov 光子数} \propto \text{电子路径长度（在超过阈值的那段路径上）}
$$

所以你 kernel 的本质是：

$$
\text{统计所有电子在各体素产生 Cherenkov 的空间分布}
$$

---

## 3.5 为什么 Cherenkov 视觉上是蓝色

因为：

$$
I(\lambda)\propto\frac{1}{\lambda^2}
$$

其中 \(I(\lambda)\) 表示单位波长区间内的发光强度（可理解为光谱强度/光子产额密度随波长的分布）。

短波长（蓝/紫）更强。

现实中还要叠加：
- 水对紫外吸收
- 探测器（相机/PMT）响应曲线
- 介质散射

所以最终看到“蓝光为主”。

---

# 4. Dose：能量沉积与 Gy 的含义（和你的 dose kernel 对齐）

你项目里 dose 输出本质是能量沉积（edep）的空间分布。

---

## 4.1 Dose 定义

$$
D=\frac{E}{m}
$$

其中：
- \(D\)：剂量（单位 Gy，且 \(1\ \mathrm{Gy}=1\ \mathrm{J\,kg^{-1}}\)）
- \(E\)：沉积能量
- \(m\)：受照质量

你在 kernel 脚本里的换算：

$$
1\ \mathrm{MeV}=1.602176634\times 10^{-13}\ \mathrm{J}
$$

体素质量（先算克，再转千克）：

$$
m_{\mathrm g}=\rho_{\mathrm{g\,cm^{-3}}}\,V_{\mathrm{cm^3}}
$$

$$
m_{\mathrm{kg}}=\frac{m_{\mathrm g}}{1000}
$$

所以：

$$D_{\mathrm{Gy}}=\frac{E_{\mathrm{MeV}}\times 1.602176634\times 10^{-13}}{m_{\mathrm{kg}}}$$

$$D_{\mathrm{Gy}}=\frac{E_{\mathrm{MeV}}\times 1.602176634\times 10^{-10}}{\rho_{\mathrm{g\,cm^{-3}}}\,V_{\mathrm{cm^3}}}$$

这与你 README 里的公式一致。

---

## 4.2 Dose 和 Cherenkov 的物理差别（你后面做相关性的核心）

Dose 主要取决于：
- 电子在介质中损失的能量（\(dE/dx\) 积分）

Cherenkov 主要取决于：
- 电子超过阈值那段的路径长度（而不是它把多少能量沉积掉）

两者在某些条件下会近似成比例：
- 如果 \(dE/dx\) 变化不大（某能量区间近似常数）
- 如果电子能量远高于阈值（Cherenkov “一直开着”）

但在低能区：
- Dose 仍然存在（能量沉积甚至更集中）
- Cherenkov 会突然消失（低于阈值）

因此你要预期：

$$
\text{Cherenkov--Dose 相关性不会在所有深度/所有区域都线性}
$$

---

# 5. Monte Carlo 统计：kernel、误差、你脚本里 Poisson 的意义

---

## 5.1 Cherenkov kernel 的数学定义

$$
K(x,y,z)=\frac{N_\gamma(\mathrm{voxel})}{N_{\mathrm{primaries}}}
$$

解释：
- \(N_\gamma(\mathrm{voxel})\)：体素内 Cherenkov 光子计数（通常用“产生点”落在哪个体素）
- \(N_{\mathrm{primaries}}\)：原粒子数（你的项目里 event≈primary，因此就是 events）

物理意义：
- 它是一个响应函数（Green’s function）
- 给定一个“单位强度的入射 primary”，在水里会产生怎样的 Cherenkov 空间分布

---

## 5.2 Poisson 不确定度：为什么对计数成立

如果你统计的是“光子计数”：
- 每个光子事件可近似独立
- 对固定体素内计数 \(N\)

为什么可近似看成 Poisson 过程：
- 在固定体素内可视为“单位试次命中概率很小、试次很多”的稀有计数问题；
- 每个命中事件近似独立，且在给定条件下平均发生率近似稳定；
- 这正是 Poisson 计数模型的常见适用条件。

则：

$$
\sigma_N=\sqrt{N}
$$

解释：\(\sqrt{N}\) 是计数涨落的 \(1\sigma\) 统计不确定度，不是“真实计数变成 \(\sqrt{N}\)”。
也就是说，计数本身仍是 \(N\)，常写作 \(N\pm\sqrt{N}\)（仅统计误差）。

归一化到 kernel：

$$
K=\frac{N}{N_{\mathrm{primaries}}}
$$

$$
\sigma_K=\frac{\sqrt{N}}{N_{\mathrm{primaries}}}
$$

在结果表达上，常写作：
$$
K \pm \sigma_K
$$
这表示“点估计 + 统计不确定度（约 \(1\sigma\)）”。

注意：
- 若存在权重（weighted events），Poisson 要改成加权方差
- 你项目目前以每 event 1 primary、常权重为主，Poisson 是合理的第一近似

与当前源码的对应关系（是对应的）：
- Cherenkov kernel：`analysis/build_cherenkov_kernel.py` 中 `compute_kernel_and_uncertainty` 实现
  \(K=\mathrm{counts}/N_{\mathrm{primaries}}\)，\(\sigma=\sqrt{\mathrm{counts}}/N_{\mathrm{primaries}}\)；
  并分别写到 `kernel_02_normalized.npy`（\(K\)）和 `kernel_03_uncertainty.npy`（\(\sigma\)）。
- Dose kernel：`analysis/build_dose_kernel.py` 中默认 `fast` 模式给
  \(K=\mathrm{sum\_w}/N_{\mathrm{primaries}}\)，\(\sigma\approx\sqrt{\mathrm{sum\_w2}}/N_{\mathrm{primaries}}\)（近似）；
  也支持 `event` 模式做事件级不确定度。

---

# 6. Cherenkov kernel 与 dose kernel：你未来论文的“主战场”

你现在已经可以做非常有价值的物理分析了：

---

## 6.1 直觉图景：为什么它们可能相关

Dose：
$$
\sim \text{电子能量损失（沉积）}
$$

Cherenkov：
$$
\sim \text{电子超阈值路径长度}
$$

若电子能量高且阈值远低于能量：
- 电子一路都在发 Cherenkov
- Cherenkov 产额与路径长度成正比
- 能量沉积也与路径长度相关（\(dE/dx\) 近似稳定）

所以在一定区域：

$$
\mathrm{Cherenkov}\propto \mathrm{Dose}
$$

---

## 6.2 为什么它们一定会偏离

你需要记住三个“破坏线性”的机制：

(1) 阈值截断：
    电子低于约 \(0.2\ \mathrm{MeV}\) 后 Cherenkov 直接没了
    但 Dose 仍然有（甚至更集中）

(2) 能谱软化（随深度）：
    深层光子平均能量下降
    产生的电子更软
    Cherenkov 相对减少

(3) 几何与边界效应：
    水体有限大小导致电子/光子逃逸
    Cherenkov 计数对边界更敏感（尤其你若统计“终止点”）

因此你应该期待：

$$
\mathrm{ratio}(z)=\frac{\mathrm{Cherenkov}(z)}{\mathrm{Dose}(z)}
$$

并且会随深度变化（通常不是常数）。

---

## 6.3 你可以做的关键分析（直接对应你已有数据）

你已经有：
- Cherenkov kernel：\(K_C(x,y,z)\)
- Dose kernel：\(K_D(x,y,z)\)（\(\mathrm{MeV/primary/voxel}\) 或 \(\mathrm{Gy/primary/voxel}\)）

你可以立刻做这些图（非常物理、非常像论文）：

A. 深度曲线对比：
$$
C(z)=\sum_{x,y}K_C(x,y,z),\quad
D(z)=\sum_{x,y}K_D(x,y,z)
$$

B. 比值曲线：
$$
R(z)=\frac{C(z)}{D(z)}
$$

C. 体素级相关性：
$$
\mathrm{corr}\!\left(K_C(i,j,k),\,K_D(i,j,k)\right)
$$
可按深度分层。

D. 中心轴 vs 离轴：
$$
\text{在 }r<r_0\text{ 和 }r>r_0\text{ 的区域分别算 }R(z)
$$

这些会直接告诉你：
- 哪些区域 Cherenkov 是 dose 的好 proxy
- 哪些区域 Cherenkov 会系统性低估/高估

---

# 7. 光学传播：你下一阶段是否需要（取决于研究目标）

你当前记录的是：
- 产生点（InitialX/Y/Z）
- 终止点（FinalX/Y/Z）
- 初/末方向
- 能量

这已经足够你做：
- 产额 kernel
- 空间统计
- Cherenkov 与 dose 的局部关系

但如果你未来要做“成像”（Cherenkov imaging）：
- 你必须考虑光在水/空气中的传播、吸收、散射、边界反射

四个必学的光学过程：
1) Absorption（吸收）
2) Rayleigh scattering（分子散射）
3) Mie scattering（若有杂质/组织更重要）
4) Fresnel reflection + Total internal reflection（界面反射与全反射）

学习建议：
- 先把“产生”吃透（你现在正在做）
- 再决定是否推进到“传播到探测面”的成像物理

---

# 8. 建议学习路线（结合你项目的“最短闭环”）

你要的不是看书看半年，而是每学一个概念就能回到项目里验证。

Week 1：把 Cherenkov 产生机制吃透
- 康普顿电子为何是主因
- Cherenkov 阈值推导
- Cherenkov 角与方向锥

Week 2：把 Frank–Tamm 与产额估算吃透
- \(dN/dx\) 与电子路径长度
- 频谱 \(\frac{1}{\lambda^2}\)
- 为什么你数据里能量/波长分布会这样

Week 3：把 Dose 和单位换算吃透
- edep -> MeV/voxel
- MeV -> Gy（你脚本里就是）
- 为什么 dose 深度分布是 PDD 的影子

Week 4：把 Cherenkov–Dose 关系变成可写的“研究结论”
- 做 R(z) 曲线
- 分区域相关性
- 写出“线性区间 + 偏离原因”

---

# 9. 你当前水平定位（很重要，避免走偏）

你已经具备：
- Geant4 工程实现能力（几何、物理过程、输出系统）
- PHSP 驱动模拟能力
- 数据系统能力（二进制格式、run_meta、核构建）
- 统计分析能力（fast/complete analysis）

你接下来最值得投入的能力是：

$$
\text{用物理语言解释你每一张图、每一个 kernel 形状}
$$

一旦你做到：
- 你的项目就从“软件”升级为“可发表的物理研究”
- Cherenkov–Dose consistency / dose proxy / kernel-based surrogate 都能顺畅推进

---

# 10. 你现在可以立刻做的“学习检查题”（自测）

你应该能不看资料，直接回答：

Q1：为什么光子不产生 Cherenkov？
Q2：6MV 束里最主要产生 Cherenkov 的上游物理过程是什么？
Q3：水中电子 Cherenkov 阈值怎么推出来？数量级是多少？
Q4：为什么 Cherenkov 偏蓝？为什么 \(\frac{1}{\lambda^2}\)？
Q5：为什么 Cherenkov kernel 与 dose kernel 可能相关，但不可能全程线性？
Q6：如果你把水体横向做小了，会对 Cherenkov kernel 造成什么系统性偏差？
Q7：你记录“产生点” vs “终止点”，对 kernel 物理意义有什么影响？

---

结束
